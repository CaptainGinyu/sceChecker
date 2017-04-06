import os
import sys
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
import requests
import json
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

sce_content = None
prices = None

class Cardset(db.Model):
    
    __tablename__ = 'cards'
    game_name = db.Column(db.Text, primary_key = True)
    curr_price = db.Column(db.Integer)
    prev_price = db.Column(db.Integer)

    def __init__(self, game_name, curr_price, prev_price):
        self.game_name = game_name
        self.curr_price = curr_price
        self.prev_price = prev_price

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
            #print('Dealing with ' + curr_game_name)
            #sys.stdout.flush()
            #if not db.session.query(Cardset).filter(Cardset.game_name == curr_game_name).count():
                #cardset = Cardset(curr_game_name, prices[curr_game_name], 0)
                #db.session.add(cardset)
                #new_entry_count += 1
                #print('ADDED ' + curr_game_name)
                #sys.stdout.flush()
                ##print('current number of new entries: ' + str(new_entry_count))
                #sys.stdout.flush()
        #print('COMMITTING...')
        #sys.stdout.flush()
        #db.session.commit()

@app.route('/')
@app.route('/index')
def home():

    print('ACCESSED HOME PAGE!')
    sys.stdout.flush()
    load_sce_inventory()
    print('LOADED SCE INVENTORY!')
    sys.stdout.flush()
    return render_template('index.html', prices = prices)

if __name__ == '__main__':
    
    port = int(os.environ.get("PORT", 5432))
    app.run(host='0.0.0.0', port = port)
