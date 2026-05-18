from typing import Callable
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player

import setup
import constants as c
import os
import random


def generate_rolelist() -> list[Callable[[str], "player.Player"]]:
    return 2 * [lambda username : MAKE_VANILLA_TOWN_WITH_ITA(username, 'town.txt')] \
        + 1 * [lambda username : MAKE_MAFIA_GOON_WITH_ITA(username, 'mafia.txt')]

def get_setup():
    return setup.Setup(game_name="fam6",
                allow_no_exe=False,
                playercount=3,
                get_rolelist=generate_rolelist
        )

def MAKE_VANILLA_TOWN_WITH_ITA(username: str, flip_path: str) -> 'player.Player':
    import player
    import abilities_standard
    result = player.Player(username, c.TOWN, flip_path, abilities=
                           [abilities_standard.ITA_ABILITY()],
                           ita_items=[player.ITAItem()]
                           )
    return result

def MAKE_MAFIA_GOON_WITH_ITA(username: str, flip_path: str) -> 'player.Player':
    import player
    import abilities_standard
    result = player.Player(username, c.MAFIA, flip_path, abilities=
                           [abilities_standard.ITA_ABILITY()],
                           ita_items=[player.ITAItem()]
                           )
    return result

