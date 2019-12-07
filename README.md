# Dumbsparce
Configurable race bot that tracks times and whatnot.

## Requirements
You will need Python 3.6 or newer with the packages `discord.py` and `asyncpg` installed.

## Setup
Login to the Discord developers' portal and create an application with a bot user account. Create a file named `config.py` in the project root and give it this content:
```py
token = "Bot OAUTH Token Here"
cogs = ["race"]
```

## To run

    python3 bot.py
