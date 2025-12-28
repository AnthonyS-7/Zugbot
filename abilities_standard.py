boolean_var: bool = True
if boolean_var:
    import ability
    import syntax_parser_standard as syn
    import fol_interface
    import player
import constants as c

def VOTECOUNT_ABILITY():
    """
    Creates and returns a votecount ability.
    """
    return ability.Ability(
        ability_name="Votecount Request",
        syntax_parser=syn.SyntaxParser("votecount", parameter_list=[]),
        action=ability.Action(lambda playername, gamestate : fol_interface.post_votecount(nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominations())),
        is_instant=True,
        ignore_action_deadline=True
    )

def VOUTECOUNT_ABILITY():
    """
    Creates and returns a voutecount ability.
    """
    return ability.Ability(
        ability_name="Voutecount Request",
        syntax_parser=syn.SyntaxParser("voutecount", parameter_list=[]),
        action=ability.Action(lambda playername, gamestate : fol_interface.post_votecount(nominated_players=gamestate.get_all_nominated_players(), nominator_to_nominee_dict=gamestate.get_nominations(), say_voutecount=True)),
        is_instant=True,
        ignore_action_deadline=True
    )

def MAKE_VANILLA_TOWN(username: str) -> "player.Player":
    import player
    result = player.Player(username, c.TOWN, "town.txt", abilities=None)
    return result

def MAKE_MAFIA_GOON(username: str) -> "player.Player":
    import player
    result = player.Player(username, c.MAFIA, "mafia.txt", abilities=None)
    return result
