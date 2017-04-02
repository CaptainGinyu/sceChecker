import os
from flask import Flask
from flask import render_template
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

def get_game_name(app_id):

    if not sce_content:
        return None

    pattern = 'appid-' + str(app_id) + '">(.*?)</option>'
    game_name_regex = re.search(pattern, sce_content)

    if not game_name_regex:
        return None

    return game_name_regex.group(1)

def load_sce_inventory():
    
    global sce_content, prices
    
    #Go to Steam Card Exchange inventory
    sce = requests.get('http://www.steamcardexchange.net/index.php?inventory')
    sce_content = str(sce.content)[2:]

    #Getting all game prices
    prices_regex = re.search('var gameprices.*({.*});.*var stocklist', sce_content, re.DOTALL)
    if prices_regex:
        prices = json.loads(prices_regex.group(1))
        for app_id in list(prices):
            prices[get_game_name(app_id)] = prices.pop(app_id)

@app.route('/')
@app.route('/index')
def home():

    load_sce_inventory()
    return render_template('index.html', prices = prices)

if __name__ == '__main__':
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port = port)
