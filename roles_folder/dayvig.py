import player
import game_state
import fol_interface
import post as p
import modbot

import re
import roles_folder.roles_exceptions as r
import roles_folder.roles_templates as rt


def empty_function(*args):
    """
    Takes any number of arguments, and does nothing.
    """
    pass


def make_day_vig(username: str, alignment: int) -> player.Player:
    result = player.Player(username, alignment, "town_day_vig.txt" if alignment == player.TOWN else "mafia_day_vig.txt", abilities=[
        player.Ability(
            syntax_parser=rt.construct_syntax_parser("shoot"),
            submission_location=player.IN_PM,
            can_use_now=lambda playername, gamestate : gamestate.is_day,
            use_action_instant=daykill_player,
            use_action_phase_end=empty_function,
            ability_priority=0
        )
    ])
    return result

def make_town_day_vig(username: str) -> player.Player:
    return make_day_vig(username, player.TOWN)

def make_mafia_day_vig(username: str) -> player.Player:
    return make_day_vig(username, player.MAFIA)

def daykill_player(player_doing_kill: str, gamestate: game_state.GameState, target_username: str):
    """
    This immediately kills the player specified in target_username.

    This ability can only be used once per cycle per player.
    """
    if player_doing_kill.lower() == target_username.lower():
        raise r.ActionException(f"You cannot self-target with a daykill.")
    if not gamestate.is_valid_kill(target_username):
        raise r.ActionException(f"{target_username} is not a valid daykill target.")
    
    player_doing_kill_object = gamestate.get_player_object_living_players_only(player_doing_kill)
    assert player_doing_kill_object is not None

    if player_doing_kill_object.last_phase_dayvig_was_used == gamestate.phase_count:
        raise r.ActionException("This player has already used their dayvig ability today.")
    
    player_doing_kill_object.last_phase_dayvig_was_used = gamestate.phase_count # type: ignore


    target_player_object = gamestate.get_player_object_living_players_only(target_username)
    assert target_player_object is not None
    target_player_object.take_damage(1)

    fol_interface.to_post_cache += "# A shot rings out! \n"

    modbot.resolve_current_deaths(gamestate)

# def vig_syntax_parser(post: p.Post):
#     """
#     The dayvig syntax is /shoot [playername].
#     """
#     moveMatcher = re.compile(r"/shoot ([^ \\][^ \\]*)", re.IGNORECASE)
#     target = moveMatcher.search(post.content)
#     if target is None:
#         raise r.ParsingException("This post had no vig shot.")
#     targetName = target.group(1)
#     targetName = modbot.resolve_name(targetName)
#     return [targetName]