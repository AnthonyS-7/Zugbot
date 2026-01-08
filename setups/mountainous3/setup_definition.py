from typing import Callable
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player

import setup

def generate_rolelist() -> list[Callable[[str], "player.Player"]]:
    import abilities_standard
    return 2 * [abilities_standard.MAKE_VANILLA_TOWN] + 1 * [abilities_standard.MAKE_MAFIA_GOON]

def get_setup():
    return setup.Setup(game_name="3p Mountainous",
                allow_no_exe=False,
                playercount=3,
                get_rolelist=generate_rolelist
        )

