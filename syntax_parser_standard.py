import re

import post as p
from roles_folder.roles_exceptions import ParsingException
import game_state
import fol_interface
import modbot

SYNTAX_PARSER_NONNEGATIVE_INT = (r"([0-9]+)", 0)
SYNTAX_PARSER_PLAYERNAME = (r"([^ \\\n]+)", 1)
SYNTAX_PARSER_NO_SPACE_STRING = (r"([^ \\\n]+)", 2) # Numbers are just so that these all do not equal eachother

class SyntaxParser:
    def __init__(self, command_name: str, parameter_list: list[tuple[str, int]] | None, include_whole_post=False) -> None:
        self.command_name = command_name
        self.parameter_list = [] if parameter_list is None else parameter_list
        self.include_whole_post = include_whole_post
    
    def parse_discourse_post(self, post: 'p.Post'):
        re_string = rf"/{self.command_name}"

        for parameter, discard in self.parameter_list:
            re_string += " " + parameter
        print(f"Looking for {re_string=}")
        re_parser = re.compile(re_string, re.IGNORECASE)
        
        re_result = re_parser.search(post.content)
        if re_result is None:
            raise ParsingException(f"This post did not contain the specified command.")
        
        final_result = []
        for num in range(len(self.parameter_list)):
            this_parameter = re_result.group(num + 1)
            if self.parameter_list[num] == SYNTAX_PARSER_PLAYERNAME:
                assert modbot.gamestate is not None
                this_parameter = modbot.resolve_name(this_parameter)
                this_parameter = modbot.gamestate.get_player_object_living_players_only(this_parameter)
                if this_parameter is None:
                    raise ParsingException("This player does not exist!")
            elif self.parameter_list[num] == SYNTAX_PARSER_NONNEGATIVE_INT:
                this_parameter = int(this_parameter)
            final_result.append(this_parameter)
        if self.include_whole_post:
            final_result.append(post.quoteString())
        return final_result

    # TODO: add method to parse Discord post
