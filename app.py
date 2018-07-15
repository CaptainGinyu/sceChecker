import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import json
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Favorites(db.Model):

    __tablename__ = 'favorites'
    steamid = db.Column(db.Text, primary_key = True, nullable = False)
    username = db.Column(db.Text, nullable = False)

    def __init__(self, steamid, username):
        self.steamid = steamid
        self.username = username

#######################################################
# Functions directly dealing with Steam Card Exchange #
#######################################################

def get_sce_inventory():

    inventory = {}

    #Accessing Steam Card Exchange
    sce = requests.get('http://www.steamcardexchange.net/api/request.php?GetInventory&_=1496541700233')
    if sce.status_code != 200:
        return inventory

    #Dealing with JSON
    '''
    Example:

    >>> sceJson['data'][0]
    [['449940', '! That Bastard Is Trying To Steal Our Gold !', 4, 1, 1], 8, 13, [5, 4, 2]]
    Index 0: See second section below
    Index 1: Price
    Index 2: Total numbers of cards in stock
    Index 3: See third section below

    >>> sceJson['data'][0][0]
    ['449940', '! That Bastard Is Trying To Steal Our Gold !', 4, 1, 1]
    Index 0: App ID
    Index 1: Game name
    Index 2: Greatest number of copies of one card
    Index 3: Enabled or disabled? (1 is enabled, 0 is disabled)
    Index 4: Marketable or non-marketable? (1 is marketable, 0 is non-marketable)

    >>> sceJson['data'][0][3]
    [5, 4, 2]
    Index 0: Number of cards in set
    Index 1: Number of unique cards
    Index 2: Number of full sets if Index 0 and Index 1 are equal (otherwise this value is useless apparently)
    
    '''    
    try:
        sceJson = json.loads(sce.text)
    except ValueError:
        return inventory

    for game in sceJson['data']:
        generalInfo = game[0]

        #Storing an entry into prices dictionary
        #Key: App ID
        #Value: [Game name, card price, number of cards in set, set price]
        card_price = game[1]
        num_cards_in_set = game[3][0]
        inventory[str(generalInfo[0])] = [generalInfo[1], card_price, num_cards_in_set, card_price * num_cards_in_set]

    return inventory
    
#################
# Miscellaneous #
#################

def get_steamid_from_profile(profile_url):

    if not re.search('http.*://steamcommunity\.com/', profile_url):
        return ''

    try:
        profile = requests.get(profile_url)
    except:
        return ''
    if profile.status_code != 200:
        return ''

    profile_regex = re.search('g_rgProfileData.*"steamid":"([0-9]*)"', profile.text, re.MULTILINE)
    if profile_regex:
        return profile_regex.group(1)

    return ''

def get_steam_inventory_cards(cards, steam_id, last_assetid, sce_inventory):

    #Accessing inventory of the user with the passed in steam_id
    #Presence of last_assetid indicates multiple pages
    steam_inventory_url = 'http://steamcommunity.com/inventory/' + str(steam_id) + '/753/6?l=english&count=5000'
    if last_assetid is not None:
        steam_inventory_url += '&start_assetid=' + str(last_assetid)
    
    steam_inventory_request = requests.get(steam_inventory_url)

    #When request is not successful for some reason
    if steam_inventory_request.status_code != 200:
        return (cards, None)

    #Case for if we get we get null instead of a JSON string
    if steam_inventory_request.text == 'null':
        return (cards, None)

    #String to JSON
    steam_inventory_json = json.loads(steam_inventory_request.text)
    
    if steam_inventory_json['success'] != 1:
        return (cards, None)
    
    if 'descriptions' not in steam_inventory_json:
        return (cards, None)

    steam_inventory_items = steam_inventory_json['descriptions']

    #If we called this function with last_assetid, that means
    #that we are starting with the last item from the previous page,
    #so we want to start at the item after this because otherwise
    #we would be counting the item that we already counted
    if last_assetid is not None:
        steam_inventory_items = steam_inventory_items[1:]

    #Going through all items in the Steam inventory
    for item in steam_inventory_items:
        #Making sure we only get Normals (ie. no Foils)
        if item['tags'][2]['localized_tag_name'] == 'Normal':
            #Making sure we only get trading cards (ie. No gems, emoticons, etc.)
            trading_card_regex = re.search('(.*) Trading Card', item['type'])
            if trading_card_regex:
                #Getting the app ID of the current game we are looking at right now
                curr_game = str(item['market_fee_app'])

                #If we have an entry for this game in our cards dictionary already, increase the count by 1
                if curr_game in cards:
                    cards[curr_game][1] += 1
                #Otherwise, we add a new list where Index 0 is the SCE info of the game and Index 1 is the number 1
                #(because this would be our first card of this game we came across so far)
                else:
                    cards[curr_game] = [sce_inventory[curr_game], 1]

    #Including the last_assetid if there is one
    if 'last_assetid' in steam_inventory_json:
        result = (cards, steam_inventory_json['last_assetid'])
    else:
        result = (cards, None)

    return result

