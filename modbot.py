import fol_interface
import discord_interface
import roles
import player as p
import post as post_class
import roles_folder.host as host
import config
import game_state

import os
import random
import time
import asyncio
import inspect
import datetime
import restore

INVALID_FLIP = "This flip is invalid, and should never be posted. If you are seeing this, it is in error."


assert config.day_length > config.action_deadline and config.night_length > config.action_deadline
assert config.action_deadline >= 1

import constants as c
import main

first_import = True # To prevent code from being run more than once due to imports

rolelist = config.get_rolelist()

if first_import:
    first_import = False
    
    # Gamestate Variables Start (do not change unless debugging) (also includes program state variables)
    nightkill_choice = ''
    continue_posting_vcs = True
    posts_in_thread_at_last_vc = -1
    game_started = False
    action_submission_open = False
    game_end_announced_already = False
    game_restored_from_file = False
    # Gamestate Variables End

    # Warnings Begin

    if not config.rand_roles:
        print("Roles are NOT randomized! If this is used in actual play, roles must be randomized.")

    # Warnings End

    # Main program begin

    if config.rand_roles:
        random.seed(time.time())
        random.shuffle(rolelist)

    # mafia_list : list[str] = []

    playerlist_player_objects : list['p.Player'] = [] # This list is not restored by restore.py so it shouldn't be used directly except when initializing the gamestate

    for num in range(len(rolelist)):
        username = config.playerlist_usernames[num]
        playerlist_player_objects.append(rolelist[num](username))

    gamestate = game_state.GameState([player for player in playerlist_player_objects], # copying the list
                                    is_day=config.first_phase_is_day,
                                    phase_count=config.first_phase_count,
                                    wincon_is_parity=True)

    capitalization_fixer : dict[str, str] = dict()
    for player in config.playerlist_usernames:
        capitalization_fixer[player.lower()] = player

    all_abilities_are_disabled = False

def get_mafia_list(gamestate: game_state.GameState) -> list[str]:
    """
    Returns the usernames of all mafia members.
    """
    mafia_players = gamestate.filter_players(filter_func=lambda player : player.alignment == c.MAFIA, living_players_only=False)
    return list(map(lambda player : player.username, mafia_players))

async def announce_game_end():
    global continue_posting_vcs
    global game_end_announced_already


    if game_end_announced_already:
        return None
    await asyncio.sleep(5)
    # print(mafia_list)
    await fol_interface.announce_winner(gamestate.is_town_win(), mafia_members=get_mafia_list(gamestate))

    roles_list_to_post = list(map(
            lambda player : [player.username, get_flip(player.username, gamestate), "MAFIA" if player.alignment == c.MAFIA else "TOWN"], 
            gamestate.original_players
        ))
    roles_list_to_post.sort(key=lambda role : role[2]) # sort by alignment
    fol_interface.post_all_roles(roles_list_to_post)

    continue_posting_vcs = False
    game_end_announced_already = True
    while (len(fol_interface.to_post_queue.queue) != 0): # wait for posting queue to finish so game end is posted
        await asyncio.sleep(5)
    for task in main.tasks:
        task.cancel()
    return None

def process_nightkill(nightkill_username: str, gamestate: game_state.GameState):
    """
    Processes the nightkill.

    Parameters:

    - nightkill_username - The username of the player to be nightkilled; must be valid.
    - gamestate - The current gamestate
    """
    player_object = gamestate.get_player_object_living_players_only(nightkill_username)
    assert player_object is not None
    player_object.take_damage(1)

def process_elimination(eliminated_player_username: str, gamestate: game_state.GameState, was_tie: bool):
    flip = get_flip(eliminated_player_username, gamestate)
    gamestate.process_elimination(eliminated_player_username)
    print(f"Day {gamestate.phase_count} has just ended.")
    if eliminated_player_username != fol_interface.NO_EXE:
        fol_interface.post_cache_elimination(
            capitalization_fixer[eliminated_player_username.lower()], 
            was_tie,
            flip, 
            living_players=gamestate.get_living_players(), )
        fol_interface.send_message("# You have died.", eliminated_player_username, priority=1)
    else:
        fol_interface.post_cache_no_exe(was_tie=was_tie,
                                    living_players=gamestate.get_living_players(),
                                )

