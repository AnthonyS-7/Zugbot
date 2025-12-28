def get_rolelist():
    import abilities_standard
    # import roles_folder.botc as botc
    rolelist = [abilities_standard.MAKE_VANILLA_TOWN] * 4 + [abilities_standard.MAKE_MAFIA_GOON] * 1
    # This is the rolelist that will be used for the game.
    return rolelist

times_accessed = 0 # here so that the written defaults are only created once, even if 
# config is imported again. this allows other files to change the config if needed

if times_accessed == 0:
    # main bot config:

    game_start_time = "" # If not '', then the game will start at this time. Also, all phases
    # will have start and end times calculated off of this time. This is in 24 hour time. This should be in the timezone
    # specified in utc_offset.
    # Example format: "2024-08-13 08:00"
    utc_offset = "-05:00" # The offset from UTC, in +-HH:MM. Example format: "-05:00"

    day_length = 4 # in minutes
    night_length = 2 # in minutes
    votecount_time_interval = 120 # How many minutes should be between votecount posts
    votecount_post_interval = 10 # How many posts should be between votecount posts
    action_deadline = 1 # The number of minutes before phase at which point actions will stop being accepted. Must be at least 1.
    # This restriction is to avoid bugs, where an action resolves concurrently with phase change, which would likely cause
    # many errors.
    action_processor_sleep_seconds = 5 # The number of seconds the action processor sleeps between consecutive calls of 
    # checking notifications.

    host_usernames = ["Zugzwang", "Zwischenzug"] # Handles substitutions, modkills, etc
    original_host_usernames = host_usernames # Should only be accessed when outputting the host usernames
    playerlist_usernames = ["Zug", "secret_cookie_thread", "Eigenzug", "zug_alt_1", "Mittens"]
                            # ["Eigenzug", "Ash", "Eddie", "L.una"] #["Zugzwang", "ElizaThePsycho", "Chomps", "May", "Ash", "L.una", "Atlas"]
    # playerlist_usernames = ["Zugzwang", "Zwischenzug", "wrongboy"] # remove this line!!!!
    host_usernames = list(map(lambda x : x.lower(), host_usernames))

    topic_id = 9145
    game_name = "Refactored Test 1"

    allow_multivoting = False
    allow_no_exe = True
    no_exe_wins_ties = True
    is_botf = False #Intended for BOTC. TODO: test if it works when True

    mafia_discord_link = ""

    rand_roles = True # If rand roles is false, rolelist[i] will go to playerlist_usernames[i]. If it's True
    # the rand happens as expected.

    flips_folder = "flips" # The path to the flips folder, starting inside the overall bot folder.

    # -----------
    # fol_interface config:

    delay_between_posts = 4 # Delay between consecutive posts (in seconds)
    delay_between_post_checks = 1 # Delay between each check for whether the to_post_queue is empty (in seconds)

    vc_post_cooldown = 10 # The number of seconds of cooldown between votecounts, relevant due to /votecount

    max_exception_retries = 20 # Number of times it retries to connect to the API, if an exception is encountered
    exception_retry_delay = 5 # The number of seconds to wait after running into an exception when doing an API call

    resolve_like_vc_plugin = True # If True, votes which are substrings of 2+ playernames are resolved like the VC plugin
                                # If False, those votes are removed

    url = "https://www.fortressoflies.com" # should not end with /
    # example: "https://www.fortressoflies.com"
    username = "Zugbot"

    turbo_pm_json_path = "turbo_pms.json"

    # ----------
    # restore config:

    restore_delay_minutes = 5
    min_delay_between_saves_seconds = 30

    # ---------------
    # Oddities config:
    do_votecounts = True # If this is False, votecount posts will be 
        # mostly disabled (only occuring at day start / substitutions / modkills). 
        # Also, at these times, the votecount will be reset. Useful for Popcorn and the like.
        # This also disables the elimination (when combined with allow_no_exe, which is required).
    first_phase_is_day = True # Whether the first phase should be day or night. True if day.
    first_phase_count = 1 # The number for the first phase.

    debug_print_all_posts = True

    assert do_votecounts or allow_no_exe
    times_accessed += 1