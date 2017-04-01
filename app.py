import os
from flask import Flask
import requests
import json
import re

app = Flask(__name__)

sce_content = None
prices = None

def get_price(app_id):
    
    if not prices:
        print('Could not load the game prices')
        return None
    if app_id is None:
        print('Could not find the game')
        return None
    return prices[app_id]

def get_app_id(game_name):

    if not sce_content:
        return None
    
    pattern = '(\d*)">' + str(game_name) + '</option>'
    id_regex = re.search(pattern, sce_content)
    
    if not id_regex:
        return None

    return id_regex.group(1)

def load_sce_inventory():
    
    global sce_content, prices
    
    #Go to Steam Card Exchange inventory
    sce = requests.get('http://www.steamcardexchange.net/index.php?inventory')
    sce_content = str(sce.content)[2:]

    #Getting all game prices
    prices_regex = re.search('var gameprices.*({.*});.*var stocklist', sce_content, re.DOTALL)
    if prices_regex:
        prices = json.loads(prices_regex.group(1))

@app.route('/')
def home():

    load_sce_inventory()
    game_name = 'GooCubelets 2'
    return 'Current price for ' + game_name + ' is ' + get_price(get_app_id(game_name))

if __name__ == '__main__':
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port = port)
