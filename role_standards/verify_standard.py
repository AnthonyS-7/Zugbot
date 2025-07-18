import re
import post as p
import player
from roles_folder.roles_exceptions import ParsingException, ActionException
import game_state
import fol_interface
import constants as c
from typing import Callable
from role_standards import syntax_parser_standard as syn


def _and(verifier_1: 'Verifier', verifier_2: 'Verifier', *args) -> tuple[bool, str]:
    """
    Given two Verifiers and *args that could be passed to verifier functions, returns '' if both Verifiers are passed,
    and an error if one or both fail.
    """
    result_1, requirement_1 = verifier_1.verifier_function(*args)
    result_2, requirement_2 = verifier_2.verifier_function(*args)
    return (result_1 and result_2, f"({requirement_1} AND {requirement_2})")

def _or(verifier_1: 'Verifier', verifier_2: 'Verifier', *args) -> tuple[bool, str]:
    """
    Given two Verifiers and *args that could be passed to verifier functions, returns '' if at least one Verifier is passed,
    and an error if both fail.
    """
    result_1, requirement_1 = verifier_1.verifier_function(*args)
    result_2, requirement_2 = verifier_2.verifier_function(*args)
    return (result_1 or result_2, f"({requirement_1} OR {requirement_2})")

def _not(verifier_1: 'Verifier', *args) -> tuple[bool, str]:
    result, requirement = verifier_1.verifier_function(*args)
    return (not result, f"(NOT {requirement})")

def _xor(verifier_1: 'Verifier', verifier_2: 'Verifier', *args) -> tuple[bool, str]:
    result_1, requirement_1 = verifier_1.verifier_function(*args)
    result_2, requirement_2 = verifier_2.verifier_function(*args)
    return (result_1 ^ result_2, f"({requirement_1} XOR {requirement_2})")


class Verifier:
    """
    This class verifies if actions can be used now and if their parameters are valid.
    """
    def __init__(self, verifier_function: Callable[[player.Player, player.Ability, game_state.GameState, list, list], tuple[bool, str]]) -> None:
        """
        The verifier function takes the player using the action, the Ability being used, the gamestate, the list of parameters looked for by the SyntaxParser, 
        and the list of parameters that the SyntaxParser outputs. 
        
        It returns (True, required_condition) if the action can be used now with the specified parameters, and
        (False, required_condition) otherwise.
        """
        self.verifier_function = verifier_function
    
    def __and__(self, other: 'Verifier'):
        new_verifier_function = lambda *args : _and(self, other, *args)
        return Verifier(new_verifier_function)
    
    def __xor__(self, other: 'Verifier'):
        new_verifier_function = lambda *args : _xor(self, other, *args)
        return Verifier(new_verifier_function)
    
    def __or__(self, other: 'Verifier'):
        new_verifier_function = lambda *args : _or(self, other, *args)
        return Verifier(new_verifier_function)
    
    def not_(self):
        return Verifier(lambda *args : _not(self, *args))
    
    def verify(self, player_using_action: player.Player, ability_being_used: player.Ability, gamestate: game_state.GameState,
               formal_parameters_of_action: list, actual_parameters_of_action: list):
        return self.verifier_function(player_using_action, ability_being_used, gamestate,
                                      formal_parameters_of_action, actual_parameters_of_action)
    
def _no_self_target_verifying_function(player_object: 'player.Player', ability_object: 'player.Ability',
                   gamestate: game_state.GameState, formal_parameters: list, actual_parameters: list) -> tuple[bool, str]:
    requirement = "You cannot self target with this ability."
    for i in range(len(actual_parameters)):
        if formal_parameters[i] == syn.SYNTAX_PARSER_PLAYERNAME and actual_parameters[i] == player_object:
            return (False, requirement)
    return (True, requirement)
def _night_only(player_object: 'player.Player', ability_object: 'player.Ability',
                   gamestate: game_state.GameState, formal_parameters: list, actual_parameters: list) -> tuple[bool, str]:
    requirement = "It must be night to do this."
    return (not gamestate.is_day, requirement)
