import ability
import syntax_parser_standard as syn
import fol_interface
import player
from typing import Callable
import constants as c

def RESET_ABILITY() -> 'ability.Ability':
    """
    This ability unsubmits all currently submitted end-of-phase abilities.
    """
    def reset_function(acting_player: player.Player, gamestate, ability: ability.Ability):
        acting_player.unresolved_actions = []

    return ability.Ability(
        ability_name="Reset Submission",
        syntax_parser=syn.SyntaxParser("reset", parameter_list=[]),
        action=ability.Action(reset_function),
        submission_location=c.IN_PM,
        is_instant=True,
        ability_restrictions=ability.AbilityRestrictions(day_required=False, night_required=False),
        action_types=[c.FALSE_ACTION],
        ignore_action_deadline=True
    )


def VOTECOUNT_ABILITY() -> "ability.Ability":
    """
    Creates and returns a votecount ability.
    """
    return ability.Ability(
        ability_name="Votecount Request",
        syntax_parser=syn.SyntaxParser("votecount", parameter_list=[]),
        action=ability.Action(lambda playername, gamestate, ability : fol_interface.post_votecount(nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominations())),
        is_instant=True,
        ignore_action_deadline=True,
        ability_restrictions=ability.AbilityRestrictions(night_required=False, day_required=True)
    )

def VOUTECOUNT_ABILITY() -> "ability.Ability":
    """
    Creates and returns a voutecount ability.
    """
    return ability.Ability(
        ability_name="Voutecount Request",
        syntax_parser=syn.SyntaxParser("voutecount", parameter_list=[]),
        action=ability.Action(lambda playername, gamestate, ability : fol_interface.post_votecount(nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominations(), say_voutecount=True)),
        is_instant=True,
        ignore_action_deadline=True,
        ability_restrictions=ability.AbilityRestrictions(night_required=False, day_required=True)
    )

def DOCTOR_ACTION() -> "ability.Action":
    """
    Returns a doctor action.
    """
    def doc_function(acting_player: player.Player, gamestate, ability: ability.Ability, target_player: player.Player):
        target_player.receive_protection(ability.ability_modifiers)
    return ability.Action(doc_function)

