import fol_interface
import discord_interface

import player as p
import post as post_class
import config
import game_state
import roles_folder.host as host
import ability as a
import post as postModule


import os
import random
import time
import asyncio
import inspect
import datetime
import restore


INVALID_FLIP = "This flip is invalid, and should never be posted. If you are seeing this, it is in error."
STAND_BY_FOR_FLIP = "Hosts will reveal the flip manually."

assert config.day_length > config.action_deadline and config.night_length > config.action_deadline
assert config.action_deadline >= 1

import constants as c
import main

# Global variables (initializations here are mostly just for types; they are overwritten when starting the game or by restore.py)
rolelist = config.get_rolelist()
nightkill_choice = ''
continue_posting_vcs = True
posts_in_thread_at_last_vc = -1
game_started = False
action_submission_open = False
game_end_announced_already = False
game_restored_from_file = False
all_abilities_are_disabled = False
gamestate: game_state.GameState | None = None
capitalization_fixer : dict[str, str] = dict()

def reset_globals_to_defaults():
    global rolelist
    global nightkill_choice
    global continue_posting_vcs
    global posts_in_thread_at_last_vc
    global game_started
    global action_submission_open
    global game_end_announced_already
    global game_restored_from_file
    global all_abilities_are_disabled
    global gamestate
    global capitalization_fixer
    rolelist = config.get_rolelist()
    nightkill_choice = ''
    continue_posting_vcs = True
    posts_in_thread_at_last_vc = -1
    game_started = False
    action_submission_open = False
    game_end_announced_already = False
    game_restored_from_file = False
    all_abilities_are_disabled = False
    gamestate = None
    capitalization_fixer = dict()


def get_mafia_list(gamestate: "game_state.GameState") -> list[str]:
    """
    Returns the usernames of all mafia members.
    """
    mafia_players = gamestate.filter_players(filter_func=lambda player : player.alignment == c.MAFIA, living_players_only=False)
    return list(map(lambda player : player.username, mafia_players))

async def announce_game_end(gamestate: game_state.GameState):
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
    if config.disable_nightkill:
        return
    player_object = gamestate.get_player_object_living_players_only(nightkill_username)
    assert player_object is not None
    player_object.take_damage(a.AbilityModifiers(damage_amount=100)) # TODO: allow modifiers for the factional??

def process_elimination(eliminated_player_username: str, gamestate: game_state.GameState, was_tie: bool):
    if config.disable_elimination:
        return
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
    actions_to_be_resolved_at_phase_end : list[tuple[a.Ability | None, list, float]] = [] #Entries here are (ability object, [acting player object,
                                         # gamestate, parameters from syntax parser], ability priority)


    for player in gamestate.current_players:
        for unresolved_action in player.unresolved_actions:
            ability_object = a.all_abilities[unresolved_action.ability_id]
            actions_to_be_resolved_at_phase_end.append((ability_object, 
                                                        [player, gamestate, unresolved_action.parameters], 
                                                        ability_object.ability_priority))
        player.unresolved_actions = [] # remove all unresolved actions

    actions_to_be_resolved_at_phase_end.append((None, [], 0)) 
    # Above ensures there's an action with priority=0, so the elimination/nightkill is processed
    actions_to_be_resolved_at_phase_end.sort(key=lambda x : x[2])

    exe_or_nightkill_processed = False

    print(f"Resolving EoD/EoN actions. There are {len(actions_to_be_resolved_at_phase_end) - 1} actions to resolve.")

    for ability, parameters, priority in actions_to_be_resolved_at_phase_end:
        print(f"{priority=}")
        if priority >= 0 and not exe_or_nightkill_processed:
            if is_day:
                process_elimination(elimination_or_nightkill, gamestate, was_tie)
            else:
                process_nightkill(elimination_or_nightkill, gamestate=gamestate)
            exe_or_nightkill_processed = True
        if ability is None: # This happens only for the filler ability to guarantee the elimination is processed.
            continue        # Since it isn't a real ability, it must be skipped; the earlier if statement does not guarantee it's skipped
        parameters[2] = a.process_redirects(parameters[2], ability, gamestate) #parameters[2] is the output of the syntax parser
        acting_player = parameters[0]
        assert type(acting_player) == p.Player
        assert type(parameters[1]) == game_state.GameState
        if ability.willpower_required is None or acting_player.willpower >= ability.willpower_required:
            await ability.action.run_action(acting_player, parameters[1], ability, *parameters[2])
            ability.use_count += 1
    
    actions_to_be_resolved_at_phase_end = []

    await resolve_current_deaths(gamestate, during_night_death_flavor=not is_day, fix_votecount=is_day)

    gamestate.go_next_phase()
    await asyncio.sleep(2)
    restore.save_all()


