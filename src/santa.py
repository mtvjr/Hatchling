from discord.ext import commands
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, BigInteger

import src.util

Base = declarative_base()


class SantaRegistrant(Base):
    __tablename__ = "secret_santa_registrations"

    guild_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, primary_key=True)

    def __repr__(self):
        return "<SecretSantaRegister(guild_id='%s', user_id='%s'" % (
            self.guild_id, self.user_id)


class SecretSanta(commands.cog.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self._last_member = None
        self.db = db

    def get_registrants_ids(self, current_guild):
        return [item.user_id for item in
                self.db.query(SantaRegistrant.user_id)
                    .filter_by(guild_id=current_guild)
                    .all()]

    @commands.group()
    async def santa(self, ctx):
        '''
        A group of commands to help with running a secret santa
        '''
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid santa command. Valid commands are [ join list ]')

    @santa.command()
    async def join(self, ctx):
        ''' Join the secret santa '''
        username = ctx.message.author.display_name
        user_id = ctx.message.author.id
        guild_id = ctx.message.guild.id

        if user_id in self.get_registrants_ids(guild_id):
            await src.util.send("Silly goose, you are already registered")
            return

        registration = SantaRegistrant(guild_id=guild_id, user_id=user_id)
        self.db.add(registration)
        self.db.commit()
        message = f"{username} has joined the secret santa!"
        await src.util.send(message, ctx)

    @santa.command()
    async def list(self, ctx):
        ''' List the secret santas '''
        santas = list()

        current_guild = ctx.message.guild.id
        for registrant in self.get_registrants_ids(current_guild):
            user = ctx.message.guild.get_member(registrant)
            if user is not None:
                santas.append(user.display_name)
            else:
                print("Unable to find username for " + registrant)

        message = "The registered Santas are: " + ", ".join(santas)
        await src.util.send(message, ctx)
