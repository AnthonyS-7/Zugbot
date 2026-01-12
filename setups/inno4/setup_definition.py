from typing import Callable
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player

import setup

def generate_rolelist() -> list[Callable[[str], "player.Player"]]:
    import abilities_standard
    return 1 * [lambda username : abilities_standard.MAKE_TOWN_INNOCENT_CHILD(username, 'town_innocent_child.txt')] \
        + 2 * [lambda username : abilities_standard.MAKE_VANILLA_TOWN(username, 'town.txt')] \
        + 1 * [lambda username : abilities_standard.MAKE_MAFIA_GOON(username, 'mafia.txt')]

def get_setup():
    return setup.Setup(game_name="inno4",
                allow_no_exe=False,
                first_phase_is_day=False,
                first_phase_count=0,
                playercount=4,
                get_rolelist=generate_rolelist
        )

