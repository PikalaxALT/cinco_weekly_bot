import discord
from discord.ext import commands, tasks
import asyncpg
import typing
import time
import base64
import asyncio
import datetime


class NoGuildConfig:
    pass


class GuildConfigExists:
    pass


class RaceDoesNotExist:
    pass


class NotHost:
    pass


class RaceNotStarted:
    pass


class RaceAlreadyStarted:
    pass


class NotRacing:
    pass


class Race(commands.Cog):
    @staticmethod
    def gen_hash(timestamp):
        return base64.b32encode(hash(timestamp).to_bytes(8, 'little')).decode().rstrip('=')

    def __init__(self):
        super().__init__()
        self.db: typing.Optional[asyncpg.Connection] = None
        self.update_db.start()

    def cog_unload(self):
        self.update_db.cancel()
        exc = self.update_db._task.exception
        if exc is not None and not isinstance(exc, asyncio.CancelledError):
            raise exc

    @tasks.loop(minutes=10)
    async def update_db(self):
        await self.db.commit()

    @update_db.before_loop
    async def init_db(self):
        self.db = await asyncpg.connect()
        try:
            await self.db.execute("""
            CREATE TABLE config(
                guild integer PRIMARY KEY,
                category integer not null,
                archive integer not null
            )
            """)
        finally:
            pass
        try:
            await self.db.execute("""
            CREATE TABLE races(
                hash text PRIMARY KEY not null,
                host integer not null,
                started timestamp,
                channel integer not null,
                role integer not null,
                voicechan integer
            )
            """)
        finally:
            pass

    @update_db.after_loop
    async def close_db(self):
        await self.db.close()
        self.db = None

    async def _get_guild_config(self, ctx: commands.Context):
        category = await self.db.fetchrow("""
            SELECT category FROM config WHERE (guild = $1)
        """, ctx.guild.id)
        if category is None:
            raise NoGuildConfig
        return category

    async def _get_race_settings(self, ctx: commands.Context, code=None):
        if code is not None:
            record = await self.db.fetchrow("""
                SELECT (*) from races where hash = $1
            """, code)
        else:
            record = await self.db.fetchrow("""
                SELECT (*) from races where channel = $1
            """, ctx.channel.id)
        if record is None:
            raise RaceDoesNotExist
        return record

    async def _get_racer(self, ctx: commands.Context, code=None):
        if code is None:
            code = (await self._get_race_settings(ctx))['hash']
        record = await self.db.fetchrow("""
            SELECT (*) from $1 where id = $2
        """, code, ctx.author.id)
        if record is None:
            raise NotRacing
        return record

    async def guild_has_category(self, ctx):
        await self._get_guild_config(ctx)
        return True

    async def guild_has_no_category(self, ctx):
        try:
            await self._get_guild_config(ctx)
        except NoGuildConfig:
            return True
        raise GuildConfigExists

    async def is_host(self, ctx):
        record = await self._get_race_settings(ctx)
        flag = await self.db.fetchval("""
            SELECT ishost FROM $1 where id = $2
        """, record['hash'], ctx.author.id)
        if not flag:
            raise NotHost
        return True

    async def is_started(self, ctx):
        record = await self._get_race_settings(ctx)
        if record['started'] is None:
            raise RaceNotStarted
        return True

    async def is_not_started(self, ctx):
        record = await self._get_race_settings(ctx)
        if record['started'] is None:
            return True
        return RaceAlreadyStarted

    async def is_racing(self, ctx):
        record = await self._get_racer(ctx)
        if record['finished'] is not None:
            raise NotRacing
        return True

    @commands.command()
    @commands.bot_has_permissions(manage_channels=True, manage_roles=True, manage_members=True)
    @commands.has_permissions(administrator=True)
    @commands.check(guild_has_no_category)
    async def config(self, ctx):
        overwrites = discord.PermissionOverwrite(read_message_history=False, send_messages=False, read_messages=False, connect=False, speak=False)
        category = await ctx.guild.create_category_channel('Races', overwrites=overwrites)
        category2 = await ctx.guild.create_category_channel('Race Archive')
        await self.db.execute("""
            INSERT INTO config(guild, category, archive) VALUES ($1, $2, $3)
        """, ctx.guild.id, category.id, category2.id)

    @commands.command()
    @commands.bot_has_permissions(manage_channels=True, manage_roles=True, manage_members=True)
    @commands.check(guild_has_category)
    async def new_race(self, ctx: commands.Context, casual=False):
        category = ctx.guild.get_channel((await self._get_guild_config(ctx))['category'])
        now = time.time()
        code = Race.gen_hash(now)
        role = await ctx.guild.create_role(name=f'Racer {code}')
        overwrites = discord.PermissionOverwrite(read_message_history=True, send_messages=True, read_messages=True, connect=True, speak=True)
        channel = await category.create_text_channel(f'race-{code.lower()}', overwrites={role: overwrites})
        if casual:
            vc = await category.create_voice_channel(f'Race Comms {code}', overwrites={role: overwrites})
        else:
            vc = None
        await self.db.execute("""
            INSERT INTO races(code, host, channel, role, voicechan) VALUES ($1, $2, $3, $4, $5)
        """, code, ctx.author.id, channel.id, role.id, vc.id)
        await self.db.execute("""
            CREATE TABLE $1(
                id integer PRIMARY KEY,
                ishost boolean NOT NULL DEFAULT FALSE,
                finished timestamp
            )
        """, code)
        await self.db.execute("""
            INSERT INTO $1(id, ishost) VALUES ($2, TRUE)
        """, code, ctx.author.id)
        await ctx.author.add_roles(role)
        await ctx.send(f'New race channel {channel.mention} created. To join, type `{ctx.prefix}{self.join} {code}`')
        await channel.send(f'{ctx.author.mention}: You are the host of this race. When everyone has joined in, '
                           f'type `{ctx.prefix}{self.start}` to start the race.')

    @commands.command()
    @commands.bot_has_permissions(manage_members=True)
    @commands.check(guild_has_category)
    async def join(self, ctx: commands.Context, code):
        category = await self._get_guild_config(ctx)
        record = await self._get_race_settings(ctx, code)
        if record['started'] is not None:
            raise RaceAlreadyStarted
        await self.db.execute("""
            INSERT INTO $1(id) VALUES ($2)
        """, code, ctx.author.id)
        channel = category.get_channel(record['channel'])
        role = ctx.guild.get_role(record['role'])
        await ctx.author.add_roles(role)
        await channel.send(f'Player {ctx.author.mention} has joined the race!')

    @commands.command()
    @commands.check(guild_has_category)
    @commands.check(is_host)
    @commands.check(is_not_started)
    async def start(self, ctx: commands.Context):
        record = await self._get_race_settings(ctx)
        await self.db.execute("""
            UPDATE races SET started=$2 WHERE hash=$1
        """, record['hash'], time.time())
        await ctx.send('Countdown started!')
        for i in range(5, 0, -1):
            await ctx.send(f'{i}...')
            await asyncio.sleep(1)
        await ctx.send('GO!!!')
        await self.db.execute("""
            UPDATE races SET started=$2 WHERE hash=$1
        """, record['hash'], time.time())
        await ctx.send(f'The race has started.\n'
                       f'To declare yourself done and get your official time, type {ctx.prefix}{self.done}.\n'
                       f'To forfeit, type {ctx.prefix}{self.forfeit}.')

    async def handle_race_finished(self, ctx, code):
        for row in await self.db.fetch("""
            SELECT (*) FROM $1
        """, code):
            if row['finished'] is None:
                return False
        await ctx.send('The race has finished. The channel will now be archived.')
        archive = ctx.guild.get_channel((await self._get_guild_config(ctx))['archive'])
        record = await self._get_race_settings(ctx, code)
        channel = ctx.guild.get_channel(record['channel'])
        await channel.edit(category=archive, overwrites={})
        role = ctx.guild.get_role(record['role'])
        await role.delete()
        if record['voicechan'] is not None:
            voicechan = ctx.guild.get_channel(record['voicechan'])
            await voicechan.edit(category=archive)
        await self.db.execute("""
            DROP TABLE $1
        """, code)

    @commands.command()
    @commands.check(guild_has_category)
    @commands.check(is_racing)
    @commands.bot_has_permissions(manage_roles=True, manage_channels=True)
    async def done(self, ctx: commands.Context):
        now = time.time()
        race = await self._get_race_settings(ctx)
        start_time = race['started']
        duration = datetime.timedelta(seconds=now - start_time)
        await self.db.execute("""
            UPDATE $1 SET finished=$2 WHERE id=$3
        """, race['hash'], now, ctx.author.id)
        await ctx.send(f'{ctx.author.mention} has finished the race with an official time of {duration}')
        await self.handle_race_finished(ctx, race['hash'])

    @commands.command()
    @commands.check(guild_has_category)
    @commands.check(is_racing)
    @commands.bot_has_permissions(manage_roles=True, manage_channels=True)
    async def forfeit(self, ctx: commands.Context):
        race = await self._get_race_settings(ctx)
        start_time = race['started']
        await self.db.execute("""
            UPDATE $1 SET finished=$2 WHERE id=$3
        """, race['hash'], start_time + 18000, ctx.author.id)
        await ctx.send(f'{ctx.author.mention} has forfeited from the race.')
        await self.handle_race_finished(ctx, race['hash'])

    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, NoGuildConfig):
            await ctx.send(f'This server is not configured. Please run {ctx.prefix}{self.config}.')
        elif isinstance(error, GuildConfigExists):
            await ctx.send('This server already has a race category.')
        elif isinstance(error, RaceNotStarted):
            await ctx.send('You cannot use this command before the race has begun.')
        elif isinstance(error, RaceDoesNotExist):
            await ctx.send('The indicated race does not exist, or you are using this command outside a race channel.')
        elif isinstance(error, NotHost):
            await ctx.send('Only the race host may start the race.')
        elif isinstance(error, NotRacing):
            await ctx.send('You are not a participant in this race, or you have already finished or forfeited.')
        elif isinstance(error, RaceAlreadyStarted):
            await ctx.send('This race cannot be started more than once.')
        else:
            await ctx.send(f'Unhandled {error.__class__.__name__} in {ctx.command}: {error}')


def setup(bot):
    bot.add_cog(Race())
