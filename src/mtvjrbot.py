import os
import sys
import discord

# Basic example for now

if __name__ == "__main__":
    client = discord.Client()

    @client.event
    async def on_message(message):
        print(message.content)

    token = os.environ.get("DISCORD_TOKEN", "No token")
    if token == "No token":
        print("No token found, exiting")
        sys.quit()
    print("Token found, starting bot")
    client.run(token)
