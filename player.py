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
import role_standards.can_use_now_standard as can_use
import role_standards.syntax_parser_standard as syn
import role_standards.verify_standard as verify_standard
import constants as c
import inspect
from roles import ParsingException

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
        syntax_parser=syn.SyntaxParser("votecount", parameter_list=[]),
        verifier=verify_standard.DAY,
        action=Action(lambda playername, gamestate : fol_interface.post_votecount(nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominations())),
        is_instant=True,
        ignore_action_deadline=True
    )

def get_default_abilities():
    """
    Returns the default list of abilities, which is what all vanilla players have.

    This is not necessarily the empty list - vanilla players still have the ability to request votecounts,
    for example.
    """
    request_votecount_ability = get_votecount_ability()
    request_voutecount_ability = Ability( # Easter egg
        ability_name="Voutecount Request",
        syntax_parser=syn.SyntaxParser(command_name="voutecount", parameter_list=[]),
        verifier=verify_standard.DAY,
        action=Action(lambda playername, gamestate : fol_interface.post_votecount(nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominations(),
                                                                                       say_voutecount=True)),
        is_instant=True
    )
    nominate_ability = Ability(
        ability_name="Nominate",
        syntax_parser=syn.SyntaxParser("nominate", [syn.SYNTAX_PARSER_PLAYERNAME]),
        submission_location=c.IN_THREAD,
        verifier=verify_standard.DAY,
        action=Action(nomination_use_action_instant),
        is_instant=True
    )
    abilities_list = []
    if config.do_votecounts:
        abilities_list.append(request_votecount_ability)
        abilities_list.append(request_voutecount_ability)
    if config.is_botf:
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
        self.voting_power = voting_power

        self.redirect_player = redirect_player
        self.redirection_strength = redirection_strength
        self.focus_increase_on_redirection = focus_increase_on_redirection

        self.unresolved_actions = [] if unresolved_actions is None else unresolved_actions

        if config.is_botf:
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

async def _add(action_1: 'Action', action_2: 'Action', player_object: Player, gamestate: game_state.GameState, *args):
    await action_1.run_action(player_object, gamestate, *args)
    await action_2.run_action(player_object, gamestate, *args)

# type checking nonsense start
from typing import Callable
from typing_extensions import Concatenate, ParamSpec
P = ParamSpec("P")
Action_Function = Callable[Concatenate[Player, game_state.GameState, P], typing.Any]
# type checking nonsense end

class Action:
    """
    This is a wrapper class for the functions that execute actions. This wrapper allows adding functions together with '+', 
    to mean two actions get put together into a single ability.
    """
    def __init__(self, use_action: Action_Function[P]) -> types.NoneType:
        self.use_action = use_action
    
    def __add__(self, other: 'Action'):
        new_use_action = lambda player_object, gamestate, *args : _add(self, other, player_object, gamestate, *args)
        return Action(new_use_action)
    
    async def run_action(self, player_object: Player, gamestate: game_state.GameState, *args):
        possible_awaitable = self.use_action(player_object, gamestate, *args) # type: ignore
        if inspect.isawaitable(possible_awaitable):
            await possible_awaitable

class AbilityRestrictions:
    """
    This class bundles together restrictions, such as x-shot and Cycling.
    """
    def __init__(self, shot_count=-1, cycling : list[str] | None = None, cooldown=1, multitask_cost: dict[str, float] | None = None) -> None:
        """
        shot_count is the number of shots this ability has. -1 for infinite shot.

        cycling should be a list of strings - these strings indicate which other abilities it must cycle with.
        For example, to make a JOAT that must cycle abilities, making each ability have cycling=['joat'] works.
        More generally, if for two abilities A and B and a string x, we have:
          (x in A.ability_restrictions.cycling) and (x in B.ability_restrictions.cycling)
          then A cannot be used unless A.use_count <= B.use_count.

        cooldown is the number of cycles the player must wait before using the ability again. 
        0 means there is no cooldown (and therefore the ability can be used multiple times in a phase),
        1 is the typical cooldown of using the ability once each cycle,
        2 means there must be a cycle in between uses, etc.
        0 can only be used with instant actions.

        multitask_cost is how much the ability 'costs' to multitask. In any phase, for any string s, 
        the sum (over all abilities ab that a player has) of ab.ability_restrictions.multitask_cost[s] must be
        less than or equal to 1.
        """
        self.shot_count = shot_count
        self.cycling = [] if cycling is None else cycling
        self.cooldown = cooldown
        self.multitask_cost: dict[str, float] = dict() if multitask_cost is None else multitask_cost

def is_submission_location_correct(submission_location: int, topic_number_parameter: str | int, username: str):
    if int(submission_location) == c.IN_THREAD:
        return fol_interface.topic_is_main_thread(topic_number_parameter)
    elif int(submission_location) == c.IN_PM:
        return fol_interface.topic_is_pm(topic_number_parameter, username=username)
    return False

