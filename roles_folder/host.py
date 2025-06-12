import player
import game_state
import fol_interface
import post as p
import modbot
import config

import types

import re
import roles_folder.roles_exceptions as r
import roles_folder.roles_templates as rt
import roles_10_7_2024.syntax_parser_standard as syn
import roles_10_7_2024.acknowledge_and_verify_standard as aav
from player import Ability
import player
import constants as c

possible_modkill_name : str = ''

def substitution_syntax_parser(post: p.Post):
    """
    Substitution syntax parser. Unlike normally, both names must be exact (and it is case sensitive).
    """
    moveMatcher = re.compile(fr"/sub ([^ \\][^ \\]*) ([^ \\][^ \\]*)", re.IGNORECASE)
    target = moveMatcher.search(post.content)
    if target is None:
        raise r.ParsingException("This post had no specified command.")
    current_player = target.group(1)
    new_player = target.group(2)
    return [current_player, new_player]

async def do_substitution(host_name_or_player: 'str | player.Player', gamestate: "game_state.GameState", current_player: 'player.Player', new_player: str):    
    role_pm = modbot.get_flip(current_player.username, gamestate)
    current_player_username = current_player.username # needed because current_player.username gets changed later
    new_player, successful_name_resolution = await fol_interface.correct_capilatization_in_discourse_username(new_player)

    if gamestate.player_exists(new_player, count_dead_as_existing=True):
        print(f"{new_player} is already in the game, so they cannot be added.")
        return
    
    if new_player.lower() == config.username.lower():
        print("Attempted to sub the bot into the game! This is not allowed.")
        return
    
    if new_player.lower() in config.host_usernames:
        print("Cannot put hosts in the game.")
        return

    if not successful_name_resolution and not fol_interface.user_exists(new_player):
        # successful name resolution implies the user exists, so this is here to save time.
        print(f"Attempted to add {new_player} to the game, but they are not a valid FoL user. If this is in error, try again.")
        return

    if not gamestate.substitute_player(current_username=current_player_username, new_username=new_player):
        print("Error when substituting player! Things are likely broken in the gamestate object.")

    player_is_mafia = current_player.alignment == c.MAFIA
    await fol_interface.process_substitution(current_username=current_player_username, 
                                             new_username=new_player, 
                                             role_pm=role_pm,
                                             player_is_mafia=player_is_mafia,
                                             teammates=modbot.get_mafia_list(gamestate.original_players) if player_is_mafia else None)
    fol_interface.create_post(string_to_post=f"# @{new_player} has replaced in for @{current_player_username}. \n\n Do not discuss replacements.")
    modbot.process_substitution_for_mafia_and_player_lists_and_nightkill(current_player=current_player_username, new_player=new_player)

    await fol_interface.post_votecount(replacements=[(current_player_username, new_player)], nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominator_to_nominee_dict(),)

    gamestate.print_playerlists()

async def do_modkill(host_name_or_player: 'str | player.Player', gamestate: "game_state.GameState", modkilled_player: 'player.Player'):
    global possible_modkill_name
    if possible_modkill_name.lower() != modkilled_player.username.lower():
        possible_modkill_name = modkilled_player.username
        fol_interface.create_post(string_to_post=f"Are you sure you want to modkill {modkilled_player.username}? Run the command again to confirm.")
        return
    fol_interface.create_post(string_to_post=f"# @{modkilled_player.username} has been modkilled. Compensation may be given. \n\n Do not discuss modkills.")
    gamestate.process_modkill(modkilled_player.username)
    fol_interface.send_message("# You have been modkilled.", modkilled_player.username, priority=1)

    await fol_interface.post_votecount(players_to_kill=[modkilled_player.username], nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominator_to_nominee_dict())

do_substitution_ability = Ability(
    ability_name="Substitute",
    syntax_parser=syn.syntax_parser_constructor(command_name="sub", 
                                                parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME, 
                                                                syn.SYNTAX_PARSER_NO_SPACE_STRING]),
    use_action_instant=do_substitution,
)

