# -*- coding: utf-8 -*-
# Command Line interface to interact with poloniex
# if you don't get it, don't use it
import ccxt
import logging
import json
import sys
import os
from decimal import *
from pathlib import Path

class LazyStarter:
    getcontext().prec = 8

    def __init__(self):
        self.keys_file = "keys.txt"
        self.user_market_name_list = []
        self.ccxt_exchanges_list = ccxt.exchanges
        self.keys = self.keys_initialisation()
        self.exchange = None
        self.user_balance = {}
        self.selected_market = None
        self.active_orders = {'buy': [], 'sell': []}
        self.history = {'buy': [], 'sell': []}

    def keys_initialisation(self):
        """Read key.txt file and construct a dict with it.with

        return: dict, with all api keys found
        """
        if not os.path.isfile(self.keys_file):
            Path(self.keys_file).touch()
            print('No file was found, an empty one has been created,\
                   please fill it as indicated in the documentation')
            self.exit()
        else:
            keys = self.keys_file_reader()
            if not keys:
                print('Your key.txt file is empty, polease fill it \
                    as indicated to the documentation')
                self.exit()
            else:
                return keys

    def keys_file_reader(self):
        keys = {}
        with open(self.keys_file , mode='r', encoding='utf-8') as keys_file:
            for line in keys_file:
                line = line.replace('\n', '')
                line = line.replace("'", '"')
                try:
                    key = json.loads(line)
                    for k in key.keys():
                        if k in self.user_market_name_list:
                            raise KeyError('You already have a key for this \
                                            marketplace, please RTFM')
                        else:
                            self.user_market_name_list.append(k)
                        if k not in self.ccxt_exchanges_list:
                            raise NameError('The marketplace name is invalid!')
                except Exception as e:
                    print('Something went wrong : ', e)
                    self.exit()
                keys.update(key)
            return keys

    def select_marketplace(self):
        i = 1
        market_choice = ''
        choice = 0
        valid_choice = False
        for market in self.user_market_name_list:
            market_choice += str(i) + ': ' + market + ', '
            i += 1
        while valid_choice is False:
            print('Please select a market:\n', market_choice)
            try:
                choice = int(input(' >> '))
                if 1 <= choice <= len(self.user_market_name_list):
                    valid_choice = True
            except ValueError:
                pass
        self.exchange = eval('ccxt.' + self.user_market_name_list[choice-1] + \
             '(' + str(self.keys[self.user_market_name_list[choice-1]]) + ')') 
        balance = self.exchange.fetchBalance()
        for key, value in balance.items():
            if 'total' in value:
                if value['total'] != 0.0:
                    pair = {key: value}
                    self.user_balance.update(pair)
                    print(pair)

    def select_market(self):
        self.exchange.load_markets()
        market_list = self.exchange.symbols
        valid_choice = False
        """while valid_choice is False:
            print('Please enter the name of a market:\n', market_list)
            choice = input(' >> ').upper()
            if choice in market_list:
                self.selected_market = choice
                valid_choice = True"""
        self.get_orders('MANA/BTC')
        #self.get_user_history('MANA/BTC')

    def get_orders(self, market):
        active_orders = {'buy': [], 'sell': []}
        orders = self.exchange.fetchOrders(market)
        for order in orders:
            if order['side'] == 'buy':
                active_orders['buy'].append([
                    order['id'], 
                    Decimal(str(order['price'])),
                    Decimal(str(order['amount'])), 
                    Decimal(str(order['price']))\
                    *Decimal(str(order['amount']))\
                    *Decimal('0.9975')])
            if order['side'] == 'sell':
                active_orders['sell'].append([
                    order['id'], 
                    Decimal(str(order['price'])),
                    Decimal(str(order['amount'])), 
                    Decimal(str(order['price']))\
                    *Decimal(str(order['amount']))\
                    *Decimal('0.9975')])

        return active_orders

    def get_user_history(self, market):
        history = {'buy': [], 'sell': []}
        trades = self.exchange.fetch_my_trades(market)
        for order in trades:
            if order['side'] == 'buy':
                history['buy'].append([
                    order['id'], 
                    Decimal(str(order['price'])),
                    Decimal(str(order['amount'])), 
                    Decimal(str(order['price']))\
                    *Decimal(str(order['amount']))\
                    *Decimal('0.9975')])
            if order['side'] == 'sell':
                history['sell'].append([
                    order['id'], 
                    Decimal(str(order['price'])),
                    Decimal(str(order['amount'])), 
                    Decimal(str(order['price']))\
                    *Decimal(str(order['amount']))\
                    *Decimal('0.9975')])

        return history


    def exit(self):
        """Clean program exit"""
        self.stop_signal = True
        sys.exit(0)

    def main(self):
        print("Start the program")
        self.select_marketplace()
        self.select_market()
        print("End the program")
        sys.exit(0)

LazyStarter = LazyStarter()
# Main Program
if __name__ == "__main__":
    # Launch main_menu
    LazyStarter.main()