import re
import sys
import discord
from discord.ext import commands
import asyncio
from termcolor import colored

class SpixInterpreter:
    PATTERNS = {
        'LET': r'^let\s+(\w+)\s+be\s+(.+)$',
        'IF': r'^if\s+(\w+)\s+is\s+(.+)$',
        'SAY': r'^say\((.*?)(?:,\s*<(\w+)>)?\)$',
        'STRING': r'^\"(.*)\"$',
        'DISCORD_LOGIN': r'^discord\.login\((.*?)\)$',
        'DISCORD_SEND': r'^discord\.send\((.*?),\s*(.*?)\)$',
        'MAKE_COMMAND': r'^\$make\s+command\s+\"(\w+)\"$',
        'DEFINE_FUNCTION': r'^function\s+for\s+(\w+):$',
        'MAKE_SLASHCOMMAND': r'^\$make\s+slashcommand\s+\"(\w+)\"$',
        'DEFINE_SLASH_FUNCTION': r'^function\s+for\s+slash\s+\"(\w+)\":$'
    }

    def __init__(self):
        self.variables = {}
        self.commands = {}
        self.slash_commands = {}
        self.current_context = None

        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.dm_messages = True
        intents.members = True
        intents.presences = True

        self.discord = commands.Bot(command_prefix='$', intents=intents)

        @self.discord.event
        async def on_ready():
            print(colored('Discord bot logged in successfully!', 'green'))

        @self.discord.event
        async def on_command_error(ctx, error):
            print(colored(f'Error: {str(error)}', 'red'))

    def evaluate_value(self, value):
        if not value:
            return value

        value = value.strip()

        # Handle numbers
        if value.isdigit():
            return int(value)

        # Handle variables
        if value in self.variables:
            return self.variables[value]

        # Handle string literals
        string_match = re.match(self.PATTERNS['STRING'], value)
        if string_match:
            return string_match.group(1)

        return value

    async def parse_line(self, line):
        line = line.strip()
        if not line or line.startswith('//'):
            return

        # Discord login
        if line.startswith('discord.login'):
            match = re.match(self.PATTERNS['DISCORD_LOGIN'], line)
            if match:
                token = self.evaluate_value(match.group(1))
                if not token:
                    print(colored('Error: No Discord token provided', 'red'))
                    sys.exit(1)
                try:
                    asyncio.create_task(self.discord.start(token))
                except Exception as e:
                    print(colored(f'Failed to login to Discord: {str(e)}', 'red'))
                    sys.exit(1)
            return

        # Discord send message
        if line.startswith('discord.send'):
            match = re.match(self.PATTERNS['DISCORD_SEND'], line)
            if match:
                channel_id = self.evaluate_value(match.group(1))
                content = self.evaluate_value(match.group(2))
                try:
                    if channel_id == 'channel':
                    channel_id = self.current_context.id
                    channel = await self.discord.fetch_channel(int(channel_id))
                    await channel.send(content)
                except Exception as e:
                    print(colored(f'Failed to send message: {str(e)}', 'red'))
            return

        # Create a text command
        if re.match(self.PATTERNS['MAKE_COMMAND'], line):
            match = re.match(self.PATTERNS['MAKE_COMMAND'], line)
            if match:
                command_name = match.group(1)
                self.commands[command_name] = []

                @self.discord.command(name=command_name)
                async def dynamic_command(ctx):
                    self.current_context = ctx.channel
                    for cmd_line in self.commands[command_name]:
                        await self.parse_line(cmd_line.replace('channel', str(ctx.channel.id)))
            return

        # Define a function for a text command
        if re.match(self.PATTERNS['DEFINE_FUNCTION'], line):
            match = re.match(self.PATTERNS['DEFINE_FUNCTION'], line)
            if match:
                command_name = match.group(1)
                if command_name in self.commands:
                    self.current_command = command_name
            return

        # Create a slash command
        if re.match(self.PATTERNS['MAKE_SLASHCOMMAND'], line):
            match = re.match(self.PATTERNS['MAKE_SLASHCOMMAND'], line)
            if match:
                slash_command_name = match.group(1)
                self.slash_commands[slash_command_name] = []

                @self.discord.tree.command(name=slash_command_name)
                async def dynamic_slash_command(interaction: discord.Interaction):
                    self.current_context = interaction.channel
                    for cmd_line in self.slash_commands[slash_command_name]:
                        await self.parse_line(cmd_line.replace('channel', str(interaction.channel.id)))
                    await interaction.response.send_message("Command executed.", ephemeral=True)
            return

        # Define a function for a slash command
        if re.match(self.PATTERNS['DEFINE_SLASH_FUNCTION'], line):
            match = re.match(self.PATTERNS['DEFINE_SLASH_FUNCTION'], line)
            if match:
                slash_command_name = match.group(1)
                if slash_command_name in self.slash_commands:
                    self.current_slash_command = slash_command_name
            return

        # Add lines to the current text or slash command
        if hasattr(self, 'current_command') and self.current_command in self.commands:
            self.commands[self.current_command].append(line)
            return

        if hasattr(self, 'current_slash_command') and self.current_slash_command in self.slash_commands:
            self.slash_commands[self.current_slash_command].append(line)
            return

        # Variable assignment
        if line.startswith('let'):
            match = re.match(self.PATTERNS['LET'], line)
            if match:
                name, value = match.groups()
                self.variables[name] = self.evaluate_value(value)
            return

        # Conditional statements
        if line.startswith('if'):
            match = re.match(self.PATTERNS['IF'], line)
            if match:
                var_name, value = match.groups()
                return self.variables.get(var_name) == self.evaluate_value(value)
            return False

        # Print statements
        if line.startswith('say'):
            match = re.match(self.PATTERNS['SAY'], line)
            if match:
                content, color = match.groups()
                content = self.evaluate_value(content)
                if color:
                    print(colored(content, color.strip()))
                else:
                    print(content)

    async def execute(self, code):
        lines = code.splitlines()
        is_conditional_block = False

        for line in lines:
            if line.strip().startswith('if'):
                is_conditional_block = await self.parse_line(line)
            elif is_conditional_block or not line.strip().startswith('if'):
                await self.parse_line(line)
                is_conditional_block = False

async def main():
    if len(sys.argv) < 2:
        print(colored('Please provide a .spx file to execute', 'red'))
        sys.exit(1)

    filename = sys.argv[1]
    try:
        with open(filename, 'r') as file:
            code = file.read()
            interpreter = SpixInterpreter()
            await interpreter.execute(code)
    except Exception as e:
        print(colored(f'Error: {str(e)}', 'red'))
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
