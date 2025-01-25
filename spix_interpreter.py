import re
import sys
import os
import importlib
import asyncio
import datetime
import traceback
import inspect

import discord
from discord.ext import commands
from termcolor import colored

class SpixBotConfiguration:
    def __init__(self):
        self.prefix = "$"
        self.owner_ids = []
        self.intents = discord.Intents.default()
        self.debug = False
        self.mentions = discord.AllowedMentions(
            users=True, 
            everyone=False, 
            replied_user=False, 
            roles=False
        )
        self.activity = None
        self.help_command = None

    def set_prefix(self, prefix):
        self.prefix = prefix

    def set_owners(self, *owners):
        self.owner_ids = [int(owner) if owner.isdigit() else owner for owner in owners]

    def set_intents(self, intent_type):
        if intent_type.lower() == 'all':
            self.intents = discord.Intents.all()
        else:
            self.intents = discord.Intents.default()

    def set_debug(self, debug_status):
        self.debug = debug_status.lower() == 'on'

    def set_mentions(self, **kwargs):
        self.mentions = discord.AllowedMentions(
            users=kwargs.get('users', True),
            everyone=kwargs.get('everyone', False),
            replied_user=kwargs.get('replied_user', False),
            roles=kwargs.get('roles', False)
        )

    def set_activity(self, activity_type, name):
        activity_types = {
            'watching': discord.ActivityType.watching,
            'playing': discord.ActivityType.playing,
            'listening': discord.ActivityType.listening,
            'streaming': discord.ActivityType.streaming
        }
        self.activity = discord.Activity(
            type=activity_types.get(activity_type.lower(), discord.ActivityType.watching), 
            name=name
        )

class DiscordBot(commands.AutoShardedBot):
    def __init__(self, config):
        intents = config.intents
        intents.message_content = True
        super().__init__(
            command_prefix=config.prefix, 
            activity=config.activity, 
            intents=intents,  
            owner_ids=set(config.owner_ids) if config.owner_ids else None,  
            enable_debug_events=config.debug,
            allowed_mentions=config.mentions
        )
        self.config = config

    async def on_ready(self):
        print(colored(f"Bot logged in as {self.user.name} (ID: {self.user.id})", "green"))

    async def on_message(self, message):
        if message.author.bot:
            return

        await self.process_commands(message)

