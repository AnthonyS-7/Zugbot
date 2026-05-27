from typing import Callable
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player

import setup
import constants as c
import os
import random

VANILLA_TOWNIES_LIST = [
    'neil_the_eel.txt',
    'italy.txt',
    'diafiasco.txt',
    'kyubey.txt',
    'sulit.txt',
    'daeron.txt',
    'jaiden.txt',
    'magnus.txt',
    'arctic.txt',
    'jason.mrrown.txt',
    'marshal.txt'
]
MAFIA_GOONS_LIST = [
    'meow.txt',
    'orangeandblack5.txt',
    'mollylikesorigami.txt'
]


def generate_rolelist() -> list[Callable[[str], "player.Player"]]:
    result = []
    for loop_var in VANILLA_TOWNIES_LIST:
        result.append(lambda username, f=loop_var: MAKE_VANILLA_TOWN_WITH_ITA(username, f))
    for loop_var in MAFIA_GOONS_LIST:
        result.append(lambda username, f=loop_var: MAKE_MAFIA_GOON_WITH_ITA(username, f))
    return result



def get_setup():
    return setup.Setup(game_name="fam6",
                allow_no_exe=False,
                playercount=14,
                get_rolelist=generate_rolelist,
                disable_nightkill=True,
                disable_elimination=True,
                include_teammates_in_role_pm=False
        )

def MAKE_VANILLA_TOWN_WITH_ITA(username: str, flip_path: str) -> 'player.Player':
    import player
    import abilities_standard
    result = player.Player(username, c.TOWN, flip_path, abilities=
                           [abilities_standard.ITA_ABILITY(), abilities_standard.SILENT_ITA_ABILITY(),
                            abilities_standard.VIEW_ITAS_ABILITY(), abilities_standard.REORDER_ITAS_ABILITY(),
                            abilities_standard.REORDER_ITAS_ABILITY_SILENT()],
                           ita_items=[player.ITAItem()]
                           )
    return result

def MAKE_MAFIA_GOON_WITH_ITA(username: str, flip_path: str) -> 'player.Player':
    import player
    import abilities_standard
    result = player.Player(username, c.MAFIA, flip_path, abilities=
                           [abilities_standard.ITA_ABILITY(), abilities_standard.SILENT_ITA_ABILITY(),
                            abilities_standard.VIEW_ITAS_ABILITY(), abilities_standard.REORDER_ITAS_ABILITY(),
                            abilities_standard.REORDER_ITAS_ABILITY_SILENT()],
                           ita_items=[player.ITAItem()]
                           )
    return result
    