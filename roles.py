"""
TODO: implement
# Standard Roles

There is a need to have a standard list of role [options? have better word here]. This is because:
    - Simple roles, such as Doctor, and simple modifiers (such as even/odd/non-consec/x-shot) should be able to
        be combined easily (meaning, in a small amount of text that does not take a long time to type out). Ideally, 
        this can be done without having any Python knowledge.
    - Many roles tie into eachother - a Godfather registers as Town to investigatives, but for certain abilities,
        it may need to register as Mafia. In this case, there must be a parameter passable to get_alignment() that 
        specifies which behavior to use - and this parameter must have the same in the Godfather as it does in other 
        roles that investigate.

The following parts of roles are complex enough to need standards:
    - syntax_parser
    - can_use_now
    - acknowledge_and_verify
    - use_action_instant
    - use_action_phase_end

## syntax_parser Standards
    - Provided by roles_10_7_2024.syntax_parser_standard.py
    - Use syntax_parser_constructor(command_name: str, parameter_list: list[str]).
        - command_name is the name of the command the player submits
        - parameter_list is the list of parameters the player must submit
            - Currently supported parameters:
                SYNTAX_PARSER_NONNEGATIVE_INT: A nonnegative integer
                SYNTAX_PARSER_PLAYERNAME: A playername (which will be put through substring-based nickname resolution)
                SYNTAX_PARSER_NO_SPACE_STRING: A string without spaces (or newlines), which will not be treated as a playername
                    and not resolved with substrings
        - Example: If "/shoot Zugbot 5" is a valid command, then:
            - command_name == "shoot"
            - parameter_list == [SYNTAX_PARSER_PLAYERNAME, SYNTAX_PARSER_NONNEGATIVE_INT]
            - Overall call: syntax_parser_constructor("shoot", [SYNTAX_PARSER_PLAYERNAME, SYNTAX_PARSER_NONNEGATIVE_INT]
                                                       gamestate)

## can_use_now Standards
    - Provided by roles_10_7_2024.can_use_now_standard.py
    - Use can_use_now_constructor(...) OR use one of the normal modifiers*.
        - instant_shot_count is the number of times an instant action can be used, or -1 if unlimited.
        - phase_end_shot_count is the number of times a phase end action can be used, or -1 if unlimited.
        - normal_modifiers: Use the Enum in can_use_now_standard. Currently supported modifiers:
            - DAY - It is a day action
            - NIGHT - It is a night action
            - EVEN_CYCLE - It can only be used on Day/Night 2, 4, 6, etc
            - ODD_CYCLE - It can only be used on Day/Night 1, 3, 5, etc
    - Note that if one x-shot modifier has been met/exceeded, the entire action will fail.
    - *Every normal modifier is a valid can_use_now function, with no other requirements - so an inifite shot day action,
        for example, can just use DAY.

## Acknowledge and Verify Standards
    - Provided by roles_10_7_2024.acknowledge_and_verify_standard.py
    - Use acknowledge_and_verify_constructor(...).
        - restrictions - The restrictions placed on the user's action (like NO_SELF_TARGET, LOYAL_FOR_MAFIA, etc). Currently
            supported restrictions:
            - NO_SELF_TARGET - None of the targets can be the player using the action.
            - LOYAL_FOR_MAFIA - All of the targets must be mafia, *and the player using the action is mafia-aligned*.
            - DISLOYAL_FOR_MAFIA - All of the targets must not be mafia, *and the player using the action is mafia-aligned*.
        - parameter_list - The format that the action's parameters are in. This parameter should be a list, where each entry
            what the parameter is in the syntax parser. For example, an action that has a single target should have a parameter
            list of [PLAYER_PARAMETER]. The following parameter types are supported:
            - PLAYER_PARAMETER - for targets that are players
            - ARBITRARY_STRING
    - If the action is rejected, a message explaining why will be sent to the user.
    - If the action is accepted, a message acknowledging the action will be sent to the user.

## Use Action Standards
    - Standard parameters for methods like get_alignment(), receive_protection(), etc:
        | Parameter Name | Data type | Applicable Method(s) / Information sources | Explanation |
        - invest_power
            - float, >= 0
            - get_alignment(), game log 
            - Roles that falsify investigative results (like Godfather, Miller, Ninja, etc) have a specified power. 
                If invest_power is greater than the power from this role, the results will not be false.
        - protect_power
            - float, >= 0
            - receive_protection()
            - Roles that cannot be protected (Macho) have a specified power. If protect_power is greater
                than the power from this role, the protection will happen anyway.
    - Standard actions:
        - Investigative actions:
            - Cop
                - Returns alignment of target to user
                - Visit is recorded
                - Parameters:
                    - 
            - Tracker
            - Watcher
        - Protective actions:
            - Doctor
        - Manipulative actions:
            - 
    
"""


