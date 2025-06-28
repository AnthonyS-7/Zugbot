# Zugbot

Zugbot is a program to automate hosting games of Mafia on Discourse forums.

For examples of Zugbot running, see:
 - https://www.fortressoflies.com/t/zugbots-multivote-mountainous-mafia-victory/12248
 - https://www.fortressoflies.com/t/popcorny-4-salvation-mafia-victory/12385

# Requirements

To use Zugbot, you will need an API key from a site admin. This API key must be placed in a file named discourse_api_key.txt.
You will also need to create a Discord bot, and place its token in discord_token.txt.

# Usage

To start a new game, choose the desired settings in config.py, and then run main.py. 

The bot will save the gamestate every so often (the exact timing is decided in config.py). If you would like to restart the bot from the last save point, you can do so with restore.py.
