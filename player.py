"""
This class represents a player, with all attributes (such as username, alignment, health, and their role/abilities).

Active abilities are shown in the abilities field. Passive abilities are given through overriding the default modifier methods.
For example, if you wanted to give someone the bulletproof modifier, you would override the take_damage method with one that does nothing.
If you wanted to give someone the godfather modifier, you would override their get_alignment method to always return player.TOWN.

ALL possible attributes, other than those specified here, have default values of 0. This allows another player's ability
to essentially "make up" an attribute, and start using it (provided the name does not overlap with any existing
attributes/functions).

"""

boolean_var: bool = True
if boolean_var:
    import game_state
    from typing import Callable
    import syntax_parser_standard as syn
    from constants import Alignment
    import abilities_standard
    import ability as a
import constants as c
import config
import fol_interface
import discord_interface
import fam6


import math

import random

def is_a_crit(chance_to_crit: float):
    return chance_to_crit > random.random()

# nomination info:
# players have: can_nominate, target_of_nomination, nomination_order

def nomination_use_action_instant(acting_player: 'Player', gamestate: 'game_state.GameState', nominated_player: 'Player'):
    if not gamestate.nominations_open:
        fol_interface.create_post(f"Nominations are not open.")
    elif not acting_player.can_nominate:
        fol_interface.create_post(f"You ({acting_player.username}) cannot nominate.")
    elif acting_player.target_of_nomination is not None:
        fol_interface.create_post(f"You ({acting_player.username}) have already nominated today.")
    elif gamestate.is_nominated(nominated_player):
        fol_interface.create_post(f"{nominated_player.username} has already been nominated today.")
    else:
        fol_interface.create_post(f"{acting_player.username} has nominated {nominated_player.username}.")
        acting_player.target_of_nomination = nominated_player # type: ignore
        acting_player.nomination_order = gamestate.nomination_counter # type: ignore
        gamestate.nomination_counter += 1


def get_default_abilities():
    """
    Returns the default list of abilities, which is what all vanilla players have.

    This is not necessarily the empty list - vanilla players still have the ability to request votecounts,
    for example.
    """
    import ability as a
    import syntax_parser_standard as syn
    nominate_ability = a.Ability(
        ability_name="Nominate",
        syntax_parser=syn.SyntaxParser("nominate", [syn.SYNTAX_PARSER_PLAYERNAME]),
        submission_location=c.IN_THREAD,
        action=a.Action(nomination_use_action_instant),
        is_instant=True
    )
    abilities_list = [abilities_standard.RESET_ABILITY()]
    if config.do_votecounts:
        abilities_list.append(abilities_standard.VOTECOUNT_ABILITY())
        abilities_list.append(abilities_standard.VOUTECOUNT_ABILITY())
    if config.is_botf:
        abilities_list.append(nominate_ability)
    return abilities_list

