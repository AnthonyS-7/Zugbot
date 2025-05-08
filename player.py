"""
This class represents a player, with all attributes (such as username, alignment, health, and their role/abilities).

Active abilities are shown in the abilities field. Passive abilities are given through overriding the default modifier methods.
For example, if you wanted to give someone the bulletproof modifier, you would override the take_damage method with one that does nothing.
If you wanted to give someone the godfather modifier, you would override their get_alignment method to always return player.TOWN.

ALL possible attributes, other than those specified here, have default values of 0. This allows another player's ability
to essentially "make up" an attribute, and start using it (provided the name does not overlap with any existing
attributes/functions).

"""

import types
import typing
import post as p
from roles_folder.roles_exceptions import ActionException, ParsingException
import fol_interface
import config
import game_state
from typing import Callable
import roles_10_7_2024.can_use_now_standard as can_use
import roles_10_7_2024.syntax_parser_standard as syn
import constants as c

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


def get_votecount_ability():
    """
    Creates and returns a votecount ability.
    """
    return Ability(
        ability_name="Votecount Request",
        syntax_parser=votecount_request_syntax_parser,
        can_use_now=can_use.DAY,
        use_action_instant=lambda playername, gamestate : fol_interface.post_votecount(nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominator_to_nominee_dict()),
        ignore_action_deadline=True
    )


def get_default_abilities():
    """
    Returns the default list of abilities, which is what all vanilla players have.

    This is not necessarily the empty list - vanilla players still have the ability to request votecounts,
    for example.
    """
    request_votecount_ability = get_votecount_ability()
    request_voutecount_ability = Ability(
        ability_name="Voutecount Request",
        syntax_parser=syn.syntax_parser_constructor(command_name="voutecount", parameter_list=[]),
        can_use_now=can_use.DAY,
        use_action_instant=lambda playername, gamestate : fol_interface.post_votecount(nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominator_to_nominee_dict(),
                                                                                       say_voutecount=True)
    )
    nominate_ability = Ability(
        ability_name="Nominate",
        syntax_parser=syn.syntax_parser_constructor("nominate", [syn.SYNTAX_PARSER_PLAYERNAME]),
        submission_location=c.IN_THREAD,
        can_use_now=can_use.DAY,
        use_action_instant=nomination_use_action_instant,
    )
    abilities_list = []
    if config.do_votecounts:
        abilities_list.append(request_votecount_ability)
        abilities_list.append(request_voutecount_ability)
    if config.require_nominations_before_voting:
        abilities_list.append(nominate_ability)
    return abilities_list

next_id = 0
def get_next_id() -> int:
    """
    Returns the next Ability ID.
    """
    global next_id
    next_id += 1
    return next_id - 1

all_abilities: list["Ability"] = []

