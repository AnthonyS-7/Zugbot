"""
This script allows anyone to run turbos with Zugbot. Only one turbo can be running at a time.
"""


import fol_interface
import asyncio
import random
import config
import constants as c
import main
import player
import post
from roles_10_7_2024 import syntax_parser_standard as syn
import roles
import inspect
import turbo_setup

turbo_task: asyncio.Task | None = None
posting_queue_task:  asyncio.Task | None = None

playerlist: list[str] = []
day_length_minutes = 10
night_length_minutes = 3
topic_id = 9145
allow_multivoting = True

setup = turbo_setup.get_setup("popcorn")
intended_player_cap = 3

ALLOWED_SETUPS = [setup.game_name.lower() for setup in turbo_setup.setups]
ALLOWED_TOPIC_IDS = [9524, 9145]

async def do_turbos():
    global turbo_task
    global posting_queue_task
    turbo_task = asyncio.create_task(run_turbo_listener())
    posting_queue_task = asyncio.create_task(fol_interface.run_fol_poster())
    await turbo_task
    await posting_queue_task

def get_turbo_help_string() -> str:
    with open("about_zugbot_turbos.md") as about_zugbot_turbos_file:
        return about_zugbot_turbos_file.read()

def display_help_post(discard_1, discard_2, post: post.Post):
    string_to_post = get_turbo_help_string()
    string_to_post += "\nAvailable Setups: " + ', '.join([setup.game_name for setup in turbo_setup.setups])
    fol_interface.create_post(string_to_post, topic_id_parameter=post.topicNumber)

def start_game(discard_1, discard_2, post: post.Post):
    global playerlist
    if len(playerlist) != intended_player_cap:
        fol_interface.create_post(f"The game cannot be started, because it is not full. However, " 
                                  "if you want, you can change the number of players required to fill.", topic_id_parameter=post.topicNumber)
    elif setup is None:
        fol_interface.create_post(f"No setup is selected, so the game cannot start yet.", topic_id_parameter=post.topicNumber)
    elif not setup.supports_playercount(intended_player_cap):
        fol_interface.create_post(f"This setup does not support {intended_player_cap} players. Change the player cap or setup.", 
                                  topic_id_parameter=post.topicNumber)
    else:
        fol_interface.create_post(f"Starting game.", topic_id_parameter=post.topicNumber)
        assert turbo_task is not None
        assert posting_queue_task is not None
        turbo_task.cancel()
        posting_queue_task.cancel()

def join_game(discard_1, discard_2, post: post.Post):
    global playerlist

    if post.poster.lower() in [player.lower() for player in playerlist]:
        fol_interface.create_post(f"{post.poster} is already in the game!", topic_id_parameter=post.topicNumber)
    elif len(playerlist) == intended_player_cap:
        fol_interface.create_post(f"The game is already full!", topic_id_parameter=post.topicNumber)
    else:
        fol_interface.create_post(f"{post.poster} has joined the game.", topic_id_parameter=post.topicNumber)
        playerlist.append(post.poster)

def leave_game(discard_1, discard_2, post: post.Post):
    global playerlist
    if post.poster.lower() in [player.lower() for player in playerlist]:
        fol_interface.create_post(f"{post.poster} has left the game.", topic_id_parameter=post.topicNumber)
        playerlist.remove(post.poster)
    else:
        fol_interface.create_post(f"{post.poster} is not in the game, so they cannot leave.", topic_id_parameter=post.topicNumber)