async def resolve_current_deaths(gamestate: game_state.GameState, during_night_death_flavor=False, fix_votecount=True,
                                 hide_death_messages=False):
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
        if not hide_death_messages:
            fol_interface.add_death_to_cache(about_to_die_player, f"has died{' during the night' if during_night_death_flavor else ''}!\n", flip)
        fol_interface.send_message("# You have died.", about_to_die_player, priority=1)

    gamestate.sync_living_players()


    # if len(about_to_die_players) > 0:
    #     fol_interface.to_post_cache += fol_interface.ping_string(gamestate.get_living_players(), include_alive_tags=True)
    if not hide_death_messages:
        fol_interface.post_cache()

    if len(about_to_die_players) > 0 and fix_votecount:
        await fol_interface.post_votecount(players_to_kill=about_to_die_players, nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominations())

    
def resolve_name(nickname: str):
    """
    Removes an '@' before the name, and resolves by substring if needed.
    Details of substring resolution are explained in fol_interface.resolve_substring_alias, with `for_votecount == False`.
    """
    if len(nickname) > 0:
        nickname = nickname[1:] if nickname[0] == '@' else nickname
    assert gamestate is not None
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
    if gamestate is not None and not gamestate.is_day and gamestate.is_valid_nightkill(player_to_kill):
        nightkill_choice = capitalization_fixer[player_to_kill.lower()]
        return True
    return False

def get_flip(player: str, gamestate: game_state.GameState, giving_role_pm=False):
    print(f"Getting flip for {player}")
    if not gamestate.player_exists(player, count_dead_as_existing=True):
        return INVALID_FLIP
    if not giving_role_pm and config.do_not_flip:
        return STAND_BY_FOR_FLIP
    flip_path = os.path.join(config.flips_folder, gamestate.get_flip_path(player))
    with open(flip_path, 'r', encoding='utf-8') as flip_file:
        return flip_file.read()

async def give_role_pms(playerlist: list[str], gamestate: game_state.GameState):
    for player in playerlist:
        flip = get_flip(player, gamestate, giving_role_pm=True)
        player_object = gamestate.get_player_object_original_players(player)
        player_is_mafia = player_object is not None and player_object.alignment == c.MAFIA
        await fol_interface.give_role_pm(player, flip, config.game_name, 
                                         discord_links=[config.mafia_discord_link] if player_is_mafia else [], 
                                         teammates=get_mafia_list(gamestate) if player_is_mafia else None)
        await discord_interface.send_message_to_hosting_discord(f"Sent role PM for {player}.")
        
        
async def run_vc_bot():
    global posts_in_thread_at_last_vc
    global continue_posting_vcs
    while continue_posting_vcs:
        await asyncio.sleep(config.votecount_time_interval * 60)
        new_postcount = int(await fol_interface.get_number_of_posts_in_thread(topic_id=config.topic_id))
        if gamestate is not None and gamestate.is_day and game_started and new_postcount - posts_in_thread_at_last_vc > config.votecount_post_interval and continue_posting_vcs:
            await fol_interface.post_votecount(nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominations())
            posts_in_thread_at_last_vc = new_postcount
    return None


