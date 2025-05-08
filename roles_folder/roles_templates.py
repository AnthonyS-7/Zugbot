import player
import game_state
import fol_interface
import post as p
import modbot

import re
from roles_folder.roles_exceptions import ActionException, ParsingException


def construct_syntax_parser(role_command: str):
    """
    Constructs syntax parser function, for a role with the provided parameters.

    Assumed:
    Role targets exactly one player

    Parameters
    - role_command: Defines what word is used after the '/'; for example, if role_command is 'shoot', then the command is /shoot

    TODO: test this
    """
    syntax_parser = lambda post : _syntax_parser_template(post, role_command=role_command)
    return syntax_parser

def construct_acknowledger(allow_self_target: bool, shot_counter_name: str, shot_count: int):
    """
    Constructs acknowledgement function, for a role with the provided parameters.

    Assumed:
    Role targets exactly one player
    Role is a non-instant role, so the only instant part is the acknowledgement

    Parameters
    - allow_self_target: True if self-targeting is allowed with this action
    - shot_counter_name: The attribute that this shot-counter should be stored in
    - x_shot: The number of shots this ability has, or -1 if infinite

    TODO: test this
    """
    acknowledger = lambda username, gamestate, target_username : _acknowledge_template(username, 
                                                                                      gamestate, 
                                                                                      target_username, 
                                                                                      allow_self_target=allow_self_target, 
                                                                                      shot_counter_name=shot_counter_name, 
                                                                                      shot_count=shot_count)
    return acknowledger

def _syntax_parser_template(post: p.Post, role_command: str):
    """
    This is a template for a syntax parser for roles with a single target (which is a lot of roles).

    This is designed similarly to acknowledge_template; the those docs for more information.

    Parameters
    - role_command: The command syntax will be /[role_command]

    TODO: test this
    """
    moveMatcher = re.compile(fr"/{role_command} ([^ \\][^ \\]*)", re.IGNORECASE)
    target = moveMatcher.search(post.content)
    if target is None:
        raise ParsingException("This post had no specified command.")
    targetName = target.group(1)
    targetName = modbot.resolve_name(targetName)
    return [targetName]


def _acknowledge_template(username: str, gamestate: "game_state.GameState", target_username: str, allow_self_target: bool, shot_counter_name: str, shot_count: int):
    """
    This is a template for acknowledgement functions for roles with a single target (which is a lot of roles).

    The first 3 parameters are the ones that would actually be passed to the finished function; the parameters afterwards
    are the things that can be changed about how this function works. This function is intended to be used 
    in a lambda expression, such as: 
    `lambda username, gamestate, target_username : acknowledge_template(username, gamestate, target_username, allow_self_target=True, shot_counter_name='cop_shot_counter', shot_count=3)`

    This is then used as the function for an acknowledgement.

    Parameters

    - allow_self_target: True if self-targeting is allowed with this action
    - shot_counter_name: The attribute that this shot-counter should be stored in
    - shot_count: The number of shots this ability has, or -1 if infinite

    TODO: test this
    """
    if not gamestate.player_exists(target_username):
        raise ActionException("This player does not exist.")
    if username.lower() == target_username.lower() and not allow_self_target:
        raise ActionException("You cannot self-target with this ability.")
    if shot_count != -1 and gamestate.get_player_object_living_players_only(username).__getattribute__(shot_counter_name) == shot_count: # type: ignore
        raise ActionException("This action has all shots exhausted already.")
    if not fol_interface.send_message("Your action has been recorded.\n", username, priority=1):
        raise ActionException("The message could not be sent successfully.")