import player
#import game_state
import fol_interface
import post as p
#import modbot

import re
# from roles_folder.dayvig import make_town_day_vig, make_mafia_day_vig
# from roles_folder.godfather import make_godfather
# from roles_folder.cop import make_town_cop
# from roles_folder.town_joat_1 import make_town_joat_1
# from roles_folder.doctor import make_town_doctor, make_mafia_doctor
from roles_folder.roles_exceptions import ActionException, ParsingException

from roles_10_7_2024 import syntax_parser_standard as syn
from roles_10_7_2024 import can_use_now_standard as can
from roles_10_7_2024 import acknowledge_and_verify_standard as aav

from typing import Iterable
import game_state
import modbot
import constants as c
import types

async def daykill_player(player_doing_kill: "player.Player", gamestate: "game_state.GameState", target_username: "player.Player"):
    """
    This immediately kills the player specified in target_username.

    This ability can only be used once per cycle per player.
    """
    
    player_doing_kill_object = gamestate.get_player_object_living_players_only(player_doing_kill.username)
    assert player_doing_kill_object is not None

    if player_doing_kill_object.last_phase_dayvig_was_used == gamestate.phase_count:
        print("This player has already used their dayvig ability today.")
        return
    
    player_doing_kill_object.last_phase_dayvig_was_used = gamestate.phase_count # type: ignore


    target_player_object = gamestate.get_player_object_living_players_only(target_username.username)
    assert target_player_object is not None
    target_player_object.take_damage(1)

    fol_interface.to_post_cache += "# A shot rings out! \n"

    await modbot.resolve_current_deaths(gamestate)



def make_day_vig(username: str) -> "player.Player":
    result = player.Player(username, c.TOWN, "town_day_vig.txt", abilities=[
        player.Ability(
            ability_name = "Day vig",
            syntax_parser=syn.syntax_parser_constructor("shoot", [syn.SYNTAX_PARSER_PLAYERNAME]),
            submission_location=c.IN_PM,
            can_use_now=can.DAY,
            use_action_instant=daykill_player,
            use_action_phase_end=empty_function,
            ability_priority=0,
            willpower_required_instant=None,
            willpower_required_phase_end=None,
            acknowledge_and_verify=aav.acknowledge_and_verify_constructor(restrictions=[
                aav.NO_SELF_TARGET
            ], parameter_list=[aav.PLAYER_PARAMETER], do_acknowledgement=False),
            target_focus=0,
            action_types=[c.KILLING]
        )
    ])
    return result


def get_cop_result(player_doing_action: str, gamestate: 'game_state.GameState', target_player: 'player.Player'):
    alignment = target_player.get_alignment()
    if not fol_interface.send_message(f"Your result: {'TOWN' if alignment == c.TOWN else 'MAFIA'}", player_doing_action):
        raise ActionException

        

