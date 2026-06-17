import fol_interface
import asyncio

import yaml

with open('temp.yaml', 'r') as players_file:
    players_dict: dict = yaml.load(players_file, yaml.Loader)
    playerlist = players_dict['playerlist_usernames']
    asyncio.run(fol_interface.ensure_all_players_exist_and_are_spelled_correctly(playerlist))

