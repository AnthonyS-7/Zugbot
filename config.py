
import yaml
import setup

with open('config.yaml', 'r') as config_file:
    config_dict: dict = yaml.load(config_file, yaml.Loader)

    url: str = config_dict['url']
    username: str = config_dict['username']

    game_name: str = config_dict['game_name']
    game_start_time: str = config_dict['game_start_time']
    utc_offset: str = config_dict['utc_offset']

    original_host_usernames: list[str] = config_dict['host_usernames']
    host_usernames: list[str] = list(map(lambda x : x.lower(), config_dict['host_usernames']))

    playerlist_usernames: list[str] = config_dict['playerlist_usernames']
    topic_id: int = config_dict['topic_id']
    mafia_discord_link: str = config_dict['mafia_discord_link']
    rand_roles: bool = config_dict['rand_roles']

    day_length: int = config_dict['day_length']
    night_length: int = config_dict['night_length']
    action_deadline: int = config_dict['action_deadline']

    setup_name: str = config_dict['setup_name']
    setup_object: setup.Setup | None = setup.get_setup(setup_name)
    assert setup_object is not None

    resolve_like_vc_plugin: bool = config_dict['resolve_like_vc_plugin']
    turbo_pm_json_path: str = config_dict['turbo_pm_json_path']
    action_processor_sleep_seconds: int = config_dict['action_processor_sleep_seconds']

    delay_between_post_checks: int = config_dict['delay_between_post_checks']
    delay_between_posts: int = config_dict['delay_between_posts']

    exception_retry_delay: int = config_dict['exception_retry_delay']
    max_exception_retries: int = config_dict['max_exception_retries']

    restore_delay_minutes: int = config_dict['restore_delay_minutes']
    min_delay_between_saves_seconds: int = config_dict['min_delay_between_saves_seconds']

    vc_post_cooldown: int = config_dict['vc_post_cooldown']
    votecount_time_interval: int = config_dict['votecount_time_interval']
    votecount_post_interval: int = config_dict['votecount_post_interval']

    debug_print_all_posts: bool = config_dict['debug_print_all_posts']

    crash_on_exception: bool = config_dict['crash_on_exception']

    include_itas: bool = config_dict['include_itas']
    ita_windows: list[dict[str, int]] = config_dict['ita_windows']
    ita_base_damage: int = config_dict['ita_base_damage']
    ita_ads: bool = config_dict['ita_ads']

    send_messages_to_hosting_discord: bool = config_dict['send_messages_to_hosting_discord']
    hosting_discord_channel_id_for_output: int = config_dict['hosting_discord_channel_id_for_output']

    do_not_flip: bool = config_dict['do_not_flip']

    # Below this line is field from the setup loaded here
    game_name = setup_object.game_name
    allow_no_exe = setup_object.allow_no_exe
    do_votecounts = setup_object.do_votecounts
    first_phase_is_day = setup_object.first_phase_is_day
    first_phase_count = setup_object.first_phase_count
    playercount = setup_object.playercount
    get_rolelist = setup_object.get_rolelist
    allow_multivoting = setup_object.allow_multivoting
    no_exe_wins_ties = setup_object.no_exe_wins_ties
    is_botf = setup_object.is_botf
    flips_folder = setup_object.flips_folder

    # This setting is enabled in turbos.py
    is_turbo = False