do_modkill_ability = Ability(
    ability_name="Modkill",
    syntax_parser=syn.syntax_parser_constructor(command_name="modkill",
                                                parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
    use_action_instant=do_modkill,
)

def reset_nominations(host_account, gamestate: game_state.GameState):
    gamestate.reset_nominations()
    fol_interface.create_post("Nominations have been reset!")

def remove_nomination_power(host_account, gamestate: game_state.GameState, target_player: 'player.Player'):
    target_player.can_nominate = False # type: ignore
    fol_interface.create_post(f"{target_player.username} can no longer nominate.")

def restore_nomination_power(host_account, gamestate: game_state.GameState, target_player: 'player.Player'):
    target_player.can_nominate = True # type: ignore
    fol_interface.create_post(f"{target_player.username} can once again nominate.")

def set_nomination(host_account, gamestate: game_state.GameState, nominating_player: 'player.Player', nominated_player: 'player.Player'):
    nominating_player.target_of_nomination = nominated_player # type: ignore
    nominating_player.nomination_order = gamestate.nomination_counter #type: ignore
    gamestate.nomination_counter += 1
    fol_interface.create_post(f"{nominating_player.username} has nominated {nominated_player.username}.")

def open_nominations(host_account, gamestate: game_state.GameState):
    gamestate.nominations_open = True
    fol_interface.create_post("Nominations are now open.")

def close_nominations(host_account, gamestate: game_state.GameState):
    gamestate.nominations_open = False
    fol_interface.create_post("Nominations are now closed.")

def disable_all_abilities(host_account, gamestate: game_state.GameState):
    modbot.all_abilities_are_disabled = True
    fol_interface.create_post("Abilities have been disabled.")

def reenable_abilities(host_account, gamestate: game_state.GameState):
    modbot.all_abilities_are_disabled = False
    fol_interface.create_post("Abilities have been enabled.")

reset_nominations_ability = Ability( # resets all nominations, but doesn't change who can nominate
    ability_name="Reset Nominations",
    syntax_parser=syn.syntax_parser_constructor(command_name="reset", parameter_list=[]),
    use_action_instant=reset_nominations,
    ignore_action_deadline=True
) 

set_nomination_ability = Ability( # sets one players as having nominated another player
    ability_name="Set Nomination",
    syntax_parser=syn.syntax_parser_constructor("set", [syn.SYNTAX_PARSER_PLAYERNAME, syn.SYNTAX_PARSER_PLAYERNAME]),
    use_action_instant=set_nomination,
    ignore_action_deadline=True
)

remove_nomination_ability = Ability(  # removes one player's ability to nominate
    ability_name="Remove Nomination Power",
    syntax_parser=syn.syntax_parser_constructor(command_name="kill", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
    use_action_instant=remove_nomination_power,
    ignore_action_deadline=True

)

restore_nomination_ability = Ability(  # restores one player's ability to nominate
    ability_name="Restore Nomination Power",
    syntax_parser=syn.syntax_parser_constructor(command_name="revive", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
    use_action_instant=restore_nomination_power,
    ignore_action_deadline=True
)

open_nominations_ability = Ability(  # opens nominations
    ability_name="Open Nominations",
    syntax_parser=syn.syntax_parser_constructor(command_name="open", parameter_list=[]),
    use_action_instant=open_nominations,
    ignore_action_deadline=True
)

close_nominations_ability = Ability(  # closes nominations
    ability_name="Close Nominations",
    syntax_parser=syn.syntax_parser_constructor(command_name="close", parameter_list=[]),
    use_action_instant=close_nominations,
    ignore_action_deadline=True
)

disable_all_abilities_ability = Ability(
    ability_name="Disable All Abilities",
    syntax_parser=syn.syntax_parser_constructor(command_name="disable", parameter_list=[]),
    use_action_instant=disable_all_abilities,
    ignore_action_deadline=True
)

reenable_abilities_ability = Ability(
    ability_name="Reenable Abilities",
    syntax_parser=syn.syntax_parser_constructor(command_name="enable", parameter_list=[]),
    use_action_instant=reenable_abilities,
    ignore_action_deadline=True
)

if not config.is_botf:
    host_abilities = [
        do_substitution_ability,
        do_modkill_ability,
        disable_all_abilities_ability,
        reenable_abilities_ability
    ]
else:
    host_abilities = [do_substitution_ability, do_modkill_ability, disable_all_abilities_ability, reenable_abilities_ability,
                      reset_nominations_ability, set_nomination_ability, remove_nomination_ability, restore_nomination_ability,
                      open_nominations_ability, close_nominations_ability]
if config.do_votecounts:
    host_abilities.append(player.get_votecount_ability())