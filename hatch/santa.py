import os
from random import shuffle
from asyncio import wait

from discord.ext import commands
from sqlalchemy import BigInteger, Boolean, create_engine, CheckConstraint, Column, ForeignKey, \
    ForeignKeyConstraint, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import hatch.util as util

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
        return "<SantaExchange(name='%s', guild_id='%s', owner_id='%s', drawn='%s')>" % (
            self.name, self.guild_id, self.owner_id, self.targets_drawn)


class Registrant(Base):
    """
    This is an SQLAlchemy class representing the table containing the registration data.
    """
    __tablename__ = "santa_registrations"

    exchange = Column(String(EXCHANGE_NAME_SIZE), ForeignKey("santa_exchanges.name"),
                      primary_key=True)
    user_id = Column(BigInteger, primary_key=True)

    def __repr__(self):
        return "<SantaRegistrant(exchange='%s', user_id='%s'>" % (
            self.exchange_id, self.user_id)


class Pairing(Base):
    """
    This is an SQLAlchemy class representing the table containing Santa/Target pairings
    """
    __tablename__ = "santa_pairings"
    exchange = Column(String(EXCHANGE_NAME_SIZE), primary_key=True)
    santa_id = Column(BigInteger, primary_key=True)
    target_id = Column(BigInteger, nullable=False)
    no_self_match = CheckConstraint("santa_id != target_id")

    __table_args__ = (
        ForeignKeyConstraint(("exchange", "santa_id"),
                             ("santa_registrations.exchange", "santa_registrations.user_id")),
        ForeignKeyConstraint(("exchange", "target_id"),
                             ("santa_registrations.exchange", "santa_registrations.user_id")),
    )

    def __repr__(self):
        return "<SantaPairing(exchange='%s', santa_id='%s', target_id='%s'>" % (
            self.exchange, self.santa_id, self.target_id)


# Create the tables needed for Secret Santa
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)
Base.metadata.create_all(engine)


def make_circular_pairs(items):
    """
    Creates a generator from a list of items, so each item is paired with the item
    that follows. The last item is paired with the first.
    """
    length = len(items)
    for i in range(length):
        yield items[i], items[(i + 1) % length]


def match_santa_pairs(participants: list):
    """ This function returns a list of tuples of (Santa, Target) pairings """
    shuffle(participants)
    return list(make_circular_pairs(participants))