def send_feedback(feedback_string: str, sources: list[p.Player] | None, receivers: list[p.Player], action_types: list[str], was_instant: bool):
    pass

def determine_if_post_within_action_deadline(post: postModule.Post, require_action_deadline: bool, require_ita_window: bool):
    assert gamestate is not None
    phase_start_time = get_phase_start_time()
    # print(f"Determined that the phase start time was: {datetime.datetime.strftime(phase_start_time, "%Y-%m-%d %H:%M")}")
    # print(f"Timestamp of post in question: {datetime.datetime.strftime(post.datetime_timestamp, "%Y-%m-%d %H:%M")}")
    # print(f"Is phase start time naive? {phase_start_time.tzinfo is None}")
    # print(f"Is post timestamp naive? {post.datetime_timestamp.tzinfo is None}")
    if require_action_deadline:
        minutes_in_phase = config.day_length if gamestate.is_day else config.night_length
        action_end_time = phase_start_time + datetime.timedelta(minutes=(minutes_in_phase - config.action_deadline))
        # print(f"Determined that the phase end time was: {datetime.datetime.strftime(action_end_time, "%Y-%m-%d %H:%M")}")
        if post.datetime_timestamp < phase_start_time or post.datetime_timestamp > action_end_time:
            return False
    if require_ita_window:
        if not config.include_itas:
            return False
        in_ita_window = False
        for ita_window_times in config.ita_windows:
            ita_window_start_time = phase_start_time + datetime.timedelta(minutes=ita_window_times["start"])
            ita_window_end_time = phase_start_time + datetime.timedelta(minutes=ita_window_times["end"])
            if ita_window_start_time <= post.datetime_timestamp and post.datetime_timestamp <= ita_window_end_time:
                in_ita_window = True
                break
        if not in_ita_window:
            return False
    return True



def get_phase_start_time():
    assert gamestate is not None
    game_start_time = get_game_start_time(include_timezone=True) 
    minutes_between_game_start_and_phase_start = (gamestate.phase_count - config.first_phase_count) * (config.night_length + config.day_length)
    if gamestate.is_day and not config.first_phase_is_day: # TODO: are night-phase game starts handled correctly?
        minutes_between_game_start_and_phase_start += config.night_length
    if not gamestate.is_day and config.first_phase_is_day: 
        minutes_between_game_start_and_phase_start += config.day_length
    phase_start_time = game_start_time + datetime.timedelta(minutes=minutes_between_game_start_and_phase_start)
    return phase_start_time

async def process_post(post: post_class.Post, gamestate: game_state.GameState, action_submission_open: bool) -> None:
    player_object = gamestate.get_player_object_living_players_only(username=post.poster)
    if (player_object is None or all_abilities_are_disabled) and post.poster.lower() not in config.host_usernames:
        print("This player does not exist, or is not alive, or all non-host abilities are disabled.")
        return None
    is_host_post = player_object is None
    for ability in (player_object.abilities if not is_host_post else host.host_abilities):
        actions_deadline_open = determine_if_post_within_action_deadline(post, True, False)
        ita_deadline_open = determine_if_post_within_action_deadline(post, False, True)
        await ability.attempt_to_use_ability(post=post, player=player_object, gamestate=gamestate, 
                                             action_submission_open=actions_deadline_open, 
                                             ita_submission_open=ita_deadline_open,
                                             is_host_post=is_host_post)
        restore.save_all()
        
async def run_action_processor():
    while True:
        if action_submission_open:
            break
        await asyncio.sleep(4)
    await fol_interface.get_new_posts_with_pings(ignore_return=True)
    # we DON'T process actions here. this is to avoid processing old pings
    while True:
        await asyncio.sleep(config.action_processor_sleep_seconds)
        new_posts = await fol_interface.get_new_posts_with_pings()
        print(f"There are {len(new_posts)} new posts to process")
        for post in new_posts:
            print(f"Processing post by: {post.poster}")
            if gamestate is not None:
                await process_post(post, gamestate, action_submission_open)
                if gamestate.is_game_over():
                    await announce_game_end(gamestate)
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