def modify_game_settings(discard_1, discard_2, setting_to_change: str, value: str, post: post.Post):
    global day_length_minutes
    global night_length_minutes
    global topic_id
    global allow_multivoting
    global setup
    global intended_player_cap
    if setting_to_change.lower() == "day_length":
        try:
            value_int = int(value)
            assert value_int > 1
            fol_interface.create_post(f"Days are now {value_int} minutes long.", topic_id_parameter=post.topicNumber)
            day_length_minutes = value_int
        except ValueError | AssertionError:
            fol_interface.create_post(f"{value} is not an integer greater than 1.", topic_id_parameter=post.topicNumber)
    elif setting_to_change.lower() == "night_length":
        try:
            value_int = int(value)
            assert value_int > 1
            fol_interface.create_post(f"Nights are now {value_int} minutes long.", topic_id_parameter=post.topicNumber)
            night_length_minutes = value_int
        except ValueError:
            fol_interface.create_post(f"{value} is not an integer.", topic_id_parameter=post.topicNumber)
        except AssertionError:
            fol_interface.create_post(f"{value} is not an integer greater than 1.", topic_id_parameter=post.topicNumber)
    elif setting_to_change.lower() == "topic_id":
        try:
            value_int = int(value)
            assert value_int in ALLOWED_TOPIC_IDS
            fol_interface.create_post(f"The game will now be played in the specified thread.",
                                  topic_id_parameter=post.topicNumber)
            topic_id = value_int
        except ValueError:
            fol_interface.create_post(f"{value} is not an integer.", topic_id_parameter=post.topicNumber)
        except AssertionError:
            fol_interface.create_post(f"{value} is not in the list of allowed topic IDs, which is: {', '.join([str(x) for x in ALLOWED_TOPIC_IDS])}.", topic_id_parameter=post.topicNumber)
    elif setting_to_change.lower() == "allow_multivoting":
        if value.lower() == "true":
            allow_multivoting = True
            fol_interface.create_post("Multivoting is now allowed.", topic_id_parameter=post.topicNumber)
        elif value.lower() == "false":
            allow_multivoting = False
            fol_interface.create_post("Multivoting is now disabled.", topic_id_parameter=post.topicNumber)
        else:
            fol_interface.create_post("This is not a valid setting for multivoting. Valid settings are 'true' and 'false'.", topic_id_parameter=post.topicNumber)
    elif setting_to_change.lower() == "setup":
        requested_setup = turbo_setup.get_setup(value)
        if requested_setup is None:
            fol_interface.create_post(f"{value} is not a supported setup.", topic_id_parameter=post.topicNumber)
        else:
            setup = requested_setup
            fol_interface.create_post(f"Setup is now set to {value}.", topic_id_parameter=post.topicNumber)
    elif setting_to_change.lower() == "playercount":
        try:
            value_int = int(value)
            assert value_int >= 3
            fol_interface.create_post(f"This game will now cap at {value_int} players.", topic_id_parameter=post.topicNumber)
            intended_player_cap = value_int
        except ValueError:
            fol_interface.create_post(f"{value} is not an integer greater than or equal to 3.", topic_id_parameter=post.topicNumber)
        except AssertionError:
            fol_interface.create_post(f"{value} is not an integer greater than or equal to 3.", topic_id_parameter=post.topicNumber)

def display_current_settings(discard_1, discard_2, post: post.Post):
    string_to_post = ''
    string_to_post += f"Day length (minutes): {day_length_minutes}\n"
    string_to_post += f"Night length (minutes): {night_length_minutes}\n"
    string_to_post += f"Topic ID: {topic_id}\n"
    string_to_post += f"Multivoting allowed: {allow_multivoting}\n"
    string_to_post += f"Current Playerlist: {', '.join(playerlist)}\n"
    string_to_post += f"Current Setup: {setup.game_name if setup is not None else 'None'}\n"
    string_to_post += f"Current Playercap: {intended_player_cap}\n"
    fol_interface.create_post(string_to_post=string_to_post, topic_id_parameter=post.topicNumber)


def make_simplified_ability(ability_name: str, syntax_parser, use_action_instant) -> player.Ability:
    """
    Makes an Ability with the provided parameters, and many defaults for ones that aren't
    useful for turbos.py.
    """
    result_ability = player.Ability(
        ability_name=ability_name,
        syntax_parser=syntax_parser,
        submission_location=-1, # NOTE: Abilities have most behavior enforced by outside constructs, not the abilities themselves.
        # In this case, turbos.py is not enforcing any submission location here.
        can_use_now=lambda *args : True,
        acknowledge_and_verify=lambda *args : None,
        use_action_instant=use_action_instant,
        use_action_phase_end=lambda *args : None,
        ability_priority=-1,
        willpower_required_instant=-1,
        willpower_required_phase_end=-1,
        target_focus=-1,
        ignore_action_deadline=False,
        action_types=[c.FALSE_ACTION]
    )
    return result_ability

