import json
import time
import random

import player as p
import constants as c
import config
from typing import Callable

gamestate_file_name = "gamestate.json"

class GamestateException(Exception):
    pass

class GameState:
    def __init__(self, players: list["p.Player"], is_day: bool, phase_count: int, wincon_is_parity: bool, game_log: None | list["RecordedEvent"] = None) -> None:
        self.original_players = players
        self.current_players = [player for player in players]
        self.is_day = is_day
        self.phase_count = phase_count
        self.wincon_is_parity = wincon_is_parity
        self.game_log = [] if game_log == None else game_log
        self.nomination_counter = 0 # Number of nominations done so far (for BOTC only)
        self.nominations_open = True # If nominations are currently open (for BOTC only)
    
    # def player_is_town(self, player: str) -> bool:
    #     for player_ in self.current_players:
    #         if player_.username.lower() == player.lower():
    #             return player_.alignment == c.TOWN
    #     return False
    
    # def player_is_mafia(self, player: str) -> bool:
    #     for player_ in self.current_players:
    #         if player_.username.lower() == player.lower():
    #             return player_.alignment == c.MAFIA
    #     return False
    
    def get_random_town(self) -> str:
        """
        Throws an exception if there are 0 town members alive.
        """
        town_players = list(filter(lambda player : player.alignment == c.TOWN, self.current_players))
        return random.choice(town_players).username
    
    def filter_players(self, filter_func: Callable, living_players_only: bool) -> 'list[p.Player]':
        result = []
        for player in (self.original_players if not living_players_only else self.current_players):
            if filter_func(player):
                result.append(player)
        return result


    def player_exists(self, player: str, count_dead_as_existing=False) -> bool:
        for player_ in (self.current_players if not count_dead_as_existing else self.original_players):
            if player_.username.lower() == player.lower():
                return True
        return False

    def is_valid_nightkill(self, player_to_kill: str) -> bool:
        player = self.get_player_object_living_players_only(player_to_kill)
        return player is not None and player.alignment != c.MAFIA
    
    def is_valid_kill(self, player_to_kill: str) -> bool:
        return self.player_exists(player_to_kill)
    
    def process_elimination(self, player: str) -> bool:
        """
        Returns True if the player was valid.

        This is similar to process_death, but ignores all protection.
        """
        if self.is_valid_kill(player):
            for num, possible_eliminated_player in enumerate(self.current_players):
                if player.lower() == possible_eliminated_player.username.lower():
                    self.current_players.pop(num)
            return True
        return False
    
    def process_modkill(self, player: str) -> bool:
        """
        Returns True if the player exists, False otherwise.

        Modkills cannot be prevented by any player passives / attributes.

        At the time of writing, this method is equivalent to process_elimation, but in the future
        there may be ways to get out of an elimination, whereas modkills can never be prevented.
        """
        if not self.player_exists(player):
            return False
        for num, possible_modkilled_player in enumerate(self.current_players):
            if player.lower() == possible_modkilled_player.username.lower():
                self.current_players.pop(num)
        return True
        
    def count_players_of_alignment(self, alignment: int):
        num = 0
        for player in self.current_players:
            if player.alignment == alignment:
                num += 1
        return num
    
    def get_player_object_living_players_only(self, username: str) -> "p.Player | None":
        for player in self.current_players:
            if player.username.lower() == username.lower():
                return player
        return None
    
    def get_player_object_original_players(self, username: str) -> "p.Player | None":
        for player in self.original_players:
            if player.username.lower() == username.lower():
                return player
        return None

    def get_flip_path(self, username: str) -> str:
        player_object = self.get_player_object_original_players(username)
        if player_object is None:
            print("The flip path of a non-existant player was requested. This is not allowed.")
            raise GamestateException("The flip path of a non-existant player was requested. This is not allowed.")
        return player_object.rolecard_path

    def is_game_over(self):
        print("Doing game over check: ")
        print(f"{self.count_players_of_alignment(c.TOWN)=}")
        print(f"{self.count_players_of_alignment(c.MAFIA)=}")
        print(f"{self.is_day=}")
        print(f"{self.wincon_is_parity=}")
        is_town_win = self.count_players_of_alignment(c.MAFIA) == 0 and self.count_players_of_alignment(c.TOWN) > 0
        is_mafia_win = self.count_players_of_alignment(c.TOWN) == 0 or (self.wincon_is_parity and self.count_players_of_alignment(c.MAFIA) >= self.count_players_of_alignment(c.TOWN))
        game_over = is_town_win or is_mafia_win
        print(f"{game_over=}")
        return game_over

    def is_town_win(self):
        """
        Throws an exception if game isn't over!
        """
        if self.is_game_over():
            for player in self.current_players:
                if player.alignment == c.MAFIA:
                    return False
            return True
        else:
            raise GamestateException("is_town_win cannot be called unless is_game_over() is true.")
    
    def go_next_phase(self):
        """
        Increments the phase (so, D1 -> N1, or N2 -> D3, for example).
        """
        self.phase_count = self.phase_count if self.is_day else self.phase_count + 1
        self.is_day = not self.is_day
        # self.save_to_json()

    def get_living_players(self) -> list[str]:
        """
        Returns the names of the living players, in a randomized order.

        The randomized order ensures that no role/alignment-indicative information can slip through as a result of this method.
        """
        random.seed(time.time())
        result = []
        for player in self.current_players:
            result.append(player.username)
        random.shuffle(result)
        return result
    
    def list_about_to_die_players(self) -> list[str]:
        """
        Lists the players who are currently at 0 health or less.

        When a player dies, they should be removed from the gamestate - this is handled by remove_dead_players.
        """
        about_to_die_players = []
        for player in self.current_players:
            if player.health <= 0:
                about_to_die_players.append(player.username)
        print(f"{about_to_die_players=}")
        return about_to_die_players

    def kill_about_to_die_players(self) -> None:
        """
        Removes any about-to-die players from the gamestate (ie, players are 0 or less health).
        """
        self.current_players = list(filter(lambda player : player.health > 0, self.current_players))

    def substitute_player(self, current_username: str, new_username: str) -> bool:
        """
        Changes the username of the player with current_username to new_username.

        Returns True if current_username refers to a valid player object, False otherwise.
        """
        player_object = self.get_player_object_original_players(current_username)
        if player_object is None:
            return False
        player_object.username = new_username
        return True
    
    def is_nominated(self, player: 'p.Player'):
        return player in self.get_all_nominated_players()
    
    def get_all_nominated_players(self):
        if not config.is_botf:
            return []
        result = []
        for player in self.current_players:
            if player.target_of_nomination is not None:
                result.append(player.target_of_nomination.username)
        return result
        
    def get_nominator_to_nominee_dict(self) -> dict[str, str]:
        return self.get_nominations()
    
    def print_playerlists(self) -> None:
        print("ORIGINAL PLAYERS: ")
        for player in self.original_players:
            print(player.username)
        print("CURRENT PLAYERS: ")
        for player in self.current_players:
            print(player.username)
    
    # def create_log(self, log_class: type, sources: list[p.Player] | None, sinks: list[p.Player], action_types: list[str], was_instant: bool):
        """
        Creates a log, and adds it to the end of the game_log.

        Parameters -

        log_class: The class of the log - currently, Visit and Feedback are the classes.
        sources: The players this event originated from. Can be None.
        sinks: The players this event "went to" (in the case of Visit, this means the targets, 
            in the case of Feedback, this means those who received the feedback, etc)
        action_types: The type(s) of action that caused this event
        was_instant: True if this was caused by an instant action, False if it was at phase end
        """
    #     assert issubclass(log_class, RecordedEvent)
    #     #log = log_class(sources=sources, sinks=sinks, action_types=action_types, phase_count=self.phase_count, was_day=self.is_day, was_instant=was_instant)
    #     self.game_log.append(log)
    
    
    def record_feedback(self, feedback_string: str, generating_players: list["p.Player"], receiving_players: list["p.Player"], action_types: list[str], was_instant: bool):
        """
        Creates a Feedback log, and adds it to the end of the game_log.

        Parameters -

        feedback_string: The exact feedback received
        generating_players: The players this event originated from. Can be empty.
        receiving_players: The players that received the feedback; can be empty (though that would be strange)
        action_types: The type(s) of action that caused this event
        was_instant: True if this was caused by an instant action, False if it was at phase end
        """
        log = Feedback(feedback_string=feedback_string, generating_players=generating_players, receiving_players=receiving_players, action_types=action_types, phase_count=self.phase_count, was_day=self.is_day, was_instant=was_instant)
        self.game_log.append(log)
    
    def record_visit(self, visitors: list["p.Player"], targets: list["p.Player"], action_types: list[str], was_instant: bool) -> None:
        """
        Creates a Visit log, and adds it to the end of the game_log.

        Parameters -

        visitors: The players who are visiting. Can be empty, though that would be strange.
        targets: The players that were visited; can be empty, though that would be strange.
        action_types: The type(s) of action that this visit
        was_instant: True if this was caused by an instant action, False if it was at phase end
        """
        log = Visit(visitors=visitors, targets=targets, action_types=action_types, phase_count=self.phase_count, was_day=self.is_day, was_instant=was_instant)
        self.game_log.append(log)

    def get_nominations(self) -> dict[str, str]:
        """
        Returns a dictionary of nominations, of the form nominations[player who nominated] == nominee.
        This dictionary is sorted by nomination order.
        """
        if not config.is_botf:
            return dict()
        result = []
        for player in self.current_players:
            if player.target_of_nomination is not None:
                result.append((player.username, player.target_of_nomination.username, player.nomination_order))

        result.sort(key=lambda x : x[2])

        result_as_dict = dict()
        for nominator_nominee_pair in result:
            result_as_dict[nominator_nominee_pair[0]] = nominator_nominee_pair[1]

        print(f"Nominations so far: {result_as_dict}")
        return result_as_dict
    
    def reset_nominations(self) -> None:
        for player in self.current_players:
            player.target_of_nomination = None

