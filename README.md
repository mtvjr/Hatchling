# Hatchling
A (newer) bot for discord

## Purpose
This bot is to be a general purpose bot for my discording needs.

It will also teach me how to use Heroku and postgres.

It will probably not suite your needs.

## Feature Roadmap

1. Secret Santa (Mostly done)
2. Contests (Hopefully done)
3. ???

## How to Run
1. Copy base.env to .env
2. Set up a developer discord account and create an Application and Bot. Add the bot's secret key to your `.env` file. https://discord.com/developers/applications
3. Create and activate a virtual environment for python3.
4. Use pip (under the venv) to install dependencies from requirements.txt
5. Install PostgreSQL and set up a database and user. Add the database URL to your `.env` file. https://stackoverflow.com/questions/3582552/postgresql-connection-url
6. While in the virtual environment, run `python hatchling.py`