class SecretSanta(commands.cog.Cog):
    """
    This class defines a collection of Discord.py commands for running a secret santa.
    """
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
            await ctx.send("Invalid santa command. Valid commands are [ create join list ]")

    @santa.command()
    async def create(self, ctx, name=""):
        """ Create a secret santa """
        if not util.is_from_guild(ctx):
            await util.send(ctx, "This message only works in a server")
            return
        if name is "":
            await util.send(ctx, "You must name your secret santa event." +
                            "\nExample: `!santa create RT2019`")
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
            await util.send(ctx, f"The Secret Santa exchange {name} has been created and opened." +
                            f" Santas may join with the command `!santa join {name}`")
        except IntegrityError:
            session.rollback()
            await util.send(ctx, f"The exchange name {name} has already been taken. Please try another")
        except:
            session.rollback()
            await util.send(ctx, f"An error occurred trying to create exchange {name}")
        session.close()

    @santa.command()
    async def join(self, ctx, exchange_name=""):
        """ Join the secret santa """
        if not util.is_from_guild(ctx):
            await util.send(ctx, "This message only works in a server")
            return

        if exchange_name == "":
            await ctx.send("You must provide the name of an exchange.\n" +
                           " Example: `!santa join RT2019`")
            return

        username = ctx.message.author.display_name
        user_id = ctx.message.author.id
        guild_id = ctx.message.guild.id

        session = self.sessionmaker()

        # Verify the exchange is created and open for the current guild
        exchange = session.query(Exchange) \
            .filter_by(name=exchange_name, guild_id=guild_id) \
            .one_or_none()

        if exchange is None:
            session.rollback()
            session.close()
            await ctx.send(f"Secret Santa exchange {exchange_name} was not found")
            return

        if not exchange.open:
            session.close()
            await ctx.send(f"Secret Santa exchange {exchange_name} is closed. Please join the next exchange")
            return

        # Check if the participant has already registered
        if session.query(Registrant) \
                .filter_by(exchange=exchange_name, user_id=user_id) \
                .count() > 0:
            session.rollback()
            session.close()
            await util.send(ctx, "Silly goose, you are already registered")
            return

        registration = Registrant(exchange=exchange_name, user_id=user_id)
        session.add(registration)
        try:
            session.commit()
            message = f"{username} has joined the secret santa {exchange_name}!"
            await util.send(ctx, message)
        except:
            session.rollback()
            message = f"There was an unknown error registering {username} for {exchange_name}!"
            await util.send(ctx, message)
        session.close()

    @santa.command()
    async def list(self, ctx, exchange_name=""):
        """ List the Secret Santa exchanges or participants"""
        if not util.is_from_guild(ctx):
            await util.send(ctx, "This message only works in a server")
        if exchange_name == "":
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
                      "\n You may create them with the command `!santa create <exchange_name>`"
        else:
            message = "The available Secret Santa exchanges are:\n\t" + "\n\t".join(exchanges) \
                      + "\n You can view the participants of an exchange with the command " \
                      + "`!santa list <exchange_name>`"
        await util.send(ctx, message)

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
            await ctx.send(f"Exchange {exchange_name} was not found")
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
        await util.send(ctx, message)

    @santa.command()
    async def message(self, context, exchange="", *, santa_message=""):
        """
        **Private Message Only** This command allows you to anonymously message your target.
        To use this command, you **MUST** send it as a private message to the bot.
        Format: !santa message <exchange_name> Your message follows
        """
        if not util.is_from_dm(context):
            await context.send("This command only works when sent through a private message to the bot." +
                               "\nPlease reword your message and try again.")
            return

        if exchange == "":
            await context.send("A Secret Santa exchange name must be provided." +
                               "\n\tYou must use the format `!santa message <exchange_name> <message>`")
            return

        if santa_message == "":
            await context.send("No message was attached" +
                               f"\n\tYou must use the format: !santa message {exchange} <message>")
            return

        session = self.sessionmaker()

        user_id = context.message.author.id

        current_exchange = session.query(Exchange).filter_by(name=exchange).one_or_none()
        if current_exchange is None:
            session.close()
            await context.send(f"The exchange {exchange} does not exist.")
            return

        if current_exchange.open:
            session.close()
            await context.send(f"The exchange {exchange} is still open, targets have not been drawn yet.")
            return

        if session.query(Registrant).filter_by(exchange=exchange, user_id=user_id).one_or_none() is None:
            session.close()
            await context.send("You are not registered for this secret santa exchange")
            return

        pairing = session.query(Pairing).filter_by(exchange=exchange, santa_id=user_id).one_or_none()
        session.close()

        if pairing is None:
            await context.send("There was an error retrieving your target")

        target = self.bot.get_user(pairing.target_id)

        message = f"Your Secret Santa from {exchange} sends you a message.\n\n" + \
                  f"Reply using `!santa reply {exchange} Your message here`\n\n" + \
                  "> " + "\n> ".join(santa_message.splitlines())  # Put each line into a quote

        await target.send(message)

    @santa.command()
    async def reply(self, context, exchange="", *, target_message=""):
        """
        **Private Message Only** This command allows you to anonymously message your santa.
        To use this command, you **MUST** send it as a private message to the bot.
        Format: !santa reply <exchange_name> Your message follows
        """
        if not util.is_from_dm(context):
            await context.send("This command only works when sent through a private message to the bot." +
                               "\nPlease reword your message and try again.")
            return

        if exchange == "":
            await context.send("A Secret Santa exchange name must be provided." +
                               "\n\tYou can use the format: !santa reply <exchange_name> <message>")
            return

        if target_message == "":
            await context.send("No message was attached" +
                               f"\n\tYou can use the format: !santa reply {exchange} <message>")
            return

        session = self.sessionmaker()

        user_id = context.message.author.id

        current_exchange = session.query(Exchange).filter_by(name=exchange).one_or_none()
        if current_exchange is None:
            session.close()
            await context.send(f"The exchange {exchange} does not exist.")
            return

        if current_exchange.open:
            session.close()
            await context.send(f"The exchange {exchange} is still open, targets have not been drawn yet.")
            return

        if session.query(Registrant).filter_by(exchange=exchange, user_id=user_id).one_or_none() is None:
            session.close()
            await context.send("You are not registered for this secret santa exchange")
            return

        pairing = session.query(Pairing).filter_by(exchange=exchange, target_id=user_id).one_or_none()
        session.close()

        if pairing is None:
            await context.send("There was an error retrieving your target")

        target = self.bot.get_user(pairing.santa_id)
        santa = context.bot.get_guild(current_exchange.guild_id).get_member(user_id).display_name

        message = f"Your target ({santa}) from the Secret Santa exchange {exchange} sends you a message.\n\n" + \
                  f"Reply using `!santa message {exchange} Your message here`\n\n" + \
                  "> " + "\n> ".join(target_message.splitlines())  # Put each line into a quote

        await target.send(message)

    @santa.command()
    async def close(self, context, exchange_name=""):
        """
        Closes an open exchange and matches santas with targets.
        """
        if not util.is_from_guild(context):
            await context.send("This command must be run from a server.")
            return

        if exchange_name == "":
            await context.send("You must include an exchange name in this command"
                               "\n\tYou must format the command this way: `!santa close <exchange_name>`")
            return

        session = self.sessionmaker()
        exchange = session.query(Exchange).filter_by(name=exchange_name).one_or_none()

        if exchange is None:
            session.close()
            await context.send(f"The exchange {exchange_name} does not exist.")
            return

        if exchange.owner_id != context.message.author.id:
            session.close()
            print("Author: {}, Owner: {}".format(context.message.author.id, exchange.owner_id))
            owner_name = context.message.guild.get_member(exchange.owner_id).display_name
            await context.send(f"Only the owner of {exchange_name} ({owner_name}) may close it.")
            return

        if not exchange.open:
            session.close()
            await context.send(f"The exchange {exchange_name} is already closed.")
            return

        # Get participants
        participants = [part.user_id for part in
                        session.query(Registrant.user_id)
                            .filter_by(exchange=exchange_name)
                            .all()]

        # Remove participants who have left the guild
        removed_users = list()
        for participant in participants:
            if context.message.guild.get_member(participant) is None:
                participants.remove(participant)
                user = context.bot.get_user(participant)
                if user is None:
                    removed_users.append(f"Unknown participant {participant}")
                else:
                    removed_users.append(user.name + "#" + user.id)

        if len(removed_users) > 0:
            await context.send(f"Users who have left the server have been removed from the exchange: " +
                               ", ".join(removed_users))

        if len(participants) < 2:
            session.close()
            await context.send(f"There must be at least 2 Santas in {exchange_name} for it to close.")
            return

        matches = match_santa_pairs(participants)

        pairings = [Pairing(
                exchange=exchange_name,
                santa_id=match[0],
                target_id=match[1],
            ) for match in matches
        ]

        # Update the database
        exchange.open = False
        session.add_all(pairings)
        session.commit()

        # Alert Santas as to their targets
        awaits = list()
        for santa, target in matches:
            target_name = context.message.guild.get_member(target).display_name
            message = (f"Congratulations Santa! You've been assigned {target_name} for {exchange_name}"
                       f"\n\nPlease **reply to this message** using the following commands to message your target."
                       f"\n\t> To send a message to your target, use `!santa message {exchange_name} Your message`"
                       f"\n\t> To send a reply to your santa, use `!santa reply {exchange_name} Your message`"
                       "\n\nIt may be worth setting yourself to invisible while communicating with your target to "
                       "help keep your identity secret.")
            awaits.append(context.bot.get_user(santa).send(message))

        message = f"The Secret Santa exchange {exchange_name} has been closed and PMs have been sent to Santas.\n"

        awaits.append(context.send(message))

        await wait(awaits)
