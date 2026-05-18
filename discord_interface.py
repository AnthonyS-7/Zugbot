import discord
from discord import app_commands
import modbot
import constants as c
import asyncio
import config
from typing import TYPE_CHECKING

GAMESTATE_NONE_ERROR_MESSAGE = "The gamestate hasn't been initialized yet. This shouldn't happen except right when Zugbot starts up."

if TYPE_CHECKING:
    import player

if not config.is_botf: # BOTF has no wolfchat, so no Discord integration
    with open("discord_token.txt", 'r') as token_file:
        token = token_file.read()

    intents = discord.Intents.default()
    intents.message_content = True

    client_started = False

    class BotClient(discord.Client):
        def __init__(self):
            super().__init__(intents=intents)
            self.tree = app_commands.CommandTree(self)

        async def setup_hook(self):
            await self.tree.sync()


    client = BotClient()

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

    @client.tree.command(name="ads", description="Toggle ads in ITAs")
    async def toggle_ads(interaction: discord.Interaction):
        config.ita_ads = not config.ita_ads
        await interaction.response.send_message(f'Ads in ITAs are now {"on" if config.ita_ads else "off"}.')

    @client.tree.command(name="armor", description="Change a player's armor value")
    @app_commands.describe(player_username="The player whose state is being modified", value="The new armor value")
    async def armor(interaction: discord.Interaction, player_username: str, value: int):
        player = await verify_player(interaction, player_username)
        if player is not None:
            player.protection = value
            await interaction.response.send_message(f"Changed armor value of {player.username} to {value}.")

    @client.tree.command(name="resistance", description="Change a player's resistance.")
    @app_commands.describe(player_username="The player whose state is being modified", value="The new resistance (negative for vulnerability).")
    async def flatResistance(interaction: discord.Interaction, player_username: str, value: int):
        player = await verify_player(interaction, player_username)
        if player is not None:
            player.passives.flat_ita_resistance = value
            await interaction.response.send_message(f"Changed resistance value of {player.username} to {value}.")
    
    @client.tree.command(name="base_damage", description="Change the global base ITA damage.")
    @app_commands.describe(value="The new base damage.")
    async def base_damage(interaction: discord.Interaction, value: int):
        if value <= 0:
            await interaction.response.send_message("You must input a positive integer.")
        else:
            config.ita_base_damage = value
            await interaction.response.send_message(f"Changed ITA base damage to {config.ita_base_damage}.")

    @client.tree.command(name="redirect", description="Set a redirection from one player to another.")
    @app_commands.describe(start_player="The player ITAs are redirected away from.", end_player="The player ITAs are redirected to.")
    async def redirect(interaction: discord.Interaction, start_player: str, end_player: str):
        import player
        start_player_obj = await verify_player(interaction, start_player)
        if start_player_obj is None:
            return
        end_player_obj = await verify_player(interaction, end_player)
        if end_player_obj is None:
            return
        redirection_obj = player.Redirection(redirect_player=end_player_obj, redirection_strength=1, focus_increase_on_redirection=100)
        start_player_obj.redirection = redirection_obj
        await interaction.response.send_message(f"Added a redirection from {start_player_obj.username} to {end_player_obj.username}.")

    @client.tree.command(name="redirect_remove", description="Remove a redirection from a player.")
    @app_commands.describe(start_player="The player ITAs are currently redirected from.")
    async def clear_redirect(interaction: discord.Interaction, start_player: str):
        start_player_obj = await verify_player(interaction, start_player)
        if start_player_obj is None:
            return
        start_player_obj.redirection = None
        await interaction.response.send_message(f"Cleared redirection effect on {start_player_obj.username}.")

    @client.tree.command(name="create_post", description="Create an arbitrary post on Zugbot!")
    @app_commands.describe(message="The message to post")
    async def create_post(interaction: discord.Interaction, message: str):
        import fol_interface
        fol_interface.create_post(message)
        await interaction.response.send_message(f"Sent your message into the thread!")

    @client.tree.command(name="vampires", description="For Marluna's vampire role.")
    @app_commands.describe()
    async def vampires(interaction: discord.Interaction, marluna: str, attacker: str, defender: str):
        try:
            import fam6
            if modbot.gamestate is not None: # Clear all vampire tags since there can only be one at a time
                modbot.gamestate.apply_function_to_all_players(clear_player_vampire_tags, living_players_only=False)
            else:
                await interaction.response.send_message(GAMESTATE_NONE_ERROR_MESSAGE)
                return

            marluna_player_object = await verify_player(interaction, marluna)
            if marluna_player_object is None:
                return
            attacker_player_object = await verify_player(interaction, attacker)
            if attacker_player_object is None:
                return
            defender_player_object = await verify_player(interaction, defender)
            if defender_player_object is None:
                return
            fam6.set_vampire_player(marluna_player_object)
            defender_player_object.passives.ita_tags.add('vampire')
            ita_abilty_of_attacker = get_ita_ability(attacker_player_object)
            ita_abilty_of_attacker.ability_modifiers.ita_tags['vampire'] = 5
            await interaction.response.send_message(f"Set player with **The Vampire's Curse's** to {marluna_player_object.username}. \n"
                                            f"Set attacking player to {attacker_player_object.username}. \n"
                                            f"Set defending player to {defender_player_object.username}. \n"
                                            f"Reset the check for whether the vampire has been healed today. \n"
                                            f"NOTE: Any other existing vampire tags / effects have been cleared by this command.")
        except Exception as e:
            import traceback
            await interaction.response.send_message(f"**{type(e).__name__}**: {e}\n```{traceback.format_exc()}```")

    @client.tree.command(name="view_ita_tags", description="View all existing ITA tags.")
    async def view_ita_tags(interaction: discord.Interaction):
        if modbot.gamestate is not None:
            result_string = "# All ITA tags: \n"
            for player_obj in modbot.gamestate.original_players:
                this_players_result = ''
                abilities_with_ita_list = list(filter(lambda x : c.ITA in x.action_types, player_obj.abilities))
                for abil in abilities_with_ita_list:
                    for tag in abil.ability_modifiers.ita_tags:
                        this_players_result += f"Attacking tag: {tag} : {abil.ability_modifiers.ita_tags[tag]}. \n"
                for tag in player_obj.passives.ita_tags:
                    this_players_result += f"Defending tag: {tag}. \n"
                if len(abilities_with_ita_list) != 1:
                    this_players_result += f"WARNING: Somehow this player had {len(abilities_with_ita_list)} ITA abilities. This should never happen, even if they have multiple shots!\n"
                if this_players_result != '':
                    result_string += f"## {player_obj.username}: \n {this_players_result}"
            await interaction.response.send_message(result_string)
        else:
            await interaction.response.send_message(GAMESTATE_NONE_ERROR_MESSAGE)

    @client.tree.command(name="view_most_ita_information", description="View health/max_health/armor/resistance/redirections/angels of all players.")
    async def view_most_ita_information(interaction: discord.Interaction):
        if modbot.gamestate is None:
            await interaction.response.send_message(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        table_headers = ["Player Name", "HP", "Max HP", "Armor", "Res.", "Redirect", 'Angel', 'CritAngel']
        rows = []
        for player in modbot.gamestate.current_players:
            redirection_target = 'None' if player.redirection is None else player.redirection.redirect_player.username
            rows.append([player.username, player.health, player.max_health, player.protection, player.passives.flat_ita_resistance, redirection_target,
                         player.passives.ita_angel_count, player.passives.ita_angel_crit_count])
        await interaction.response.send_message(make_table(table_headers, rows))

    @client.tree.command(name="view_redirections", description="View redirections on all players.")
    async def view_redirections(interaction: discord.Interaction):
        if modbot.gamestate is None:
            await interaction.response.send_message(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        table_headers = ["Player Name", 'Redirected To']
        rows = []
        last_redir_pair = ''
        for player in modbot.gamestate.current_players:
            redirection_target = 'None' if player.redirection is None else player.redirection.redirect_player.username
            if redirection_target != 'None':
                last_redir_pair = f'For example: ITAs are redirected from {player.username} to {redirection_target}.'
            rows.append([player.username, redirection_target])
        await interaction.response.send_message(make_table(table_headers, rows)
                                                + "Note on redirections: ITAs are redirected from the player on the left-most column to the player in the redirection column. \n" 
                                                + last_redir_pair)

    @client.tree.command(name="view_hp_armor_res", description="Designed for mobile clients. Larger screens can just use view_most_ita_information.")
    async def view_hp_armor_res(interaction: discord.Interaction):
        if modbot.gamestate is None:
            await interaction.response.send_message(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        table_headers = ["Player Name", "HP", "Ar.", 'Res.']
        rows = []
        for player in modbot.gamestate.current_players:
            rows.append([player.username, player.health, player.protection, player.passives.flat_ita_resistance])
        await interaction.response.send_message(make_table(table_headers, rows))

    def make_table(headers, rows):
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        
        def format_row(cells):
            return " | ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(cells))
        
        separator = "-+-".join("-" * w for w in col_widths)
        
        lines = [format_row(headers), separator]
        for row in rows:
            lines.append(format_row(row))
        
        return "```\n" + "\n".join(lines) + "\n```"

    @client.tree.command(name="ultimate_assassin", description="Give someone the Ultimate Assassin ability.")
    @app_commands.describe(assassin_player="The player to get the Ultimate Assassin ability tag.")
    async def ultimate_assassin(interaction: discord.Interaction, assassin_player: str):
        player_obj = await verify_player(interaction, assassin_player)
        if player_obj is None:
            return
        abilities_with_ita_list = list(filter(lambda x : c.ITA in x.action_types, player_obj.abilities))
        for abil in abilities_with_ita_list:
            abil.ability_modifiers.ita_tags["full_health"] = 3
        if len(abilities_with_ita_list) != 1:
            await interaction.response.send_message(f"WARNING: Somehow this player had {len(abilities_with_ita_list)} ITA abilities. This should never happen, even if they have multiple shots!\n"
                                                    "To each ability, I added the appropriate modifier, but tread carefully because things are broken!")
        else:
            await interaction.response.send_message(f"Ultimate Assassin ability successfully granted to {player_obj.username}.")

    def clear_player_vampire_tags(player_obj: 'player.Player'):
        player_obj.passives.ita_tags.discard('vampire')
        for abil in player_obj.abilities:
            if c.ITA in abil.action_types:
                abil.ability_modifiers.ita_tags.pop('vampire', 0)

    @client.tree.command(name="vampires_clear", description="Clear any existing Vampire effects.")
    @app_commands.describe()
    async def vampires_clear(interaction: discord.Interaction): # TODO: test!
        import fam6
        fam6.set_vampire_player(None)
        if modbot.gamestate is not None:
            modbot.gamestate.apply_function_to_all_players(clear_player_vampire_tags, living_players_only=False)
            await interaction.response.send_message("All vampire-related information has been cleared.")
        else:
            await interaction.response.send_message(GAMESTATE_NONE_ERROR_MESSAGE)

    @client.tree.command(name="ita_angel", description="Change the ITA Angel count on a player.")
    @app_commands.describe(player_username="The player whose state is being modified", value="The new ITA Angel value")
    async def ita_angel(interaction: discord.Interaction, player_username: str, value: int):
        player = await verify_player(interaction, player_username)
        if player is not None:
            player.passives.ita_angel_count = value
            await interaction.response.send_message(f"Changed ITA Angel count of {player.username} to {value}.")

    @client.tree.command(name="ita_crit_angel", description="Change the ITA Crit Angel count on a player.")
    @app_commands.describe(player_username="The player whose state is being modified", value="The new ITA Crit Angel value")
    async def ita_crit_angel(interaction: discord.Interaction, player_username: str, value: int):
        player = await verify_player(interaction, player_username)
        if player is not None:
            player.passives.ita_angel_crit_count = value
            await interaction.response.send_message(f"Changed ITA Crit Angel count of {player.username} to {value}.")

    @client.tree.command(name="defensive_tag", description="Add/remove a defensive tag to a player.")
    @app_commands.describe(player_username="The player whose state is being modified", tag="The defensive tag.", add="True to add, false to remove.")
    async def defensive_tag(interaction: discord.Interaction, player_username: str, tag: str, add: bool):
        player = await verify_player(interaction, player_username)
        if player is None:
            return
        if add:
            player.passives.ita_tags.add(tag)
            await interaction.response.send_message(f"{player.username} now has tag {tag}.")
        elif tag in player.passives.ita_tags:
            player.passives.ita_tags.discard(tag)
            await interaction.response.send_message(f"Removed {tag} from {player.username}.")
        else:
            await interaction.response.send_message(f"{player.username} already did not have {tag}.")

    @client.tree.command(name="offensive_tag", description="Add/remove an offensive tag to a player.")
    @app_commands.describe(player_username="The player whose state is being modified", tag="The offensive tag.", value="The offensive tag's damage modifier (doesn't matter if you're removing the tag).", add="True to add, false to remove.")
    async def offensive_tag(interaction: discord.Interaction, player_username: str, tag: str, value: int, add: bool):
        player = await verify_player(interaction, player_username)
        if player is None:
            return
        ita_ability = get_ita_ability(player)
        if add:
            ita_ability.ability_modifiers.ita_tags[tag] = value
            await interaction.response.send_message(f"{player.username} now has tag {tag} with damage modifier {value}.")
        elif tag in ita_ability.ability_modifiers.ita_tags:
            ita_ability.ability_modifiers.ita_tags.pop(tag, 0)
            await interaction.response.send_message(f"Removed {tag} from {player.username}.")
        else:
            await interaction.response.send_message(f"{player.username} already did not have {tag}.")

    def get_ita_ability(player_obj: 'player.Player'):
        abilities_with_ita_list = list(filter(lambda x : c.ITA in x.action_types, player_obj.abilities))
        if len(abilities_with_ita_list) != 1:
            print(f"ERROR: A player had {len(abilities_with_ita_list)} which should never happen!")
        return abilities_with_ita_list[0]

    async def verify_player(interaction: discord.Interaction, player_username: str) -> 'player.Player | None':
        resolved_name = modbot.resolve_name(player_username)
        if modbot.gamestate is None:
            await interaction.response.send_message(GAMESTATE_NONE_ERROR_MESSAGE)
            return None
        player = modbot.gamestate.get_player_object_original_players(resolved_name)
        if player is None:
            await interaction.response.send_message(f"There is no player with the username {player_username}. Action unsuccessful.")
            return None
        return player
    


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

