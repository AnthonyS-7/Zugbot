"""
This script allows anyone to run turbos with Zugbot. Only one turbo can be running at a time.
"""


import fol_interface
import asyncio
import random
import config
import constants as c
import main
import ability
import post as p
import syntax_parser_standard as syn
from role_standards import verify_standard as ver
import roles
import inspect
import setup

turbo_task: asyncio.Task | None = None
posting_queue_task:  asyncio.Task | None = None

playerlist: list[str] = []
day_length_minutes = 10
night_length_minutes = 3
topic_id = 9145

setup_object = setup.get_setup("mountainous3")
assert setup_object is not None

ALLOWED_SETUPS = setup.list_available_setups()
ALLOWED_TOPIC_IDS = [9524, 9145]
TURBO_HOST_ACCOUNTS = ["Zwischenzug"]

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

def display_help_post():
    def inner_func(discard_1, discard_2, discard_3, post: p.Post):
        string_to_post = get_turbo_help_string()
        string_to_post += "\nAvailable Setups: " + ', '.join(ALLOWED_SETUPS)
        fol_interface.create_post(string_to_post, topic_id_parameter=post.topicNumber)
    return ability.Action(inner_func)

def start_game():
    def inner_func(discard_1, discard_2, discard_3, post: p.Post):
        global playerlist
        assert setup_object is not None
        if len(playerlist) != setup_object.playercount:
            fol_interface.create_post(f"The game cannot be started, because it is not full.", topic_id_parameter=post.topicNumber)
        else:
            fol_interface.create_post(f"Starting game.", topic_id_parameter=post.topicNumber)
            assert turbo_task is not None
            assert posting_queue_task is not None
            turbo_task.cancel()
            posting_queue_task.cancel()
    return ability.Action(inner_func)

def join_game():
    def inner_func(discard_1, discard_2, discard_3, post: p.Post):
        assert setup_object is not None
        global playerlist
        if post.poster.lower() in [player.lower() for player in playerlist]:
            fol_interface.create_post(f"{post.poster} is already in the game!", topic_id_parameter=post.topicNumber)
        elif len(playerlist) == setup_object.playercount:
            fol_interface.create_post(f"The game is already full!", topic_id_parameter=post.topicNumber)
        else:
            fol_interface.create_post(f"{post.poster} has joined the game.", topic_id_parameter=post.topicNumber)
            playerlist.append(post.poster)
    return ability.Action(inner_func)

def leave_game():
    def inner_func(discard_1, discard_2, discard_3, post: p.Post):
        global playerlist
        if post.poster.lower() in [player.lower() for player in playerlist]:
            fol_interface.create_post(f"{post.poster} has left the game.", topic_id_parameter=post.topicNumber)
            playerlist.remove(post.poster)
        else:
            fol_interface.create_post(f"{post.poster} is not in the game, so they cannot leave.", topic_id_parameter=post.topicNumber)
    return ability.Action(inner_func)

def modify_game_settings():
    def inner_func(discard_1, discard_2, discard_3, setting_to_change: str, value: str, post: p.Post):
        global day_length_minutes
        global night_length_minutes
        global topic_id
        global setup_object
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
        elif setting_to_change.lower() == "setup":
            requested_setup = setup.get_setup(value)
            if requested_setup is None:
                fol_interface.create_post(f"{value} is not a supported setup.", topic_id_parameter=post.topicNumber)
            else:
                setup_object = requested_setup
                fol_interface.create_post(f"Setup is now set to {value}.", topic_id_parameter=post.topicNumber)
    return ability.Action(inner_func)

def display_current_settings():
    def inner_func(discard_1, discard_2, discard_3, post: p.Post):
        assert setup_object is not None
        string_to_post = ''
        string_to_post += f"Day length (minutes): {day_length_minutes}\n"
        string_to_post += f"Night length (minutes): {night_length_minutes}\n"
        string_to_post += f"Topic ID: {topic_id}\n"
        string_to_post += f"Current Setup: {setup_object.game_name if setup_object is not None else 'None'}\n"
        string_to_post += f"Playercount: {len(playerlist)}/{setup_object.playercount}\n"
        string_to_post += f"Playerlist: {', '.join(playerlist) if playerlist else 'No players currently signed up.'}"
        fol_interface.create_post(string_to_post=string_to_post, topic_id_parameter=post.topicNumber)
    return ability.Action(inner_func)


