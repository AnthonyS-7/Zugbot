"""
Docstring written: 12-29-2025

This file (and some others) will eventually replace and extend turbo_setup.py. 

There will be a Setup class, which contains all the information needed to run a setup. 
There will also be a "setups" folder, and inside the setups folder will be one folder for each setup.
Setups will contain all necessary information to run their setup within their respective folders, so that there is not a messy, ever-growing flips folder.
Then, the config.py file will have some of its settings replaced with a variable for the chosen setup.
"""

import constants as c


from typing import Callable
import os
from typing import TYPE_CHECKING
import importlib
if TYPE_CHECKING:
    import player

class InvalidSetupException(Exception):
    def __init__(self) -> None:
        pass

class Setup:
    def __init__(self, game_name: str, 
                 playercount: int, 
                 get_rolelist: Callable[[], list[Callable[[str], "player.Player"]]],
                 allow_no_exe: bool,
                 allow_multivoting=False,
                 no_exe_wins_ties=True,
                 do_votecounts=True, 
                 first_phase_is_day=True,
                 first_phase_count=1,
                 is_botf=False,
                 ) -> None:
        """
        Most parameters here are self-explanatory. The one that is not:

        get_rolelist is a function that takes no parameters, and returns a list of 
        functions which (when given a username) return a player object.

        The reason we store get_rolelist as a function, instead of storing the output of that function,
        is to allow setups to have randomized rolelists.
        """
        self.game_name = game_name
        self.allow_no_exe = allow_no_exe
        self.do_votecounts = do_votecounts
        self.first_phase_is_day = first_phase_is_day
        self.first_phase_count = first_phase_count
        self.playercount = playercount
        self.get_rolelist = get_rolelist
        self.allow_multivoting = allow_multivoting
        self.no_exe_wins_ties = no_exe_wins_ties

        self.is_botf = is_botf # TODO: consider moving elsewhere?

        self.flips_folder = ''

        if not (do_votecounts or allow_no_exe):
            raise InvalidSetupException()

    
def get_setup(setup_name: str) -> Setup | None:
    """
    Returns a Setup with the specified name (this name must match the name in the setups folder exactly),
    or None if no such setup is found.
    """
    path_to_setup = os.path.join(c.SETUP_FOLDER, setup_name)
    if os.path.isdir(path_to_setup):
        setup_module = importlib.import_module(f"{c.SETUP_FOLDER}.{setup_name}.{c.SETUP_FILE_NAME}")
        setup_to_return: Setup = setup_module.get_setup()
        setup_to_return.flips_folder = os.path.join(c.SETUP_FOLDER, setup_name, c.FLIPS_FOLDER_NAME)
        return setup_to_return
    else:
        return None
    
def list_available_setups() -> list[str]:
    """
    Returns the names of the available setups.
    """
    return os.listdir(c.SETUP_FOLDER)
