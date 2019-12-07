#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from discord.ext import commands
import discord
import config


class Bot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(command_prefix='.', **kwargs)
        for cog in config.cogs:
            try:
                self.load_extension(cog)
            except Exception as exc:
                print(f'Could not load extension {cog} due to {exc.__class__.__name__}: {exc}')

    async def on_ready(self):
        print('Logged on as {self.user} (ID: {self.user.id})')


bot = Bot()

# write general commands here

bot.run(config.token)
