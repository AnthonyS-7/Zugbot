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
    
def do_doctor_protection(player_doing_action: str, gamestate: game_state.GameState, target_player: str):
    target_player_object = gamestate.get_player_object_living_players_only(target_player)
    if target_player_object is None:
        raise r.ActionException("Somehow, the doctor's target was None.")
    target_player_object.receive_protection(1)

def make_doctor(username: str, alignment: int) -> player.Player:
    result = player.Player(username, alignment, "town_doctor.txt" if alignment == player.TOWN else "mafia_doctor.txt", abilities=[
        player.Ability(
            syntax_parser=rt.construct_syntax_parser("protect"),
            submission_location=player.IN_PM,
            can_use_now=lambda playername, gamestate : not gamestate.is_day,
            use_action_instant=rt.construct_acknowledger(allow_self_target=False,
                                                         shot_counter_name="doc_shots_used",
                                                         shot_count=-1),
            use_action_phase_end=do_doctor_protection,
            ability_priority=-1000

        )
    ])
    return result

def make_town_doctor(username: str):
    return make_doctor(username, player.TOWN)

def make_mafia_doctor(username: str):
    return make_doctor(username, player.MAFIA)