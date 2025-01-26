import re
import sys
import os
import importlib
import asyncio
import traceback
import discord
from discord.ext import commands
from discord import app_commands
from termcolor import colored
import logging

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
        self.slash_commands = []
        self.slash_command_actions = {}

class DiscordBot(commands.Bot):
    def __init__(self, config):
        intents = config.intents
        intents.message_content = True
        super().__init__(
            command_prefix=config.prefix,
            activity=config.activity,
            intents=intents,
            owner_ids=set(config.owner_ids) if config.owner_ids else None,
            allowed_mentions=config.mentions
        )
        self.config = config

    async def setup_hook(self):
        for cmd_name, actions in self.config.slash_command_actions.items():
            @self.tree.command(name=cmd_name)
            async def _dynamic_slash_command(interaction: discord.Interaction):
                await interaction.response.defer()
                for action in actions:
                    match = re.match(r'discord\.send\(channel,\s*"([^"]+)"\)', action)
                    if match:
                        message = match.group(1)
                        await interaction.followup.send(message)
        
        await self.tree.sync()

    async def on_ready(self):
        print(colored(f"Bot logged in as {self.user.name} (ID: {self.user.id})", "green"))

class SpixInterpreter:
    PATTERNS = {
        'DISCORD_LOGIN': r'^discord\.login\((.*?)\)$',
        'CONFIGURATION': r'^configuration\s+bot:$',
        'PREFIX': r'^let\s+prefix\s+be\s+"(.*?)"$',
        'OWNERS': r'^let\s+owner\s+be\s+(.+)$',
        'INTENTS': r'^let\s+intents\s+be\s+(.+)$',
        'DEBUG': r'^let\s+debug\s+be\s+(\w+)$',
        'ACTIVITY': r'^let\s+activity\s+be\s+"(\w+)"\s+"(.*?)"$',
        'MAKE_SLASH_COMMAND': r'^\$make\s+slash-command\s+"(\w+)":$',
        'DISCORD_SEND': r'^discord\.send\(channel,\s*"([^"]+)"\)$',
    }

    def __init__(self):
        self.variables = {}
        self.integrated_packages = {}
        self.bot_config = SpixBotConfiguration()
        self.discord_token = None
        self.current_command = None
        self.current_command_type = None

    async def parse_configuration(self, line):
        # Prefix
        prefix_match = re.match(self.PATTERNS['PREFIX'], line)
        if prefix_match:
            self.bot_config.prefix = prefix_match.group(1)
            return True

        owners_match = re.match(self.PATTERNS['OWNERS'], line)
        if owners_match:
            owner = owners_match.group(1).strip('"')
            self.bot_config.owner_ids = [int(owner)]
            return True

        intents_match = re.match(self.PATTERNS['INTENTS'], line)
        if intents_match:
            intent_type = intents_match.group(1)
            self.bot_config.intents = discord.Intents.all() if intent_type.lower() == 'all' else discord.Intents.default()
            return True

        debug_match = re.match(self.PATTERNS['DEBUG'], line)
        if debug_match:
            self.bot_config.debug = debug_match.group(1).lower() == 'on'
            return True

        activity_match = re.match(self.PATTERNS['ACTIVITY'], line)
        if activity_match:
            activity_type, activity_name = activity_match.groups()
            activity_types = {
                'watching': discord.ActivityType.watching,
                'playing': discord.ActivityType.playing,
                'listening': discord.ActivityType.listening,
                'streaming': discord.ActivityType.streaming
            }
            self.bot_config.activity = discord.Activity(
                type=activity_types.get(activity_type.lower(), discord.ActivityType.watching),
                name=activity_name
            )
            return True

        return False

    async def parse_line(self, line, bot):
        line = line.strip()

        if line == 'configuration bot:':
            self.current_command_type = 'configuration'
            return

        if self.current_command_type == 'configuration':
            config_parsed = await self.parse_configuration(line)
            if config_parsed or line == 'end':
                return

        login_match = re.match(self.PATTERNS['DISCORD_LOGIN'], line)
        if login_match:
            self.discord_token = login_match.group(1).strip('"')
            return

        slash_command_match = re.match(self.PATTERNS['MAKE_SLASH_COMMAND'], line)
        if slash_command_match:
            self.current_command = slash_command_match.group(1)
            self.current_command_type = 'slash_command'
            self.bot_config.slash_command_actions[self.current_command] = []
            return

        send_match = re.match(self.PATTERNS['DISCORD_SEND'], line)
        if send_match and self.current_command_type == 'slash_command':
            action = f'discord.send(channel, "{send_match.group(1)}")'
            self.bot_config.slash_command_actions[self.current_command].append(action)
            return

        if line == 'end':
            self.current_command = None
            self.current_command_type = None

    async def execute(self, code):
        lines = code.splitlines()

        bot = DiscordBot(self.bot_config)

        for line in lines:
            await self.parse_line(line, bot)

        if self.discord_token:
            try:
                async with bot:
                    await bot.start(self.discord_token)
            except Exception as e:
                print(colored(f'Failed to start bot: {str(e)}', 'red'))
                traceback.print_exc()

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