def make_simplified_ability(ability_name: str, syntax_parser: syn.SyntaxParser, use_action_instant: ability.Action) -> ability.Ability:
    """
    Makes an Ability with the provided parameters, and many defaults for ones that aren't
    useful for turbos.py.
    """
    result_ability = ability.Ability(
        ability_name=ability_name,
        syntax_parser=syntax_parser,
        submission_location=-1, # NOTE: Abilities have most behavior enforced by outside constructs, not the abilities themselves.
        # In this case, turbos.py is not enforcing any submission location here.
        action=use_action_instant,
        is_instant=True,
        ability_priority=-1,
        willpower_required=None,
        action_types=[c.FALSE_ACTION]
    )
    return result_ability

def get_turbo_out_of_game_abilities() -> list["ability.Ability"]:
    help_ability = make_simplified_ability(
        ability_name="Print help",
        syntax_parser=syn.SyntaxParser(command_name="help", parameter_list=[]),
        use_action_instant=display_help_post(),
    )
    signup_ability = make_simplified_ability(
        ability_name="Join Game",
        syntax_parser=syn.SyntaxParser(command_name="in", parameter_list=[]),
        use_action_instant=join_game(),
    )
    quit_ability = make_simplified_ability(
        ability_name="Leave Game",
        syntax_parser=syn.SyntaxParser(command_name="out", parameter_list=[]),
        use_action_instant=leave_game(),
    )
    start_ability = make_simplified_ability(
        ability_name="Start Game",
        syntax_parser=syn.SyntaxParser(command_name="start", parameter_list=[]),
        use_action_instant=start_game(),
    )
    modify_ability = make_simplified_ability(
        ability_name="Modify Game",
        syntax_parser=syn.SyntaxParser(command_name="modify", parameter_list=[syn.SYNTAX_PARSER_NO_SPACE_STRING, syn.SYNTAX_PARSER_NO_SPACE_STRING]),
        use_action_instant=modify_game_settings(),
    )
    display_ability = make_simplified_ability(
        ability_name="Display settings",
        syntax_parser=syn.SyntaxParser(command_name="display", parameter_list=[]),
        use_action_instant=display_current_settings()
    )

    return [help_ability, signup_ability, quit_ability, start_ability, modify_ability, display_ability]

async def process_turbo_post(post: p.Post, out_of_game_abilities: list[ability.Ability]):
    for ability in out_of_game_abilities:        
        try:
            parameters = ability.syntax_parser.parse_discourse_post(post)
        except roles.ParsingException as e:
            print(f"This message could not be parsed the ability: {ability.ability_name}. Error below: ")
            print(e.args)
            continue
        print(f"Input for {ability.ability_name} parsed successfully; the parameters are {parameters}")
        
        parameters.append(post) # This use of Ability often wants the post as a parameter, to read topic ID and the like
        print(f"Running instant action with {len(parameters)} parameters, plus the player and gamestate")
        await ability.action.run_action(None, None, ability, *parameters) # type: ignore
        ability.use_count += 1

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
        assert setup_object is not None

        config.game_name = setup_object.game_name
        config.allow_no_exe = setup_object.allow_no_exe
        config.do_votecounts = setup_object.do_votecounts
        config.first_phase_is_day = setup_object.first_phase_is_day
        config.first_phase_count = setup_object.first_phase_count
        config.playercount = setup_object.playercount
        config.get_rolelist = setup_object.get_rolelist
        config.allow_multivoting = setup_object.allow_multivoting
        config.no_exe_wins_ties = setup_object.no_exe_wins_ties
        config.is_botf = setup_object.is_botf
        config.flips_folder = setup_object.flips_folder

        config.playerlist_usernames = playerlist
        config.day_length = day_length_minutes
        config.night_length = night_length_minutes
        config.topic_id = topic_id

        config.original_host_usernames = TURBO_HOST_ACCOUNTS
        config.host_usernames = list(map(lambda x : x.lower(), TURBO_HOST_ACCOUNTS))
        
        try:
            asyncio.run(main.start_all_components())
        except asyncio.exceptions.CancelledError:
            print("Turbo completed.")
        
        playerlist = []