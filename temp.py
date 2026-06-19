import asyncio

import yaml

with open('temp.yaml', 'r') as players_file:
    players_dict: dict = yaml.load(players_file, yaml.Loader)
    playerlist = players_dict['playerlist_usernames']