def get_nightkill_ability():
    """
    In turbos specifically, there is a wolfchat on the forum where the nightkill must be submitted (as opposed to discord).

    Mafia-aligned players are given this ability in turbos to allow this.
    """
    def nightkill_function(playername, gamestate, ability, target_player: 'Player'):
        import modbot # Here to avoid circular import
        modbot.submit_nightkill(target_player.username)

    return a.Ability(
        ability_name="Nightkill",
        syntax_parser=syn.SyntaxParser("nightkill", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
        action=a.Action(nightkill_function),
        is_instant=True,
        submission_location=c.IN_WOLFCHAT,
        ignore_action_deadline=True,
        force_send_feedback_in_submission_location=True,
        ability_restrictions=a.AbilityRestrictions(night_required=True, day_required=False, disloyal=True,
                                                   allowed_cycles=lambda x : x >= 0),
        ability_modifiers=a.AbilityModifiers(damage_amount=1)
    )

class Redirection:
    """
    This is a struct-like to hold redirection-related effects on a player.
    """
    def __init__(self, redirect_player: "Player", redirection_strength: int, focus_increase_on_redirection: int) -> None:
        self.redirect_player = redirect_player
        self.redirection_strength = redirection_strength
        self.focus_increase_on_redirection = focus_increase_on_redirection

class Passives:
    """
    These are passive effects (think modifiers) that apply directly to a player.
    Their effects are all enforced elsewhere in the code - this class only serves as the place that all
    such passives are stored.
    """
    def __init__(self,
                 voting_power=1,
                 voting_power_is_public=True,
                 invest_alignment: 'Alignment | None' = None,
                 invest_resistance=1.0,
                 protection_multiplier=1.0,
                 damage_multiplier=1.0,
                 ita_angel_count=0,
                 ita_angel_crit_count=0,
                 flat_ita_resistance=0,
                 ita_tags: 'set[str] | None' = None) -> None:
        self.voting_power = voting_power # TODO: implement
        self.voting_power_is_public = voting_power_is_public # TODO: implement
        self.invest_alignment = invest_alignment
        self.invest_resistance = invest_resistance
        self.protection_multiplier = protection_multiplier
        self.damage_multiplier = damage_multiplier # damage is multiplied *after* protection.
        self.ita_angel_count = ita_angel_count 
        self.ita_angel_crit_count = ita_angel_crit_count
        self.flat_ita_resistance = flat_ita_resistance
        self.ita_tags: set[str] = ita_tags if ita_tags is not None else set()


class ITAItem:
    """
    This class holds information about ITAs. 
    This does not implement the actual use of ITAs.

    Note that only positive damage ITAs are allowed. The default value of -1 mean that it is the
    global base damage.

    Note that the identifier is shown to the player!
    """
    def __init__(self, 
                 damage=-1,
                 can_crit=True,
                 identifier="Innate ITA") -> None:
        self.damage=damage
        self.can_crit=can_crit
        self.identifier = identifier


class Player:
    def __init__(self, 
                 username: str,
                 alignment: 'Alignment', 
                 rolecard_path: str, 
                 abilities: None | list["a.Ability"] = None,
                 willpower=0.0, 
                 redirection: Redirection | None = None,
                 unresolved_actions: "None | list[UnresolvedPhaseEndAction]" = None, 
                 passives: None | Passives = None,
                 ita_items: None | list[ITAItem] = None,
                 max_health=100
                 ) -> None:
        """
        Creates a player.

        username - The player's username.
        alignment - The player's win condition. player.TOWN for town, and player.MAFIA for mafia.
        health - A float between 0 and 1, representing the player's current health. If the player's health reaches 0, they die.
        rolecard_path - The filepath to their rolecard, starting in the flips folder
        protection - The amount of protection this player currently has.
        abilities - The active abilities they have. (should be of type list[Ability]) - Note that players should not have
            two abilities with the same ability_name - this will cause bugs.
        
        For willpower, redirect_player, redirection_strength, and focus_increase_on_redirection, see Ability's documentation.
        willpower is for roleblocks, and the other 3 are for redirection.

        unresolved_actions should likely be left as None - this is used as the list of unresolved phase-end actions for this player.

        """
        self.username = username
        self.alignment = alignment
        self.health: int = max_health
        self.max_health = max_health
        self.rolecard_path = rolecard_path
        self.protection: int = 0
        self.abilities = ([] if abilities is None else abilities) + get_default_abilities() \
                          + ([get_nightkill_ability()] if alignment == c.MAFIA else [])
        self.willpower = willpower
        self.redirection = redirection

        self.unresolved_actions = [] if unresolved_actions is None else unresolved_actions

        if config.is_botf:
            self.can_nominate = True
            self.target_of_nomination: Player | None = None

        self.passives = passives if passives is not None else Passives()
        self.ita_items = ita_items if ita_items is not None else []
        self.actions_costs: dict[str, float] = dict() # This stores the costs of any instant actions during the current phase
                                                    # and is used when verifying any (instant or non-instant) actions
                                                    # to ensure they do not exceed the maximum costs
                                                    # In other words, this is part of how multitasking (or the lack thereof)
                                                    # is handled.
        
    def get_redirect(self, target_focus: int) -> 'Player':
        """
        Given target_focus, returns the player the action should target.
        """
        if self.redirection is None or target_focus >= self.redirection.redirection_strength:
            return self
        return self.redirection.redirect_player
    
    def get_redirect_focus_increase(self) -> int:
        return 0 if self.redirection is None else self.redirection.focus_increase_on_redirection

    def take_damage(self, modifiers: 'a.AbilityModifiers') -> bool:
        """
        Returns True if the player died due to this damage, False otherwise.
        """
        damage_amount = modifiers.damage_amount
        if damage_amount <= self.protection:
            self.protection -= damage_amount
            return False
        damage_amount = math.ceil( (damage_amount - self.protection) * self.passives.damage_multiplier )
        self.protection = 0
        self.health = max(0, self.health - damage_amount)
        return self.health == 0
    
    def add_default_ita_tags(self):
        """
        This method examines the player state to add or remove certain ita tags.

        Tags added/removed:
        - full_health if max_health == health
        """
        if self.max_health == self.health:
            self.passives.ita_tags.add("full_health")
        else:
            self.passives.ita_tags.discard("full_health")
    
    async def take_ita_damage(self, modifiers: 'a.AbilityModifiers', ita_item_used: ITAItem) -> str:
        """
        Returns the ITA feedback that should be posted publicly.
        """
        self.add_default_ita_tags()

        # Marluna's role
        if 'vampire' in self.passives.ita_tags and 'vampire' in modifiers.ita_tags:
            fam6.heal_vampire_player()

        can_crit = ita_item_used.can_crit
        damage = ita_item_used.damage
        if damage == -1:
            damage = config.ita_base_damage

        await discord_interface.send_message_to_hosting_discord(f"ITA properties: {damage=}, {can_crit=}")
        await discord_interface.send_message_to_hosting_discord(f"Defensive properties: {self.health=}, {self.protection=}, {self.passives.flat_ita_resistance=}")
        await discord_interface.send_message_to_hosting_discord(f"Misc properties:  {self.passives.ita_angel_count=}, {self.passives.ita_angel_crit_count=}")
        if (self.passives.ita_angel_count > 0):
            self.passives.ita_angel_count -= 1
            return "# Miss!"
        if (self.passives.ita_angel_crit_count > 0):
            self.passives.ita_angel_crit_count -= 1
            can_crit = False
        for tag in self.passives.ita_tags:
            if tag in modifiers.ita_tags:
                await discord_interface.send_message_to_hosting_discord(f"ITA damage increased by {modifiers.ita_tags[tag]} due to tag: {tag}")
                damage += modifiers.ita_tags[tag]

        damage -= self.passives.flat_ita_resistance
        if self.protection >= damage:
            self.protection -= damage
            damage = 0
        elif self.protection > 0:
            damage -= self.protection
            self.protection = 0
        crit_chance = (damage / self.health) if can_crit else 0
        is_crit = is_a_crit(crit_chance)
        await discord_interface.send_message_to_hosting_discord(f"ITA has crit chance: {crit_chance}. Is crit: {is_crit}")
        if damage >= self.health:
            self.health = 0
            await discord_interface.send_message_to_hosting_discord(f"## {self.username} has died by reaching 0 HP!")
            return f"# Hit! The target has reached 0 HP and died. Stand by for flip."
        if is_crit:
            self.health = 0
            await discord_interface.send_message_to_hosting_discord(f"## {self.username} has died from a direct hit!")
            return f"# Direct hit! Stand by for flip."
        self.health -= damage
        return "The shot connects."
    
        # TODO: other custom roles
        


    def receive_protection(self, modifiers: 'a.AbilityModifiers'):
        self.protection += round( modifiers.protection_level * self.passives.protection_multiplier )
    
    def do_day_start_changes(self):
        self.protection = 0
        self.actions_costs = dict()

    def do_night_start_changes(self):
        self.actions_costs = dict()

    def get_alignment(self, modifiers: 'a.AbilityModifiers'):
        if self.passives.invest_alignment is None or self.passives.invest_resistance < modifiers.invest_power:
            return self.alignment
        return self.passives.invest_alignment
    
    def get_health(self):
        return self.health
    
    def __getattr__(self, attr):
        print(f"WARNING: Attempted to access attribute {attr}. This is allowed, because all player"
              " attributes have default values of 0, unless otherwise specified. However, "
              "this could be in error, so this warning is provided.")
        return 0
    
    def record_action(self, ability_id: int, parameters: list) -> bool:
        """
        Records an action in self.unresolved_actions.

        The parameters given **should not have redirects processed yet**.

        If the player does not have an ability with the specified ID, this method will return False (otherwise, it will return True).
        If the player already has an action from an ability with this ID, it will overwrite the old action.
        """
        def action_recorder(ability_id: int, parameters: list) -> None:
            """
            Does the actual recording, but assumes the player has this ability. (Here only to make the code cleaner)
            """
            for i, unresolved_action in enumerate(self.unresolved_actions):
                if unresolved_action.ability_id == ability_id:
                    self.unresolved_actions[i] = UnresolvedPhaseEndAction(ability_id, parameters)
                    return None
            self.unresolved_actions.append(UnresolvedPhaseEndAction(ability_id, parameters))

        for ability in self.abilities:
            if ability_id == ability.id:
                action_recorder(ability_id, parameters)
                return True
        return False
    
    def __getstate__(self):
        print(f"Player with name {self.username} is being Pickled!")
        return self.__dict__
    
    def __setstate__(self, state):
        self.__dict__.update(state)

class UnresolvedPhaseEndAction:
    """
    This class records an action that needs to be resolved at the end of the phase.

    Parameters - 
        ability_id - The ID of the relevant ability
        parameters - (Almost!) the parameters to pass the use_action_phase_end function. Specifically:
            This should not have the playername or gamestate - just the parameters the player input.
            Also, this should not have redirects resolved yet.
    """
    def __init__(self, ability_id: int, parameters: list) -> None:
        self.ability_id = ability_id
        self.parameters = parameters