async def resolve_day_or_night_end_actions(elimination_or_nightkill: str, gamestate: game_state.GameState, was_tie: bool, is_day: bool):
    """
    - elimination_or_nightkill - The player who's voted out or nightkilled
    - gamestate - The gamestate object
    - was_tie - True if this was an elimination that randed, False otherwise
    - is_day - True if a day just ended, False if night ended
    """
    actions_to_be_resolved_at_phase_end : list[tuple[p.Ability | None, list, float]] = [] #Entries here are (ability object, [acting player object,
                                         # gamestate, parameters from syntax parser], ability priority)


    for player in gamestate.current_players:
        for unresolved_action in player.unresolved_actions:
            ability_object = p.all_abilities[unresolved_action.ability_id]
            actions_to_be_resolved_at_phase_end.append((ability_object, 
                                                        [player, gamestate, unresolved_action.parameters], 
                                                        ability_object.ability_priority))

    actions_to_be_resolved_at_phase_end.append((None, [], 0)) 
    # Above ensures there's an action with priority=0, so the elimination/nightkill is processed
    actions_to_be_resolved_at_phase_end.sort(key=lambda x : x[2])

    exe_or_nightkill_processed = False

    for ability, parameters, priority in actions_to_be_resolved_at_phase_end:
        if priority >= 0 and not exe_or_nightkill_processed:
            if is_day:
                process_elimination(elimination_or_nightkill, gamestate, was_tie)
            else:
                process_nightkill(elimination_or_nightkill, gamestate=gamestate)
            exe_or_nightkill_processed = True
            continue
        if ability is None: # This happens only for the filler ability to guarantee the elimination is processed.
            continue        # Since it isn't a real ability, it must be skipped; the earlier if statement does not guarantee it's skipped
        parameters[2] = process_redirects(parameters[2], ability) #parameters[2] is the output of the syntax parser
        action_function = ability.use_action_phase_end
        acting_player = parameters[0]
        assert type(acting_player) == p.Player
        if ability.willpower_required_instant is None or acting_player.willpower >= ability.willpower_required_instant:
            possible_awaitable = action_function(parameters[0], parameters[1], *parameters[2])
            if inspect.isawaitable(possible_awaitable):
                await possible_awaitable
            ability.phase_end_use_count += 1
    
    actions_to_be_resolved_at_phase_end = []

    await resolve_current_deaths(gamestate, during_night_death_flavor=not is_day, fix_votecount=is_day)

    gamestate.go_next_phase()
    await asyncio.sleep(2)
    restore.save_all()


async def resolve_current_deaths(gamestate: game_state.GameState, during_night_death_flavor=False, fix_votecount=True):
    """
    Kills all players whose health is at 0, and posts the deaths in the thread. This also posts anything in the cache, which
    can be used for death flavor / shot announcements.

    Players whose health is at 0 should always die immediately, so this should be called after any damage is dealt to a player,
    in case they die.

    Disabling the votecount fix should only be done when the votecount would be fixed by something else (for example,
    if these players are dying at the end of the night, the votecount will be reset at day start anyway).
    """
    about_to_die_players = gamestate.list_about_to_die_players()
    
    for about_to_die_player in about_to_die_players:
        flip = get_flip(about_to_die_player, gamestate)
        fol_interface.add_death_to_cache(about_to_die_player, f"has died{' during the night' if during_night_death_flavor else ''}!\n", flip)
        fol_interface.send_message("# You have died.", about_to_die_player, priority=1)

    gamestate.kill_about_to_die_players()


    # if len(about_to_die_players) > 0:
    #     fol_interface.to_post_cache += fol_interface.ping_string(gamestate.get_living_players(), include_alive_tags=True)
    fol_interface.post_cache()

    if len(about_to_die_players) > 0 and fix_votecount:
        await fol_interface.post_votecount(players_to_kill=about_to_die_players, nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominator_to_nominee_dict())