###########
# Routing #
###########

@app.route('/', methods = ['GET', 'POST'])
def steam_inventory_to_sce_prices():    

    if request.method == 'GET':
        return render_template('inventorytosce.html')
    
    sce_inventory = get_sce_inventory()
    steam_id = request.form.get('steam_id')
    if not steam_id.isdigit():
        steam_id = get_steamid_from_profile(steam_id)

    #Keys are game names, values are number of unique cards owned for a given game
    cards = {}
    
    last_assetid = None

    cards, last_assetid = get_steam_inventory_cards(cards, steam_id, None, sce_inventory)

    while last_assetid is not None:
        cards, last_assetid = get_steam_inventory_cards(cards, steam_id, last_assetid, sce_inventory)
    
    return jsonify(cards)

@app.route('/add_to_favorites', methods = ['POST'])
def add_to_favorites():

    steamid = request.form.get('steamid')

    if (steamid == None) or (len(steamid) == 0):
        return

    if Favorites.query.filter_by(steamid = steamid).first() == None:
        db.session.add(Favorites(steamid, 'placeholder'))
        db.session.commit()

@app.route('/remove_from_favorites', methods = ['POST'])
def remove_from_favorites():

    steamid = request.form.get('steamid')

    if (steamid == None) or (len(steamid) == 0):
        return

    query = Favorites.query.filter_by(steamid = steamid).first()
    
    if query != None:
        db.session.delete(query)
        db.session.commit()

@app.route('/get_all_favorites', methods = ['POST'])
def get_all_favorites():

    return jsonify(favorites = Favorites.query.all())

@app.route('/steamlvluptosce', methods = ['GET', 'POST'])
def steamlvluptosce():

    if request.method == 'GET':
        return render_template('steamlvluptosce.html')

    sce_inventory = get_sce_inventory()

    #Navigating to the first page of results from STEAMLVLUP
    page = 0
    steamlvlup_page = requests.get('https://steamlvlup.com/shop/items?hide_exist=false&page_size=999&page=' + str(page) + '&sort_by=price&sort_type=asc')

    #Case for when STEAMLVLUP site is having issues
    if steamlvlup_page.status_code != 200:
        return render_template('steamlvluptosce.html', request_status = 'error', steamlvlup_prices = {}, curr_prices = {})

    #Getting necessary info from the JSON
    steamlvlup_json = json.loads(steamlvlup_page.text)
    steamlvlup_count = steamlvlup_json['count']
    steamlvlup_items = steamlvlup_json['items']

    #Going through the rest of the pages of results
    while steamlvlup_count > 0:
        page += 1
        steamlvlup_page = requests.get('https://steamlvlup.com/shop/items?hide_exist=false&page_size=999&page=' + str(page) + '&sort_by=price&sort_type=asc')

        #Case for when STEAMVLUP site happens to error out in the middle of us looking through it
        if steamlvlup_page.status_code != 200:
            return render_template('steamlvluptosce.html', request_status = 'error', steamlvlup_prices = {}, curr_prices = {}, update_time = update_time)

        #Getting necessary info from JSON
        steamlvlup_json = json.loads(steamlvlup_page.text)
        steamlvlup_count = steamlvlup_json['count']
        steamlvlup_items += steamlvlup_json['items']

    steamlvlup_prices = {}
    sce_card_set_prices = {}

    #Going through the list of items from STEAMLVLUP
    for item in steamlvlup_items:
        app_id = str(item['appid'])
        if app_id not in sce_inventory.keys():
            continue
        steamlvlup_prices[app_id] = item['set_price']
        curr_game = sce_inventory[app_id]
        
        if app_id not in sce_inventory:
            sce_card_set_prices[app_id] = [curr_game[0], '?']
        else:            
            sce_card_set_prices[app_id] = [curr_game[0], curr_game[3]]
        
    return jsonify(request_status = 'success', sce_card_set_prices = sce_card_set_prices, steamlvlup_prices = steamlvlup_prices)

if __name__ == '__main__':
    
    port = int(os.environ.get("PORT", 5432))
    app.run(host='0.0.0.0', port = port)
