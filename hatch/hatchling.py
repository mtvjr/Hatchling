import os
import discord.ext.commands.bot
from sqlalchemy import create_engine
from hatch.santa import SecretSanta

bot_authors = [
    "mtvjr",
]

bot_description = "A discord bot to handle things and stuff."
bot_source = "https://www.github.com/mtvjr/hatchling"
bot_name = "Hatchling"
bot_version = "0.0.2"

if __name__ == "__main__":
    if not os.getenv("DISCORD_TOKEN"):
        raise RuntimeError("DISCORD_TOKEN not set")

    token = os.getenv("DISCORD_TOKEN")

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL not set")

    url = os.getenv("DATABASE_URL")

    engine = create_engine(url)

    bot = discord.ext.commands.Bot('!', description=bot_description)
    bot.add_cog(SecretSanta(bot, engine))

    @bot.event
    async def on_ready():
        print(f'{bot_name} is up and ready')

    @bot.command()
    async def source(ctx):
        await ctx.send(f"You can view my source at {bot_source}")

    @bot.command()
    async def authors(ctx):
        await ctx.send("I was written by: " + ", ".join(bot_authors))

    @bot.command()
    async def version(ctx):
        await ctx.send(f"I am on version {bot_version}.")

    print(f"Starting {bot_name}")
    bot.run(token)
