from typing import Callable
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player
    import ability

import setup
import constants as c

def generate_rolelist() -> list[Callable[[str], "player.Player"]]:
    import abilities_standard
    return 5 * [lambda username : abilities_standard.MAKE_VANILLA_TOWN(username, 'town.txt')] \
        + 2 * [lambda username : abilities_standard.MAKE_MAFIA_GOON(username, 'mafia.txt')] \
        + 1 * [lambda username : make_desperado_inventor(username, 'town_inventor.txt')]


def get_setup():
    return setup.Setup(game_name="desp8",
                allow_no_exe=False,
                playercount=8,
                get_rolelist=generate_rolelist
        )

def inventor_action(ability_to_add_creator: Callable[[], 'ability.Ability']):
    import fol_interface
    import ability
    def inner_func(acting_player: "player.Player", gamestate, ability: "ability.Ability", target_player: "player.Player"):
        ability_to_add = ability_to_add_creator()
        target_player.abilities.append(ability_to_add)
        shot_count = ability_to_add.ability_restrictions.shot_count
        fol_interface.send_message(f"You have been given a {shot_count if shot_count != -1 else 'infinite'}-shot {ability_to_add.ability_name} ability! Use it with /shoot [player].", target_player.username)
    print("About to create the Inventor action.")
    return ability.Action(inner_func)

def inventor_ability(shot_count: int, ability_to_add_creator: Callable[[], 'ability.Ability']) -> "ability.Ability":
    import ability
    import syntax_parser_standard as syn
    print("About to create the Inventor ability.")
    return ability.Ability(
        ability_name="Inventor",
        syntax_parser=syn.SyntaxParser(command_name="invent", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
        action=inventor_action(ability_to_add_creator=ability_to_add_creator),
        is_instant=False,
        ability_restrictions=ability.AbilityRestrictions(shot_count=shot_count),
        action_types=[c.ACTION_TYPE_OTHER]
    )

def make_desperado_inventor(username: str, flip_path: str):
    import player
    import syntax_parser_standard as syn
    import ability
    import modbot
    import fol_interface
    async def desperado_action_function(acting_player: player.Player, gamestate, ability: "ability.Ability", target_player: player.Player):
        print("Running the Desperado action now.")
        if target_player.get_alignment(ability.ability_modifiers) == c.TOWN:
            acting_player.take_damage(ability.ability_modifiers)
        else:
            target_player.take_damage(ability.ability_modifiers)
        fol_interface.to_post_cache += "# A shot rings out! \n"
        await modbot.resolve_current_deaths(gamestate)
    
    def ability_creator():
        print("Creating Desperado Ability!")
        return ability.Ability(
            ability_name="Desperado",
            syntax_parser=syn.SyntaxParser(command_name="shoot", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
            action=ability.Action(desperado_action_function),
            is_instant=True,
            ability_restrictions=ability.AbilityRestrictions(shot_count=1, day_required=True, night_required=False),
            ability_modifiers=ability.AbilityModifiers(invest_power=10, damage_amount=1),
            action_types=[c.ACTION_TYPE_OTHER]
        )
    print("About to create Inventor player.")
    result = player.Player(username, c.TOWN, flip_path, abilities=[inventor_ability(shot_count=1, ability_to_add_creator=ability_creator)])
    return result



