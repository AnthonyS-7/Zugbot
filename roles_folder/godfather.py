import player
import game_state
import fol_interface
import post as p
import modbot
import constants as c

import types

import re
import roles_folder.roles_exceptions as r

def godfather_get_alignment(self, falsifiable=True, *args):
    if falsifiable:
        return c.TOWN
    return self.alignment

def make_godfather(username: str) -> player.Player:
    result = player.Player(username, c.MAFIA, "mafia_godfather.txt", abilities=None)
    result.get_alignment = types.MethodType(godfather_get_alignment, result)
    return result


