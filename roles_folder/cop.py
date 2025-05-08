import player
import game_state
import fol_interface
import post as p
import modbot

import re
import roles_folder.roles_exceptions as r
import roles_folder.roles_templates as rt


# def cop_syntax_parser(post: p.Post):
#     """
#     The cop syntax is /investigate [playername].
#     """
#     moveMatcher = re.compile(r"/investigate ([^ \\][^ \\]*)", re.IGNORECASE)
#     target = moveMatcher.search(post.content)
#     if target is None:
#         raise r.ParsingException("This post had no cop use.")
#     targetName = target.group(1)
#     targetName = modbot.resolve_name(targetName)
#     return [targetName]

# def cop_acknowledge(username: str, gamestate: game_state.GameState, target_username: str):
#     if not gamestate.player_exists(target_username):
#         raise r.ActionException
#     if not fol_interface.send_message("Your action has been recorded.\n", username):
#         raise r.ActionException
    
def get_cop_result(player_doing_action: str, gamestate: game_state.GameState, target_player: str):
    target_player_object = gamestate.get_player_object_living_players_only(target_player)
    assert target_player_object is not None
    alignment = target_player_object.get_alignment()
    if not fol_interface.send_message(f"Your result: {'TOWN' if alignment == player.TOWN else 'MAFIA'}", player_doing_action, priority=1):
        raise r.ActionException

def make_cop(username: str, alignment: int) -> player.Player:
    result = player.Player(username, alignment, "town_cop.txt" if alignment == player.TOWN else "mafia_cop.txt", abilities=[
        player.Ability(
            syntax_parser=rt.construct_syntax_parser("investigate"),
            submission_location=player.IN_PM,
            can_use_now=lambda playername, gamestate : not gamestate.is_day,
            use_action_instant=rt.construct_acknowledger(allow_self_target=False,
                                                         shot_counter_name="cop_shots_used",
                                                         shot_count=-1),
            use_action_phase_end=get_cop_result,
            ability_priority=-10

        )
    ])
    return result

def make_town_cop(username: str):
    return make_cop(username, player.TOWN)

def make_mafia_cop(username: str):
    return make_cop(username, player.MAFIA)