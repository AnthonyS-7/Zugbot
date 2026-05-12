


from __future__ import annotations
import inspect
import typing
from typing import Callable
from typing_extensions import Concatenate, ParamSpec
from roles_folder.roles_exceptions import ParsingException, ActionException


import ability as a
import fol_interface
import constants as c
import post as p
import syntax_parser_standard as syn
import game_state
import config

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player as pl
    P = ParamSpec("P")
    Action_Function = Callable[Concatenate[pl.Player, game_state.GameState, P], typing.Any]


class InvalidAbilityParametersException(Exception):
    pass

next_id = 0

def get_next_id() -> int:
    """
    Returns the next Ability ID.
    """
    global next_id
    next_id += 1
    return next_id - 1

all_abilities: list["Ability"] = []

async def _add(action_1: 'Action', action_2: 'Action', player_object: 'pl.Player', gamestate: 'game_state.GameState', ability: 'Ability', *args):
    await action_1.run_action(player_object, gamestate, ability, *args)
    await action_2.run_action(player_object, gamestate, ability, *args)

class Action:
    """
    This is a wrapper class for the functions that execute actions. This wrapper allows adding functions together with '+', 
    to mean two actions get put together into a single ability.
    """
    def __init__(self, use_action: Action_Function[P]) -> None:
        self.use_action = use_action

    def __add__(self, other: 'Action'):
        new_use_action = lambda player_object, gamestate, ability, *args : _add(self, other, player_object, gamestate, ability, *args)
        return Action(new_use_action)

    async def run_action(self, player_object: 'pl.Player', gamestate: 'game_state.GameState', ability: 'Ability', *args):
        """
        Docstring for run_action
        
        :param player_object: The player using the action.
        :type player_object: 'pl.Player'
        :param gamestate: The gamestate.
        :type gamestate: 'game_state.GameState'
        :param ability: The ability object that this Action belongs to.
        :type ability: 'Ability'
        :param args: Other arguments this action takes.
        """
        print(f"run_action() called for ability {ability.ability_name}.")
        print(f"Extra parameters: {args}")
        possible_awaitable = self.use_action(player_object, gamestate, ability, *args) # type: ignore
        if inspect.isawaitable(possible_awaitable):
            await possible_awaitable

class AbilityModifiers:
    """
    When an ability calls a method that a player has, all of these are passed as keyword arguments.
    """
    def __init__(self,
                 invest_power=1.0,
                 protection_level=0,
                 damage_amount=0,
                 target_focus=0, # TODO: should this be in here? unsure.
                 ) -> None:
        self.invest_power = invest_power
        self.protection_level = protection_level
        self.target_focus = target_focus
        self.damage_amount = damage_amount


def process_redirects(action_parameters: list, ability: 'a.Ability', no_redirects=False) -> list:
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
        current_player: pl.Player = result[index]
        current_focus: int = ability.ability_modifiers.target_focus
        no_more_redirects = False
        while not no_more_redirects:
            try:
                next_player = current_player.get_redirect(current_focus)
                current_focus += current_player.get_redirect_focus_increase()
                no_more_redirects = current_player == next_player
                current_player = next_player
            except AttributeError: # means result[index] was not a player
                # WARNING: If some object, somehow, had get_redirect and get_redirect_focus_increase
                # then it would be redirected as if it was a player.
                no_more_redirects = True
        result[index] = current_player
    return result

