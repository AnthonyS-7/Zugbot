import player
import game_state
import fol_interface
import post as p
import modbot

import re
import roles_folder.roles_exceptions as r
import roles_folder.cop as cop
import roles_folder.dayvig as dayvig
import roles_folder.roles_templates as rt

# def joat_cop_acknowledge(username: str, gamestate: game_state.GameState, target_username: str):
#     if not gamestate.player_exists(target_username):
#         raise r.ActionException("This player does not exist.")
#     if username.lower() == target_username.lower():
#         raise r.ActionException("You cannot self-target with this ability.")
#     if gamestate.get_player_object(username).joat_cop_shot_used == 1: # type: ignore
#         raise r.ActionException("This action has been used already.")
#     if not fol_interface.send_message("Your action has been recorded.\n", username):
#         raise r.ActionException
    
# def joat_vig_acknowledge(username: str, gamestate: game_state.GameState, target_username: str):
#     if not gamestate.player_exists(target_username):
#         raise r.ActionException("This player does not exist.")
#     if username.lower() == target_username.lower():
#         raise r.ActionException("You cannot self-target with this ability.")
#     if gamestate.get_player_object(username).joat_vig_shot_used == 1: # type: ignore
#         raise r.ActionException("This action has been used already.")
#     if not fol_interface.send_message("Your action has been recorded.\n", username):
#         raise r.ActionException

# def joat_doc_acknowledge(username: str, gamestate: game_state.GameState, target_username: str):
#     if not gamestate.player_exists(target_username):
#         raise r.ActionException("This player does not exist.")
#     if username.lower() == target_username.lower():
#         raise r.ActionException("You cannot self-target with this ability.")
#     if gamestate.get_player_object(username).joat_doc_shot_used == 1: # type: ignore
#         raise r.ActionException("This action has been used already.")
#     if not fol_interface.send_message("Your action has been recorded.\n", username):
#         raise r.ActionException
    
def joat_get_cop_result(player_doing_action: str, gamestate: game_state.GameState, target_player: str):
    joat_player = gamestate.get_player_object_living_players_only(player_doing_action)
    assert joat_player is not None
    joat_player.joat_cop_shots_used += 1 # type: ignore
    cop.get_cop_result(player_doing_action, gamestate, target_player)
    
def joat_vig_player(player_doing_action: str, gamestate: game_state.GameState, target_player: str):    
    target_player_object = gamestate.get_player_object_living_players_only(target_player)
    assert target_player_object is not None
    joat_player = gamestate.get_player_object_living_players_only(player_doing_action)
    assert joat_player is not None
    joat_player.joat_vig_shots_used += 1 # type: ignore
    target_player_object.take_damage(1)

def joat_doc_player(player_doing_action: str, gamestate: game_state.GameState, target_player: str):    
    target_player_object = gamestate.get_player_object_living_players_only(target_player)
    assert target_player_object is not None
    joat_player = gamestate.get_player_object_living_players_only(player_doing_action)
    assert joat_player is not None
    joat_player.joat_doc_shots_used += 1 # type: ignore
    target_player_object.receive_protection(1)


# def doc_syntax_parser(post: p.Post):
#     """
#     The doctor syntax is /protect [playername].
#     """
#     moveMatcher = re.compile(r"/protect ([^ \\][^ \\]*)", re.IGNORECASE)
#     target = moveMatcher.search(post.content)
#     if target is None:
#         raise r.ParsingException("This post had no vig shot.")
#     targetName = target.group(1)
#     targetName = modbot.resolve_name(targetName)
#     return [targetName]


def make_town_joat_1(username: str) -> player.Player:
    result = player.Player(username, player.TOWN, "town_joat_1.txt", abilities=[
        player.Ability(
            syntax_parser=rt.construct_syntax_parser("investigate"),
            submission_location=player.IN_PM,
            can_use_now=lambda playername, gamestate : not gamestate.is_day,
            use_action_instant=rt.construct_acknowledger(allow_self_target=False, shot_counter_name="joat_cop_shots_used", shot_count=1),
            use_action_phase_end=joat_get_cop_result,
            ability_priority=-10
        ),
        player.Ability(
            syntax_parser=rt.construct_syntax_parser("shoot"),
            submission_location=player.IN_PM,
            can_use_now=lambda playername, gamestate : not gamestate.is_day,
            use_action_instant=rt.construct_acknowledger(allow_self_target=False, shot_counter_name="joat_vig_shots_used", shot_count=1),
            use_action_phase_end=joat_vig_player,
            ability_priority=-10

        ),
        player.Ability(
            syntax_parser=rt.construct_syntax_parser("protect"),
            submission_location=player.IN_PM,
            can_use_now=lambda playername, gamestate : not gamestate.is_day,
            use_action_instant=rt.construct_acknowledger(allow_self_target=False, shot_counter_name="joat_doc_shots_used", shot_count=1),
            use_action_phase_end=joat_doc_player,
            ability_priority=-100
        )
    ])
    return result