def DOCTOR_ABILITY(protection_level=100, shot_count=-1, target_focus=0, ) -> "ability.Ability":
    """
    Returns a doctor ability.
    """
    return ability.Ability(
        ability_name="Doctor Protection",
        syntax_parser=syn.SyntaxParser("protect", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
        action=DOCTOR_ACTION(),
        is_instant=False,
        ability_priority=-1, # Make protection be before kills!
        ignore_action_deadline=False,
        ability_restrictions=ability.AbilityRestrictions(night_required=True, day_required=False,
                                                         shot_count=shot_count, self_target_allowed=False),
        ability_modifiers=ability.AbilityModifiers(protection_level=protection_level, target_focus=target_focus),
    )

def COP_ACTION() -> "ability.Action":
    """
    Returns a cop action.
    """
    def cop_function(acting_player: player.Player, gamestate, ability: ability.Ability, target_player: player.Player):
        resulting_alignment = target_player.get_alignment(ability.ability_modifiers)
        fol_interface.send_message(f"You learn your target is {resulting_alignment.string_rep()}.", username=acting_player.username)
    return ability.Action(cop_function)

def COP_ABILITY(invest_strength=1.0, shot_count=-1, target_focus=0) -> "ability.Ability":
    """
    Returns a cop ability.
    """
    return ability.Ability(
        ability_name="Cop Investigation",
        syntax_parser=syn.SyntaxParser("cop", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
        action=COP_ACTION(),
        is_instant=False,
        ignore_action_deadline=False,
        ability_restrictions=ability.AbilityRestrictions(night_required=True, day_required=False,
                                                         shot_count=shot_count, self_target_allowed=False),
        ability_modifiers=ability.AbilityModifiers(invest_power=invest_strength, target_focus=target_focus)
    )

def VIG_ACTION() -> "ability.Action":
    """
    Returns a vigilante action.
    """
    def vig_function(acting_player: player.Player, gamestate, ability: ability.Ability, target_player: player.Player):
        target_player.take_damage(ability.ability_modifiers)
    return ability.Action(vig_function)

def VIG_ABILITY(damage_amount=100, shot_count=-1, target_focus=0) -> "ability.Ability":
    """
    Returns a vig ability.
    """
    return ability.Ability(
        ability_name="Vigilante Shot",
        syntax_parser=syn.SyntaxParser("shoot", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
        action=VIG_ACTION(),
        is_instant=False,
        ignore_action_deadline=False,
        ability_restrictions=ability.AbilityRestrictions(night_required=True, day_required=False,
                                                         shot_count=shot_count, self_target_allowed=False),
        ability_modifiers=ability.AbilityModifiers(damage_amount=damage_amount, target_focus=target_focus)
    )

def IC_ACTION() -> "ability.Action":
    """
    Returns an innocent child action.
    """
    def ic_function(acting_player: player.Player, gamestate, ability: ability.Ability):
        print("Using IC action now.")
        fol_interface.create_post(f"# @{acting_player.username} reveals as a member of the [color]Town[/color]!")
    return ability.Action(ic_function)

def IC_ABILITY(allowed_cycles: list[int] | Callable[[int], bool]) -> "ability.Ability":
    """
    Returns an innocent child ability.
    """
    return ability.Ability(
        ability_name="Innocent Child Reveal",
        syntax_parser=syn.SyntaxParser("reveal", parameter_list=[]),
        action=IC_ACTION(),
        is_instant=True,
        ignore_action_deadline=False,
        ability_restrictions=ability.AbilityRestrictions(night_required=False, day_required=True,
                                                         shot_count=1, allowed_cycles=allowed_cycles)
    )

def make_cycling(abilities_list: list["ability.Ability"], cycle_name: str):
    """
    This makes the passed abilities cycle together with the specified cycle name.
    """
    for abil in abilities_list:
        abil.ability_restrictions.cycling.append(cycle_name)

def make_non_multitaskable(abilities_list: list["ability.Ability"], cost_name: str):
    """
    This makes the passed abilities unable to be multitasked together.
    """
    for abil in abilities_list:
        abil.ability_restrictions.multitask_cost[cost_name] = 1

# player creators start here

def MAKE_VANILLA_TOWN(username: str, flip_path: str) -> "player.Player":
    import player
    result = player.Player(username, c.TOWN, flip_path, abilities=None)
    return result

def MAKE_MAFIA_GOON(username: str, flip_path: str) -> "player.Player":
    import player
    result = player.Player(username, c.MAFIA, flip_path, abilities=None)
    return result

def MAKE_TOWN_COP(username: str, flip_path: str, invest_strength=1.0, shot_count=-1, target_focus=0.0) -> 'player.Player':
    import player
    result = player.Player(username, c.TOWN, flip_path, abilities=[
        COP_ABILITY(invest_strength=invest_strength, shot_count=shot_count, target_focus=target_focus)])
    return result

def MAKE_TOWN_VIG(username: str, flip_path: str, damage_amount=1.0, shot_count=-1, target_focus=0.0) -> 'player.Player':
    import player
    result = player.Player(username, c.TOWN, flip_path, abilities=
                           [VIG_ABILITY(damage_amount=damage_amount, shot_count=shot_count, target_focus=target_focus)]
                           )
    return result

def MAKE_MAFIA_VIG(username: str, flip_path: str, damage_amount=1.0, shot_count=-1, target_focus=0.0) -> 'player.Player':
    import player
    result = player.Player(username, c.MAFIA, flip_path, abilities=
                           [VIG_ABILITY(damage_amount=damage_amount, shot_count=shot_count, target_focus=target_focus)]
                           )
    return result


def MAKE_TOWN_INNOCENT_CHILD(username: str, flip_path: str, allowed_cycles : list[int] | Callable[[int], bool]=lambda x : x >= 1):
    import player
    result = player.Player(username, c.TOWN, flip_path, abilities=[
        IC_ABILITY(allowed_cycles=allowed_cycles)
    ])
    return result