from typing import Callable
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player

import setup
import abilities_standard

def generate_rolelist() -> list[Callable[[str], player.Player]]:
    return 12 * [abilities_standard.MAKE_VANILLA_TOWN] + 3 * [abilities_standard.MAKE_MAFIA_GOON]

def get_setup():
    return setup.Setup(game_name="15p Mountainous",
                allow_no_exe=False,
                playercount=15,
                get_rolelist=generate_rolelist
        )