class Ability:
    def __init__(self,
                 ability_name: str,
                 syntax_parser: 'syn.SyntaxParser',
                 action: 'Action',
                 submission_location: int = c.IN_PM,
                 is_instant: bool = False,
                 ability_restrictions: 'AbilityRestrictions | None' = None,
                 ability_modifiers: 'AbilityModifiers | None' = None,
                 ability_priority: float = 0,
                 willpower_required: float | None = None,
                 action_types: list[str] = [c.FALSE_ACTION],
                 ignore_action_deadline=False,
                 force_send_feedback_in_submission_location=False) -> None:
        """
        TODO: update ability docs
        """
        self.ability_name = ability_name
        self.syntax_parser = syntax_parser
        if ability_restrictions is not None:
            self.ability_restrictions = ability_restrictions
        elif is_instant:
            self.ability_restrictions = AbilityRestrictions(cooldown=0)
        else:
            self.ability_restrictions = AbilityRestrictions()
        self.action = action
        self.ability_modifiers = ability_modifiers if ability_modifiers is not None else AbilityModifiers()
        self.is_instant = is_instant

        self.ignore_action_deadline = ignore_action_deadline
        self.submission_location = submission_location
        self.ability_priority = ability_priority
        self.willpower_required = willpower_required
        self.action_types = action_types

        self.use_count = 0

        self.id = get_next_id()
        all_abilities.append(self)

        self.force_send_feedback_in_submission_location = force_send_feedback_in_submission_location
        if force_send_feedback_in_submission_location and submission_location == c.IN_THREAD:
            raise InvalidAbilityParametersException("Forcing feedback to be sent in the submission location is not allowed unless the submission location is the role PM or wolfchat.")
        if submission_location == c.IN_PM:
            self.force_send_feedback_in_submission_location = False # The default behavior is to send feedback there anyway


    async def use_ability_as_host(self, post: p.Post, gamestate: game_state.GameState):
        try:
            parameters = self.syntax_parser.parse_discourse_post(post)
        except ParsingException as e:
            print(f"This message could not be parsed the ability: {self.ability_name}. Error below: ")
            print(e.args)
            return
        print(f"Input for {self.ability_name} parsed successfully; the parameters are {parameters}")
        parameters = process_redirects(parameters, self, no_redirects=True)
        print(f"Running instant action with {len(parameters)} parameters, plus the gamestate")
        await self.action.run_action(None, gamestate, self, *parameters) # type: ignore
        self.use_count += 1


    async def attempt_to_use_ability(self, post: p.Post, player: 'pl.Player | None', gamestate: game_state.GameState, action_submission_open: bool, is_host_post: bool = False):
        """
        post: The post that may have attempted to use this ability
        player: The player that attempted to use an ability
        gamestate: The gamestate
        action_submission_open: Whether action deadline is passed
        is_host_post: Whether this is run by the host (removes many checks that could otherwise prevent the ability from happening)
        """
        print(f"Testing if {self.ability_name} was used.")
        if is_host_post:
            try:
                await self.use_ability_as_host(post, gamestate)
            except Exception as e:
                print(f"Tried to use {self.ability_name} but ran into unexpected exception of type {type(e)}. Exception below: ")
                print(e)
            return
        

        assert player is not None
        if not self.ignore_action_deadline and not action_submission_open:
            print("Action submission is not open, and this ability does not ignore the action deadline.")
            return
        if not is_submission_location_correct(self.submission_location, post.topicNumber, post.poster):
            print(f"Submission location for {self.ability_name} is wrong")
            return
        print(f"Submission location for {self.ability_name} is correct (or is a host command)")

        try:
            parameters = self.syntax_parser.parse_discourse_post(post)
        except ParsingException as e:
            print(f"This message could not be parsed for the ability: {self.ability_name}. Error below: ")
            print(e.args)
            return
        except Exception as e:
            print(f"Unintended exception of type {type(e)} occured. Exception is: ")
            print(e)
            return
        print(f"Input for {self.ability_name} parsed successfully; the parameters are {parameters}")

        success, error_message = self.ability_restrictions.verify(player, self, gamestate,
                                                        self.syntax_parser.parameter_list, parameters)
        if not success:
            if not self.force_send_feedback_in_submission_location:
                fol_interface.send_message(error_message, player.username, priority=5)
            else:
                fol_interface.create_post(string_to_post=error_message, topic_id_parameter=post.topicNumber, priority=5)
            print(f"This ability failed verification with message: {error_message}")
            return
        print("Ability passed verification!")
        if not self.force_send_feedback_in_submission_location:
            fol_interface.send_message("Action processed.", player.username, priority=5)
        else:
            fol_interface.create_post(string_to_post="Action processed.", topic_id_parameter=post.topicNumber, priority=5)

        if self.is_instant and (self.willpower_required is None or player.willpower >= self.willpower_required):
            parameters = process_redirects(parameters, self, no_redirects=is_host_post)
            print(f"Running instant action with {len(parameters)} parameters, plus the player and gamestate and ability")

            await self.action.run_action(player, gamestate, self, *parameters) # type: ignore
            self.use_count += 1
        else:
            player.record_action(self.id, parameters)



