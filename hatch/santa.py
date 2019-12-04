import os

from discord.ext import commands
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, ForeignKey, \
    ForeignKeyConstraint, String, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import hatch.util

EXCHANGE_NAME_SIZE = 30

Base = declarative_base()

class Exchange(Base):
    """
    This is an SQLAlchemy class representing the table containing the exchange data.
    """
    __tablename__ = "santa_exchanges"

    name = Column(String(EXCHANGE_NAME_SIZE), primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    owner_id = Column(BigInteger, nullable=False)
    open = Column(Boolean, nullable=False)

    def __repr__(self):
        return "<SantaExchange(name='%s', guild_id='%s', owner_id='%s', drawn='%s')" % (
            self.name, self.guild_id, self.owner_id, self.targets_drawn)


class Registrant(Base):
    """
    This is an SQLAlchemy class representing the table containing the registration data.
    """
    __tablename__ = "santa_registrations"

    exchange = Column(String(EXCHANGE_NAME_SIZE), ForeignKey('santa_exchanges.name'),
                      primary_key=True)
    user_id = Column(BigInteger, primary_key=True)

    def __repr__(self):
        return "<SantaRegistrant(exchange='%s', user_id='%s'" % (
            self.exchange_id, self.user_id)


class Pairing(Base):
    """
    This is an SQLAlchemy class representing the table containing Santa/Target pairings
    """
    __tablename__ = "santa_pairings"
    exchange = Column(String(EXCHANGE_NAME_SIZE), primary_key=True)
    santa_id = Column(BigInteger, primary_key=True)
    target_id = Column(BigInteger, nullable=False)
    no_self_match = CheckConstraint('santa_id != target_id')

    __table_args__ = (
        ForeignKeyConstraint(('exchange', 'santa_id'),
                             ('santa_registrations.exchange', 'santa_registrations.user_id')),
        ForeignKeyConstraint(('exchange', 'target_id'),
                             ('santa_registrations.exchange', 'santa_registrations.user_id')),
    )

    def __repr__(self):
        return "<SantaPairing(exchange_id='%s', santa_id='%s', target_id='%s'" % (
            self.exchange_id, self.santa_id, self.target_id)


# Create the tables needed for Secret Santa
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)
Base.metadata.create_all(engine)


class SecretSanta(commands.cog.Cog):
    def __init__(self, bot, db_engine):
        self.bot = bot
        self.sessionmaker = sessionmaker(bind=db_engine)

    def get_registrants_ids(self, exchange):
        session = self.sessionmaker()
        registrants = (session.query(Registrant)
                       .filter_by(exchange=exchange)
                       .all())
        session.close()
        return [entry.user_id for entry in registrants]

    @commands.group()
    async def santa(self, ctx):
        """
        A group of commands to help with running a secret santa
        """
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid santa command. Valid commands are [ create join list ]')

    @santa.command()
    async def create(self, ctx, name=''):
        """ Create a secret santa """
        if ctx.message.guild is None:
            await ctx.send('You must send this command in a server.')
        if name is '':
            await hatch.util.send(ctx, 'You must name your secret santa event.' +
                                  '\nExample: "!santa create RT2019"')
            return

        exchange = Exchange(
            name=name,
            guild_id=ctx.message.guild.id,
            owner_id=ctx.message.author.id,
            open=True,
        )

        session = self.sessionmaker()
        session.add(exchange)
        try:
            session.commit()
            await hatch.util.send(ctx, f'The Secret Santa exchange {name} has been created and opened.' +
                                  f' Santas may join with the command "!santa join {name}"')
        except IntegrityError:
            session.rollback()
            await hatch.util.send(ctx, f"The exchange name {name} has already been taken. Please try another")
        except:
            session.rollback()
            await hatch.util.send(ctx, f"An error occurred trying to create exchange {name}")
        session.close()

    @santa.command()
    async def join(self, ctx, exchange_name=''):
        """ Join the secret santa """
        if ctx.message.guild is None:
            await ctx.send('You must send this command in a server.')
            return

        if exchange_name == '':
            await ctx.send('You must provide the name of an exchange.\n' +
                           ' Example: "!santa join RT2019"')
            return

        username = ctx.message.author.display_name
        user_id = ctx.message.author.id
        guild_id = ctx.message.guild.id

        session = self.sessionmaker()

        # Verify the exchange is created and open for the current guild
        exchange = session.query(Exchange) \
            .filter_by(name=exchange_name, guild_id=guild_id, open=True) \
            .one_or_none()

        if exchange is None:
            session.rollback()
            session.close()
            await ctx.send(f'Secret Santa exchange {exchange_name} was not found')
            return

        if not exchange.open:
            session.close()
            await ctx.send(f'Secret Santa exchange {exchange_name} is closed. Please join the next exchange')
            return

        if session.query(Registrant) \
                .filter_by(exchange=exchange_name, user_id=user_id) \
                .count() > 0:
            session.rollback()
            session.close()
            await hatch.util.send(ctx, "Silly goose, you are already registered")
            return

        registration = Registrant(exchange=exchange_name, user_id=user_id)
        session.add(registration)
        try:
            session.commit()
            message = f"{username} has joined the secret santa {exchange_name}!"
            await hatch.util.send(ctx, message)
        except:
            session.rollback()
            message = f"There was an unknown error registering {username} for {exchange_name}!"
            await hatch.util.send(ctx, message)
        session.close()

    @santa.command()
    async def list(self, ctx, exchange_name=''):
        """ List the Secret Santa exchanges or participants"""
        if ctx.message.guild is None:
            await ctx.send('You must send this command in a server.')
            return
        if exchange_name == '':
            # List the possible exchanges
            await self.list_exchanges(ctx)
        else:
            # List the participants in the exchange
            await self.list_participants(ctx, exchange_name)

    async def list_exchanges(self, ctx):
        """ List the exchanges available in the context """
        # Verify the exchange is created for the current guild
        guild_id = ctx.message.guild.id
        session = self.sessionmaker()
        exchanges = [exchange.name for exchange in
                     session.query(Exchange)
                     .filter_by(guild_id=guild_id, open=True)
                     .all()]
        session.close()

        if len(exchanges) == 0:
            message = "No Secret Santa exchanges are open for this server." + \
                      '\n You may create them with the command "!santa create <exchange_name>"'
        else:
            message = "The available Secret Santa exchanges are:\n\t" + "\n\t".join(exchanges) \
                      + "\n You can view the participants of an exchange with the command " \
                      + '"!santa list <exchange_name>"'
        await hatch.util.send(ctx, message)

    async def list_participants(self, ctx, exchange_name):
        """ List the participants in the exchange """
        guild_id = ctx.message.guild.id
        session = self.sessionmaker()

        # Verify the exchange is created for the current guild
        if session.query(Exchange) \
                .filter_by(name=exchange_name, guild_id=guild_id) \
                .one_or_none() is None:
            session.rollback()
            session.close()
            await ctx.send(f'Exchange {exchange_name} was not found')
            return

        santas = session.query(Registrant.user_id) \
            .filter_by(exchange=exchange_name) \
            .all()

        session.close()

        # Grab discord display names
        santas = [ctx.message.guild.get_member(santa.user_id) for santa in santas]
        santa_names = list()
        for santa in santas:
            if santa is not None:
                santa_names.append(santa.display_name)

        if len(santa_names) == 0:
            message = "There are no registered Santas for " + exchange_name
        else:
            message = f"The registered Santas for {exchange_name} are: " + ", ".join(santa_names)
        await hatch.util.send(ctx, message)
