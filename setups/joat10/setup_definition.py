from typing import Callable
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player

import setup
import constants as c

def generate_rolelist() -> list[Callable[[str], "player.Player"]]:
    import abilities_standard
    return 7 * [lambda username : abilities_standard.MAKE_VANILLA_TOWN(username, 'town.txt')] \
        + 2 * [lambda username : abilities_standard.MAKE_MAFIA_GOON(username, 'mafia.txt')] \
        + 1 * [lambda username : make_joat(username, 'town_joat.txt')]


def get_setup():
    return setup.Setup(game_name="joat10",
                allow_no_exe=True,
                playercount=10,
                get_rolelist=generate_rolelist
        )

def make_joat(username: str, flip_path: str) -> "player.Player":
    import abilities_standard
    import player
    doc_ability = abilities_standard.DOCTOR_ABILITY(shot_count=1)
    cop_ability = abilities_standard.COP_ABILITY(shot_count=1)
    vig_ability = abilities_standard.VIG_ABILITY(shot_count=1)
    all_joat_abilities = [doc_ability, cop_ability, vig_ability]
    abilities_standard.make_cycling(all_joat_abilities, cycle_name="joat")
    abilities_standard.make_non_multitaskable(all_joat_abilities, cost_name="joat")
    result = player.Player(username, c.TOWN, flip_path, abilities=all_joat_abilities)
    return result