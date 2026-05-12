from typing import Callable
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import player
    import ability

import setup
import constants as c

def generate_rolelist() -> list[Callable[[str], "player.Player"]]:
    import abilities_standard
    return 6 * [lambda username : abilities_standard.MAKE_VANILLA_TOWN(username, 'town.txt')] \
        + 1 * [lambda username : abilities_standard.MAKE_TOWN_INNOCENT_CHILD(username, 'town_innocent_child_day_2.txt', allowed_cycles=lambda x : x >= 2)] \
        + 1 * [lambda username : make_bomb_inventor(username, 'town_inventor.txt')] \
        + 1 * [lambda username : abilities_standard.MAKE_MAFIA_GOON(username, 'mafia.txt')] \
        + 1 * [lambda username : make_pr_killer(username, 'mafia_pr_killer.txt')]


def get_setup():
    return setup.Setup(game_name="bomb10",
                allow_no_exe=True,
                playercount=10,
                get_rolelist=generate_rolelist
        )

def inventor_action(ability_to_add_creator: Callable[[], 'ability.Ability']):
    import fol_interface
    import ability
    def inner_func(acting_player: "player.Player", gamestate, ability: "ability.Ability", target_player: "player.Player"):
        ability_to_add = ability_to_add_creator()
        target_player.abilities.append(ability_to_add)
        shot_count = ability_to_add.ability_restrictions.shot_count
        fol_interface.send_message(f"You have been given a {shot_count if shot_count != -1 else 'infinite'}-shot {ability_to_add.ability_name} ability! Use it with /bomb [player].", target_player.username)
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

def make_pr_killer(username: str, flip_path: str) -> "player.Player":
    import ability
    import syntax_parser_standard as syn
    import player
    def pr_kill_ability() -> "ability.Ability":
        return ability.Ability(
            ability_name="PR Killer",
            syntax_parser=syn.SyntaxParser(command_name="invent", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
            action=pr_kill_action(),
            ability_restrictions=ability.AbilityRestrictions(shot_count=1),
            ability_modifiers=ability.AbilityModifiers(damage_amount=100),
            action_types=[c.KILLING]
        )
    def pr_kill_action() -> "ability.Action":
        def inner_func(acting_player: "player.Player", gamestate, ability: "ability.Ability", target_player: "player.Player"):
            ability_names_of_target = [ability.ability_name for ability in target_player.abilities]
            if "Inventor" in ability_names_of_target:
                target_player.take_damage(ability.ability_modifiers)
        return ability.Action(inner_func)
    
    result = player.Player(username, c.MAFIA, flip_path, abilities=[pr_kill_ability()])
    return result

def make_bomb_inventor(username: str, flip_path: str):
    import player
    import syntax_parser_standard as syn
    import ability
    import modbot
    import fol_interface
    async def bomb_action_function(acting_player: player.Player, gamestate, ability: "ability.Ability", target_player: player.Player):
        print("Running the Bomb action now.")
        target_player.take_damage(ability.ability_modifiers)
        acting_player.take_damage(ability.ability_modifiers)
        fol_interface.to_post_cache += "# A bomb goes off! \n"
        await modbot.resolve_current_deaths(gamestate)
    
    def ability_creator():
        print("Creating Bomb Ability!")
        return ability.Ability(
            ability_name="Bomb",
            syntax_parser=syn.SyntaxParser(command_name="bomb", parameter_list=[syn.SYNTAX_PARSER_PLAYERNAME]),
            action=ability.Action(bomb_action_function),
            is_instant=True,
            ability_restrictions=ability.AbilityRestrictions(shot_count=1, day_required=True, night_required=False),
            ability_modifiers=ability.AbilityModifiers(invest_power=10, damage_amount=100),
            action_types=[c.ACTION_TYPE_OTHER]
        )
    print("About to create Inventor player.")
    result = player.Player(username, c.TOWN, flip_path, abilities=[inventor_ability(shot_count=1, ability_to_add_creator=ability_creator)])
    return result