def resolve_name(nickname: str):
    """
    Removes an '@' before the name, and resolves by substring if needed.
    Details of substring resolution are explained in fol_interface.resolve_substring_alias, with `for_votecount == False`.
    """
    if len(nickname) > 0:
        nickname = nickname[1:] if nickname[0] == '@' else nickname
    return fol_interface.resolve_substring_alias(nickname, gamestate.get_living_players(), for_votecount=False)
    

def get_pregame_post_string():
    with open("about_zugbot.md", "r") as about_zugbot_file:
        pregame_post_string = about_zugbot_file.read()

    pregame_post_string += "# Parameters for this game \n"
    pregame_post_string += f"Day length: {config.day_length // 60} hours, {config.day_length % 60} minutes \n"
    pregame_post_string += f"Night length: {config.night_length // 60} hours, {config.night_length % 60} minutes \n"
    pregame_post_string += f"Action Deadline: {config.action_deadline} minutes before phase change \n"
    pregame_post_string += f"Multivoting allowed: {config.allow_multivoting} \n"
    pregame_post_string += f"No-Exe allowed: {config.allow_no_exe} \n"
    if config.allow_no_exe:
        pregame_post_string += f"No-Exe wins ties: {config.no_exe_wins_ties} \n"
    pregame_post_string += f"Votes Match VC Plugin: {config.resolve_like_vc_plugin} \n"
    pregame_post_string += f"Minimum Delay Between Votecounts: {config.votecount_time_interval} minutes\n"
    pregame_post_string += f"Minimum Postcount Between Votecounts: {config.votecount_post_interval} posts\n"
    pregame_post_string += f"Hosts: {', '.join(config.original_host_usernames)}\n"
    
    return pregame_post_string

def submit_nightkill(player_to_kill: str) -> bool:
    global nightkill_choice
    if not gamestate.is_day and gamestate.is_valid_nightkill(player_to_kill):
        nightkill_choice = capitalization_fixer[player_to_kill.lower()]
        return True
    return False

def get_flip(player: str, gamestate: game_state.GameState):
    print(f"Getting flip for {player}")
    if not gamestate.player_exists(player, count_dead_as_existing=True):
        return INVALID_FLIP
    flip_path = os.path.join(config.flips_folder, gamestate.get_flip_path(player))
    with open(flip_path, 'r') as flip_file:
        return flip_file.read()

async def give_role_pms(playerlist: list[str], gamestate: game_state.GameState):
    for player in playerlist:
        flip = get_flip(player, gamestate)
        player_object = gamestate.get_player_object_original_players(player)
        player_is_mafia = player_object is not None and player_object.alignment == c.MAFIA
        await fol_interface.give_role_pm(player, flip, config.game_name, 
                                         discord_links=[config.mafia_discord_link] if player_is_mafia else [], 
                                         teammates=get_mafia_list(gamestate) if player_is_mafia else None)
        
async def run_vc_bot():
    global posts_in_thread_at_last_vc
    global continue_posting_vcs
    while continue_posting_vcs:
        await asyncio.sleep(config.votecount_time_interval * 60)
        new_postcount = int(await fol_interface.get_number_of_posts_in_thread(topic_id=config.topic_id))
        if gamestate.is_day and game_started and new_postcount - posts_in_thread_at_last_vc > config.votecount_post_interval and continue_posting_vcs:
            await fol_interface.post_votecount(nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominator_to_nominee_dict())
            posts_in_thread_at_last_vc = new_postcount
    return None