class Player:
    def __init__(self, username: str, alignment: int, rolecard_path: str, abilities: None | list["Ability"] = None,
                 willpower=0.0, redirect_player: "None | Player" = None, redirection_strength=0.0, focus_increase_on_redirection=1.0,
                 unresolved_actions: "None | list[UnresolvedPhaseEndAction]" = None, voting_power=1) -> None:
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

        voting_power is the number of votes this player has.
        """
        self.username = username
        self.alignment = alignment
        self.health = 1
        self.rolecard_path = rolecard_path
        self.protection = 0
        self.abilities = ([] if abilities is None else abilities) + get_default_abilities()
        self.willpower = willpower
        self.redirect_player = redirect_player
        self.redirection_strength = redirection_strength
        self.focus_increase_on_redirection = focus_increase_on_redirection
        self.unresolved_actions = [] if unresolved_actions is None else unresolved_actions
        self.voting_power = voting_power
        if config.require_nominations_before_voting:
            self.can_nominate = True
            self.target_of_nomination: Player | None = None
        assert self.focus_increase_on_redirection > 0
              

    def redirect_action(self, target_focus: float) -> bool:
        """
        Returns True if the action should be redirected; False otherwise.
        """
        return target_focus < self.redirection_strength
    
    def get_redirect(self, target_focus: float) -> 'Player':
        """
        Given target_focus, returns the player the action should target.
        """
        if self.redirect_player is None or not self.redirect_action(target_focus=target_focus):
            return self
        return self.redirect_player
    
    def get_redirect_focus_increase(self) -> float:
        return self.focus_increase_on_redirection

    def take_damage(self, damage_amount: float, *args) -> bool:
        """
        Returns True if the player died due to this damage, False otherwise.
        """
        original_damage_amount = damage_amount
        damage_amount = max(0, damage_amount - self.protection)
        self.protection = max(0, self.protection - original_damage_amount)
        self.health = max(0, self.health - damage_amount)
        return self.health == 0

    def receive_protection(self, protection_amount: float):
        self.protection += protection_amount
    
    def do_day_start_changes(self):
        self.protection = 0

    def get_alignment(self, *args):
        return self.alignment
    
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
        
class Ability:
    def __init__(self, 
                 ability_name: str, 
                 syntax_parser: Callable[[p.Post], list],
                 submission_location: int = c.IN_PM, 
                 acknowledge_and_verify: Callable = lambda *args : None,
                 can_use_now: Callable[[Player, "Ability", "game_state.GameState"], bool] = lambda *args : True,
                 use_action_instant: Callable = lambda *args : None, 
                 use_action_phase_end: Callable = lambda *args : None, 
                 ability_priority: float = 0, 
                 willpower_required_instant: float | None = None, 
                 willpower_required_phase_end: float | None = None, 
                 target_focus: float = 0, 
                 action_types: list[str] = [c.FALSE_ACTION],
                 ignore_action_deadline=False) -> None:
        """
        ability_name is the name of the ability.

        syntax_parser should take the original post as a Post object, and return a list of arguments for the action.
        If the post cannot be parsed, it should throw a ParsingException.
        If syntax_parser is returning a player, it should return the player object, not the username. If the username is invalid,
        throw a ParsingException.

        submission_location is the required place the action must be submitted. For example, if an action
        must be submitted in thread, but it's submitted in a PM instead, it should be ignored.

        can_use_now is a function that takes:
           - the acting player's Player object as the first parameter
           - the Abilty object being used as the second
           - the current gamestate as the third.
        It returns True if the action is allowed to be used now; False otherwise. 
        Typically, this can be used to enforce an action being used only in the Day or only in the Night, or
        only during even cycles, etc. However, this function can be written to have much, much more unorthodox conditions as 
        well. Notably, the use_action functions can make this function obsolete, but it is less confusing to have 
        conditions in here if possible.

        acknowledge_and_verify, use_action_instant, and use_action_phase_end take the following arguments:
        
         -player object for acting player
         -ability object for the ability being used (only for acknowledge_and_verify)
         -current gamestate
         -arguments from the result of syntax_parser (the list from syntax parser should be unpacked 
         when passing to these functions)
        
        These functions actually perform the action.
        This may include posting in thread, or modifying the gamestate in various ways.

        acknowledge_and_verify first verifies that the parameters provided are valid for the action (EG: a disloyal action
        submitted by a Mafia member should not work if the target is a mafia member, and this function would handle that). If 
        the parameters are valid, then it sends an acknowledgement of the submission in the user's role PM. If they are invalid,
        it throws an ActionException and use_action_instant & use_action_phase_end are not executed.

        use_action_instant should be called as soon as the action is submitted, while use_action_phase_end should be called at
        the end of the phase. Neither of these functions should ever throw exceptions.

        ability_priority is the order actions should occur in. Actions with a lower ability_priority go first.
        The nightkill and elimination both have priority 0.

        willpower_required is the required willpower to use the action. Similar to the system used in Sc2 Mafia's
        13th anniversary KRC, roleblocks are done by decreasing a player's willpower. If willpower_required is None, then
        there is no willpower required to use the action. Note that willpower_required, and willpower itself, can be negative.

        target_focus is a measure of how difficult it is to redirect the action. Every player p has (among other fields):
        - p.redirect_player
        - p.redirection_strength
        - p.focus_increase_on_redirection (must be >0)

        If (p.redirect_player is not None) and (target_focus < p.redirection_strength), then the action will be redirected to
        p.redirect_player. Then, this process is repeated with p.redirect_player, but using target_focus + p.focus_increase_on_redirection
        instead of target_focus - this continues until the action is not redirected, and has thus found its target.

        action_types is what types of action this ability is (use the enum in player.py); order DOES matter (indicates what
        types are a larger part of the action).

        instant_use_count is the number of times the instant ability has been used.
        phase_end_use_count is the number of times the phase end ability has been used.
        This behavior (as with most behaviors in Ability) must be enforced by modbot.py.

        ignore_action_deadline is whether the ability should be usable past the action deadline.
        Anything that can effect the gamestate should never have this turned on, to prevent race conditions.
        This is intended for things like /votecount.

        ------

        The ability ID is automatically assigned, and should not be accessed by custom roles.
        Note that all_abilities[self.id] == self - this is used to look up abilities easily.

        ------


        Overall action processing sequence:

        for each ability:
        - submission location correct (quit if not)
        - can use now (quit if not)
        - parse post (throw error? quit!)
        - acknowledge_and_verify (throw error? quit!)
        - for each player mentioned in this ability, process redirects
        - if willpower_required_instant is high enough -> do instant action. NEVER throws exception.

        later (at phase end)

        - if willpower_required_phase_end is high enough -> do delayed action. NEVER throws exception.

        -----

        """
        self.ability_name = ability_name
        self.syntax_parser = syntax_parser
        self.submission_location = submission_location
        self.can_use_now = can_use_now
        self.acknowledge_and_verify = acknowledge_and_verify
        self.use_action_instant = use_action_instant
        self.use_action_phase_end = use_action_phase_end
        self.ability_priority = ability_priority
        self.willpower_required_instant = willpower_required_instant
        self.willpower_required_phase_end = willpower_required_phase_end
        self.target_focus = target_focus
        self.action_types = action_types
        self.ignore_action_deadline = ignore_action_deadline
        self.instant_use_count = 0
        self.phase_end_use_count = 0

        self.id = get_next_id()

        all_abilities.append(self)


def votecount_request_syntax_parser(post: p.Post):
    if post.content.find("/votecount") == -1:
        raise ParsingException("This post did not request a votecount.")
    return []

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



    
        