class SpixInterpreter:
    PATTERNS = {
        'DISCORD_LOGIN': r'^discord\.login\((.*?)\)$',
        'LET': r'^let\s+(\w+)\s+be\s+(.+)$',
        'SAY': r'^say\((.*?)\)$',
        'INTEGRATE': r'^integrate\s+(\w+)(?:\s+as\s+(\w+))?$',
        'CONFIGURATION': r'^configuration\s+bot:$',
        'PREFIX': r'^let\s+prefix\s+be\s+"(.*?)"$',
        'OWNERS': r'^let\s+owner\s+be\s+(.+)$',
        'INTENTS': r'^let\s+intents\s+be\s+(.+)$',
        'DEBUG': r'^let\s+debug\s+be\s+(\w+)$',
        'ACTIVITY': r'^let\s+activity\s+be\s+"(\w+)"\s+"(.*?)"$',
        'MAKE_COMMAND': r'^\$make command\s+"(.*?)"$',
        'SEND': r'^discord\.send\((\d+),\s+"(.*?)"\)$',
        'END': r'^end$'
    }

    def __init__(self):
        self.variables = {}
        self.integrated_packages = {}
        self.bot_config = SpixBotConfiguration()
        self.discord_token = None
        self.parsing_bot_config = False
        self.current_command = None
        self.command_actions = {}

    def integrate_package(self, package_name, alias=None):
        try:
            module = importlib.import_module(package_name)
            alias = alias or package_name
            self.integrated_packages[alias] = module
            print(colored(f'Successfully integrated package: {package_name} as {alias}', 'green'))
            return module
        except ImportError:
            print(colored(f'Failed to integrate package: {package_name}', 'red'))
            return None

    def evaluate_value(self, value):
        value = value.strip()

        # Handle numbers
        if value.isdigit():
            return int(value)

        # Handle string literals
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]

        # Handle variables
        if value in self.variables:
            return self.variables[value]

        # Handle integrated package methods
        if '.' in value:
            parts = value.split('.')
            if parts[0] in self.integrated_packages:
                try:
                    module = self.integrated_packages[parts[0]]
                    return getattr(module, parts[1])
                except AttributeError:
                    pass

        return value

    async def parse_line(self, line, bot):
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('//'):
            return

        # Configuration start
        if re.match(self.PATTERNS['CONFIGURATION'], line):
            self.parsing_bot_config = True
            return

        # Bot configuration parsing
        if self.parsing_bot_config:
            # Prefix configuration
            prefix_match = re.match(self.PATTERNS['PREFIX'], line)
            if prefix_match:
                self.bot_config.set_prefix(prefix_match.group(1))
                return

            # Owners configuration
            owners_match = re.match(self.PATTERNS['OWNERS'], line)
            if owners_match:
                owners = [o.strip().strip('"') for o in owners_match.group(1).split(',')]
                self.bot_config.set_owners(*owners)
                return

            # Intents configuration
            intents_match = re.match(self.PATTERNS['INTENTS'], line)
            if intents_match:
                self.bot_config.set_intents(intents_match.group(1))
                return

            # Debug configuration
            debug_match = re.match(self.PATTERNS['DEBUG'], line)
            if debug_match:
                self.bot_config.set_debug(debug_match.group(1))
                return

            # Activity configuration
            activity_match = re.match(self.PATTERNS['ACTIVITY'], line)
            if activity_match:
                self.bot_config.set_activity(activity_match.group(1), activity_match.group(2))
                return

            # End of configuration
            if not line.startswith('let'):
                self.parsing_bot_config = False

        # Discord login
        login_match = re.match(self.PATTERNS['DISCORD_LOGIN'], line)
        if login_match:
            self.discord_token = self.evaluate_value(login_match.group(1))
            return

        # Variable assignment
        let_match = re.match(self.PATTERNS['LET'], line)
        if let_match:
            name, value = let_match.groups()
            self.variables[name] = self.evaluate_value(value)
            return

        # Say (print) statement
        say_match = re.match(self.PATTERNS['SAY'], line)
        if say_match:
            content = self.evaluate_value(say_match.group(1))
            print(content)
            return

        # Package integration
        integrate_match = re.match(self.PATTERNS['INTEGRATE'], line)
        if integrate_match:
            package_name = integrate_match.group(1)
            alias = integrate_match.group(2)
            self.integrate_package(package_name, alias)
            return

        # Make Command
        make_command_match = re.match(self.PATTERNS['MAKE_COMMAND'], line)
        if make_command_match:
            self.current_command = make_command_match.group(1)
            self.command_actions[self.current_command] = []
            return

        # Command action: Send message
        send_match = re.match(self.PATTERNS['SEND'], line)
        if send_match and self.current_command:
            channel_id = int(send_match.group(1))
            message = send_match.group(2)

            async def send_action(ctx):
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(message)
                else:
                    print(colored(f'Channel ID {channel_id} not found', 'red'))

            self.command_actions[self.current_command].append(send_action)
            return

        # End Command
        end_match = re.match(self.PATTERNS['END'], line)
        if end_match and self.current_command:
            command_name = self.current_command

            @bot.command(name=command_name)
            async def combined_action(ctx):
                for action in self.command_actions[command_name]:
                    await action(ctx)

            self.current_command = None
            return

    async def execute(self, code):
        # Parse the entire code
        lines = code.splitlines()

        # Create the bot
        bot = DiscordBot(self.bot_config)

        # Process each line
        for line in lines:
            await self.parse_line(line, bot)

        # Login and run the bot
        if self.discord_token:
            try:
                await bot.start(self.discord_token)
            except Exception as e:
                print(colored(f'Failed to start bot: {str(e)}', 'red'))

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
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