def _day_only(player_object: 'player.Player', ability_object: 'player.Ability',
                   gamestate: game_state.GameState, formal_parameters: list, actual_parameters: list) -> tuple[bool, str]:
    requirement = "It must be day to do this."
    return (gamestate.is_day, requirement)
def _even_cycle(player_object: 'player.Player', ability_object: 'player.Ability',
                   gamestate: game_state.GameState, formal_parameters: list, actual_parameters: list) -> tuple[bool, str]:
    return (gamestate.phase_count % 2 == 0, 'It must be an even cycle to do this.')
def _odd_cycle(player_object: 'player.Player', ability_object: 'player.Ability',
                   gamestate: game_state.GameState, formal_parameters: list, actual_parameters: list) -> tuple[bool, str]:
    return (gamestate.phase_count % 2 == 1, 'It must be an odd cycle to do this.')
def _disloyal_for_mafia(player_object: 'player.Player', ability_object: 'player.Ability',
                   gamestate: game_state.GameState, formal_parameters: list, actual_parameters: list) -> tuple[bool, str]:
    assert player_object.alignment == c.MAFIA
    requirement = "You cannot target a mafia member with this ability."
    for i in range(len(actual_parameters)):
        if formal_parameters[i] == syn.SYNTAX_PARSER_PLAYERNAME and actual_parameters[i].alignment == c.MAFIA:
            return (False, requirement)
    return (True, requirement)

ALWAYS_TRUE = Verifier(lambda *args : (True, ''))
NO_SELF_TARGET = Verifier(_no_self_target_verifying_function)
DAY = Verifier(_day_only)
NIGHT = Verifier(_night_only)
EVEN_CYCLE = Verifier(_even_cycle)
ODD_CYCLE = Verifier(_odd_cycle)
DISLOYAL_FOR_MAFIA = Verifier(_disloyal_for_mafia)

# def acknowledge_and_verify_constructor(restrictions: list, parameter_list: list[int], do_acknowledgement=True) -> Callable:
#     """
#     This constructs acknowledge_and_verify functions.

#     restrictions - The restrictions placed on the user's action (like NO_SELF_TARGET, LOYAL_FOR_MAFIA, etc).
#     parameter_list - The format that the action's parameters are in. For example, SINGLE_TARGET_PARAMETER_LIST means
#         that the parameter list output by the syntax parser is [action's target].
#     """
#     return lambda player_object, ability, gamestate, *parameters : _acknowledge_and_verify_helper(restrictions, parameter_list, do_acknowledgement, player_object, ability, gamestate,
#                                                                           *parameters)

# def _acknowledge_and_verify_helper(restrictions: list, parameter_list: list[int], do_acknowledgement: bool,
#         player_object: "player.Player", ability: "player.Ability", gamestate: "game_state.GameState",
#                         *parameters):
#     """
#     Only for use in acknowledge_and_verify_constructor.

#     Note: Unfortunately, each possible restriction may need it's own set of parameters, and each parameter_list needs to have
#     code here to parse it (rather than the code being the constant, which would be ideal).

#     Note 2: Restrictions return True if they are satisfied, and False otherwise.
#     """
#     targets = []
#     for i in range(len(parameter_list)):
#         if parameter_list[i] == PLAYER_PARAMETER:
#             targets.append(parameters[i])
    
#     for target in targets:
#         if NO_SELF_TARGET in restrictions and not NO_SELF_TARGET(player_object, target):
#             fol_interface.send_message(message="You cannot self-target with this ability.",
#                                         username=player_object.username, priority=1)
#             raise ActionException("You cannot self-target with this ability.")
#         if LOYAL_FOR_MAFIA in restrictions and not LOYAL_FOR_MAFIA(player_object, target):
#             fol_interface.send_message(message="You must target a mafia member.",
#                                         username=player_object.username, priority=1)
#             raise ActionException("You must target a mafia member.")

#         if DISLOYAL_FOR_MAFIA in restrictions and not DISLOYAL_FOR_MAFIA(player_object, target):
#             fol_interface.send_message(message="You must not target a mafia member.",
#                                            username=player_object.username, priority=1)
#             raise ActionException("You must not target a mafia member.")
    
#     if do_acknowledgement:
#         fol_interface.send_message(message="Your action has been recorded.", username=player_object.username, priority=1)    