def is_submission_location_correct(submission_location: int, topic_number_parameter: str | int, username: str):
    if int(submission_location) == c.IN_THREAD:
        return fol_interface.topic_is_main_thread(topic_number_parameter)
    elif int(submission_location) == c.IN_PM:
        return fol_interface.topic_is_pm(topic_number_parameter, username=username)
    return False

def send_feedback(feedback_string: str, sources: list[p.Player] | None, receivers: list[p.Player], action_types: list[str], was_instant: bool):

    pass

"""
Overall action processing sequence:

for each ability:
- submission location correct (quit if not)
- can_use_now (quit if not)
- parse post (throw error? quit!)
- acknowledge_and_verify (throw error? quit!)
- for each player mentioned in this ability, process redirects, making a new set of parameters for the instant action
- if willpower_required_instant is high enough -> do instant action. NEVER throws exception.

later

- for each player mentioned in this ability (original submission, not the result of processing redirects for the instant action), 
    process redirects, making a new set of parameters for the delayed action
- if willpower_required_phase_end is high enough -> do delayed action. NEVER throws exception.

"""

def process_redirects(action_parameters: list, ability: p.Ability, no_redirects=False) -> list:
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
        if type(result[index]) == p.Player:
            current_focus = ability.target_focus
            current_player = result[index]
            assert type(current_player) == p.Player
            no_more_redirects = False
            while not no_more_redirects:
                next_player = current_player.get_redirect(current_focus)
                current_focus += current_player.get_redirect_focus_increase()
                no_more_redirects = current_player == next_player
                current_player = next_player
            result[index] = current_player
    return result

async def process_post(post: post_class.Post, gamestate: game_state.GameState, action_submission_open: bool) -> None:
    player_object = gamestate.get_player_object_living_players_only(username=post.poster)
    if (player_object is None or all_abilities_are_disabled) and post.poster.lower() not in config.host_usernames:
        print("This player does not exist, or is not alive, or all non-host abilities are disabled.")
        return None
    is_host_post = player_object is None
    for ability in (player_object.abilities if not is_host_post else host.host_abilities):
        if not is_host_post and not ability.ignore_action_deadline and not action_submission_open:
            print("Action submission is not open, and this ability does not ignore the action deadline.")
            continue

        if not is_host_post and not is_submission_location_correct(ability.submission_location, post.topicNumber, post.poster):
            print(f"Submission location for {ability.ability_name} is wrong")
            continue
        print(f"Submission location for {ability.ability_name} is correct (or is a host command)")

        if not is_host_post and not ability.can_use_now(player_object, ability, gamestate):
            print(f"{ability.ability_name} cannot be used now.")
            continue
        print(f"{ability.ability_name} can be used now!")
        
        try:
            parameters = ability.syntax_parser(post)
        except roles.ParsingException as e:
            print(f"This message could not be parsed the ability: {ability.ability_name}. Error below: ")
            print(e.args)
            continue
        print(f"Input for {ability.ability_name} parsed successfully; the parameters are {parameters}")

        try:
            possible_awaitable = ability.acknowledge_and_verify(player_object, ability, gamestate, *parameters)
            if inspect.isawaitable(possible_awaitable):
                await possible_awaitable
        except roles.ActionException as e:
            print(f"{post.poster} attempted to use an action with the following parameters: {parameters},"
                  " but it threw an ActionException. Error below:")
            print(e.args)
            continue
        
        instant_parameters = process_redirects(parameters, ability, no_redirects=is_host_post)

        if is_host_post or ability.willpower_required_instant is None or player_object.willpower >= ability.willpower_required_instant:
            print(f"Running instant action with {len(instant_parameters)} parameters, plus the player and gamestate")
            possible_awaitable = ability.use_action_instant(player_object, gamestate, *instant_parameters)
            if inspect.isawaitable(possible_awaitable):
                await possible_awaitable
            ability.instant_use_count += 1

        if player_object is None:
            print("Note that host abilities cannot have delayed effects at the moment."
                  "If the host ability that was just used was purely instant, disregard this message.")
        else:
            player_object.record_action(ability.id, parameters)
        restore.save_all()
        

