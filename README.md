# Dumbsparce
Configurable race bot that tracks times and whatnot.

## Requirements
You will need postgresql and Python 3.6 or newer with the packages `discord.py[voice]` and `asyncpg` installed via pip.

## Setup
Login to the Discord developers' portal and create an application with a bot user account. Create a file named `config.py` in the project root and give it this content:
```py
token = "Bot OAUTH Token Here"
cogs = ["cogs.race"]
postgre_user = "postgresql-username-here"
postgre_pass = "postgresql-password-here"
```

## To run

    python3 bot.py
