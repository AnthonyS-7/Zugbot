import discord
from discord import app_commands
import modbot
import constants as c
import asyncio
import config
from typing import TYPE_CHECKING
import time
import queue

GAMESTATE_NONE_ERROR_MESSAGE = "The gamestate hasn't been initialized yet. This shouldn't happen except right when Zugbot starts up."
reset_itas_last_time_of_use = 0
send_feedback_last_time_of_use = 0
suggestions_day_of_last_use = 0
sow_doubt_used = False


if TYPE_CHECKING:
    import player

feedback_to_send: 'dict[player.Player, str]' = dict()
queue_of_posts_for_hosting_discord = queue.Queue()

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
            guild = discord.Object(id=config.hosting_discord_guild_id)
            self.tree.copy_global_to(guild=guild) 
            await self.tree.sync(guild=guild)
            await self.tree.sync()

    client = BotClient()

    @client.event
    async def on_ready():
        print(f'We have logged in as {client.user}')

    @client.event
    async def on_message(message: discord.message.Message):
        global feedback_to_send
        if message.author == client.user:
            return

        if message.content.startswith('$nightkill') and not config.disable_nightkill:
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
        if message.content.startswith('$feedback ') and message.guild is not None and message.guild.id == config.hosting_discord_guild_id:
            if modbot.gamestate is None:
                await message.channel.send(GAMESTATE_NONE_ERROR_MESSAGE)
                return
            player_name = message.content.split(' ')[1]
            player_name_corrected = modbot.resolve_name(player_name, living_players_only=False)
            player_obj = modbot.gamestate.get_player_object_original_players(player_name_corrected)
            if player_obj is None:
                await message.channel.send(f"{player_name} is not a valid player.")
                return
            feedback_string = message.content.split('$feedback ' + player_name + ' ')[1]
            feedback_to_send[player_obj] = feedback_string
            await message.channel.send(f"Changed feedback of player {player_name_corrected} to: \n ```\n{feedback_string}\n```")

    @client.tree.command(name="sub", description="Perform a substitution.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(current_player_username="The username of the player currently in the game.", new_player_username="The username of the person to sub into the game")
    async def sub(interaction: discord.Interaction, current_player_username: str, new_player_username: str):
        await interaction.response.defer()
        try:
            current_player_obj = await verify_player(interaction, current_player_username)
            if current_player_obj is None:
                return
            if modbot.gamestate is None:
                await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
                return
            from roles_folder import host
            result = await host.do_substitution(None, modbot.gamestate, None, current_player_obj, new_player_username)
            await interaction.followup.send(result)
        except Exception as e:
            import traceback
            await interaction.followup.send(f"**{type(e).__name__}**: {e}\n```{traceback.format_exc()}```")


    @client.tree.command(name="toggle_itas", description="Toggle ITAs on or off.", guild=discord.Object(id=config.hosting_discord_guild_id))
    async def toggle_itas(interaction: discord.Interaction):
        config.include_itas = not config.include_itas
        await interaction.response.defer()
        await interaction.followup.send(f"ITAs have been turned {'on' if config.include_itas else 'off'}.")

    @client.tree.command(name="spooky_role_change_cooldowns", description="Change the cooldowns on Spooky's abilities (necessary if bot has to be restarted).", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(suggestions_already_used="Whether the Suggestions ability has been used today.", sow_doubt_already_used="Whether the Sow Doubt ability has been used this game.")
    async def spooky_role_reset_cooldowns(interaction: discord.Interaction, suggestions_already_used: bool, sow_doubt_already_used: bool):
        global suggestions_day_of_last_use
        global sow_doubt_used
        await interaction.response.defer()

        if modbot.gamestate is None:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        
        if suggestions_already_used:
            suggestions_day_of_last_use = modbot.gamestate.phase_count
        else:
            suggestions_day_of_last_use = 0
        sow_doubt_used = sow_doubt_already_used

        await interaction.followup.send(f"Spooky's Suggestions ability marked as {'on' if suggestions_already_used else 'off'} cooldown. \n" +
                                        f"Spooky's Sow Doubt ability marked as {'on' if sow_doubt_already_used else 'off'} cooldown.")
        
    @client.tree.command(name="lol", description="Toggle whether this player has the lol role.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(lol_username="The username of the player being marked as lol.")
    async def lol(interaction: discord.Interaction, lol_username: str):
        await interaction.response.defer()
        player_obj = await verify_player(interaction, lol_username)
        if player_obj is None:
            return
        if 'lol' not in player_obj.passives.defensive_ita_tags:
            await interaction.followup.send(f"Player {player_obj.username} has been given the lol role.")
            player_obj.passives.defensive_ita_tags.add('lol')
        else:
            await interaction.followup.send(f"The lol role has been removed from Player {player_obj.username}.")
            player_obj.passives.defensive_ita_tags.discard('lol')

    @client.tree.command(name="feedback_send", description="Send out all feedback.", guild=discord.Object(id=config.hosting_discord_guild_id))
    async def feedback_send(interaction: discord.Interaction):
        global feedback_to_send
        global send_feedback_last_time_of_use
        await interaction.response.defer()
        current_time = time.time()
        if current_time - send_feedback_last_time_of_use > 120:
            await interaction.followup.send("Are you SURE you want to send out feedback? Run the command again to confirm. Note the command will take a while to finish.")
            send_feedback_last_time_of_use = current_time
            return
        import fol_interface
        for player_obj in feedback_to_send:
            fol_interface.send_message(feedback_to_send[player_obj], player_obj.username)
            await asyncio.sleep(2)
        feedback_to_send = dict()
        await interaction.followup.send("Sent all feedback.")

    @client.tree.command(name="feedback_view", description="View currently stored feedback.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The player whose feedback you want to view")
    async def feedback_view(interaction: discord.Interaction, player_username: str):
        await interaction.response.defer()
        player_obj = await verify_player(interaction, player_username)
        if player_obj is None:
            return
        if player_obj not in feedback_to_send:
            await interaction.followup.send(f"Player {player_obj.username} currently has no feedback.")
        else:
            await interaction.followup.send(f"```\n{feedback_to_send[player_obj]}\n```")

    @client.tree.command(name="ads", description="Toggle ads in ITAs", guild=discord.Object(id=config.hosting_discord_guild_id))
    async def toggle_ads(interaction: discord.Interaction):
        config.ita_ads = not config.ita_ads
        await interaction.response.defer()
        await interaction.followup.send(f'Ads in ITAs are now {"on" if config.ita_ads else "off"}.')

    @client.tree.command(name="armor", description="Change a player's armor value", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The player whose state is being modified", value="The new armor value")
    async def armor(interaction: discord.Interaction, player_username: str, value: int):
        await interaction.response.defer()
        player = await verify_player(interaction, player_username)
        if player is not None:
            player.protection = value
            await interaction.followup.send(f"Changed armor value of {player.username} to {value}.")

    @client.tree.command(name="resistance", description="Change a player's resistance.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The player whose state is being modified", value="The new resistance (negative for vulnerability).")
    async def flatResistance(interaction: discord.Interaction, player_username: str, value: int):
        await interaction.response.defer()
        player = await verify_player(interaction, player_username)
        if player is not None:
            player.passives.flat_ita_resistance = value
            await interaction.followup.send(f"Changed resistance value of {player.username} to {value}.")
    
    @client.tree.command(name="base_damage", description="Change the global base ITA damage.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(value="The new base damage.")
    async def base_damage(interaction: discord.Interaction, value: int):
        await interaction.response.defer()
        if value <= 0:
            await interaction.followup.send("You must input a positive integer.")
        else:
            config.ita_base_damage = value
            await interaction.followup.send(f"Changed ITA base damage to {config.ita_base_damage}.")

    @client.tree.command(name="redirect", description="Set a redirection from one player to another.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(start_player="The player ITAs are redirected away from.", end_player="The player ITAs are redirected to.")
    async def redirect(interaction: discord.Interaction, start_player: str, end_player: str):
        await interaction.response.defer()
        import player
        start_player_obj = await verify_player(interaction, start_player)
        if start_player_obj is None:
            return
        end_player_obj = await verify_player(interaction, end_player)
        if end_player_obj is None:
            return
        redirection_obj = player.Redirection(redirect_player=end_player_obj, redirection_strength=1, focus_increase_on_redirection=100)
        start_player_obj.redirection = redirection_obj
        await interaction.followup.send(f"Added a redirection from {start_player_obj.username} to {end_player_obj.username}.")

    @client.tree.command(name="redirect_remove", description="Remove a redirection from a player.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(start_player="The player ITAs are currently redirected from.")
    async def clear_redirect(interaction: discord.Interaction, start_player: str):
        await interaction.response.defer()
        start_player_obj = await verify_player(interaction, start_player)
        if start_player_obj is None:
            return
        start_player_obj.redirection = None
        await interaction.followup.send(f"Cleared redirection effect on {start_player_obj.username}.")

    @client.tree.command(name="create_post", description="Create an arbitrary post on Zugbot!", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(message="The message to post")
    async def create_post(interaction: discord.Interaction, message: str):
        await interaction.response.defer()
        import fol_interface
        fol_interface.create_post(message)
        await interaction.followup.send(f"Sent your message into the thread!")

    @client.tree.command(name="vampires", description="For Marluna's vampire role.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe()
    async def vampires(interaction: discord.Interaction, marluna: str, attacker: str, defender: str):
        await interaction.response.defer()
        try:
            import fam6
            if modbot.gamestate is not None: # Clear all vampire tags since there can only be one at a time
                modbot.gamestate.apply_function_to_all_players(clear_player_vampire_tags, living_players_only=False)
            else:
                await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
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
            defender_player_object.passives.defensive_ita_tags.add('vampire')
            attacker_player_object.passives.offensive_ita_tags['vampire'] = 5
            await interaction.followup.send(f"Set player with **The Vampire's Curse's** to {marluna_player_object.username}. \n"
                                            f"Set attacking player to {attacker_player_object.username}. \n"
                                            f"Set defending player to {defender_player_object.username}. \n"
                                            f"NOTE: Any other existing vampire tags / effects have been cleared by this command.")
        except Exception as e:
            import traceback
            await interaction.followup.send(f"**{type(e).__name__}**: {e}\n```{traceback.format_exc()}```")

    @client.tree.command(name="willow", description="For the Willow role.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(willow="The player with the Willow role (or the Willow role's ability).", bird="The player chosen as the bird.")
    async def willow(interaction: discord.Interaction, willow: str, bird: str):
        await interaction.response.defer()
        willow_obj = await verify_player(interaction, willow)
        if willow_obj is None:
            return
        bird_obj = await verify_player(interaction, bird)
        if bird_obj is None:
            return
        import fam6
        fam6.set_bird_player(bird_obj)
        fam6.set_willow_player(willow_obj)
        await interaction.followup.send(f"Set Willow to {willow_obj.username} and Bird to {bird_obj.username}.")

    @client.tree.command(name="willow_clear", description="Clear the Bird/Willow variables.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe()
    async def willow_clear(interaction: discord.Interaction):
        await interaction.response.defer()
        import fam6
        fam6.set_willow_player(None)
        fam6.set_bird_player(None)
        await interaction.followup.send("The Bird and Willow players have been set to None.")
    

    @client.tree.command(name="view_ita_tags", description="View all existing ITA tags.", guild=discord.Object(id=config.hosting_discord_guild_id))
    async def view_ita_tags(interaction: discord.Interaction):
        await interaction.response.defer()
        if modbot.gamestate is not None:
            result_strings = ["# All ITA tags:"]
            for player_obj in modbot.gamestate.current_players:
                this_players_result = ''
                for tag in player_obj.passives.offensive_ita_tags:
                    this_players_result += f"Attacking tag: {tag} : {player_obj.passives.offensive_ita_tags[tag]}. \n"
                for tag in player_obj.passives.defensive_ita_tags:
                    if tag != "full_health":
                        this_players_result += f"Defending tag: {tag}. \n"
                if this_players_result != '':
                    result_strings.append(f"## {player_obj.username}: \n {this_players_result}")
            for msg in condense_messages(result_strings):
                await interaction.followup.send(msg)
        else:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)

    @client.tree.command(name="view_most_ita_information", description="View health/max_health/armor/resistance/redirections/angels of all players.", 
                         guild=discord.Object(id=config.hosting_discord_guild_id))
    async def view_most_ita_information(interaction: discord.Interaction):
        await interaction.response.defer()
        if modbot.gamestate is None:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        table_headers = ["Player Name", "HP", "Max HP", "Armor", "Res.", "Redirect", 'Angel', 'CritAngel']
        rows = []
        for player in modbot.gamestate.current_players:
            redirection_target = 'None' if player.redirection is None else player.redirection.redirect_player.username
            rows.append([player.username, player.health, player.max_health, player.protection, player.passives.flat_ita_resistance, redirection_target,
                         player.passives.ita_angel_count, player.passives.ita_angel_crit_count])
        for table in make_tables(table_headers, rows):
            await interaction.followup.send(table)

    @client.tree.command(name="view_redirections", description="View redirections on all players.",
                                     guild=discord.Object(id=config.hosting_discord_guild_id))
    async def view_redirections(interaction: discord.Interaction):
        await interaction.response.defer()
        if modbot.gamestate is None:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        table_headers = ["Player Name", 'Redirected To']
        rows = []
        last_redir_pair = ''
        for player in modbot.gamestate.current_players:
            redirection_target = 'None' if player.redirection is None else player.redirection.redirect_player.username
            if redirection_target != 'None':
                last_redir_pair = f'For example: ITAs are redirected from {player.username} to {redirection_target}.'
            rows.append([player.username, redirection_target])
        for table in make_tables(table_headers, rows):
            await interaction.followup.send(table)
        await interaction.followup.send("Note on redirections: ITAs are redirected from the player on the left-most column to the player in the redirection column. \n" 
                                                + last_redir_pair)

    @client.tree.command(name="view_hp_armor_res", description="Designed for mobile clients. Larger screens can just use view_most_ita_information.",
                        guild=discord.Object(id=config.hosting_discord_guild_id))
    async def view_hp_armor_res(interaction: discord.Interaction):
        await interaction.response.defer()
        if modbot.gamestate is None:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        table_headers = ["Player Name", "HP", "Ar.", 'Res.']
        rows = []
        for player in modbot.gamestate.current_players:
            rows.append([player.username, player.health, player.protection, player.passives.flat_ita_resistance])
        for table in make_tables(table_headers, rows):
            await interaction.followup.send(table)

    def make_tables(headers, rows, char_limit=2000):
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        def format_row(cells):
            return " | ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(cells))

        separator = "-+-".join("-" * w for w in col_widths)
        header_block = format_row(headers) + "\n" + separator + "\n"
        overhead = len("```\n") + len(header_block) + len("\n```")

        tables = []
        current_rows = []
        current_len = overhead

        for row in rows:
            line = format_row(row) + "\n"
            if current_len + len(line) > char_limit and current_rows:
                tables.append(current_rows)
                current_rows = []
                current_len = overhead
            current_rows.append(line)
            current_len += len(line)

        if current_rows:
            tables.append(current_rows)

        results = []
        for group in tables:
            body = "```\n" + header_block + "".join(group) + "```"
            results.append(body)

        return results

    # def make_table(headers, rows):
    #     col_widths = [len(h) for h in headers]
    #     for row in rows:
    #         for i, cell in enumerate(row):
    #             col_widths[i] = max(col_widths[i], len(str(cell)))
        
    #     def format_row(cells):
    #         return " | ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(cells))
        
    #     separator = "-+-".join("-" * w for w in col_widths)
        
    #     lines = [format_row(headers), separator]
    #     for row in rows:
    #         lines.append(format_row(row))
        
    #     return "```\n" + "\n".join(lines) + "\n```"

    @client.tree.command(name="ultimate_assassin", description="Give someone the Ultimate Assassin ability.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(assassin_player="The player to get the Ultimate Assassin ability tag.")
    async def ultimate_assassin(interaction: discord.Interaction, assassin_player: str):
        await interaction.response.defer()
        player_obj = await verify_player(interaction, assassin_player)
        if player_obj is None:
            return
        player_obj.passives.offensive_ita_tags['full_health'] = 3
        await interaction.followup.send(f"Ultimate Assassin ability successfully granted to {player_obj.username}.")

    def clear_player_vampire_tags(player_obj: 'player.Player'):
        player_obj.passives.defensive_ita_tags.discard('vampire')
        player_obj.passives.offensive_ita_tags.pop('vampire', 0)

    @client.tree.command(name="vampires_clear", description="Clear any existing Vampire effects.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe()
    async def vampires_clear(interaction: discord.Interaction): # TODO: test!
        await interaction.response.defer()
        import fam6
        fam6.set_vampire_player(None)
        if modbot.gamestate is not None:
            modbot.gamestate.apply_function_to_all_players(clear_player_vampire_tags, living_players_only=False)
            await interaction.followup.send("All vampire-related information has been cleared.")
        else:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)

    @client.tree.command(name="health", description="Change a player's health.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The player whose state is being modified", value="The new health value")
    async def health(interaction: discord.Interaction, player_username: str, value: int):
        await interaction.response.defer()
        if modbot.gamestate is None:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        player_obj = await verify_player(interaction, player_username)
        if player_obj is not None:
            player_obj.health = value
            modbot.gamestate.sync_living_players()
            await interaction.followup.send(f"Changed health of {player_obj.username} to {value}. \n"
                                                    "**If you killed or revived a player with this command, ensure you fix the votecount!**")

    @client.tree.command(name="change_main_thread", description="Change the ID of the main thread.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(new_id="The new topic ID of the main thread.")
    async def change_main_thread(interaction: discord.Interaction, new_id: int):
        await interaction.response.defer()
        if new_id < 1:
            await interaction.followup.send("Invalid topic ID.")
            return
        import fol_interface
        if not await fol_interface.check_if_new_main_thread_id_is_valid(new_id):
            await interaction.followup.send("This topic is not valid! (Rarely, connection issues can make a valid topic ID give this message too.)")
            return
        config.topic_id = new_id
        modbot.posts_in_thread_at_last_vc = 1
        await interaction.followup.send(f"Successfully made the main thread have ID {new_id}, and reset {modbot.posts_in_thread_at_last_vc} to 1.")

    @client.tree.command(name="max_health", description="Change a player's health.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The player whose state is being modified", value="The new max health value")
    async def max_health(interaction: discord.Interaction, player_username: str, value: int):
        await interaction.response.defer()
        player_obj = await verify_player(interaction, player_username)
        if player_obj is not None:
            player_obj.max_health = value
            await interaction.followup.send(f"Changed max health of {player_obj.username} to {value}.")

    @client.tree.command(name="ita_angel", description="Change the ITA Angel count on a player.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The player whose state is being modified", value="The new ITA Angel value")
    async def ita_angel(interaction: discord.Interaction, player_username: str, value: int):
        await interaction.response.defer()
        player = await verify_player(interaction, player_username)
        if player is not None:
            player.passives.ita_angel_count = value
            await interaction.followup.send(f"Changed ITA Angel count of {player.username} to {value}.")

    @client.tree.command(name="ita_crit_angel", description="Change the ITA Crit Angel count on a player.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The player whose state is being modified", value="The new ITA Crit Angel value")
    async def ita_crit_angel(interaction: discord.Interaction, player_username: str, value: int):
        await interaction.response.defer()
        player = await verify_player(interaction, player_username)
        if player is not None:
            player.passives.ita_angel_crit_count = value
            await interaction.followup.send(f"Changed ITA Crit Angel count of {player.username} to {value}.")

    @client.tree.command(name="defensive_tag", description="Add/remove a defensive tag to a player.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The player whose state is being modified", tag="The defensive tag.", add="True to add, false to remove.")
    async def defensive_tag(interaction: discord.Interaction, player_username: str, tag: str, add: bool):
        await interaction.response.defer()
        player = await verify_player(interaction, player_username)
        if player is None:
            return
        if add:
            player.passives.defensive_ita_tags.add(tag)
            await interaction.followup.send(f"{player.username} now has tag {tag}.")
        elif tag in player.passives.defensive_ita_tags:
            player.passives.defensive_ita_tags.discard(tag)
            await interaction.followup.send(f"Removed {tag} from {player.username}.")
        else:
            await interaction.followup.send(f"{player.username} already did not have {tag}.")

    @client.tree.command(name="offensive_tag", description="Add/remove an offensive tag to a player.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The player whose state is being modified", tag="The offensive tag.", value="The offensive tag's damage modifier (doesn't matter if you're removing the tag).", add="True to add, false to remove.")
    async def offensive_tag(interaction: discord.Interaction, player_username: str, tag: str, value: int, add: bool):
        await interaction.response.defer()
        player = await verify_player(interaction, player_username)
        if player is None:
            return
        if add:
            player.passives.offensive_ita_tags[tag] = value
            await interaction.followup.send(f"{player.username} now has tag {tag} with damage modifier {value}.")
        elif tag in player.passives.offensive_ita_tags:
            player.passives.offensive_ita_tags.pop(tag, 0)
            await interaction.followup.send(f"Removed {tag} from {player.username}.")
        else:
            await interaction.followup.send(f"{player.username} already did not have {tag}.")

    @client.tree.command(name="add_ita", description="Give a player an ITA shot.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The player receiving this ITA", damage="The damage this ITA should do", 
                           identifier="The name of this ITA. This is visible to the player, and a player cannot have two ITAs with the same identifier.",
                           can_crit="True if this ITA can crit (like most ITAs) or False if it cannot",
                           is_silent="True if this is a silent ITA, False if it is a normal ITA.")
    async def add_ita(interaction: discord.Interaction, player_username: str, identifier: str, damage: int, can_crit: bool, is_silent: bool):
        await interaction.response.defer()
        try:
            import player
            player_obj = await verify_player(interaction, player_username)
            if player_obj is None:
                return
            if not identifier.replace(' ', '').isalnum():
                await interaction.followup.send("Error: Identifiers must consist of only letters, numbers, and spaces, and must have at least one non-space character.")
                return
            new_ita_item = player.ITAItem(damage=damage, can_crit=can_crit, identifier=identifier)
            list_to_add_to = player_obj.silent_ita_items if is_silent else player_obj.ita_items
            current_identifiers = list(map(lambda x : x.identifier, player_obj.ita_items + player_obj.silent_ita_items))
            if identifier in current_identifiers:
                await interaction.followup.send(f"Error: Player {player_obj.username} already has an ITA with identifier {identifier}.")
                return
            if damage < -1:
                await interaction.followup.send(F"Error: Negative damage ITAs are not allowed (though you can use -1 to mean base damage).")
                return
            list_to_add_to.append(new_ita_item)
            await interaction.followup.send(f"Player {player_obj.username} successfully given ITA with {damage=}, {identifier=}, {can_crit=}, {is_silent=}.")
        except Exception as e:
            import traceback
            await interaction.followup.send(f"**{type(e).__name__}**: {e}\n```{traceback.format_exc()}```")

    @client.tree.command(name="reset_itas", description="Reset the ITAs held by all players. This must be run at every day start.",
                        guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe()
    async def reset_itas(interaction: discord.Interaction):
        await interaction.response.defer()
        import player
        global reset_itas_last_time_of_use
        if modbot.gamestate is None:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        current_time = time.time()
        if current_time - reset_itas_last_time_of_use > 120:
            await interaction.followup.send("Are you SURE you want to reset all ITAs? Run the command again to confirm.")
            reset_itas_last_time_of_use = current_time
            return
        reset_itas_last_time_of_use = 0
        for player_obj in modbot.gamestate.original_players:
            player_obj.silent_ita_items = []
            player_obj.ita_items = [player.ITAItem()]
            player_obj.passives.number_of_itas_taken = 0
        await interaction.followup.send("ALL ITAs have been reset.\n"
                                                "All players have exactly one shot of their ITA, which does the default base damage."
                                                "\nAny previously existing ITAs have been deleted.")
    
    @client.tree.command(name="view_itas", description="View all ITAs currently held by players.")
    @app_commands.describe()
    async def view_itas(interaction: discord.Interaction):
        await interaction.response.defer()
        if modbot.gamestate is None:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
            return None
        table_headers = ["Player With ITA", "Identifier", "Index", "Damage", 
                        "Can Crit?", "Is Silent?"] if interaction.guild_id == config.hosting_discord_guild_id else [
                        "Player With ITA", "Identifier", "Index", "Is Silent?"
                        ]
        table_rows = []
        for player_obj in modbot.gamestate.current_players:
            if interaction.guild_id != config.hosting_discord_guild_id and player_obj.alignment != c.MAFIA:
                continue
            for i, normal_ita in enumerate(player_obj.ita_items):
                if interaction.guild_id == config.hosting_discord_guild_id:
                    table_rows.append([player_obj.username, normal_ita.identifier, i + 1, normal_ita.damage, normal_ita.can_crit, False])
                else:
                    table_rows.append([player_obj.username, normal_ita.identifier, i + 1, False])
            for i, silent_ita in enumerate(player_obj.silent_ita_items):
                if interaction.guild_id == config.hosting_discord_guild_id:
                    table_rows.append([player_obj.username, silent_ita.identifier, i + 1, silent_ita.damage, silent_ita.can_crit, True])
                else:
                    table_rows.append([player_obj.username, normal_ita.identifier, i + 1, True])
        if interaction.guild_id == config.hosting_discord_guild_id:
            string_to_send = f"Note: -1 damage means the ITA deals the base damage set in the config, which is currently {config.ita_base_damage}. \n"
        else:
            string_to_send = "Note: This view shows the information wolfchat has. Only hosts can get the full view (by running this command in hostcord).\n"
        await interaction.followup.send(string_to_send)
        for table in make_tables(table_headers, table_rows):
            await interaction.followup.send(table)

    @client.tree.command(name="remove_ita", description="Remove an ITA from a player.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The player whose ITA is being removed", 
                           identifier="The name of the ITA to remove",)
    async def remove_ita(interaction: discord.Interaction, player_username: str, identifier: str):
        await interaction.response.defer()
        try:
            player_obj = await verify_player(interaction, player_username)
            if player_obj is None:
                return
            ita_collections = [player_obj.ita_items, player_obj.silent_ita_items]
            for ita_collection in ita_collections:
                i = 0
                while i < len(ita_collection):
                    if ita_collection[i].identifier == identifier:
                        ita_collection.pop(i)
                        await interaction.followup.send(f"Removed ITA with identifier {identifier} from {player_obj.username}.")
                        return
                    i += 1
            await interaction.followup.send(f"Player {player_obj.username} did not have any ITAs with identifier {identifier}.")
        except Exception as e:
            import traceback
            await interaction.followup.send(f"**{type(e).__name__}**: {e}\n```{traceback.format_exc()}```")


    @client.tree.command(name="reorder_itas", description="Reorder a living player's ITAs.")
    @app_commands.describe(player_username="The player whose ITAs are being reordered", 
                           index_1="The index of the first ITA to swap", 
                           index_2="The index of the second ITA to swap", 
                           silent_itas="True if the swap should be done to the normal ITA list, "
                           "and False if it should be done to the silent ITA list.")
    async def reorder_itas(interaction: discord.Interaction, player_username: str, index_1: int, index_2: int, silent_itas: bool):
        # Note: inputs are 1-indexed so we fix that here
        await interaction.response.defer()
        index_1 -= 1
        index_2 -= 1
        player_obj = await verify_player(interaction, player_username, living_only=True)
        if player_obj is None:
            return
        if interaction.guild_id != config.hosting_discord_guild_id and player_obj.alignment != c.MAFIA:
            await interaction.followup.send("You cannot modify the ITAs of someone who's not in wolfchat.")
            return
        collection_to_modify = player_obj.silent_ita_items if silent_itas else player_obj.ita_items
        if index_1 < 0 or index_1 >= len(collection_to_modify):
            await interaction.followup.send(f"Index {index_1 + 1} is out of range.")
            return
        if index_2 < 0 or index_2 >= len(collection_to_modify):
            await interaction.followup.send(f"Index {index_2 + 1} is out of range.")
            return
        if index_1 == index_2:
            await interaction.followup.send("index_1 and index_2 are the same, meaning there would be no change.")
            return
        item_at_index_1 = collection_to_modify[index_1]
        collection_to_modify[index_1] = collection_to_modify[index_2]
        collection_to_modify[index_2] = item_at_index_1
        await interaction.followup.send(f"Successfully modified ITA order for {player_obj.username}.")

    @client.tree.command(name="add_player", description="Add a player to the game.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The username of the player to add.",
                           health="The health of this player.",
                           max_health="The max health of this player.",
                           rolecard_path="The file path of the rolecard for this player.",
                           is_town="True if player is Town.",
                           )
    async def add_player(interaction: discord.Interaction, player_username: str,
                         health: int, max_health: int, rolecard_path: str,
                         is_town: bool):
        await interaction.response.defer()
        try: 
            if modbot.gamestate is None:
                await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
                return
            
            if modbot.gamestate.player_exists(player_username, count_dead_as_existing=True):
                await interaction.followup.send(f"{player_username} is already in the game, so they cannot be added.")
                return
            
            if player_username.lower() == config.username.lower():
                await interaction.followup.send("You cannot put the bot into the game.")
                return
            
            if player_username.lower() in config.host_usernames:
                await interaction.followup.send("Cannot put hosts in the game.")
                return
            
            if max_health <= 0:
                await interaction.followup.send("You cannot make players with nonpositive max health.")
                return

            if health <= 0:
                await interaction.followup.send("You cannot make players with nonpositive health.")
                return

            if config.setup_object is None:
                await interaction.followup.send("The setup object in the config is None, which should not happen except possibly at startup.")
                return
            
            if not config.setup_object.check_if_flip_path_is_valid(rolecard_path):
                await interaction.followup.send("This is not a valid rolecard path.")
                return
            
            import fol_interface
            if not fol_interface.user_exists(player_username):
                await interaction.followup.send("This user does not appear to exist on FoL. (Though, rarely, this check can fail to detect a user that does exist.)")
                return
            player_username, _ = await fol_interface.correct_capilatization_in_discourse_username(player_username)

            import player
            import abilities_standard
            new_player_object = player.Player(username=player_username, 
                            alignment=c.TOWN if is_town else c.MAFIA,
                            rolecard_path=rolecard_path,
                            abilities=[abilities_standard.ITA_ABILITY(), abilities_standard.SILENT_ITA_ABILITY(),
                                    abilities_standard.VIEW_ITAS_ABILITY(), abilities_standard.REORDER_ITAS_ABILITY(),
                                    abilities_standard.REORDER_ITAS_ABILITY_SILENT()],
                            max_health=max_health
                        )
            new_player_object.health = health
            modbot.gamestate.add_player(new_player_object)

            flip_text = config.setup_object.get_flip_text_from_path(rolecard_path)
            if flip_text is None:
                flip_text = 'Failed to find flip. This shouldnt really matter much though.'

            await fol_interface.process_substitution(current_username='', 
                                                    new_username=player_username, 
                                                    role_pm=flip_text, 
                                                    player_is_mafia=not is_town, 
                                                    teammates=None) # TODO: make it specify teammates!
            await interaction.followup.send(f"Added player with username {player_username}. They have {max_health=}, {health=}, "
                                        + f"and alignment {new_player_object.alignment.string_rep()}. \n"
                                        + "### Be sure to add ITAs to this player if needed! This player has with no ITA shots right now. \n"
                                        + "### If the account you added should be able to vote or be voted, then also be sure to correct the votecount in thread.")

        except Exception as e:
            import traceback
            await interaction.followup.send(f"**{type(e).__name__}**: {e}\n```{traceback.format_exc()}```")
        
        
    
    @client.tree.command(name="kill_player", description="Kill a player (without any announcement and without informing the player they died).", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(player_username="The username of the player to kill.",
                           )
    async def kill_player(interaction: discord.Interaction, player_username: str):
        await interaction.response.defer()
        try: 
            if modbot.gamestate is None:
                await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
                return
            
            if not modbot.gamestate.player_exists(player_username, count_dead_as_existing=False):
                await interaction.followup.send(f"{player_username} is not in the game (or is dead already), so they cannot be killed.\n"
                                                        "To prevent accidental kills, this command requires you type the exact name of the player to use this command.")
                return
            
            player_obj = modbot.gamestate.get_player_object_living_players_only(player_username)
            assert player_obj is not None
            player_obj.health = 0
            modbot.gamestate.sync_living_players()
                    
            await interaction.followup.send(f"Killed player with username {player_username}. \n"
                                                + "### Remember to correct the votecount yourself! This command does not correct it because it is primarily designed to be used at SOD for many deaths.")
        except Exception as e:
            import traceback
            await interaction.followup.send(f"**{type(e).__name__}**: {e}\n```{traceback.format_exc()}```")

    @client.tree.command(name="use_silent_ita", description="Proxy a silent ITA with this command.")
    @app_commands.describe(player_holding_ita="The username of the player with the Silent ITA.",
                           target_player="The username of the player to shoot at.")
    async def use_silent_ita(interaction: discord.Interaction, player_holding_ita: str, target_player: str):
        try:
            await interaction.response.defer()

            if modbot.gamestate is None:
                await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
                return
            attacker_obj = await verify_player(interaction, player_holding_ita, living_only=True)
            if attacker_obj is None:
                return
            target_obj = await verify_player(interaction, target_player, living_only=True)
            if target_obj is None:
                return
            if modbot.all_abilities_are_disabled:
                await interaction.followup.send("All abilities have been disabled, so you cannot do this right now. If the hosts haven't made an announcement about this, then this is a bug and you should ping Zugzwang.")
                return
            if attacker_obj.alignment != c.MAFIA:
                await interaction.followup.send(f"Player {attacker_obj.username} is not in wolfchat, so you cannot attempt to use their Silent ITAs. \n-# why did you try this... :angry:")
                return
            if len(attacker_obj.silent_ita_items) == 0:
                await interaction.followup.send(f"Player {attacker_obj.username} has no Silent ITAs.")
                return
            silent_ita_abil = None
            for ability_obj in attacker_obj.abilities:
                if c.ITA in ability_obj.action_types and ability_obj.submission_location == c.IN_PM:
                    silent_ita_abil = ability_obj
                    break
            
            if silent_ita_abil is None:
                await interaction.followup.send("silent_ita_abil is None. This shouldn't ever happen. Ping Zugzwang or other hosts to fix :(")
                return
            if interaction.created_at.tzinfo == None or interaction.created_at.tzinfo.utcoffset(interaction.created_at) == None:
                await interaction.followup.send("Discord created_at datetime is naive instead of aware! This shouldn't ever happen. If this just happened it probably means the Python discord module is out of date and you should ping Zugzwang.")
                return
            import post
            in_ita_window = modbot.determine_if_post_within_action_deadline(post_datetime_timestamp=interaction.created_at,
                                                            require_action_deadline=False, require_ita_window=True)
            fake_post = post.Post(poster=attacker_obj.username,
                                  timestamp=interaction.created_at.strftime('%Y-%m-%d %H:%M:%S %Z'),
                                  postNumber=50, # no special meaning to this number
                                  content=f"/ita {target_obj.username}",
                                  topicNumber='9145') # number chosen to be a private thread that only Zugzwang can see; it shouldn't matter though.
            result_of_use = await silent_ita_abil.attempt_to_use_ability(fake_post, player=attacker_obj, 
                                                    gamestate=modbot.gamestate,
                                                    action_submission_open=True,
                                                    ita_submission_open=in_ita_window,
                                                    is_host_post=False,
                                                    fake_post_used=True)
            if result_of_use:
                await interaction.followup.send(f"Successfully had {attacker_obj.username} fire a Silent ITA at {target_obj.username}.")
            else:
                await interaction.followup.send("Something went wrong when trying to use the Silent ITA (such as not being in an ITA window right now). "
                                                "If there is nothing that should prevent you from using a Silent ITA right now, ping the hosts who can manually deal with it.")
                
        except Exception as e:
            import traceback
            await interaction.followup.send(f"**{type(e).__name__}**: {e}\n```{traceback.format_exc()}```")




    @client.tree.command(name="suggestions", description="For the spookycat27 role's Suggestions ability.")
    @app_commands.describe(player_username="The username of the player to post about.")
    async def suggestions(interaction: discord.Interaction, player_username: str):
        global suggestions_day_of_last_use
        await interaction.response.defer()
        player_obj = await verify_player(interaction, player_username, living_only=True)
        if player_obj is None:
            return
        if modbot.gamestate is None:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        if not modbot.gamestate.is_day:
            await interaction.followup.send("This ability can only be used during the day.")
            return
        if suggestions_day_of_last_use > modbot.gamestate.phase_count:
            await interaction.followup.send("Somehow, the last day this ability was used on is greater than the current day. Ping Zug about this; it shouldn't ever happen.")
            return
        if suggestions_day_of_last_use == modbot.gamestate.phase_count:
            await interaction.followup.send("You have already used this command today!")
            return
        import fam6
        if (fam6.spooky_player is None) or (not modbot.gamestate.player_exists(fam6.spooky_player.username)):
            await interaction.followup.send("The player with the spookycat27 role is not alive (if this is false ping Zug for him to run the command to fix it).")
            return
        import fol_interface
        fol_interface.create_post(f"A little birdie told me you should vote {player_obj.username} :)")
        await interaction.followup.send("Post complete.")
        suggestions_day_of_last_use = modbot.gamestate.phase_count

    @client.tree.command(name="sow_doubt", description="For the spookycat27 role's Sow Doubt ability.")
    @app_commands.describe(player_1="The username of player_1.", player_2="The username of player_2", player_3="The username of player_3")
    async def sow_doubt(interaction: discord.Interaction, player_1: str, player_2: str, player_3: str):
        global sow_doubt_used
        await interaction.response.defer()
        player_1_obj = await verify_player(interaction, player_1, living_only=True)
        if player_1_obj is None:
            return
        player_2_obj = await verify_player(interaction, player_2, living_only=True)
        if player_2_obj is None:
            return
        player_3_obj = await verify_player(interaction, player_3, living_only=True)
        if player_3_obj is None:
            return
        if sow_doubt_used:
            await interaction.followup.send("This ability has already been used!")
            return
        if modbot.gamestate is None:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        if modbot.gamestate.is_day:
            await interaction.followup.send("This ability can only be used during the night.")
            return
        import fam6
        if (fam6.spooky_player is None) or (not modbot.gamestate.player_exists(fam6.spooky_player.username)):
            await interaction.followup.send("The player with the spookycat27 role is not alive (if this is false ping Zug for him to run the command to fix it).")
            return
        import fol_interface
        fol_interface.create_post(f"ok ok ok ok ok ok what if if if if if {player_1_obj.username} is pulling a "
                                  "spooooooooooooooooky spooooooooooooooookster play and is actually "
                                  f"scum!!!!!!!!!!! setting up {player_2_obj.username} ML followed by "
                                  f"{player_3_obj.username}!!!!!!!!!!!!!!! so real and true!!!!!!!!!!!\n"
                                  "real and true!!!!!!!!!!!!!!!!!!!\n"
                                  "the tinfoil part of me cannot completely dismiss this")
        await interaction.followup.send("Post complete.")
        sow_doubt_used = True
    
    @client.tree.command(name="spooky", description="For the Spooky role.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(spooky="The player with the Spooky role (or the Spooky role's ability).")
    async def spooky(interaction: discord.Interaction, spooky: str):
        await interaction.response.defer()
        spooky_obj = await verify_player(interaction, spooky)
        if spooky_obj is None:
            return
        import fam6
        fam6.set_spooky_player(spooky_obj)
        await interaction.followup.send(f"Set Spooky to {spooky_obj.username}.")

    @client.tree.command(name="votecount", description="For hosts to summon votecounts.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe()
    async def votecount(interaction: discord.Interaction):
        await interaction.response.defer()
        if modbot.gamestate is None:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
            return
        if not modbot.gamestate.is_day:
            await interaction.followup.send("You can only call votecounts during the day.")
            return
        if not modbot.game_started:
            await interaction.followup.send("The game hasn't started yet! You can't call a votecount now.")
            return
        if not modbot.continue_posting_vcs:
            await interaction.followup.send("modbot.continue_posting_vcs is False. This means the game is probably over.")
            return
        import fol_interface
        await fol_interface.post_votecount(nominated_players=modbot.gamestate.get_all_nominated_players(), nominator_to_nominee_dict=modbot.gamestate.get_nominations())
        await interaction.followup.send("Put your votecount into the thread!")

    @client.tree.command(name="votecount_parameters", description="For hosts to modify the auto-VC rate.", guild=discord.Object(id=config.hosting_discord_guild_id))
    @app_commands.describe(minutes="The number of minutes to wait between votecounts.", posts="The number of posts to wait between votecounts.")
    async def votecount_parameters(interaction: discord.Interaction, minutes: int, posts: int):
        await interaction.response.defer()
        if minutes < 1:
            await interaction.followup.send("You must choose a positive integer for minutes!")
            return
        if minutes > 60:
            await interaction.followup.send("You cannot do a delay of more than 60 minutes!")
            return
        if posts < 10:
            await interaction.followup.send("You must choose an integer that is at least 10 for posts!")
            return
        config.votecount_post_interval = posts
        config.votecount_time_interval = minutes
        await interaction.followup.send(f"Set minutes to {minutes} and posts to {posts}.")

    async def verify_player(interaction: discord.Interaction, player_username: str, living_only=False) -> 'player.Player | None':
        if modbot.gamestate is None:
            await interaction.followup.send(GAMESTATE_NONE_ERROR_MESSAGE)
            return None
        resolved_name = modbot.resolve_name(player_username, living_players_only=living_only)
        if living_only:
            player = modbot.gamestate.get_player_object_living_players_only(resolved_name)
        else:
            player = modbot.gamestate.get_player_object_original_players(resolved_name)
        if player is None:
            await interaction.followup.send(f"There is no{' living ' if living_only else ' '}player with the username {player_username}. Action unsuccessful.")
            return None
        return player

    def condense_messages(messages: list[str]) -> list[str]:
        """
        This takes a list of messages to send, and joins them into messages that are less than 2000 characters.

        If a single input message is 2000 characters or more, it is truncated to 1999 characters.
        """
        result_list = []
        newest_result_string = ''
        for message in messages:
            if len(newest_result_string) + len(message) + 1 < 2000:
                newest_result_string += "\n" + message
            elif len(message) < 2000:
                result_list.append(newest_result_string)
                newest_result_string = message
            else:
                result_list.append(newest_result_string)
                result_list.append(message[0:1999])
                newest_result_string = ''
        if newest_result_string:
            result_list.append(newest_result_string)
        return result_list

    async def hosting_discord_pipeline():
        global queue_of_posts_for_hosting_discord
        while config.send_messages_to_hosting_discord:
            messages_to_send = []
            while not queue_of_posts_for_hosting_discord.empty():
                messages_to_send.append(queue_of_posts_for_hosting_discord.get())
            if len(messages_to_send) != 0:
                channel_to_send_to = await client.fetch_channel(config.hosting_discord_channel_id_for_output)
                for message_to_send in condense_messages(messages_to_send):
                    await channel_to_send_to.send(message_to_send) # type: ignore
                    await asyncio.sleep(config.delay_between_discord_host_logs)
            else:
                await asyncio.sleep(config.delay_between_discord_host_logs)

    async def send_message_to_hosting_discord(message_to_send: str):
        if config.send_messages_to_hosting_discord:
            queue_of_posts_for_hosting_discord.put(message_to_send)


    async def start_discord_bot():
        global client_started
        if not client_started:
            print("Starting discord client!")
            await client.start(token=token)
            client_started = True
