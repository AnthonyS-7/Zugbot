import discord
import modbot
import asyncio

with open("discord_token.txt", 'r') as token_file:
    token = token_file.read()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$nightkill'):
        assert type(message.content) == str
        if message.content == "$nightkill" or message.content.count(" ") != 1:
            await message.channel.send('Usage: $nightkill [player]')
        else:
            player = message.content.split(" ")[1]
            if modbot.submit_nightkill(player):
                await message.channel.send(f'Nightkill successfully submitted on {player}.')
            else:
                await message.channel.send(f"Nightkill could not be submitted on {player}. Either their name is spelled"
                                           " incorrectly, it is not night, or they are a member of the mafia.")

@client.event
async def on_game_end():
    await client.close()

async def start_discord_bot():
    await client.start(token=token)

def turn_bot_off():
    """
    Untested.
    """
    client.dispatch("on_game_end")

