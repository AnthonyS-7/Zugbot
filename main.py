import asyncio

import fol_interface
#import game_state
import modbot
import discord_interface
import restore
import config

tasks: list[asyncio.Task] = []

async def start_all_components():
    global tasks
    start_discord_bot = asyncio.create_task(discord_interface.start_discord_bot())
    start_control = asyncio.create_task(modbot.run_modbot())
    start_action_listener = asyncio.create_task(modbot.run_action_processor())
    start_fol_poster = asyncio.create_task(fol_interface.run_fol_poster())
    start_state_saver = asyncio.create_task(restore.save_every_x_minutes(config.restore_delay_minutes))
    tasks = [start_discord_bot, start_control, start_action_listener, start_fol_poster, start_state_saver]
    if config.do_votecounts:
        start_vc_bot = asyncio.create_task(modbot.run_vc_bot())
        tasks.append(start_vc_bot)
        await start_vc_bot
    await start_discord_bot
    await start_control
    await start_action_listener
    await start_fol_poster
    await start_state_saver
    
if __name__ == "__main__":
    asyncio.run(start_all_components())