def get_turbo_out_of_game_abilities() -> list["player.Ability"]:
    help_ability = make_simplified_ability(
        ability_name="Print help",
        syntax_parser=syn.syntax_parser_constructor(command_name="help", parameter_list=[]),
        use_action_instant=display_help_post,
    )
    signup_ability = make_simplified_ability(
        ability_name="Join Game",
        syntax_parser=syn.syntax_parser_constructor(command_name="in", parameter_list=[]),
        use_action_instant=join_game,
    )
    quit_ability = make_simplified_ability(
        ability_name="Leave Game",
        syntax_parser=syn.syntax_parser_constructor(command_name="out", parameter_list=[]),
        use_action_instant=leave_game,
    )
    start_ability = make_simplified_ability(
        ability_name="Start Game",
        syntax_parser=syn.syntax_parser_constructor(command_name="start", parameter_list=[]),
        use_action_instant=start_game,
    )
    modify_ability = make_simplified_ability(
        ability_name="Modify Game",
        syntax_parser=syn.syntax_parser_constructor(command_name="modify", parameter_list=[syn.SYNTAX_PARSER_NO_SPACE_STRING, syn.SYNTAX_PARSER_NO_SPACE_STRING]),
        use_action_instant=modify_game_settings,
    )
    display_ability = make_simplified_ability(
        ability_name="Display settings",
        syntax_parser=syn.syntax_parser_constructor(command_name="display", parameter_list=[]),
        use_action_instant=display_current_settings
    )

    return [help_ability, signup_ability, quit_ability, start_ability, modify_ability, display_ability]

async def process_turbo_post(post: post.Post, out_of_game_abilities: list[player.Ability]):
    for ability in out_of_game_abilities:        
        try:
            parameters = ability.syntax_parser(post)
        except roles.ParsingException as e:
            print(f"This message could not be parsed the ability: {ability.ability_name}. Error below: ")
            print(e.args)
            continue
        print(f"Input for {ability.ability_name} parsed successfully; the parameters are {parameters}")
        
        parameters.append(post) # This use of Ability often wants the post as a parameter, to read topic ID and the like
        print(f"Running instant action with {len(parameters)} parameters, plus the player and gamestate")
        possible_awaitable = ability.use_action_instant(None, None, *parameters)
        if inspect.isawaitable(possible_awaitable):
            await possible_awaitable
        ability.instant_use_count += 1

async def run_turbo_listener():
    await fol_interface.get_new_posts_with_pings(ignore_return=True, accept_private_messages=False)
    # DON'T process posts here. this is to avoid processing old pings
    out_of_game_abilties = get_turbo_out_of_game_abilities() 
    while True:
        await asyncio.sleep(config.action_processor_sleep_seconds)
        new_posts = await fol_interface.get_new_posts_with_pings(accept_private_messages=False)
        print(f"There are {len(new_posts)} new posts to process")
        for post in new_posts:
            print(f"Processing post by: {post.poster}")
            await process_turbo_post(post, out_of_game_abilties)
    

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(do_turbos())
        except asyncio.exceptions.CancelledError:
            print("Turbo starting now!")

        # Setting config to chosen settings
        assert setup is not None
        config.playerlist_usernames = playerlist
        config.day_length = day_length_minutes
        config.night_length = night_length_minutes
        config.topic_id = topic_id
        config.allow_multivoting = allow_multivoting
        
        config.allow_no_exe = setup.allow_no_exe
        config.do_votecounts = setup.do_votecounts
        config.first_phase_is_day = setup.first_phase_is_day
        config.first_phase_count = setup.first_phase_count
        config.game_name = setup.game_name

        rolelist = setup.get_rolelist(len(playerlist))
        config.get_rolelist = lambda : rolelist

        try:
            asyncio.run(main.start_all_components())
        except asyncio.exceptions.CancelledError:
            print("Turbo completed.")
        
        playerlist = []
