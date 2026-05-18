"""
This file has some custom code for FAM6.
"""
import random
import setups.fam6.fam6_misc as fam6_misc

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player

vampire_player: 'None | player.Player' = None

def get_ita_ad():
    return fam6_misc.get_random_ad()

def set_vampire_player(vamp: 'player.Player | None'):
    global vampire_player
    vampire_player = vamp

def heal_vampire_player():
    global vampire_player
    if  vampire_player is not None:
        vampire_player.health = min(vampire_player.max_health, vampire_player.health + 20)
            

        