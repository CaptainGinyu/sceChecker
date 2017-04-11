import os
import sys
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import json
import re
import urllib.parse
import math

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

sce_content = None
prices = None

class CardHistory(db.Model):
    
    __tablename__ = 'card_history'
    label = db.Column(db.Text, primary_key = True, nullable = False)
    curr_info = db.Column(db.JSON)
    prev_info = db.Column(db.JSON)
    last_update = db.Column(db.Text)

    def __init__(self, label, curr_info, prev_info, last_update):
        self.label = label
        self.curr_info = curr_info
        self.prev_info = prev_info
        self.last_update = last_update

def get_num_cards_in_set(app_id):

    if not prices:
        return 0

    if not app_id:
        return 0

    pattern = '"' + str(app_id) + '":.?\n?\["(\d*)"'
    num_cards_regex = re.search(pattern, sce_content)

    if not num_cards_regex:
        return 0

    return int(num_cards_regex.group(1))

def get_price(app_id):
    
    if not prices:
        print('Could not load the game prices')
        sys.stdout.flush()
        return None
    if app_id is None:
        print('Could not find the game')
        sys.stdout.flush()
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

    return game_name_regex.group(1).encode('utf-8').decode('unicode-escape').encode('latin-1').decode('utf-8')

def load_sce_inventory():
    
    global sce_content, prices
    
    #Go to Steam Card Exchange inventory
    sce = requests.get('http://www.steamcardexchange.net/index.php?inventory')
    sce_content = str(sce.content)[2:]

    #Getting all game prices
    prices_regex = re.search('var gameprices.*({.*});.*var stocklist', sce_content, re.DOTALL)
    if prices_regex:
        prices = json.loads(prices_regex.group(1))
        new_entry_count = 0
        for app_id in list(prices):
            curr_game_name = get_game_name(app_id)
            prices[curr_game_name] = prices.pop(app_id)

def update_postgres():

    global prices

    if not prices:
        print('Steam Card Exchange was down at ') + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sys.stdout.flush()
        return

    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    prices_row = CardHistory.query.filter_by(label = 'prices').first()

    if prices_row:
        prices_row.prev_info = prices_row.curr_info
        prices_row.curr_info = prices
        prices_row.last_update = update_time
    else:
        db.session.add(CardHistory('prices', prices, None, update_time))

    db.session.commit()

@app.route('/')
def index():

    print('ACCESSED HOME PAGE!')
    sys.stdout.flush()
    
    prices_row = CardHistory.query.filter_by(label = 'prices').first()    
    
    if prices_row:
        curr_prices = prices_row.curr_info
        prev_prices = prices_row.prev_info
        update_time = prices_row.last_update
    else:
        curr_prices = {}
        prev_prices = {}
        update_time = 'Have not done first update yet'
    
    return render_template('index.html', curr_prices = curr_prices, prev_prices = prev_prices, update_time = update_time)

@app.route('/steamlvluptosce')
def steamlvluptosce():

    print('ACCESSED STEAMLVLUP TO SCE PAGE!')
    sys.stdout.flush()

    prices_row = CardHistory.query.filter_by(label = 'prices').first()    
    
    if prices_row:
        curr_prices = prices_row.curr_info
        update_time = prices_row.last_update
    else:
        curr_prices = {}
        update_time = 'Have not done first update yet'

    page = 0
    steamlvlup_url = 'https://steamlvlup.com/shop/items?hide_exist=false&page=' + str(page) + '&sort_by=price&sort_type=asc'
    steamlvlup_page = requests.get(steamlvlup_url)
    if steamlvlup_page.status_code != 200:
        return render_template('steamlvluptosce.html', request_status = 'error', steamlvlup_prices = {}, curr_prices = {}, update_time = update_time)
    steamlvlup_json = json.loads(steamlvlup_page.text)
    steamlvlup_items = steamlvlup_json['items']
    if type(steamlvlup_items) is dict:
        steamlvlup_items = steamlvlup_items.values()

    #This is how the STEAMLVLUP guys calculate the last page
    last_page = math.ceil(steamlvlup_json['max_count'] / 28)

    for page in range(1, last_page):
        steamlvlup_url = 'https://steamlvlup.com/shop/items?hide_exist=false&page=' + str(page) + '&sort_by=price&sort_type=asc'
        steamlvlup_page = requests.get(steamlvlup_url)
        steamlvlup_json = json.loads(steamlvlup_page.text)
        if not steamlvlup_json['success']:
            break
        if type(steamlvlup_json['items']) is dict:
            steamlvlup_items += steamlvlup_json['items'].values()
        elif type(steamlvlup_json['items']) is list:
            steamlvlup_items += steamlvlup_json['items']

    steamlvlup_prices = {}
    sce_card_set_prices = {}
    load_sce_inventory()
    for item in steamlvlup_items:
        app_id = item['appid']
        curr_item_name = get_game_name(app_id)
        steamlvlup_prices[curr_item_name] = item['set_price']
        if curr_item_name not in curr_prices:
            sce_card_set_prices[curr_item_name] = 0
        else:
            sce_card_set_prices[curr_item_name] = get_num_cards_in_set(app_id) * int(curr_prices[curr_item_name])
        
    return render_template('steamlvluptosce.html', request_status = 'success', sce_card_set_prices = sce_card_set_prices, steamlvlup_prices = steamlvlup_prices, curr_prices = curr_prices, update_time = update_time)

if __name__ == '__main__':
    
    port = int(os.environ.get("PORT", 5432))
    app.run(host='0.0.0.0', port = port)
