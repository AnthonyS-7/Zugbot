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


def make_suicide_bomber(username: str, alignment: int) -> player.Player:
    result = player.Player(username, alignment, "town_suicide_bomber.txt" if alignment == player.TOWN else "mafia_suicide_bomber.txt", abilities=[
        player.Ability(
            syntax_parser=rt.construct_syntax_parser("bomb"),
            submission_location=player.IN_PM,
            can_use_now=lambda playername, gamestate : gamestate.is_day,
            use_action_instant=daykill_player,
            use_action_phase_end=empty_function,
            ability_priority=0
        )
    ])
    return result

def make_town_suicide_bomber(username: str) -> player.Player:
    return make_suicide_bomber(username, player.TOWN)

def make_mafia_suicide_bomber(username: str) -> player.Player:
    return make_suicide_bomber(username, player.MAFIA)

def daykill_player(player_doing_kill: str, gamestate: game_state.GameState, target_username: str):
    """
    This immediately kills both the player in player_doing_kill and the player in target_username.

    This ability can only be used once.
    """
    if player_doing_kill.lower() == target_username.lower():
        raise r.ActionException(f"You cannot self-target with a suicide bomb.")
    if not gamestate.is_valid_kill(target_username):
        raise r.ActionException(f"{target_username} is not a valid bomb target.")
    
    player_doing_kill_object = gamestate.get_player_object_living_players_only(player_doing_kill)
    target_object = gamestate.get_player_object_living_players_only(player_doing_kill)
    if player_doing_kill_object is None or target_object is None:
        raise r.ActionException("One or both of the target player or player doing the kill was None, somehow.")

    if player_doing_kill_object.used_bomb_already == 1:
        raise r.ActionException("This player has already used their suicide bomb ability.")
    
    player_doing_kill_object.used_bomb_already = 1 # type: ignore

    player_doing_kill_object.take_damage(1)
    target_object.take_damage(1)

    fol_interface.to_post_cache += "# A bomb explodes! \n"

    modbot.resolve_current_deaths(gamestate)