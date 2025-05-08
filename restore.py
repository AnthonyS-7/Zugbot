import fol_interface
import modbot
import game_state
import config
import player


import json
import dill
import asyncio
import queue
import time

GAMESTATE_JSON_PATH = "gamestate.json" # Note that 'gamestate' is used loosely here -
# For the purposes of the variable name, we consider everything the program is storing to be part of the gamestate.
# In other parts of the program, the gamestate generally refers to objects like player, phase count, etc - while
# not referring to things like player's role PM topic ID numbers. Essentially, gamestate in other parts of the program
# contains/refers to things that would be relevant to a manual host who's executing the game according to the algorithm
# Zugbot is using, while gamestate here refers to everything stored.

GAMESTATE_PICKLE_PATH = "gamestate.pkl" # refers to tuple of (gamestate object, player.all_abilities)


last_save_time = -1

async def save_every_x_minutes(minutes: float):
    """
    Attempts to save the game every x minutes. This attempt is skipped if the time the game was last saved
    was less than config.min_delay_between_saves_seconds ago.
    """
    assert minutes > 0
    while True:
        await asyncio.sleep(minutes * 60)
        save_all()

def save_all():
    """
    Saves the game, unless the last time the game was saved was less than
    config.min_delay_between_saves_seconds ago.
    """
    global last_save_time
    if time.time() - last_save_time > config.min_delay_between_saves_seconds:
        last_save_time = time.time()
        save_json()
        save_pickle()

def queue_encoder(obj):
    if isinstance(obj, queue.PriorityQueue):
        return {"queue_contents": list(obj.queue)}
    else:
        raise TypeError(f"Object of type {type(obj)} is not serializiable.")
    
def queue_decoder(dct):
    if "queue_contents" in dct:
        result = queue.PriorityQueue()
        for item in dct["queue_contents"]:
            result.put(tuple(item))
        return result
    else:
        return dct

def restore_individual_variables(json_input: dict):
    """
    Given the JSON, this restores the following variables:

    player.next_id,
    fol_interface.to_post_cache,
    fol_interface.username_to_role_pm_id,
    fol_interface.topic_id_to_last_post_accessed,
    fol_interface.previous_post_time,
    fol_interface.to_post_queue,
    fol_interface.last_notification_id_seen,
    fol_interface.posts_added_to_queue,
    modbot.nightkill_choice,
    modbot.continue_posting_vcs,
    modbot.posts_in_thread_at_last_vc,
    modbot.game_started,
    modbot.action_submission_open,
    modbot.game_end_announced_already

    Also, modbot.game_restored_from_file is set to True.

    This could certainly be done concisely with exec, and very likely
    can be done concisely with some clever reflection, or simply a way to
    access the global variables of other files.

    Since the user (and anyone with access to the computer) can modify this data, using
    exec would be a security risk. Other forms of reflection would be ideal, but I do not know
    any concise ways of doing them. So, this is written out directly.
    """
    player.next_id = json_input["player.next_id"]
    fol_interface.to_post_cache = json_input["fol_interface.to_post_cache"]
    fol_interface.username_to_role_pm_id = json_input["fol_interface.username_to_role_pm_id"]
    fol_interface.topic_id_to_last_post_accessed = json_input["fol_interface.topic_id_to_last_post_accessed"]
    fol_interface.previous_post_time = json_input["fol_interface.previous_post_time"]
    fol_interface.to_post_queue = json_input["fol_interface.to_post_queue"]
    fol_interface.last_notification_id_seen = json_input["fol_interface.last_notification_id_seen"]
    fol_interface.posts_added_to_queue = json_input["fol_interface.posts_added_to_queue"]
    modbot.nightkill_choice = json_input["modbot.nightkill_choice"]
    modbot.continue_posting_vcs = json_input["modbot.continue_posting_vcs"]
    modbot.posts_in_thread_at_last_vc = json_input["modbot.posts_in_thread_at_last_vc"]
    modbot.game_started = json_input["modbot.game_started"]
    modbot.action_submission_open = json_input["modbot.action_submission_open"]
    modbot.game_end_announced_already = json_input["modbot.game_end_announced_already"]
    modbot.game_restored_from_file = True
    config.game_start_time = json_input["config.game_start_time"]

def save_json():
    to_save = {
        "player.next_id" : player.next_id,
        "fol_interface.to_post_cache" : fol_interface.to_post_cache,
        "fol_interface.username_to_role_pm_id" : fol_interface.username_to_role_pm_id,
        "fol_interface.topic_id_to_last_post_accessed" : fol_interface.topic_id_to_last_post_accessed,
        "fol_interface.previous_post_time" : fol_interface.previous_post_time,
        "fol_interface.to_post_queue" : fol_interface.to_post_queue,
        "fol_interface.last_notification_id_seen" : fol_interface.last_notification_id_seen,
        "fol_interface.posts_added_to_queue" : fol_interface.posts_added_to_queue,
        "modbot.nightkill_choice" : modbot.nightkill_choice,
        "modbot.continue_posting_vcs" : modbot.continue_posting_vcs,
        "modbot.posts_in_thread_at_last_vc" : modbot.posts_in_thread_at_last_vc,
        "modbot.game_started" : modbot.game_started,
        "modbot.action_submission_open" : modbot.action_submission_open,
        "modbot.game_end_announced_already" : modbot.game_end_announced_already,
        "config.game_start_time" : config.game_start_time
    }
    json_file = open(GAMESTATE_JSON_PATH, 'w')
    json.dump(to_save, json_file, indent=4, default=queue_encoder)
    json_file.close()

def save_pickle():
    gamestate_file = open(GAMESTATE_PICKLE_PATH, 'bw')
    dill.dump((modbot.gamestate, player.all_abilities), gamestate_file)
    gamestate_file.close()

# def load_everything():
#     gamestate_json = open(GAMESTATE_JSON_PATH, 'r')
#     loaded_gamestate_json = json.load(gamestate_json, object_hook=queue_decoder)
#     gamestate_json.close()
#     print(loaded_gamestate_json)
#     print(loaded_gamestate_json["fol_interface.to_post_queue"].queue)


#     gamestate_file = open(GAMESTATE_PICKLE_PATH, 'rb')
#     gamestate_object, all_abilities = dill.load(gamestate_file)
#     print(type(gamestate_object))
#     print(type(all_abilities))

def load_everything_and_convert_to_game():
    gamestate_json = open(GAMESTATE_JSON_PATH, 'r')
    loaded_gamestate_json = json.load(gamestate_json, object_hook=queue_decoder)
    gamestate_json.close()
    restore_individual_variables(loaded_gamestate_json)
        
    gamestate_file = open(GAMESTATE_PICKLE_PATH, 'rb')
    gamestate_object, all_abilities = dill.load(gamestate_file)
    modbot.gamestate = gamestate_object
    player.all_abilities = all_abilities

    # while(True):
    #     command_to_run = input("REMOVE THIS LATER")
    #     try:
    #         exec(command_to_run)
    #     except Exception as e:
    #         print(e)

    import main # here to avoid circular import
    asyncio.run(main.start_all_components())


if __name__ == "__main__":
    load_everything_and_convert_to_game()