def make_town_cop(username: str) -> "player.Player":
    result = player.Player(username, c.TOWN, "town_cop.txt", abilities=[
        player.Ability(
            ability_name = "Cop",
            syntax_parser=syn.syntax_parser_constructor("investigate", [syn.SYNTAX_PARSER_PLAYERNAME]),
            submission_location=c.IN_PM,
            can_use_now=can.NIGHT,
            use_action_instant=empty_function,
            use_action_phase_end=get_cop_result,
            ability_priority=0,
            willpower_required_instant=None,
            willpower_required_phase_end=None,
            acknowledge_and_verify=aav.acknowledge_and_verify_constructor(restrictions=[
                aav.NO_SELF_TARGET
            ], parameter_list=[aav.PLAYER_PARAMETER]),
            target_focus=0,
            action_types=[c.INVESTIGATIVE]
        )
    ])
    return result

def make_town_joat(username: str) -> "player.Player":
    """
    Makes a town joat, with Cop, Doctor, and Vig 1-shots.
    The JOAT from joat10.
    """
    result = player.Player(username, c.TOWN, "town_joat_1.txt", abilities=[
        player.Ability(
            ability_name = "JOAT",
            syntax_parser=syn.syntax_parser_constructor("act", [syn.SYNTAX_PARSER_NO_SPACE_STRING, syn.SYNTAX_PARSER_PLAYERNAME]),
            submission_location=c.IN_PM,
            can_use_now=can.NIGHT,
            use_action_instant=empty_function,
            use_action_phase_end=do_joat,
            ability_priority=-1,
            willpower_required_instant=None,
            willpower_required_phase_end=None,
            acknowledge_and_verify=aav.acknowledge_and_verify_constructor(restrictions=[
                aav.NO_SELF_TARGET
            ], parameter_list=[aav.ARBITRARY_STRING_PARAMETER, aav.PLAYER_PARAMETER]),
            target_focus=0,
            action_types=[c.INVESTIGATIVE, c.PROTECTIVE, c.KILLING]
        )
    ])
    return result

def visit(acting_player: "player.Player", gamestate: "game_state.GameState", target_players: Iterable["player.Player"], action_types: list[str], was_instant: bool):
    """
    This function records a visit from acting_player to target_players.
    """
    gamestate.record_visit([acting_player], list(target_players), action_types, was_instant=was_instant)

def empty_function(*args):
    """
    Takes any number of arguments, and does nothing.
    """
    pass
    
def modpost_syntax_parser(post: p.Post) -> list[str]:
    matcher = re.compile(r"/modpost\s(.*)", re.DOTALL | re.IGNORECASE)
    full_post = matcher.search(post.content_with_quotes)
    if post.content_with_quotes.find("[votecount]") != -1 or post.content_with_quotes.find("[alive]") != -1:
        raise ParsingException("This modpost has [votecount] or [alive] tags in it, which is not allowed.")
    if full_post is None:
        raise ParsingException("This post is not in the modpost format.")
    mod_post = full_post.group(1)
    return [mod_post]

def make_vanilla_town(username: str) -> "player.Player":
    result = player.Player(username, c.TOWN, "town.txt", abilities=None)
    return result

def make_mafia_goon(username: str) -> "player.Player":
    result = player.Player(username, c.MAFIA, "mafia.txt", abilities=None)
    return result


def make_modposter(username: str, alignment: int) -> 'player.Player':
    result = player.Player(username, alignment, "town_modposter.txt" if alignment == c.TOWN else "mafia_modposter.txt", abilities=[
        player.Ability(
            ability_name="Modpost",
            syntax_parser=modpost_syntax_parser,
            submission_location=c.IN_PM,
            can_use_now=lambda playername, ability, gamestate: gamestate.is_day,
            acknowledge_and_verify=aav.acknowledge_and_verify_constructor(restrictions=[], parameter_list=[aav.ARBITRARY_STRING_PARAMETER]),
            use_action_instant=lambda playername, gamestate, content : fol_interface.create_post(
                "The following is a modpost: \n [quote] \n" +
                content
                + "\n[/quote]\n"
                ),
            use_action_phase_end=empty_function,
            ability_priority=0,
            willpower_required_instant=None,
            willpower_required_phase_end=None,
            target_focus=0,
            action_types=[c.COMMUNICATIVE]
        )
    ])
    return result

