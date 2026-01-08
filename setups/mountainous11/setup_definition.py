from typing import Callable
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player

import setup
import abilities_standard

def generate_rolelist() -> list[Callable[[str], player.Player]]:
    return 9 * [abilities_standard.MAKE_VANILLA_TOWN] + 2 * [abilities_standard.MAKE_MAFIA_GOON]

def get_setup():
    return setup.Setup(game_name="11p Mountainous",
                allow_no_exe=False,
                playercount=11,
                get_rolelist=generate_rolelist
        )

