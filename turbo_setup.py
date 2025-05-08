import roles
import math
from typing import Callable
import player

class Setup:
    def __init__(self, game_name: str, allow_no_exe: bool, do_votecounts: bool, first_phase_is_day: bool,
                 first_phase_count: int, supports_playercount: Callable[[int], bool], 
                 get_rolelist: Callable[[int], list[Callable[[str], "player.Player"]]]) -> None:
        self.game_name = game_name
        self.allow_no_exe = allow_no_exe
        self.do_votecounts = do_votecounts
        self.first_phase_is_day = first_phase_is_day
        self.first_phase_count = first_phase_count
        self.supports_playercount = supports_playercount
        self.get_rolelist = get_rolelist

def get_rolelist_popcorn(playercount: int) -> list[Callable[[str], "player.Player"]]:
    if playercount <= 4:
        mafia_amount = 1
    else:
        mafia_amount = math.ceil(playercount // 3)
    return [roles.make_mafia_popcorn] * mafia_amount + [roles.make_town_popcorn] * (playercount - mafia_amount)

def get_rolelist_vig10(playercount: int) -> list[Callable[[str], "player.Player"]]:
    return [roles.make_vanilla_town] * 7 + [roles.make_day_vig] + [roles.make_mafia_goon] * 2

setups = [
    Setup(game_name="Popcorn",
          allow_no_exe=True,
          do_votecounts=False,
          first_phase_is_day=False,
          first_phase_count=0,
          supports_playercount=lambda x : x >= 3,
          get_rolelist=get_rolelist_popcorn
          ),
    Setup(game_name="Vig10",
          allow_no_exe=True,
          do_votecounts=True,
          first_phase_is_day=True,
          first_phase_count=1,
          supports_playercount=lambda x : x == 10,
          get_rolelist=get_rolelist_vig10
          ),
]

# TODO: Parity with Turby on MU. Supported setups there:
# joat10
# vig10 - Done
# bomb10
# bml10
# ita10
# ita13
# cop9
# cop13
# paritycop9
# doublejoat13
# random10er
# closedrandomXer
# randommadnessXer

def get_setup(setup_name: str) -> Setup | None:
    for setup in setups:
        if setup.game_name.lower() == setup_name.lower():
            return setup
    return None