class AbilityRestrictions:
    """
    This class bundles together restrictions, such as x-shot and Cycling.
    """
    def __init__(self, shot_count=-1, cycling : list[str] | None = None,
                 cooldown=1, multitask_cost: dict[str, float] | None = None,
                 self_target_allowed=False,
                 loyal=False,
                 disloyal=False,
                 day_required=False,
                 night_required=True,
                 ita_required=False,
                 allowed_cycles: list[int] | None | Callable[[int], bool] = None
                 ) -> None:
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

        self_target_allowed: True if you can self-target.

        loyal: If True, and this player is mafia aligned, will prevent this action from being used on non-mafia players.
        disloyal: If True, and this player is mafia aligned, will prevent this action from being used on mafia players.

        day_required: If True, this ability cannot be used if it is not day.
        night_required: If True, this ability cannot be used if it is not night.

        allowed_cycles: This should be a list of all cycles the ability can be used in, \
                        or a function which takes a cycle number and returns true if the ability can be used, \
                        or None (in which case the ability can be used in all cycles that are at least 1)
        """
        self.shot_count = shot_count
        self.cycling = [] if cycling is None else cycling
        self.cooldown = cooldown
        self.multitask_cost: dict[str, float] = dict() if multitask_cost is None else multitask_cost
        self.self_target_allowed = self_target_allowed
        self.loyal = loyal
        self.disloyal = disloyal
        self.day_required = day_required
        self.night_required = night_required
        self.ita_required = ita_required
        if allowed_cycles is None:
            self.check_if_cycle_is_allowed: Callable[[int], bool] = lambda x : x >= 1
        elif type(allowed_cycles) == list:
            self.check_if_cycle_is_allowed: Callable[[int], bool] = lambda x : (x in allowed_cycles) # type: ignore
        else:
            self.check_if_cycle_is_allowed: Callable[[int], bool] = allowed_cycles # type: ignore

    def verify(self, player_using_action: pl.Player, ability_being_used: 'Ability', gamestate: game_state.GameState,
               formal_parameters_of_action: list, actual_parameters_of_action: list) -> tuple[bool, str]:
        
        # Shot count check:
        if self.shot_count != -1 and ability_being_used.use_count >= self.shot_count:
            return (False, f'This ability is {self.shot_count}-shot and has been used {ability_being_used.use_count} times.')
        
        # Cycling check:
        for ability in player_using_action.abilities:
            shared_cycles = set(ability_being_used.ability_restrictions.cycling).intersection(set(ability.ability_restrictions.cycling))
            if len(shared_cycles) != 0 and ability_being_used.use_count > ability.use_count:
                return (False, f"{ability.ability_name} (used {ability.use_count} times) and {ability_being_used.ability_name} (used {ability_being_used.use_count} times) are cycling."
                        f" Therefore, you cannot use {ability_being_used.ability_name} now.")

        # TODO: cooldown

        # TODO: multitask_cost check:
        for cost_key in self.multitask_cost:
            cost_of_this_ability = self.multitask_cost[cost_key]
            cost_of_actions_used_so_far = player_using_action.actions_costs.get(cost_key, 0) # Cost of instant actions used so far this phase
            total_cost_for_this_key = 0
            for unresolved_action in player_using_action.unresolved_actions:
                if unresolved_action.ability_id != ability_being_used.id:
                    total_cost_for_this_key += all_abilities[unresolved_action.ability_id].ability_restrictions.multitask_cost.get(cost_key, 0)
            if total_cost_for_this_key + cost_of_this_ability > 1:
                return (False, f"This ability cannot be used now, due to the \"{cost_key}\" multitask \
                        restriction. {'You can use /reset to withdraw the non-instant actions you have submitted this phase, allowing you to then submit this action. ' if cost_of_actions_used_so_far + cost_of_this_ability <= 1 else ''}")

        # Loyal / Disloyal check:
        for i in range(len(formal_parameters_of_action)):
            if formal_parameters_of_action[i] == syn.SYNTAX_PARSER_PLAYERNAME:
                targeted_player: pl.Player | None = actual_parameters_of_action[i]
                if targeted_player is not None:
                    alignments_same = targeted_player.alignment == player_using_action.alignment
                    if (self.loyal and not alignments_same):
                        return (False, f"This ability is loyal, but you are targeting someone not of your alignment.")
                    if (self.disloyal and alignments_same):
                        return (False, f"This ability is disloyal, but you are targeting someone of your alignment.")
                    if (player_using_action == targeted_player):
                        return (False, f"You are not allowed to self-target with this ability.")
        
        # Day / Night / Phase count check:
        if self.day_required and not gamestate.is_day:
            return (False, f"This ability can only be used during the day.")
        if self.night_required and gamestate.is_day:
            return (False, f"This ability can only be used during the night.")
        if not self.check_if_cycle_is_allowed(gamestate.phase_count):
            return (False, f'This ability cannot be used during cycle {gamestate.phase_count}.')
        
        # Passed all checks:
        return (True, '')
    
def is_submission_location_correct(submission_location: int, topic_number_parameter: str | int, username: str):
    if int(submission_location) == c.IN_THREAD:
        return fol_interface.topic_is_main_thread(topic_number_parameter)
    elif int(submission_location) == c.IN_PM:
        return fol_interface.topic_is_pm(topic_number_parameter, username=username) or fol_interface.topic_is_wolfchat(topic_number_parameter)
    elif int(submission_location) == c.IN_WOLFCHAT:
        return fol_interface.topic_is_wolfchat(topic_number_parameter)
    return False


"""
        # OUTDATED ABILITY DOCS
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

"""