with open("discourse_api_key.txt", 'r') as discourse_api_key_file:
    api_key = discourse_api_key_file.read()

NOT_VOTING = "NO_VOTE"
UNKNOWN_VOTE = "unknown"
NO_EXE_ALIASES = list(map(lambda x : x.lower(), ["no-exe", "noelim", "noexe", "sleep"]))
NO_EXE = "sleep"

import post as p
import config
import time
import random
import re
import asyncio
from fluent_discourse import Discourse
import queue
import json
import os

fluent_discourse_client = Discourse(base_url=config.url, username=config.username, api_key=api_key)

to_post_cache = ''

username_to_role_pm_id = dict() # Example: username_to_role_pm_id["zugzwang"] == 9145
# usernames here are all lowercase
# This dict is filled out by give_role_pm
topic_id_to_last_post_accessed: dict[str, int] = dict()

previous_post_time = time.time()
to_post_queue = queue.PriorityQueue()
post_response_list = []
posts_added_to_queue = 0
last_time_vc_was_posted = time.time()

last_notification_id_seen = -1

def load_turbo_pm_ids() -> dict:
    if not os.path.exists(config.turbo_pm_json_path):
        turbo_json_file = open(config.turbo_pm_json_path, 'w')
        turbo_json_file.close()
        return dict()
    else:
        with open(config.turbo_pm_json_path, 'r') as turbo_pm_file:
            return json.load(turbo_pm_file)
        
def save_turbo_pm_ids() -> None:
    turbo_json_file = open(config.turbo_pm_json_path, 'w')
    json.dump(turbo_pm_ids, turbo_json_file)

turbo_pm_ids: dict = load_turbo_pm_ids()


vote_cleaner = re.compile(r"[^A-Za-z0-9\-\._]") # everything not in the list is a character that can't be
    # in a Discourse username



async def do_api_call(function_to_run, ignore_return: bool, max_retries=-1):
    """
    Runs function_to_run, and returns the result if ignore_return is False.
    function_to_run should take no parameters.

    If function_to_run gives an exception, retries up to max_exception_retries times, and 
    waits exception_retry_delay times inbetween retries. If max_exception_retries is exceeded,
    rethrows the exception.

    If max_retries is not -1, this is used instead of max_exception_retries.
    """
    retries = 0
    while(True):
        try:
            if ignore_return:
                function_to_run()
                return None
            else:
                return function_to_run()
        except Exception as e: #yes this is generally bad code but I don't know all the types of exceptions I could get here from a well-formed API call
            print(f"While trying to do an API call, we ran into an exception of type {type(e)}. There were {retries} retries so far.")
            print(f"The exception: {e}")
            if (config.max_exception_retries if max_retries == -1 else max_retries) == retries:
                print("Max retries exceeded. Rethrowing exception.")
                raise e
            retries += 1
            await asyncio.sleep(config.exception_retry_delay)


def user_exists(username: str) -> bool:
    """
    Returns True if username is an existing user on the site, and False otherwise.

    If the connection fails for other reasons (such as not having internet), this method 
    will still return False - so, rarely, this method could return an incorrect False.
    """
    try:
        fluent_discourse_client.u._(username).summary.json.get()
        return True
    except:
        return False

async def process_substitution(current_username: str, new_username: str, role_pm: str, player_is_mafia: bool, teammates: list[str] | None = None):
    """
    Creates a new role PM for the new user, and fixes username_to_role_pm_id accordingly.

    Do not call with invalid usernames. It will break.
    """
    # role_pm_id = username_to_role_pm_id[current_username.lower()]
    # username_to_role_pm_id[new_username.lower()] = role_pm_id
    # del username_to_role_pm_id[current_username.lower()]

    # await do_api_call(lambda : fluent_discourse_client.t._(str(role_pm_id)).invite.post({"user" : new_username, "custom_message" : ""}), ignore_return=True)
    # await do_api_call(lambda : fluent_discourse_client.t._(str(role_pm_id))._("remove-allowed-user").put({"username" : current_username}), ignore_return=True)

    await give_role_pm(new_username, role_pm, config.game_name, 
                                        discord_links=[config.mafia_discord_link] if player_is_mafia else [], 
                                        teammates=teammates if player_is_mafia else None)
    del username_to_role_pm_id[current_username.lower()]

async def run_fol_poster():
    global post_response_list
    while True:
        while not to_post_queue.empty():
            priority_to_discard, post_to_make = to_post_queue.get()
            post_response_list.append(await do_api_call(lambda : fluent_discourse_client.posts.json.post(post_to_make), ignore_return=False))           
            await asyncio.sleep(config.delay_between_posts)
        await asyncio.sleep(config.delay_between_post_checks)



