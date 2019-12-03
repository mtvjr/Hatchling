import os
import sys
import discord.ext.commands.bot
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from src.santa import SecretSanta

bot_authors = [
    "mtvjr",
]

bot_description = "A discord bot to handle things for mtvjr."
bot_source = "https://www.github.com/mtvjr/mtvjrbot"

if __name__ == "__main__":
    if not os.getenv("DISCORD_TOKEN"):
        raise RuntimeError("DISCORD_TOKEN not set")

    token = os.getenv("DISCORD_TOKEN")

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL not set")

    url = os.getenv("DATABASE_URL")

    print(f"Got URL {url}")
    engine = create_engine(url)
    db = scoped_session(sessionmaker(bind=engine))

    bot = discord.ext.commands.Bot('!', description=bot_description)
    bot.add_cog(SecretSanta(bot, db))

    @bot.event
    async def on_ready():
        print('mtvjrbot is up and ready')

    @bot.command()
    async def source(ctx):
        await ctx.send(f"You can view my source at {bot_source}")

    @bot.command()
    async def authors(ctx):
        await ctx.send("I was written by: " + ", ".join(bot_authors))

    print("Starting bot")
    bot.run(token)
