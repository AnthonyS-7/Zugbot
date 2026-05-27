"""
This file has some custom code for FAM6.
"""
import random
import setups.fam6.fam6_misc as fam6_misc

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player

vampire_player: 'None | player.Player' = None

bird_player: 'None | player.Player' = None
willow_player: 'None | player.Player' = None

def get_ita_ad():
    return fam6_misc.get_random_ad()

def set_vampire_player(vamp: 'player.Player | None'):
    global vampire_player
    vampire_player = vamp

def set_bird_player(bird: 'player.Player | None'):
    global bird_player
    bird_player = bird

def set_willow_player(willow: 'player.Player | None'):
    global willow_player
    willow_player = willow

def do_bird_check(player_shot: 'player.Player') -> bool:
    if bird_player is None or willow_player is None:
        return False
    if player_shot != bird_player:
        return False
    if player_shot.health > 0:
        return False
    if not (willow_player.health > 0):
        return False
    player_shot.health = min(player_shot.max_health, willow_player.health)
    willow_player.health = 0
    return True

def heal_vampire_player():
    global vampire_player
    if  vampire_player is not None:
        vampire_player.health = min(vampire_player.max_health, vampire_player.health + 20)
            