def make_mafia_modposter(username: str) -> 'player.Player':
    return make_modposter(username, c.MAFIA)

def make_town_modposter(username: str) -> 'player.Player':
    return make_modposter(username, c.TOWN)



# Popcorn explanation:
# The gunbearer has 1 health
# Non-gunbearer town have 2 health, mafia have 1 health
# The take_damage method for town members is overriden to: 
    # give themselves a gun if they're at 2 health (and deal 1 health to themself)
    # and be normal otherwise
# The gun deals 1 damage to mafia, and 1 damage to town; if town is shot the gunbearer takes 1 damage as well


async def use_popcorn_gun(player_object: 'player.Player', 
                    gamestate: "game_state.GameState", target_player: 'player.Player'):
    target_player.take_damage(1)
    if target_player.get_alignment() == c.TOWN:
        fol_interface.to_post_cache += f"# A shot rings out, but bounces back!\n"
        player_object.take_damage(1)
    else:
        fol_interface.to_post_cache += f"# A shot rings out and hits! {player_object.username} keeps their gun.\n"
    await modbot.resolve_current_deaths(gamestate)

def town_popcorn_take_damage(self: 'player.Player', damage: float):
    if self.health == 2:
        gun_ability = player.Ability(
            ability_name="Popcorn gun",
            syntax_parser=syn.syntax_parser_constructor(command_name="shoot", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
            submission_location=c.IN_THREAD,
            can_use_now=can.can_use_now_constructor(instant_shot_count=-1, phase_end_shot_count=-1,
                                                    normal_modifiers=[can.DAY]),
            acknowledge_and_verify=aav.acknowledge_and_verify_constructor(restrictions=[aav.NO_SELF_TARGET],
                                                                        parameter_list=[aav.PLAYER_PARAMETER],
                                                                        do_acknowledgement=False),
            use_action_instant=use_popcorn_gun,
            use_action_phase_end=lambda *args : None,
            ability_priority=0,
            willpower_required_instant=None,
            willpower_required_phase_end=None,
            target_focus=0,
            action_types=[c.KILLING],
            ignore_action_deadline=False)
        self.abilities.append(gun_ability)
        self.health -= damage
        fol_interface.to_post_cache += f"# @{self.username} now has the gun!\n"
        return False
    else:
        self.health -= damage
        return self.health <= 0

def make_town_popcorn(username: str) -> 'player.Player':
    result = player.Player(username, c.TOWN, "town_popcorn.txt", abilities=None)
    result.take_damage = types.MethodType(town_popcorn_take_damage, result)
    result.health = 2
    return result

def choose_gunholder(player_object: 'player.Player', 
                    gamestate: "game_state.GameState", target_player: 'player.Player'):
    for player_object in gamestate.current_players:
        if player_object.health != 2 and player_object.alignment == c.TOWN : # prevents this from being used with a living gunbearer
            return
    target_player.take_damage(1)
    fol_interface.post_cache()

def make_mafia_popcorn(username: str) -> 'player.Player':
    result = player.Player(username, c.MAFIA, "mafia_popcorn.txt", abilities=[
        player.Ability(
            ability_name="Choose gunholder",
            syntax_parser=syn.syntax_parser_constructor(command_name="choose", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
            submission_location=c.IN_PM,
            can_use_now=can.DAY,
            acknowledge_and_verify=aav.acknowledge_and_verify_constructor(restrictions=[aav.DISLOYAL_FOR_MAFIA], parameter_list=[aav.PLAYER_PARAMETER]),
            use_action_instant=choose_gunholder,
            use_action_phase_end=lambda *args : None,
            ability_priority=0,
            willpower_required_instant=None,
            willpower_required_phase_end=None,
            target_focus=0,
            action_types=[c.FALSE_ACTION],
            ignore_action_deadline=True
        )
    ])
    return result