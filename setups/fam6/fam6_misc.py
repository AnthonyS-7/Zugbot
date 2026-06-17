import os
import random
ADS_FOLDER_NAME = 'ita_ads'
import constants as c

def get_path_to_ads_folder():
    return os.path.join(c.SETUP_FOLDER, 'fam6', ADS_FOLDER_NAME)

def get_random_ad():
    if random.random() < 0.08:
        options = os.listdir(get_path_to_ads_folder())
        choice = random.choice(options)
        result = ''
        with open(os.path.join(c.SETUP_FOLDER, 'fam6', ADS_FOLDER_NAME, choice), 'r') as file:
            result = file.read()
        return result
    else:
        return ''