async def run_action_processor():
    while True:
        if action_submission_open:
            break
        await asyncio.sleep(4)
    await fol_interface.get_new_posts_with_pings(ignore_return=True)
    # DON'T process actions here. this is to avoid processing old pings
    while True:
        await asyncio.sleep(config.action_processor_sleep_seconds)
        new_posts = await fol_interface.get_new_posts_with_pings()
        print(f"There are {len(new_posts)} new posts to process")
        for post in new_posts:
            print(f"Processing post by: {post.poster}")
            await process_post(post, gamestate, action_submission_open)
            if gamestate.is_game_over():
                await announce_game_end()
                return None
    
def process_substitution_for_mafia_and_player_lists_and_nightkill(current_player: str, new_player: str):
    """
    Corrects playerlist_usernames and capitalization_fixer to include the new player instead of the current player.
    """
    global nightkill_choice
    # global mafia_list

    playerlist_fixer = lambda list_to_change : list(map(
        lambda player : new_player if player.lower() == current_player.lower() else player, list_to_change))

    config.playerlist_usernames = playerlist_fixer(config.playerlist_usernames)
    # mafia_list = playerlist_fixer(mafia_list)

    if current_player.lower() == nightkill_choice.lower():
        nightkill_choice = new_player

    del capitalization_fixer[current_player.lower()]
    capitalization_fixer[new_player.lower()] = new_player


async def wait_for_time(time_datetime: datetime.datetime):
    """
    Given a datetime, sleeps until that time is reached.
    """
    seconds_to_sleep = (time_datetime - datetime.datetime.now()).total_seconds()
    if seconds_to_sleep <= 0:
        return None
    print(f"Sleeping for {seconds_to_sleep} seconds")
    await asyncio.sleep(seconds_to_sleep)

async def start_game() -> bool:
    """
    This method:

    - Posts the pregame "About Zugbot" post
    - Hands out role PMs
    - Closes the thread, and sets the thread open timer
      - If the game start time isn't set in the config file, this is automatically set here


    """
    fol_interface.create_post(get_pregame_post_string(), topic_id_parameter=config.topic_id)
    await fol_interface.close_or_open_thread(close=True)
    await asyncio.sleep(5)
    playerlist_is_valid = await fol_interface.ensure_all_players_exist_and_are_spelled_correctly(playerlist=config.playerlist_usernames)
    if not playerlist_is_valid:
        print("Playerlist is not valid! Game start cancelled.")
        return False
    await give_role_pms(playerlist=config.playerlist_usernames, gamestate=gamestate)
    if config.game_start_time != '':
        game_start_time = datetime.datetime.strptime(config.game_start_time, "%Y-%m-%d %H:%M")
        await fol_interface.set_timer(f"{config.game_start_time}{config.utc_offset}", close=False)
        await wait_for_time(game_start_time)
    else:
        game_start_time = datetime.datetime.now()
        config.game_start_time = datetime.datetime.strftime(game_start_time, "%Y-%m-%d %H:%M")
    return True

def get_game_start_time() -> datetime.datetime:
    return datetime.datetime.strptime(config.game_start_time, "%Y-%m-%d %H:%M")