def process_redirects(action_parameters: list, ability: 'Ability', no_redirects=False) -> list:
    """
    This method takes the parameters for an action, and an Ability, and redirects the action's target(s) if needed.

    action_parameters are the parameters for the action, and ability is the Ability.

    This method returns a copy of action_parameters, with the redirects made.

    no_redirects should only be used for false actions (such as modkills and substitutions).

    """
    if no_redirects:
        return action_parameters.copy()
    result = action_parameters.copy()
    for index in range(len(result)):
        if type(result[index]) == Player:
            current_focus = ability.target_focus
            current_player = result[index]
            assert type(current_player) == Player
            no_more_redirects = False
            while not no_more_redirects:
                next_player = current_player.get_redirect(current_focus)
                current_focus += current_player.get_redirect_focus_increase()
                no_more_redirects = current_player == next_player
                current_player = next_player
            result[index] = current_player
    return result


class Ability:
    def __init__(self, 
                 ability_name: str, 
                 syntax_parser: 'syn.SyntaxParser',
                 action: 'Action',
                 verifier: 'verify_standard.Verifier' = verify_standard.ALWAYS_TRUE,
                 submission_location: int = c.IN_PM,
                #  acknowledge_and_verify: Callable = lambda *args : None,
                #  can_use_now: Callable[[Player, "Ability", "game_state.GameState"], bool] = lambda *args : True,
                 is_instant: bool = False,
                 ability_restrictions: AbilityRestrictions | None = None,
                #  use_action_instant: Callable = lambda *args : None, 
                #  use_action_phase_end: Callable = lambda *args : None, 
                 ability_priority: float = 0, 
                 willpower_required: float | None = None, 
                 target_focus: float = 0, 
                 action_types: list[str] = [c.FALSE_ACTION],
                 ignore_action_deadline=False) -> None:
        """
        TODO 6-12-2025: Update this documentation

        ability_name is the name of the ability.

        syntax_parser - This parses a post to determine if it used the action, and the parameters/targets of the action.
            See the SyntaxParser class for more info.

        submission_location is the required place the action must be submitted. For example, if an action
        must be submitted in thread, but it's submitted in a PM instead, it should be ignored.

        verifier 

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
        self.is_instant = is_instant
        self.ignore_action_deadline = ignore_action_deadline
        self.submission_location = submission_location
        self.ability_priority = ability_priority
        self.willpower_required = willpower_required
        self.target_focus = target_focus
        self.action_types = action_types

        if ability_restrictions is not None:
            self.ability_restrictions = ability_restrictions
        elif is_instant:
            self.ability_restrictions = AbilityRestrictions(cooldown=0)
        else:
            self.ability_restrictions = AbilityRestrictions()

        self.syntax_parser = syntax_parser
        self.verifier = verifier
        self.action = action

        # self.can_use_now = can_use_now
        # self.acknowledge_and_verify = acknowledge_and_verify
        
        self.use_count = 0

        self.id = get_next_id()
        all_abilities.append(self)

    def attempt_to_use_ability(self, post: p.Post, player: Player, gamestate: game_state.GameState, action_submission_open: bool, is_host_post: bool = False):
        """
        post: The post that may have attempted to use this ability
        player: The player that attempted to use an ability
        gamestate: The gamestate
        action_submission_open: Whether action deadline is passed
        is_host_post: Whether this is run by the host (removes many checks that could otherwise prevent the ability from happening)
        """
        if not is_host_post and not self.ignore_action_deadline and not action_submission_open:
            print("Action submission is not open, and this ability does not ignore the action deadline.")
            return
        if not is_host_post and not is_submission_location_correct(self.submission_location, post.topicNumber, post.poster):
            print(f"Submission location for {self.ability_name} is wrong")
            return
        print(f"Submission location for {self.ability_name} is correct (or is a host command)")

        try:
            parameters = self.syntax_parser.parse_discourse_post(post)
        except ParsingException as e:
            print(f"This message could not be parsed the ability: {self.ability_name}. Error below: ")
            print(e.args)
            return
        print(f"Input for {self.ability_name} parsed successfully; the parameters are {parameters}")

        if not is_host_post:
            success, required_condition = self.verifier.verify(player, self, gamestate,
                                                            self.syntax_parser.parameter_list, parameters) # TODO: make verifier enforce ability_restrictions
            if not success:
                fol_interface.send_message(required_condition, player.username, priority=5)
                print(f"This ability failed verification with message: {required_condition}")
                return
        print("Ability passed verification!")

        if not is_host_post:
            fol_interface.send_message("Action processed.", player.username, priority=5)
        
        if self.is_instant and (is_host_post or self.willpower_required is None or player.willpower >= self.willpower_required):
            parameters = process_redirects(parameters, self, no_redirects=is_host_post)
            print(f"Running instant action with {len(parameters)} parameters, plus the player and gamestate")
            await self.action.run_action(player, gamestate, *parameters) # type: ignore
            self.use_count += 1

        if is_host_post:
            print("Note that host abilities cannot have delayed effects at the moment."
                    "If the host ability that was just used was purely instant, disregard this message.")
        elif not self.is_instant:
            player.record_action(self.id, parameters)
    
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



