import player
import game_state
import fol_interface
import post as p
import modbot
import constants as c
import re
import roles_folder.roles_exceptions as r
import roles_folder.roles_templates as rt



def make_botc_role(username: str, botc_rolename: str, alignment: int) -> player.Player:
    return player.Player(username, alignment, f"{botc_rolename}.txt")

def make_specific_role_function(botc_rolename: str, alignment: int):
    return lambda username : make_botc_role(username, botc_rolename, alignment)

def get_botc_rolelist():
    return [
        make_specific_role_function("imp", c.MAFIA),

        make_specific_role_function("goblin", c.MAFIA),

        make_specific_role_function("damsel", c.TOWN),
        make_specific_role_function("plague_doctor", c.TOWN),

        make_specific_role_function("huntsman", c.TOWN),
        make_specific_role_function("amnesiac", c.TOWN),
        make_specific_role_function("town_crier", c.TOWN),
        make_specific_role_function("village_idiot", c.TOWN),
        make_specific_role_function("village_idiot", c.TOWN)
    ]