def add_player_to_player_lists(new_player: str):
    """
    Corrects playerlist_usernames and capitalization_fixer to include the new player.
    """
    config.playerlist_usernames.append(new_player)
    capitalization_fixer[new_player.lower()] = new_player




async def wait_for_time(time_datetime: datetime.datetime):
    """
    Given a datetime, sleeps until that time is reached.
    """
    if time_datetime.tzinfo == None or time_datetime.tzinfo.utcoffset(time_datetime) == None: # if input time is naive
        seconds_to_sleep = (time_datetime - datetime.datetime.now()).total_seconds()
    else:
        seconds_to_sleep = (time_datetime - datetime.datetime.now(datetime.UTC)).total_seconds()
    if seconds_to_sleep <= 0:
        return None
    print(f"Sleeping for {seconds_to_sleep} seconds")
    await asyncio.sleep(seconds_to_sleep)

async def post_ita_window_announcements():
    while gamestate is None or game_started == False:
        await asyncio.sleep(2)
    current_phase = gamestate.phase_count - 1
    while True:
        if gamestate.is_day == False:
            night_end_time = get_phase_start_time() + datetime.timedelta(minutes=config.night_length)
            await asyncio.sleep(15)
            await wait_for_time(night_end_time)
        if gamestate.is_day:
            if current_phase == gamestate.phase_count:
                await asyncio.sleep(15)
                continue
            current_phase = gamestate.phase_count
            phase_start_time = get_phase_start_time()
            ita_window_counter = 1
            for ita_window_times in config.ita_windows:
                ita_window_start_time = phase_start_time + datetime.timedelta(minutes=ita_window_times["start"])
                ita_window_end_time = phase_start_time + datetime.timedelta(minutes=ita_window_times["end"])
                await wait_for_time(ita_window_start_time)
                if config.include_itas:
                    fol_interface.create_post(f"# ITA Window {ita_window_counter} has begun! Use /ITA [playername] @Zugbot to shoot. \n"
                                            "- You *must* ping Zugbot for your shot to be registered. \n" \
                                            "- Hosts will post flips manually. \n")
                    await discord_interface.send_message_to_hosting_discord(f"Posted ITA window {ita_window_counter} start announcement.")
                await wait_for_time(ita_window_end_time)
                if config.include_itas:
                    fol_interface.create_post(f"# ITA Window {ita_window_counter} has ended!")
                    await discord_interface.send_message_to_hosting_discord(f"Posted ITA window {ita_window_counter} end announcement.")
                ita_window_counter += 1
            


