import re
import post as p
import player
from roles_folder.roles_exceptions import ParsingException, ActionException
import game_state
from typing import Callable

DAY = lambda player_object, ability, gamestate : gamestate.is_day
NIGHT = lambda player_object, ability, gamestate : not DAY(player_object, ability, gamestate)
EVEN_CYCLE = lambda player_object, ability, gamestate: gamestate.phase_count % 2 == 0
ODD_CYCLE = lambda player_object, ability, gamestate : not EVEN_CYCLE(player_object, ability, gamestate)


def can_use_now_constructor(instant_shot_count: int, phase_end_shot_count: int,
                            normal_modifiers: list[Callable[["player.Player", "player.Ability", "game_state.GameState"], bool]]):
    """
    This constructs can_use_now functions.

    instant_shot_count - The max number of times the instant action can be used; -1 if unlimited
    phase_end_shot_count - The max number of times the phase end action can be used; -1 if unlimited
    normal_modifiers - Standard modifiers that can be added (such as DAY, NIGHT, EVEN_CYCLE, etc)
    gamestate - The gamestate.

    """
    return lambda player_object, ability, gamestate : _can_use_now_helper(player_object, ability, gamestate,
                                                                          instant_shot_count, phase_end_shot_count,
                                                                          normal_modifiers)


def _can_use_now_helper(player_object: "player.Player", ability: "player.Ability", gamestate: "game_state.GameState", 
                        instant_shot_count: int, 
                        phase_end_shot_count: int, 
                        normal_modifiers: list[Callable[["player.Player", "player.Ability", "game_state.GameState"], bool]]):
    """
    Only for use in can_use_now_constructor.
    """
    can_use = (instant_shot_count == -1 or ability.instant_use_count < instant_shot_count)
    can_use &= (phase_end_shot_count == -1 or ability.phase_end_use_count < phase_end_shot_count)
    
    for modifier in normal_modifiers:
        can_use &= modifier(player_object, ability, gamestate)

    return can_use

