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
        self.active_orders = {'sell': [], 'buy': []}
        self.history = {'sell': [], 'buy': []}

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

    def lw_initialisation(self):
        marketplace_name = self.select_marketplace()
        print('All of your balance for our balances on ', marketplace_name)
        self.get_balances()
        self.selected_market = self.select_market()
        self.history = self.get_user_history(self.selected_market)
        print('Your trading history for the market ', self.selected_market, ':')
        self.display_user_trades(self.history)
        self.active_orders = self.get_orders(self.selected_market)
        print('Your actives orders for the market ', self.selected_market, ':')
        self.display_user_trades(self.active_orders)
        orders_in_logs = self.check_for_log_file()

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
        return self.user_market_name_list[choice-1]

    def get_balances(self):
        balance = self.exchange.fetchBalance()
        for key, value in balance.items():
            if 'total' in value:
                if value['total'] != 0.0:
                    pair = {key: value}
                    self.user_balance.update(pair)
                    print(pair)

    def select_market(self):
        """
        self.exchange.load_markets()
        market_list = self.exchange.symbols
        valid_choice = False
        while valid_choice is False:
            print('Please enter the name of a market:\n', market_list)
            choice = input(' >> ').upper()
            if choice in market_list:
                self.selected_market = choice
                valid_choice = True
"""
        return 'MANA/BTC' #choice
    
    def format_order(self, id, price, amount, date):
        return [id, Decimal(str(price)), Decimal(str(amount)),\
                Decimal(str(price)) * Decimal(str(amount)) * Decimal('0.9975'),\
                date]

    def get_orders(self, market):
        orders = {'sell': [], 'buy': []}
        raw_orders = self.exchange.fetchOrders(market)
        for order in raw_orders:
            if order['side'] == 'buy':
                orders['buy'].append(self.format_order(
                    order['id'], 
                    order['price'],
                    order['amount'], 
                    order['datetime']))
            if order['side'] == 'sell':
                orders['sell'].append(self.format_order(
                    order['id'], 
                    order['price'],
                    order['amount'], 
                    order['datetime']))

        return orders

    def get_user_history(self, market):
        orders = {'sell': [], 'buy': []}
        raw_orders = self.exchange.fetch_my_trades(market)
        for order in raw_orders:
            if order['side'] == 'buy':
                orders['buy'].append(self.format_order(
                    order['order'], 
                    order['price'],
                    order['amount'], 
                    order['datetime']))
            if order['side'] == 'sell':
                orders['sell'].append(self.format_order(
                    order['order'], 
                    order['price'],
                    order['amount'], 
                    order['datetime']))

        return orders

    def display_user_trades(self, orders):
        for order in orders['sell']:
            print('date & time: ', order[4], 'Sell, id: ', order[0], ', price: ',\
                order[1], ', amount: ', order[2], ', value: ', order[3])
        for order in orders['buy']:
            print('date & time: ', order[4], 'Buy, id: ', order[0], ', price: ',\
                order[1], ', amount: ', order[2], ', value: ', order[3])

    def check_for_log_file(self):
        log_file_name = 'debug.log'
        orders = {'sell': [], 'buy': []}
        if not os.path.isfile(log_file_name):
            Path(log_file_name).touch()
            print('No file was found, an empty one has been created')
            return None
        with open(log_file_name , mode='r', encoding='utf-8') as log_file:
            if not log_file:
                print('The log file is empty')
                return None
            else:
                print("Reading the log file")
                for line in log_file:
                    print(line)
                    if line[0] == '{':
                        line = line.replace('\n', '')
                        line = line.replace("'", '"')
                        try:
                            order = json.loads(line)
                            if order['side'] == 'buy':
                                orders['buy'].append(self.format_order(
                                    order['order'], 
                                    order['price'],
                                    order['amount'], 
                                    order['datetime']))
                            if order['side'] == 'sell':
                                orders['sell'].append(self.format_order(
                                    order['order'], 
                                    order['price'],
                                    order['amount'], 
                                    order['datetime']))
                        except Exception as e:
                            print('Something went wrong : ', e)
                            self.exit()
                return orders

    def exit(self):
        """Clean program exit"""
        print("End the program")
        sys.exit(0)

    def main(self):
        print("Start the program")
        self.lw_initialisation()
        #self.select_marketplace()
        #print(self.exchange.fetch_my_trades('MANA/BTC'))
        self.exit()

LazyStarter = LazyStarter()
# Main Program
if __name__ == "__main__":
    # Launch main_menu
    LazyStarter.main()