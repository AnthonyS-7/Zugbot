import re
import post as p
import player
from roles_folder.roles_exceptions import ParsingException, ActionException
import game_state
import fol_interface
import constants as c
from typing import Callable

def no_self_target(player_object: 'player.Player', target: 'player.Player'):
    return player_object != target

def loyal_for_mafia(player_object: 'player.Player', target: 'player.Player'):
    """DO NOT PUT THIS ON A TOWN-ALIGNED PLAYER."""
    return player_object.alignment == c.TOWN or target.alignment == c.MAFIA

def disloyal_for_mafia(player_object: 'player.Player', target: 'player.Player'):
    """DO NOT PUT THIS ON A TOWN-ALIGNED PLAYER."""
    return not loyal_for_mafia(player_object, target)


NO_SELF_TARGET = no_self_target
LOYAL_FOR_MAFIA = loyal_for_mafia
DISLOYAL_FOR_MAFIA = disloyal_for_mafia

PLAYER_PARAMETER = 0
ARBITRARY_STRING_PARAMETER = 1

# SINGLE_TARGET_PARAMETER_LIST = 0
# SINGLE_ARBITRARY_STRING_PARAMETER_LIST = 1 # usually for modposters/messengers etc.


def acknowledge_and_verify_constructor(restrictions: list, parameter_list: list[int], do_acknowledgement=True) -> Callable:
    """
    This constructs acknowledge_and_verify functions.

    restrictions - The restrictions placed on the user's action (like NO_SELF_TARGET, LOYAL_FOR_MAFIA, etc).
    parameter_list - The format that the action's parameters are in. For example, SINGLE_TARGET_PARAMETER_LIST means
        that the parameter list output by the syntax parser is [action's target].

    """
    return lambda player_object, ability, gamestate, *parameters : _acknowledge_and_verify_helper(restrictions, parameter_list, do_acknowledgement, player_object, ability, gamestate,
                                                                          *parameters)


def _acknowledge_and_verify_helper(restrictions: list, parameter_list: list[int], do_acknowledgement: bool,
        player_object: "player.Player", ability: "player.Ability", gamestate: "game_state.GameState",
                        *parameters):
    """
    Only for use in acknowledge_and_verify_constructor.

    Note: Unfortunately, each possible restriction may need it's own set of parameters, and each parameter_list needs to have
    code here to parse it (rather than the code being the constant, which would be ideal).

    Note 2: Restrictions return True if they are satisfied, and False otherwise.
    """
    targets = []
    for i in range(len(parameter_list)):
        if parameter_list[i] == PLAYER_PARAMETER:
            targets.append(parameters[i])
    
    for target in targets:
        if NO_SELF_TARGET in restrictions and not NO_SELF_TARGET(player_object, target):
            fol_interface.send_message(message="You cannot self-target with this ability.",
                                        username=player_object.username, priority=1)
            raise ActionException("You cannot self-target with this ability.")
        if LOYAL_FOR_MAFIA in restrictions and not LOYAL_FOR_MAFIA(player_object, target):
            fol_interface.send_message(message="You must target a mafia member.",
                                        username=player_object.username, priority=1)
            raise ActionException("You must target a mafia member.")

        if DISLOYAL_FOR_MAFIA in restrictions and not DISLOYAL_FOR_MAFIA(player_object, target):
            fol_interface.send_message(message="You must not target a mafia member.",
                                           username=player_object.username, priority=1)
            raise ActionException("You must not target a mafia member.")
    
    if do_acknowledgement:
        fol_interface.send_message(message="Your action has been recorded.", username=player_object.username, priority=1)    

