import asyncio

import fol_interface
import modbot
import discord_interface
import restore
import config
import game_state
import syntax_parser_standard as syn
import constants as c
from constants import Alignment
import abilities_standard
import ability as a
import setup


tasks: list[asyncio.Task] = []

    global tasks
    if reset_globals:
        modbot.reset_globals_to_defaults()
    if update_latest_posts_in_role_pms:
        invalidation_success = await fol_interface.invalidate_previous_role_pm_commands()
        if invalidation_success:
            print("Finished invalidating all previous commands in role PMs.")
        else:
            print("Attempted to invalidte all previous commands in role PMs, but failed on some of them! Proceed with caution.")
    if config.crash_on_exception:
        async with asyncio.TaskGroup() as group:
            start_control = group.create_task(modbot.run_modbot())
            start_action_listener = group.create_task(modbot.run_action_processor())
            start_fol_poster = group.create_task(fol_interface.run_fol_poster())
            start_state_saver = group.create_task(restore.save_every_x_minutes(config.restore_delay_minutes))
            tasks = [start_control, start_action_listener, start_fol_poster, start_state_saver]
            if not config.is_turbo:
                start_discord_bot = group.create_task(discord_interface.start_discord_bot())
                tasks.append(start_discord_bot)
            if config.do_votecounts:
                start_vc_bot = group.create_task(modbot.run_vc_bot())
                tasks.append(start_vc_bot)
            if not config.is_turbo and config.send_messages_to_hosting_discord:
                start_discord_host_logs = group.create_task(discord_interface.hosting_discord_pipeline())
                tasks.append(start_discord_host_logs)
            start_ita_window_poster = group.create_task(modbot.post_ita_window_announcements())
            tasks.append(start_ita_window_poster)
    else:
        start_control = asyncio.create_task(modbot.run_modbot())
        start_action_listener = asyncio.create_task(modbot.run_action_processor())
        start_fol_poster = asyncio.create_task(fol_interface.run_fol_poster())
        start_state_saver = asyncio.create_task(restore.save_every_x_minutes(config.restore_delay_minutes))
        tasks = [start_control, start_action_listener, start_fol_poster, start_state_saver]
        if not config.is_turbo:
            start_discord_bot = asyncio.create_task(discord_interface.start_discord_bot())
            tasks.append(start_discord_bot)
        if config.do_votecounts:
            start_vc_bot = asyncio.create_task(modbot.run_vc_bot())
            tasks.append(start_vc_bot)
        start_ita_window_poster = asyncio.create_task(modbot.post_ita_window_announcements())
        tasks.append(start_ita_window_poster)
        if not config.is_turbo and config.send_messages_to_hosting_discord:
            start_discord_host_logs = asyncio.create_task(discord_interface.hosting_discord_pipeline())
            tasks.append(start_discord_host_logs)
        await start_control
        await start_action_listener
        await start_fol_poster
        await start_state_saver

    print("All components started.")
    
if __name__ == "__main__":
    asyncio.run(start_all_components())