class RecordedEvent:
    def __init__(self, sources: list["p.Player"] | None, sinks: list["p.Player"] | None, action_types: list[str], phase_count: int, was_day: bool, was_instant: bool) -> None:
        self.sources = sources.copy() if sources is not None else []
        self.sinks = sinks.copy() if sinks is not None else []
        self.action_types = action_types
        self.phase_count = phase_count
        self.was_day = was_day
        self.was_instant = was_instant

    def __getattr__(self, attr):
        print(f"WARNING: Attempted to access attribute {attr}. This is allowed, because all {type(self).__name__}"
              " attributes have default values of 0, unless otherwise specified. However, "
              "this could be in error, so this warning is provided.")
        return 0

class Visit(RecordedEvent):
    def __init__(self, visitors: list["p.Player"], targets: list["p.Player"], action_types: list[str], phase_count: int, was_day: bool, was_instant: bool) -> None:
        RecordedEvent.__init__(self, sources=visitors, sinks=targets, action_types=action_types, phase_count=phase_count, was_day=was_day, was_instant=was_instant)
        self.visitors = self.sources
        self.targets = self.sinks

class Feedback(RecordedEvent):
    def __init__(self, feedback_string: str, generating_players: list["p.Player"], receiving_players: list["p.Player"], action_types: list[str], phase_count: int, was_day: bool, was_instant: bool) -> None:
        RecordedEvent.__init__(self, sources=generating_players, sinks=receiving_players, action_types=action_types, phase_count=phase_count, was_day=was_day, was_instant=was_instant)
        self.generating_players = self.sources
        self.receiving_players = self.sinks
        self.feedback_string = feedback_string


