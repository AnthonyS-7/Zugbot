import re
import post as p
from roles_folder.roles_exceptions import ParsingException, ActionException
import game_state
import modbot


SYNTAX_PARSER_NONNEGATIVE_INT = (r"([0-9]+)", 0)
SYNTAX_PARSER_PLAYERNAME = (r"([^ \\\n]+)", 1)
SYNTAX_PARSER_NO_SPACE_STRING = (r"([^ \\\n]+)", 2) # Numbers are just so that these all do not equal eachother

def syntax_parser_constructor(command_name: str, parameter_list: list[tuple[str, int]]):
    """
    This constructs syntax parsers for slash commands.

    This method can support an arbitrary number of parameters, and returns a syntax parser function
    which takes a post and parses it.
    """
    return lambda post : _syntax_parser_template_new(post, command_name, parameter_list)

def _syntax_parser_template_new(post: p.Post, command_name: str, parameter_list: list[tuple[str, int]]):
    """
    This parses the specified post, looking for the specified command name and parameter list.

    This is intended only to be used directly in syntax_parser_constructor.

    TODO: test this
    """
    re_string = rf"/{command_name}"

    for parameter, discard in parameter_list:
        re_string += " " + parameter
    re_parser = re.compile(re_string, re.IGNORECASE)
    
    re_result = re_parser.search(post.content)
    if re_result is None:
        raise ParsingException(f"This post did not contain the specified command.")
    
    final_result = []
    for num in range(len(parameter_list)):
        this_parameter = re_result.group(num + 1)
        if parameter_list[num] == SYNTAX_PARSER_PLAYERNAME:
            this_parameter = modbot.resolve_name(this_parameter)
            this_parameter = modbot.gamestate.get_player_object_living_players_only(this_parameter)
            if this_parameter is None:
                raise ParsingException("This player does not exist!")
        final_result.append(this_parameter)
    return final_result