async def do_day_start(game_start_time: datetime.datetime) -> tuple[datetime.datetime, datetime.datetime]:
    """
    If the day start time has not passed, or the game is not restored from a file, this method:
        - Does the day start changes that apply to all players
        - Posts the day start post
        - Opens the thread
        - Sets the thread close time
        - Opens action submission
    Otherwise, does nothing.
    
    This returns the time at which action submission closes, and the time the day ends.
    """
    global action_submission_open
    global game_restored_from_file
    thread_close_time = game_start_time + datetime.timedelta(minutes=(
        (gamestate.phase_count - config.first_phase_count + 1) * (config.day_length + config.night_length) 
        - config.night_length
        - (config.day_length if not config.first_phase_is_day else 0)
        ))

    actions_close_time = thread_close_time - datetime.timedelta(minutes=config.action_deadline)
    day_start_time = thread_close_time - datetime.timedelta(minutes=config.day_length)
    if day_start_time < datetime.datetime.now() and game_restored_from_file:
        game_restored_from_file = False
        return actions_close_time, thread_close_time
    for player in gamestate.original_players:
        player.do_day_start_changes()
    fol_interface.start_day(gamestate.get_living_players(), gamestate.phase_count)
    await fol_interface.close_or_open_thread(close=False)
    
    assert type(thread_close_time) == datetime.datetime
    assert type(actions_close_time) == datetime.datetime
    await fol_interface.set_timer(thread_close_time.strftime("%Y-%m-%d %H:%M" + config.utc_offset), close=True)
    action_submission_open = True
    return actions_close_time, thread_close_time

async def do_night_start(game_start_time: datetime.datetime) -> tuple[datetime.datetime, datetime.datetime]:
    """
    If the night start time has not passed, or the game is not restored from a file, this method:
        - Posts the night start post
        - Sets the thread open time
        - Opens action submission
    Otherwise, does nothing.
    
    This returns the time at which action submission closes, and the time the night ends.
    """
    global action_submission_open
    global game_restored_from_file

    thread_open_time = game_start_time + datetime.timedelta(minutes=(
        (gamestate.phase_count - config.first_phase_count + 1) * (config.day_length + config.night_length)
        - (config.day_length if not config.first_phase_is_day else 0)
        ))
    actions_close_time = thread_open_time - datetime.timedelta(minutes=config.action_deadline)
    night_start_time = thread_open_time - datetime.timedelta(minutes=config.night_length)

    if night_start_time < datetime.datetime.now() and game_restored_from_file:
        game_restored_from_file = False
        return actions_close_time, thread_open_time

    await fol_interface.close_or_open_thread(close=True)
    fol_interface.announce_night_start(phase_number=gamestate.phase_count, living_players=gamestate.get_living_players())
    action_submission_open = True

    await fol_interface.set_timer(thread_open_time.strftime("%Y-%m-%d %H:%M" + config.utc_offset), close=False)
    return actions_close_time, thread_open_time



async def run_modbot():
    global game_started
    global nightkill_choice
    global continue_posting_vcs
    global action_submission_open
    

    if not game_started: # When run_modbot is called from a restored game, game_started may be True
        started_successfully = await start_game()
        if not started_successfully:
            return

    game_start_time = get_game_start_time()
    game_started = True

    while not gamestate.is_game_over():
        if gamestate.is_day: #going into this, gamestate should be day and have all night actions resolved
            actions_close_time, thread_close_time = await do_day_start(game_start_time=game_start_time)
            await wait_for_time(actions_close_time)
            action_submission_open = False
            await wait_for_time(thread_close_time + datetime.timedelta(seconds=config.eod_close_delay_seconds)) # type: ignore
            if gamestate.is_game_over(): # in case immediate actions ended the game
                break
            await fol_interface.close_or_open_thread(close=True)
            eliminated_player, was_tie = await fol_interface.decide_elimination()
            await resolve_day_or_night_end_actions(eliminated_player, gamestate, was_tie, is_day=True)
        else: #going into this, gamestate should be night and have the eliminated player dead
            actions_close_time, thread_open_time = await do_night_start(game_start_time=game_start_time)
            await wait_for_time(actions_close_time)
            action_submission_open = False
            await wait_for_time(thread_open_time)
            if gamestate.is_game_over(): # in case immediate actions ended the game
                break
            if not gamestate.is_valid_nightkill(nightkill_choice):
                nightkill_choice = gamestate.get_random_town()
            await resolve_day_or_night_end_actions(elimination_or_nightkill=nightkill_choice, gamestate=gamestate, was_tie=False, is_day=False)

    await announce_game_end()

