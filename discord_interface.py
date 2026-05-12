import discord
import modbot
import asyncio
import config

if not config.is_botf: # BOTF has no wolfchat, so no Discord integration
    with open("discord_token.txt", 'r') as token_file:
        token = token_file.read()

    intents = discord.Intents.default()
    intents.message_content = True

    client_started = False

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

    async def send_message_to_hosting_discord(message_to_send: str):
        if config.send_messages_to_hosting_discord:
            channel_to_send_to = await client.fetch_channel(config.hosting_discord_channel_id_for_output)
            await channel_to_send_to.send(message_to_send) # type: ignore


    async def start_discord_bot():
        global client_started
        if not client_started:
            print("Starting discord client!")
            await client.start(token=token)
            client_started = True

    def turn_bot_off():
        """
        Untested.
        """
        client.dispatch("on_game_end")

