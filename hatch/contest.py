import os
from random import shuffle
from asyncio import wait

from discord.ext import commands
from sqlalchemy import BigInteger, Boolean, create_engine, CheckConstraint, Column, Integer, \
    ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import hatch.util as util

EXCHANGE_NAME_SIZE = 30

def print_rank(winner, context):
    return f"{winner.win_rank}. {util.get_displayname(winner.user_id, context)}"

Base = declarative_base()

class Contest(Base):
    """
    This is an SQLAlchemy class representing the table containing the contest data.
    """
    __tablename__ = "contest_contest"

    cid = Column(Integer, primary_key=True)
    name = Column(String(EXCHANGE_NAME_SIZE), nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    owner_id = Column(BigInteger, nullable=False)
    open = Column(Boolean, nullable=False)
    num_winners = Column(Integer, nullable=True)

    unique_name = UniqueConstraint('guild_id', 'name')

    def __repr__(self):
        return f"<ContestContest(name='{self.name}', guild_id='{self.guild_id}', owner_id='{self.owner_id}', drawn='{not self.open}')>"


class Entry(Base):
    """
    This is an SQLAlchemy class representing the table containing the registration data.
    """
    __tablename__ = "contest_entries"

    contest = Column(Integer, ForeignKey("contest_contest.cid"), primary_key=True)
    user_id = Column(BigInteger, primary_key=True)
    win_rank = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<ContestEntry(contest='{self.contest.name}', user_id='{self.user_id}', win_rank='{self.win_rank}''>"


# Create the tables needed for the contest
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)
Base.metadata.create_all(engine)


class Contests(commands.cog.Cog):
    """
    This class defines a collection of Discord.py commands for running a contest
    """
    def __init__(self, bot, db_engine):
        self.bot = bot
        self.sessionmaker = sessionmaker(bind=db_engine)

    @commands.group()
    async def contest(self, context):
        """
        A group of commands to help with running a contest
        """
        if context.invoked_subcommand is None:
            await context.send("Invalid command. Valid commands are [ close draw enter list open ]")

    @contest.command()
    async def open(self, context, name=""):
        """ Create a contest """
        if not util.is_from_guild(context):
            await util.send(context, "This message only works in a server")
            return
        if name == "":
            await util.send(context, "You must name your contest event." +
                            "\nExample: `!contest create RT2019`")
            return

        contest = Contest(
            name=name,
            guild_id=context.message.guild.id,
            owner_id=context.message.author.id,
            open=True,
        )

        session = self.sessionmaker()
        session.add(contest)
        try:
            session.commit()
            await util.send(context, f"The contest {name} has been created and opened." +
                            f" You may join with the command `!contest enter {name}`")
        except IntegrityError:
            session.rollback()
            await util.send(context, f"The contest name {name} has already been used. Please try another")
        except:
            session.rollback()
            await util.send(context, f"An error occurred trying to create contest {name}")
        session.close()

    @contest.command()
    async def enter(self, context, contest_name=""):
        """ Join the contest contest """
        if not util.is_from_guild(context):
            await util.send(context, "This message only works in a server")
            return

        if contest_name == "":
            await context.send("You must provide the name of an contest.\n" +
                           " Example: `!contest enter RT2019`")
            return

        username = context.message.author.display_name
        user_id = context.message.author.id
        guild_id = context.message.guild.id

        session = self.sessionmaker()

        # Verify the contest is created and open for the current guild
        contest = session.query(Contest) \
            .filter_by(name=contest_name, guild_id=guild_id) \
            .one_or_none()

        if contest is None:
            session.rollback()
            session.close()
            await context.send(f"Contest {contest_name} was not found")
            return

        if not contest.open:
            session.rollback()
            session.close()
            await context.send(f"Contest {contest_name} is closed. Please join the next contest")
            return

        # Check if the participant has already registered
        if session.query(Entry) \
                .filter_by(contest=contest.cid, user_id=user_id) \
                .count() > 0:
            session.rollback()
            session.close()
            await util.send(context, "No cheating! You already entered")
            return

        registration = Entry(contest=contest.cid, user_id=user_id)
        session.add(registration)
        try:
            session.commit()
            message = f"{username} has joined the contest {contest_name}!"
        except:
            session.rollback()
            message = f"There was an unknown error registering {username} for {contest_name}!"
        await util.send(context, message)
        session.close()

    @contest.command()
    async def list(self, context, contest_name=""):
        """ List the contests or entries"""
        if not util.is_from_guild(context):
            await util.send(context, "This message only works in a server")
        if contest_name == "":
            # List the possible contests
            await self.list_contests(context)
        else:
            # List the entries in the contest
            await self.list_entries(context, contest_name)

    async def list_contests(self, context):
        """ List the contests available in the context """
        # Verify the contest is created for the current guild
        guild_id = context.message.guild.id
        session = self.sessionmaker()
        contests = [contest.name for contest in
                     session.query(Contest)
                         .filter_by(guild_id=guild_id, open=True)
                         .all()]
        session.close()

        if len(contests) == 0:
            message = "No contests are open for this server." + \
                      "\n You may create them with the command `!contest create <contest_name>`"
        else:
            message = "The available contests are:\n\t" + "\n\t".join(contests) \
                      + "\n You can view the participants of an contest with the command " \
                      + "`!contest list <contest_name>`"
        await util.send(context, message)

    async def list_entries(self, context, contest_name):
        """ List the entries in the contest """
        guild_id = context.message.guild.id
        session = self.sessionmaker()

        # Verify the contest is created for the current guild
        if session.query(Contest) \
                .filter_by(name=contest_name, guild_id=guild_id) \
                .one_or_none() is None:
            session.rollback()
            session.close()
            await context.send(f"Contest {contest_name} was not found")
            return

        contests = session.query(Entry.user_id) \
            .filter(Contest.name == contest_name, Contest.guild_id == guild_id) \
            .all()

        session.close()

        # Grab discord display names
        usernames = [util.get_displayname(contest.user_id, context) for contest in contests]

        if len(usernames) == 0:
            message = "There are no entries for " + contest_name
        else:
            message = f"The entries for {contest_name} are: " + ", ".join(usernames)
        await util.send(context, message)


    @contest.command()
    async def close(self, context, contest_name=""):
        """
        Closes an open contest
        """
        if not util.is_from_guild(context):
            await context.send("This command must be run from a server.")
            return

        if contest_name == "":
            await context.send("You must include an contest name in this command"
                               "\n\tYou must format the command this way: `!drawing close <contest_name>`")
            return

        guild_id = context.message.guild.id
        session = self.sessionmaker()
        contest = session.query(Contest) \
            .filter_by(name=contest_name, guild_id=guild_id) \
            .one_or_none()

        if contest is None:
            session.close()
            await context.send(f"The contest {contest_name} does not exist.")
            return

        if contest.owner_id != context.message.author.id:
            session.close()
            print("Author: {}, Owner: {}".format(context.message.author.id, contest.owner_id))
            owner_name = context.message.guild.get_member(contest.owner_id).display_name
            await context.send(f"Only the owner of {contest_name} ({owner_name}) may close it.")
            return

        if not contest.open:
            session.close()
            await context.send(f"The contest {contest_name} is already closed.")
            return

        contest.open = False
        session.commit()

        await context.send(f"The contest {contest_name} has been closed.")


    @contest.command()
    async def draw(self, context, contest_name="", num_winners=""):
        """
        Draw winners for a contest
        num_winners must be either a positive number, or "all"
        """
        syntax = "You must format the command this way: `!contest draw contest_name [num_winners|all]`"

        if not util.is_from_guild(context):
            await context.send("This command must be run from a server.")
            return

        if contest_name == "":
            await context.send("You must include an contest name in this command\n\t" + syntax)
            return

        guild_id = context.message.guild.id
        session = self.sessionmaker()

        contest = session.query(Contest) \
            .filter_by(name=contest_name, guild_id=guild_id) \
            .one_or_none()

        if contest is None:
            session.close()
            await context.send(f"The contest {contest_name} does not exist.")
            return

        if contest.owner_id != context.message.author.id:
            session.close()
            print("Author: {}, Owner: {}".format(context.message.author.id, contest.owner_id))
            owner_name = context.message.guild.get_member(contest.owner_id).display_name
            await context.send(f"Only the owner of {contest_name} ({owner_name}) may close it.")
            return
        
        if num_winners == "":
            num_winners = 1
            all_winners = False
        elif num_winners.lower() == "all":
            all_winners = True
            num_winners = 1 # Temporary, until we get number of entries
        else:
            try:
                num_winners = int(num_winners)
            except:
                await context.send(f"{num_winners} is not a valid number or 'all'\n\t" + syntax)
                return
        
        if num_winners < 1:
            await context.send(f"The number of winners must be greater than 1.\n\t" + syntax)
            return
        
        if contest.num_winners is not None:
            prev_winners = contest.num_winners
        else:
            prev_winners = 0

        # Get entries who are not winners
        entries = (session.query(Entry)
                        .filter(Entry.contest == contest.cid, Entry.win_rank == None)
                        .all())
        
        # Remove winners
        entries = [entry for entry in entries if entry.win_rank is None]

        # Remove entries who have left the guild
        removed_users = list()
        for entry in entries:
            if context.message.guild.get_member(entry.user_id) is None:
                entries.remove(entry)
                removed_users.append(util.get_displayname(entry.user_id, context))
                session.delete(entry)

        if len(removed_users) > 0:
            await context.send(f"Users who have left the server have been removed from the contest: " +
                               ", ".join(removed_users))
        
        if all_winners or len(entries) < num_winners:
            num_winners = len(entries)
        
        # Randomize order, then pick the top few as winners
        shuffle(entries)
        winners = entries[:num_winners]

        for rank, winner in enumerate(winners, prev_winners + 1):
            winner.win_rank = rank
        
        contest.num_winners = prev_winners + num_winners

        # Update the database
        session.commit()

        message = ("Congrats to the following winners: \n\t" +
                    "\n\t".join([print_rank(winner, context) for winner in winners]))

        await context.send(message)

    @contest.command()
    async def winners(self, context, contest_name=""):
        """
        Show winners for a contest
        """
        syntax = "You must format the command this way: `!contest winners contest_name [num_winners|all]`"
        if not util.is_from_guild(context):
            await context.send("This command must be run from a server.")
            return

        if contest_name == "":
            await context.send("You must include an contest name in this command\n\t" + syntax)
            return

        session = self.sessionmaker()
        guild_id = context.message.guild.id
        session = self.sessionmaker()
        contest = (session.query(Contest)
                    .filter_by(name=contest_name, guild_id=guild_id)
                    .one_or_none())

        if contest is None:
            session.close()
            await context.send(f"The contest {contest_name} does not exist.")
            return

        if contest.num_winners is None:
            await context.send(f"The contest {contest_name} has no winners")
            return
        
        winners = (session.query(Entry)
                    .filter(Entry.contest == contest.cid, Entry.win_rank.isnot(None))
                    .order_by(Entry.win_rank)
                    .all())

        message = ("Congrats to the following winners: \n\t" +
                    "\n\t".join([print_rank(winner, context) for winner in winners]))
        
        await context.send(message)
