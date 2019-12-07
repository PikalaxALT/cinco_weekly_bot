#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from discord.ext import commands
import discord
import config


class Bot(commands.Bot):
    def __init__(self, **kwargs):
        postgre_user = kwargs.pop('pguser', None)
        postgre_pass = kwargs.pop('pgpass', None)
        super().__init__(command_prefix='.', **kwargs)
        self.postgre_user = postgre_user
        self.postgre_pass = postgre_pass
        for cog in config.cogs:
            try:
                self.load_extension(cog)
            except Exception as exc:
                print(f'Could not load extension {cog} due to {exc.__class__.__name__}: {exc}')

    async def on_ready(self):
        print(f'Logged on as {self.user} (ID: {self.user.id})')


bot = Bot(pguser=config.postgre_user, pgpass=config.postgre_pass)

# write general commands here

bot.run(config.token)