def raw_page_to_posts(raw_page: str, topic_number: str | int) -> list[p.Post]:
        """
        Takes a raw page from discourse_site.com/raw/{topic_id}?page={page_number},
        and returns all the posts on that page as Post objects.

        Posts will be ordered by postnumber, ascendingly.
        """
        postStrings = raw_page.split("\n\n-------------------------\n\n")
        result = []
        for postString in postStrings:
            assert type(postString) == str
            if postString.find("#") ==  -1:
                continue
            poster, remainder = postString.split(" | ", 1)
            timestamp, remainder = remainder.split(" | #", 1)
            toBeAdded, content = remainder.split("\n\n", 1)
            postNumber = str(toBeAdded)
            result.append(p.Post(poster, timestamp, postNumber, content, str(topic_number)))
        return result

async def get_new_posts_in_thread(topic_id: int | str):
    """
    Returns all posts in thread with the specified topic_id, excluding those that
    were previously returned from this method.

    This should not be called on long threads - this will heavily slow down the program.

    This method can theoretically be broken by a deleted post in a very unlucky position, but 
    it is very unlikely.

    This method uses the raw text pages - while this requires parsing unlike the API, it allows for the efficient
    access of posts.
    """
    topic_id = str(topic_id)
    last_post_accessed = topic_id_to_last_post_accessed.get(topic_id, 0)
    new_page_to_access = max(1, last_post_accessed // 100)

    print(f"The last post accessed in {topic_id} is post {last_post_accessed}")

    posts: list[p.Post] = []
    all_new_posts_accessed = False
    while not all_new_posts_accessed:
        print(f"About to access page {new_page_to_access}")
        raw_page = await do_api_call(lambda : fluent_discourse_client.raw._(f"{topic_id}?page={new_page_to_access}").get(), ignore_return=False)
        assert type(raw_page) == str
        new_posts = raw_page_to_posts(raw_page=raw_page, topic_number=topic_id)
        posts += new_posts
        # last_post_number = int(posts[len(posts) - 1].postNumber)
        new_page_to_access += 1
        if not new_posts:
            all_new_posts_accessed = True
    topic_id_to_last_post_accessed[topic_id] = int(posts[-1].postNumber)
    posts = list(filter(lambda post : int(post.postNumber) > last_post_accessed, posts))
    return posts
    
async def get_new_posts_with_pings(ignore_return=False, accept_private_messages=True) -> list[p.Post]:
    """
    Gets all* new** posts that pinged*** the bot. They are returned in increasing order, by notification ID.
    This means they are also in chronological order.

    - *may have a limit on the number of posts returned; returns the most recent X posts if limited by it
    - **new, meaning since this method has been called last
    - ***includes posts that were PM notifications (unless accept_private_messages is False, which means even PMs have to ping)

    If ignore_return is True, this method's return value will likely be an empty list.
    This makes it faster to update the last-seen post.
    """
    global last_notification_id_seen
    print("get_new_posts_with_pings called")
    raw_notifications_dict = await do_api_call(lambda : fluent_discourse_client.notifications.json.get(), ignore_return=False)
    assert type(raw_notifications_dict) == dict
    notifications_list = raw_notifications_dict["notifications"]
    
    if len(notifications_list) == 0:
        return []

    result = []
    new_last_nofication_id_seen = notifications_list[0]["id"]
    notifications_list.sort(key=lambda notification : int(notification["id"]))
    assert type(new_last_nofication_id_seen) == int
    if not ignore_return:
        for notification in notifications_list:
            if last_notification_id_seen >= notification["id"]: # If this notification has been 
            # processed by the program already. I don't use whether it's read, so that entering the bot account doesn't break it.
                continue
            if notification["notification_type"] == 1 or (notification["notification_type"] == 6 and accept_private_messages): # if notification is a ping or private message
                topic_id_local = notification["topic_id"]
                if topic_id_local == config.topic_id or not accept_private_messages: # if post is in the main thread or PMs without pings aren't accepted
                    post_id = notification["data"]["original_post_id"]
                    post_json_dict = await do_api_call(lambda : fluent_discourse_client.posts._(post_id).json.get(), ignore_return=False)
                    assert type(post_json_dict) == dict
                    result.append(p.Post(poster=post_json_dict["username"], 
                            timestamp=post_json_dict["created_at"],
                            postNumber=post_json_dict["post_number"],
                            content=post_json_dict["raw"],
                            topicNumber=post_json_dict["topic_id"]))
                else:
                    print(f"Getting new posts in topic with id {topic_id_local}")
                    new_posts = await get_new_posts_in_thread(topic_id_local)
                    print(f"Finished getting posts from topic with id {topic_id_local}")
                    result += new_posts
    last_notification_id_seen = new_last_nofication_id_seen
    # The below lines guarantee that:
    # - Posts submitted in the same PM will be processed in order
    # - Posts submitted in different seconds will be processed in order
    result.sort(key=lambda post : post.postNumber)
    result.sort(key=lambda post : post.datetime_timestamp)
    for post in result:
        assert type(post) == p.Post
        print(post.displayString())
    return result


def send_message(message: str, username: str, priority=0) -> bool:
    """
    Sends a message in the PM of the player specified. Returns True if the message was successfully sent.

    Setting priority changes the position of the post in the posting queue (lower is faster).
    """

    topic_id_for_this_user = username_to_role_pm_id.get(username.lower(), -1)
    if topic_id_for_this_user == -1:
        return False
    create_post(message, topic_id_for_this_user, priority=priority)
    return True

def create_post(string_to_post: str, topic_id_parameter: int | str = -1, priority=0):
    """
    This method is nearly equivalent to

    `fluent_discourse_client.posts.json.post({"raw" : string_to_post, "topic_id" : topic_id})`

    However, this method (along with helper methods) ensures a minimum delay between posts, to avoid crashing
    due to being rate limited. Note this method only works if run_fol_poster is currently running.

    Also, a random string of characters is hidden in an HTML tag - this prevents Discourse from blocking posts
    for being the same as a previous post.

    This should be used for replies, not new topics.


    NOTE: Because of the delay between posts, this method will likely return before the post is created.

    To change the priority of posts, change the priority argument. Lower priority means it will be posted first.
    This is useful to avoid private feedback (such as a dayvig acknowledgement) delaying public announcements.
    """
    global posts_added_to_queue
    print("create_post called!")
    if config.debug_print_all_posts:
        print(string_to_post)
    if topic_id_parameter == -1:
        topic_id_parameter = config.topic_id
    string_to_post += f"\n<aaa{os.urandom(15).hex()}aaa>\n"
    to_post_queue.put(([priority, posts_added_to_queue], {"raw" : string_to_post, "topic_id" : topic_id_parameter}))
    posts_added_to_queue += 1



async def get_number_of_posts_in_thread(topic_id: int | str) -> str:
    thread_information = await do_api_call(lambda : fluent_discourse_client.t._(str(topic_id)).json.get(), ignore_return=False)
    assert type(thread_information) == dict
    return str(thread_information["highest_post_number"])

def resolve_substring_alias(voted_player: str, playerlist: list[str], for_votecount=True):
    """
    IMPORTANT: THIS METHOD SHOULD BE CALLED ONLY WITH *CLEANED* VOTES. This means a vote (here named vote_string) must have 
    been through the regex:

    ```
    vote_cleaner = re.compile(r"[^A-Za-z0-9\\-\\._]")
    vote_string = re.sub(vote_cleaner, "", vote_string)
    ```

    ---
    
    Resolves votes to playernames by substrings. Players that do not match any names,
    or match multiple names, are mapped to NOT_VOTING. 
    
    "NO_VOTE" is resolved to itself (which is equivalent to NOT_VOTING), because it is what non-voting players are considered to be voting.

    Anything in NO_EXE_ALIASES is mapped to NO_EXE.

    ---

    If for_votecount is False, this behaves the same, except unregonized names are returned as-is instead of being made
    NOT_VOTING, and a name in NO_EXE_ALIASES is not resolved to NO_EXE. Essentially, this resolves nicknames for purposes
    that are not related to voting. 

    If config.resolve_like_vc_plugin is True, and for_votecount is also True, then voted_player will be matched with the first
    username which it is a substring of, even if voted_player is a substring of multiple players. This is the only case
    in which playerlist's order matters.

    """
    if voted_player == NOT_VOTING and for_votecount:
        return NOT_VOTING
    if voted_player in NO_EXE_ALIASES and for_votecount:
        return NO_EXE
    num_matched = 0
    result = NOT_VOTING
    for player in playerlist:
        if voted_player.lower() == player.lower():
            return player
        elif player.lower().find(voted_player.lower()) != -1:
            if for_votecount and config.resolve_like_vc_plugin:
                return player
            num_matched += 1
            result = player
    if num_matched == 1:
        return result
    else:
        return NOT_VOTING if for_votecount else voted_player
    
def ping_string(living_players: list[str], include_alive_tags: bool) -> str:
    result = ''
    result += "[details='Ping']\n"
    result += "[alive]\n" if include_alive_tags else ''
    for player in living_players:
        result += f"@{player}\n"
    result += "[/alive]\n" if include_alive_tags else ''
    result += "[/details]\n"
    return result

def start_day(living_players: list[str], day_count: int):
    """
    Adds the day start announcement to the cache, then posts the cache.
    """
    global to_post_cache
    
    random.seed(time.time())
    living_players = living_players.copy()
    random.shuffle(living_players)

    string_to_post = f'# Day {day_count} has begun.\n'
    string_to_post += ping_string(living_players=living_players, include_alive_tags=True)

    to_post_cache += string_to_post
    post_cache()
    
def post_all_roles(username_flip_alignment_list: list[list]):
    string_to_post = "# All Roles: \n"
    for username, flip, alignment in username_flip_alignment_list:
        string_to_post += f"[details='{username} - {alignment}']\n"
        string_to_post += "[quote]\n"
        string_to_post += flip + "\n"
        string_to_post += "[/quote]\n"
        string_to_post += "[/details]\n"
    create_post(string_to_post)

async def close_or_open_thread(close=True):
    await do_api_call(lambda : fluent_discourse_client.t._(str(config.topic_id)).status.json.put({"status":"closed", "enabled":"true" if close else "false"}), ignore_return=True)


def get_votecount(votecount_dict: dict, nominated_players: list[str] | None = None) -> dict[str, list[str]]:
    """
    Takes the unprocessed votecount dictionary (grabbed from the json page), and returns a processed votecount dictionary.

    This means:
    Votes first have characters that are not [numbers, letters, dashes, dots, and underscores] removed. These cannot 
    be in Discourse usernames, so they can (and should) be ignored.

    Then, votes are resolved by substring, if there is an unambiguous match. If a substring matches more than one name, it is set to NOT_VOTING
    If allow_multivotes is False, players who are voting multiple people will be corrected to be not voting
    If allow_no_exe is False, people voting for no elimination will be corrected to not be voting. Note that votes for no exe
    must be one of those in NO_EXE_ALIASES (ignoring characters removed in the first step).

    The returned dictionary will be in the form:
    {
        "player_1" : ["player_voting_player_1", "other_player_voting_player_1", ...],
        etc.
        NO_EXE : ["player_voting_no_exe"], # This line will not be here, if allow_no_exe is False
        NOT_VOTING : ["player_not_voting", "other_player_not_voting", ...]
    }
    
    TODO: Determine if this preserves voting order; make this happen if it doesn't.
    """
    votes_list = votecount_dict["votecount"]
    playerlist = votecount_dict["alive"]
    nominated_players = nominated_players if nominated_players is not None else []

    all_votables = playerlist + ([NOT_VOTING, NO_EXE] if config.allow_no_exe else [NOT_VOTING])
    result = dict()
    for vote_option in all_votables:
        result[vote_option] = []
    
    for vote_voter_pair in votes_list: # vote_voter_pair is in form {"voter":"Frostwolf103","votes":["Bionic"]}
        voter = vote_voter_pair["voter"]
        votes = vote_voter_pair["votes"]
        if (not config.allow_multivoting and len(votes) != 1) or (not config.do_votecounts):
            votes = [NOT_VOTING]
        for num in range(len(votes)):
            votes[num] = re.sub(vote_cleaner, "", votes[num])
            votes[num] = resolve_substring_alias(votes[num], playerlist=playerlist)
            votes[num] = NOT_VOTING if votes[num] == NO_EXE and not config.allow_no_exe else votes[num]
            votes[num] = NOT_VOTING if ((votes[num].lower() not in [x.lower() for x in nominated_players]) 
                                        and config.is_botf) \
                                        and votes[num] != NO_EXE \
                                    else votes[num]
        votes = list(set(votes))
        for vote in votes:
            if not (len(votes) != 1 and vote == NOT_VOTING): #To prevent being listed as not voting, while voting players, which can happen if you multivote people and NO_VOTE
                result[vote].append(voter)
    return result

def votecount_to_elimination(votecount_dict):
    """
    Takes the votecount dictionary, and returns a tuple of (eliminated player, true if there was a rand else false).
    """
    votecount = get_votecount(votecount_dict)
    print("Votecount is: ")
    for votable in votecount:
        print(f"{votable} - {votecount[votable]}")
    del votecount[NOT_VOTING]
    
    votecount_as_list = list(votecount.items())
    votecount_as_list.sort(key=lambda x : len(x[1]), reverse=True)
    max_votes_received = len(votecount_as_list[0][1])
    print(f"The most votes any player received: {max_votes_received}")

    print(f"{votecount_as_list=}")
    potential_elimination_votable_voters_pairs = list(filter(
        lambda votable_voters_pair : len(votable_voters_pair[1]) == max_votes_received, 
                                                            votecount_as_list))
    print(f"{potential_elimination_votable_voters_pairs=}")
    elimination = list(map(lambda x : x[0],
        potential_elimination_votable_voters_pairs))
    print(f"{elimination=}")
    # filter gets all the votable_voters_pairs where the number of voters equals the max votes received
    # the map turns each one into the eliminated player (or NO_EXE)
    if len(elimination) == 1:
        return elimination[0], False
    if NO_EXE in elimination and config.no_exe_wins_ties: 
        return NO_EXE, False
    random.seed(time.time())
    print(f"There was a tie! The tied votable options were: {elimination}")
    return random.choice(elimination), True
    
def do_death_in_votecount(votecount: dict[str, list[str]], dead_player: str):
    """
    Takes a votecount (as generated by get_votecount()) and removes dead_player.
    """
    new_votecount = dict()
    players_voting_dead_player = []
    for votable in votecount:
        corrected_voters = list(filter(lambda voter : voter.lower() != dead_player.lower(), votecount[votable]))
        if votable.lower() == dead_player.lower():
            players_voting_dead_player = corrected_voters
        else:
            new_votecount[votable] = corrected_voters
    new_votecount[NOT_VOTING] = list(set(new_votecount[NOT_VOTING] + players_voting_dead_player))
    return new_votecount

async def correct_capilatization_in_discourse_username(username: str) -> tuple[str, bool]:
    """
    Given a username, returns the a tuple of the username with correct capitalization (matching the actual user),
    and True if the username was resolved successfully (false otherwise).

    WARNING: Not fully tested.
    Returns the username parameter if the username is not valid, or if this function breaks.

    Any of the following criteria make usernames invalid:
        - Username does not exist on site
        - Username contains '/'
        - Username contains ' '

    """
    if username.find("/") != -1 or username.find(" ") != -1:
        return username, False
    try:
        user_info = await do_api_call(lambda : fluent_discourse_client.u._(username).json.get(), ignore_return=False, max_retries=0)
        assert type(user_info) == dict
        corrected_username = user_info["user"]["username"]
        print(f"{corrected_username=}")
        return corrected_username, True
    except Exception as e:
        print(f"While resolving username {username}, we ran into the error below:")
        print(type(e))
        print(e)
        print(f"So, we are returning '{username}' as is.")
        return username, False


async def do_replacement_in_votecount(votecount: dict[str, list[str]], old_player: str, new_player: str):
    """
    Takes a votecount (as generated by get_votecount() and replaces old_player with new_player).

    new_player must have exactly correct capilatization.
    """
    print(f"Replacing {old_player} with {new_player} in votecount.")
    new_votecount = dict()
    for votable in votecount:
        new_votable = new_player if votable.lower() == old_player.lower() else votable
        new_votecount[new_votable] = list(map(lambda voter : new_player if voter.lower() == old_player.lower() else voter,
                                              votecount[votable]))
    return new_votecount

def write_botc_style_votecount(votecount: dict[str, list[str]], nominator_to_nominee_dict: dict[str, str]) -> str:
    result = '| Nominator | [color=FF000P]Nominee[/color] | # | Voters |\n'
    result += '|-|-|-|-|\n'
    if len(votecount[NO_EXE]) != 0:
        result += f' | | Sleep | {len(votecount[NO_EXE])} | {", ".join(votecount[NO_EXE])}\n'
    for nominator in nominator_to_nominee_dict:
        nominee = nominator_to_nominee_dict[nominator]
        result += f'{nominator} | {nominee} | {len(votecount[nominee])} | {", ".join(votecount[nominee])}\n'
    result += '| | --- |\n'
    result += f'| | **[color=777777]Not Voting[/color]** | {len(votecount[NOT_VOTING])} | {", ".join(votecount[NOT_VOTING])}'
    return result

def write_normal_votecount(votecount: dict[str, list[str]]) -> str:
    result = '[votecount] \n'

    non_voting_string = ""
    strings_and_vote_numbers: list[tuple[str, int]] = [] # does not include the Not Voting string
    for votable in votecount:
        num_votes_received = len(votecount[votable])
        if num_votes_received != 0:
            if votable == NOT_VOTING:
                non_voting_string = f"**Not Voting ({num_votes_received}):** {', '.join(votecount[votable])}" + "\n"
            else:
                strings_and_vote_numbers.append((f"**{votable} ({num_votes_received}):** {', '.join(votecount[votable])}" + "\n", num_votes_received))
    strings_and_vote_numbers.sort(key=lambda x : x[1], reverse=True)
    result += ''.join(list(map(lambda x : x[0], strings_and_vote_numbers)))
    result += "\n" + non_voting_string

    result += "[/votecount] \n"
    return result


                   
async def post_votecount(players_to_kill: list[str] | None = None,
                         replacements: list[tuple[str, str]] | None = None, nominated_players: list[str] | None = None,
                         nominator_to_nominee_dict: dict[str, str] | None = None, force_post=False,
                         say_voutecount=False) -> bool:
    """
    Posts the current votecount, respecting the parameters allow_multivotes and allow_no_exe.

    If post_number is not None, posts a retrospective votecount from that post, or does nothing if this post number
    is greater than the number of posts in the thread (or otherwise invalid).

    Returns True if the votecount was successfully posted.

    players_to_kill is players who are now dead, who should be removed from the votecount.
    replacements is players who need to be replaced - the votecount must be amended for them.

    If force_post is True, the votecount will be posted even if posting a votecount is on cooldown. 
    If replacements or players_to_kill are not None, then force_post is automatically set to True.
    """
    global last_time_vc_was_posted
    force_post = force_post or (replacements is not None) or (players_to_kill is not None)

    if not force_post and time.time() - last_time_vc_was_posted < 10:
        print("Votecount not posted, because it's on cooldown.")
        return False

    global post_response_list
    replacements = [] if replacements is None else replacements
    players_to_kill = [] if players_to_kill is None else players_to_kill
    print("Posting votecount. Most important parameters: ")
    print(f"{replacements=}")
    print(f"{players_to_kill=}")

    votecount_placeholder_string = "Loading votecount..."

    create_post(votecount_placeholder_string, config.topic_id)
    seconds_waited_for_loading_post = 0
    time_between_checks = 0.25
    max_wait_time_for_loading_post = 20
    while True:
        if seconds_waited_for_loading_post > max_wait_time_for_loading_post:
            print("Timed out when trying to post votecount.")
            return False
        if len(post_response_list) == 0:
            await asyncio.sleep(time_between_checks)
            seconds_waited_for_loading_post += time_between_checks
        else:
            this_response: dict = post_response_list.pop(0)
            print(this_response)
            if this_response["username"].lower() == config.username.lower() and \
                    this_response["raw"].startswith(votecount_placeholder_string) and \
                    votecount_placeholder_string and int(this_response["topic_id"]) == int(config.topic_id):
                post_to_get_vc_for = this_response["post_number"]
                post_to_get_vc_for_post_id = this_response["id"]
                break

    # number_of_posts_in_thread = await get_number_of_posts_in_thread(config.topic_id)
    
    # post_to_get_vc_for = number_of_posts_in_thread
    print("About to do the API call to get the votecount.")
    votecount_dict = await do_api_call(lambda : fluent_discourse_client.votecount._(str(config.topic_id))._(post_to_get_vc_for).json.get(), ignore_return=False)
    print("Finished the API call to get the votecount.")
    assert type(votecount_dict) == dict
    votecount = get_votecount(votecount_dict, nominated_players)
    for player_dying in players_to_kill:
        votecount = do_death_in_votecount(votecount=votecount, dead_player=player_dying)
    for player_being_replaced, replacement_player in replacements:
        votecount = await do_replacement_in_votecount(votecount=votecount, old_player=player_being_replaced,
                                                new_player=replacement_player)


    print(f"Votecount is: {votecount}")
    string_to_post = f'## Current {"Votecount" if not say_voutecount else "Voutecount"}\n'
    if config.is_botf:
        assert nominator_to_nominee_dict is not None
        string_to_post += write_botc_style_votecount(votecount, nominator_to_nominee_dict)
        string_to_post += '\n [details=""]\n'
    string_to_post += write_normal_votecount(votecount)
    if config.is_botf:
        string_to_post += "\n[/details]\n"
    
    await do_api_call(lambda : fluent_discourse_client.posts._(post_to_get_vc_for_post_id).json.put(
        {"raw" : string_to_post, "edit_reason" : "Votecount Added"}
    ), ignore_return=True)
    # create_post(string_to_post, config.topic_id)
    last_time_vc_was_posted = time.time()
    return True



# def votecount_to_elimination_old(votecount_dict):
#     """
#     Takes the votecount dictionary, and returns a tuple of (eliminated player, true if there was a rand else false).
#     Old / outdated method.
#     """
#     votes_list = votecount_dict["votecount"]
#     playerlist = list(map(lambda x : x["voter"], votes_list))
#     playerlist_with_votecounts = list(map(lambda x : [x, 0], playerlist))

#     for vote in votes_list:
#         voted_players = vote["votes"]
#         if len(voted_players) != 1:
#             final_vote = NOT_VOTING
#         else:
#             final_vote = resolve_substring_alias(voted_players[0], playerlist=playerlist)
#         if final_vote != NOT_VOTING:
#             player_index = playerlist.index(final_vote) #Should never raise error
#             playerlist_with_votecounts[player_index][1] += 1
    
#     players_with_max_votes = playerlist #Note! This cannot be an empty list, in case of no votes.
#     most_votes_received = 0
#     for player, num_votes_received in playerlist_with_votecounts:
#         if num_votes_received > most_votes_received:
#             players_with_max_votes = [player]
#             most_votes_received = num_votes_received
#         elif num_votes_received == most_votes_received and most_votes_received != 0:
#             players_with_max_votes.append(player)
    
#     random.seed(time.time())
#     return random.choice(players_with_max_votes), len(players_with_max_votes) != 1
    

async def decide_elimination():
    """
    Decides the elimination.

    This does *not* post the elimination.
    Instead, this method returns a tuple of (eliminated_player, True if there was a tie)
    
    """

    # fluent_discourse_client.t._(str(topic_id)).status.json.put({"status":"closed", "enabled":"true"}) #Locks thread

    number_of_posts_in_thread = await get_number_of_posts_in_thread(config.topic_id)
    eliminated_player, was_tie = votecount_to_elimination(
        await do_api_call(lambda : fluent_discourse_client.votecount._(str(config.topic_id))._(number_of_posts_in_thread).json.get(), ignore_return=False))

    assert type(eliminated_player) == str
    return eliminated_player, was_tie

def post_cache_no_exe(was_tie: bool, living_players: list[str]):
    global to_post_cache

    string_to_post = f"# {'Sleep won the tie.' if was_tie else ''} No one was eliminated. \n "
    #string_to_post += f"# Night {phase_number} begins now.\n" if not game_is_over else ''
    #string_to_post += ping_string(living_players=living_players, include_alive_tags=False)

    to_post_cache += string_to_post
    #create_post(string_to_post, topic_id_parameter=topic_id)

def post_cache_elimination(eliminated_player: str, was_tie: bool, flip: str, living_players: list[str]):
    global to_post_cache
    string_to_post = f"# @{eliminated_player} was eliminated{' at random among the tied players' if was_tie else ''}.\n"
    string_to_post += '[details="They were..."]\n'
    string_to_post += "[quote]\n"
    string_to_post += flip + "\n"
    string_to_post += "[/quote]\n"
    string_to_post += '[/details]\n'
    #string_to_post += f"# Night {phase_number} begins now.\n" if not game_is_over else ''
    
    #string_to_post += ping_string(living_players=living_players, include_alive_tags=False)

    to_post_cache += string_to_post
    #create_post(string_to_post, topic_id)

def announce_night_start(phase_number: int, living_players: list[str]):
    string_to_post = f"# Night {phase_number} begins now.\n"
    string_to_post += ping_string(living_players=living_players, include_alive_tags=False)
    create_post(string_to_post, config.topic_id)



def post_nightkill(dead_player: str, flip: str, phase_number: int, living_players: list[str], game_is_over: bool):
    string_to_post = f"# @{dead_player} has died during the night!\n"
    string_to_post += '[details="They were..."]\n'
    string_to_post += "[quote]\n"
    string_to_post += flip + "\n"
    string_to_post += "[/quote]\n"
    string_to_post += '[/details]\n'
    #string_to_post += f"# Day {phase_number + 1} begins now.\n" if not game_is_over else ''
    
    string_to_post += ping_string(living_players=living_players, include_alive_tags=True)

    create_post(string_to_post, config.topic_id)

def add_death_to_cache(dead_player: str, death_flavor: str, flip: str):
    """
    Adds the specified death to the cache. The death will be announced as:

    f"# @{dead_player} {death_flavor} \\n"
    """
    global to_post_cache
    string_to_add_to_cache = f"# @{dead_player} {death_flavor} \n"
    string_to_add_to_cache += '[details="They were..."]\n'
    string_to_add_to_cache += "[quote]\n"
    string_to_add_to_cache += flip + "\n"
    string_to_add_to_cache += "[/quote]\n"
    string_to_add_to_cache += '[/details]\n'
    to_post_cache += string_to_add_to_cache

def post_cache() -> bool:
    """
    Posts the current cache in to_post_cache. If to_post_cache is empty, does nothing.

    Returns True if a post was made, False otherwise.
    """
    global to_post_cache
    if to_post_cache == "":
        return False
    to_post_cache += "<filler>" # This is to avoid running into crashes. If a "..." or something similar is attempted, this will
    # crash, but if a post with an html tag that gets hidden is attempted, it will be posted successfully (though it will be blank).
    create_post(to_post_cache, topic_id_parameter=config.topic_id)
    to_post_cache = ''
    return True


async def announce_winner(town_win: bool, mafia_members: list[str]) -> None:
    string_to_post = f'# Congratulations to the {"[color=00ff00]Town[/color]" if town_win else "[color=red]Mafia[/color]"} for winning!\n'

    string_to_post += "The Mafia: \n"
    for player in mafia_members:
        string_to_post += player + "\n"
    
    create_post(string_to_post, config.topic_id)
    await close_or_open_thread(close=False)


def get_turbo_pm_id(player: str) -> int | str:
    global turbo_pm_ids
    return turbo_pm_ids.get(player.lower(), -1)

async def give_role_pm(player: str, role_pm: str, game_name: str, discord_links=None, teammates=None, is_turbo=False):
    """
    Note: The provided role_pm should not have "You are..." at the top, nor should it
    be surrounded by quote tags. This function will take care of that.

    All links in discord_links will be added at the bottom of the PM, outside of the rolecard.

    All teammates in teammates will be listed below Discord links.

    If is_turbo is True, the role PM will be given in a permanent turbo PM, should one exist. This is to speed up
    game start speeds.
    """
    if is_turbo and not os.path.exists(config.turbo_pm_json_path):
        turbo_json_file = open(config.turbo_pm_json_path, 'w')
        turbo_json_file.close()

    discord_links = [] if discord_links is None else discord_links
    teammates = [] if teammates is None else teammates

    full_pm = "# You are...\n"
    full_pm += "[quote]\n"
    full_pm += role_pm + "\n"
    full_pm += "[/quote]\n"

    for link in discord_links:
        full_pm += link + "\n"

    if not config.is_botf: # if not BOTF, wolves should be told teammates
        if len(teammates) != 0:
            full_pm += "Teammates: \n"
        for teammate in teammates:
            full_pm += f"{teammate} \n"

    if is_turbo:
        pm_id = get_turbo_pm_id(player)
        if pm_id != -1:
            create_post(full_pm, topic_id_parameter=pm_id)
    if not is_turbo or pm_id == -1:
        pm_name = f"{game_name} Rolecard - {player}" if not is_turbo else f"Turbo Rolecard - {player}"
        data = {
            "title" : pm_name,
            "raw" : full_pm,
            "target_recipients" : ','.join([player] + config.host_usernames),
            "archetype" : "private_message",
        }
        await do_api_call(lambda : fluent_discourse_client.posts.json.post(data), ignore_return=True)


    await asyncio.sleep(5)
    pm_id = await get_id_of_most_recently_sent_pm_with_specified_name(pm_name)
    if is_turbo:
        turbo_pm_ids[player.lower()] = pm_id
    print(f"ID for this PM: {pm_id}")
    username_to_role_pm_id[player.lower()] = pm_id
    
    await asyncio.sleep(11)


class TopicNotFoundException(Exception):
    pass

async def get_id_of_most_recently_sent_pm_with_specified_name(name: str):
    """
    Gets the topic ID of the most recently active* PM that matches the specified name.

    *May only include PMs that Zugbot created.

    Throws a TopicNotFoundException if no name matches.
    
    """
    private_message_sent_dict = await do_api_call(lambda : fluent_discourse_client.topics._("private-messages-sent")._(config.username).json.get(), ignore_return=False)
    assert type(private_message_sent_dict) == dict
    private_topics_list = private_message_sent_dict["topic_list"]["topics"]

    for topic in private_topics_list:
        if topic["title"] == name:
            return topic["id"]
    raise TopicNotFoundException(f"No topic with name '{name}'.")

async def set_timer(time_string: str, close: bool):
    """
    Sets a timer to open/close the thread.

    Example format for time_string: "2024-08-13 08:00+04:00"
    
    """
    print(f"Setting main thread to {'close' if close else 'open'} at {time_string}.")
    await do_api_call(lambda : fluent_discourse_client.t._(config.topic_id).timer.json.post({
        "time" : time_string,
        "status_type" : "close" if close else "open",
        }), ignore_return=True)


def topic_is_pm(topic_number_parameter: str | int, username: str):
    return int(topic_number_parameter) == int(username_to_role_pm_id[username.lower()])


def topic_is_main_thread(topic_number_parameter: str | int):
    return config.topic_id == int(topic_number_parameter)

async def ensure_all_players_exist_and_are_spelled_correctly(playerlist: list[str]):
    await asyncio.sleep(1)
    for player in playerlist:
        print(f"{player=}")
        corrected_capitalization, success = await correct_capilatization_in_discourse_username(player)
        print(f"{corrected_capitalization=}")
        if not success or player != corrected_capitalization:
            return False
    return True



# print(fluent_discourse_client.posts._(str(1456634)).json.get())

# relevant_post_ids = []
# for num in range(1456634 - 200, 1456634 + 50):
#     relevant_post_ids.append(num)

# print(fluent_discourse_client.t._(9656).posts.json.get({"post_ids[]" : relevant_post_ids}))

# async def testing():
#     posts = await get_new_posts_in_thread(9675)
#     for post_ in posts:
#         print(f"Postnumber is: {post_.postNumber}")
#         print(post_.displayString())

# asyncio.run(testing())

# fluent_discourse_client.t._(9139).timer.json.post({
#     "time" : "2024-08-13 08:00+04:00",
#     "status_type" : "close",
# })


# print(fluent_discourse_client.u.hippowolf.json.get()["user"]["username"])