async def start_game() -> bool:
    """
    This method:

    - Initializes modbot.py's global variables
    - Posts the pregame "About Zugbot" post
    - Hands out role PMs
    - Closes the thread, and sets the thread open timer
      - If the game start time isn't set in the config file, this is automatically set here

    """
    global rolelist
    global nightkill_choice
    global continue_posting_vcs
    global posts_in_thread_at_last_vc
    global game_started
    global action_submission_open
    global game_end_announced_already
    global game_restored_from_file
    global all_abilities_are_disabled
    global gamestate
    global capitalization_fixer

    rolelist = config.get_rolelist()
    nightkill_choice = ''
    continue_posting_vcs = True
    posts_in_thread_at_last_vc = -1
    game_started = False
    action_submission_open = False
    game_end_announced_already = False
    game_restored_from_file = False
    all_abilities_are_disabled = False

    print("About to decide roles.")
    if config.rand_roles:
        random.seed(time.time())
        random.shuffle(rolelist)

    if len(config.playerlist_usernames) != config.playercount:
        print(f"The playercount of this setup is {config.playercount}, but there are {len(config.playerlist_usernames)} players in the playerlist.")
        return False

    playerlist_player_objects : list['p.Player'] = []

    for num in range(len(rolelist)):
        username = config.playerlist_usernames[num]
        playerlist_player_objects.append(rolelist[num](username))
        print(f"Created player object {num + 1}.")

    gamestate = game_state.GameState([player for player in playerlist_player_objects], # copying the list
                                    is_day=config.first_phase_is_day,
                                    phase_count=config.first_phase_count,
                                    wincon_is_parity=True)

    capitalization_fixer = dict()
    for player in config.playerlist_usernames:
        capitalization_fixer[player.lower()] = player

    fol_interface.create_post(get_pregame_post_string(), topic_id_parameter=config.topic_id)
    await fol_interface.close_or_open_thread(close=True)
    await asyncio.sleep(5)
    playerlist_is_valid = await fol_interface.ensure_all_players_exist_and_are_spelled_correctly(playerlist=config.playerlist_usernames)
    if not playerlist_is_valid:
        print("Playerlist is not valid! Game start cancelled.")
        return False
    await give_role_pms(playerlist=config.playerlist_usernames, gamestate=gamestate)
    await fol_interface.make_wolfchat_pm(
        list(filter(lambda user : gamestate.get_player_object_original_players(user).alignment == c.MAFIA, config.playerlist_usernames))) # type: ignore
    if config.game_start_time != '':
        game_start_time = datetime.datetime.strptime(config.game_start_time, "%Y-%m-%d %H:%M")
        await fol_interface.set_timer(f"{config.game_start_time}{config.utc_offset}", close=False)
        await wait_for_time(game_start_time)
    else:
        game_start_time = datetime.datetime.now()
        config.game_start_time = datetime.datetime.strftime(game_start_time, "%Y-%m-%d %H:%M")
    return True

def get_game_start_time(include_timezone=False) -> datetime.datetime:
    if not include_timezone:
        return datetime.datetime.strptime(config.game_start_time, "%Y-%m-%d %H:%M")
    else:
        return datetime.datetime.strptime(f"{config.game_start_time} {config.utc_offset.replace(":", "")}", "%Y-%m-%d %H:%M %z")

async def do_day_start(game_start_time: datetime.datetime, gamestate: game_state.GameState) -> tuple[datetime.datetime, datetime.datetime]:
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

async def do_night_start(game_start_time: datetime.datetime, gamestate: game_state.GameState) -> tuple[datetime.datetime, datetime.datetime]:
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
    
    for player in gamestate.original_players:
        player.do_night_start_changes()

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
        
    assert gamestate is not None
    game_start_time = get_game_start_time()
    game_started = True
    print("Game started.")

    while not gamestate.is_game_over():
        if gamestate.is_day: #going into this, gamestate should be day and have all night actions resolved
            actions_close_time, thread_close_time = await do_day_start(game_start_time=game_start_time, gamestate=gamestate)
            await wait_for_time(actions_close_time)
            action_submission_open = False
            await wait_for_time(thread_close_time) # type: ignore
            if gamestate.is_game_over(): # in case immediate actions ended the game
                break
            await fol_interface.close_or_open_thread(close=True)
            eliminated_player, was_tie = await fol_interface.decide_elimination()
            await discord_interface.send_message_to_hosting_discord("# Day has ended.")
            await resolve_day_or_night_end_actions(eliminated_player, gamestate, was_tie, is_day=True)
        else: #going into this, gamestate should be night and have the eliminated player dead
            actions_close_time, thread_open_time = await do_night_start(game_start_time=game_start_time, gamestate=gamestate)
            await wait_for_time(actions_close_time)
            action_submission_open = False
            await wait_for_time(thread_open_time)
            if gamestate.is_game_over(): # in case immediate actions ended the game
                break
            if not gamestate.is_valid_nightkill(nightkill_choice):
                nightkill_choice = gamestate.get_random_town()
            await discord_interface.send_message_to_hosting_discord("# Night has ended.")
            await resolve_day_or_night_end_actions(elimination_or_nightkill=nightkill_choice, gamestate=gamestate, was_tie=False, is_day=False)

    await announce_game_end(gamestate)
