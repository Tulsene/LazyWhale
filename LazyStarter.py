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
from bisect import bisect_left
from datetime import datetime

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
        self.params = {}
        self.intervals = []

    def keys_initialisation(self):
        """Check if a key.txt file exist and create one if none.
        return: dict, with all api keys found.
        """
        if not os.path.isfile(self.keys_file):
            Path(self.keys_file).touch()
            print('No file was found, an empty one has been created,\
                   please fill it as indicated in the documentation')
            self.exit()
        else:
            keys = self.keys_file_reader()
            if not keys:
                print('Your key.txt file is empty, please fill it \
                    as indicated to the documentation')
                self.exit()
            else:
                return keys

    def keys_file_reader(self):
        """Check the consistence of datas in key.txt.
        return: dict, api keys
        """
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
        """Marketplace sélection menu, connect to the selected marketplace.
        return: string, the name of the selected marketplace
        """
        i = 1
        market_choice = ''
        choice = 0
        valid_choice = False
        """
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
        """
        self.exchange = eval('ccxt.' + self.user_market_name_list[0] + \
             '(' + str(self.keys[self.user_market_name_list[0]]) + ')')
        """
        self.exchange = eval('ccxt.' + self.user_market_name_list[choice-1] + \
             '(' + str(self.keys[self.user_market_name_list[choice-1]]) + ')')
             """
        return self.user_market_name_list[0] #self.user_market_name_list[choice-1]

    def get_balances(self):
        """Get the balance of a user on a marketplace and print it"""
        balance = self.exchange.organizeBalance()
        for key, value in balance.items():
            if 'total' in value:
                if value['total'] != 0.0:
                    pair = {key: value}
                    self.user_balance.update(pair)
                    print(pair)

    def select_market(self):
        """Market selection menu.
        return: string, selected market.
        """
        self.exchange.load_markets()
        """
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
        """Sort the information of an order in a list.
        id: string, order unique identifier.
        price: float.
        amount: float.
        date: string.
        return: list, containing id, price, amount, value and date.
        """
        return [id, Decimal(str(price)), Decimal(str(amount)),\
                Decimal(str(price)) * Decimal(str(amount)) * Decimal('0.9975'),\
                date]

    def get_orders(self, market):
        """Get actives orders from a marketplace and organize them.
        return: dict, containing list of buy & list of sell.
        """
        orders = {'sell': [], 'buy': []}
        raw_orders = self.exchange.organizeOrders(market)
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
        """Get orders history from a marketplace and organize them.
        return: dict, containing list of buy & list of sell.
        """
        orders = {'sell': [], 'buy': []}
        raw_orders = self.exchange.organize_my_trades(market)
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
        """Pretify display of orders list.
        orders: dict, contain all orders.
        """
        for order in orders['sell']:
            print('date & time: ', order[4], 'Sell, id: ', order[0], ', price: ',\
                order[1], ', amount: ', order[2], ', value: ', order[3])
        for order in orders['buy']:
            print('date & time: ', order[4], 'Buy, id: ', order[0], ', price: ',\
                order[1], ', amount: ', order[2], ', value: ', order[3])

    def check_for_log_file(self):
        """Create a logfile if none is found. Read it, import data and organize it.
        return: None or dict containing : list of exectuted buy, 
                                          list of executed sell, 
                                          dict of parameters
        """
        log_file_name = 'debug.log'
        logs_data = {'sell': [], 'buy': [], 'params': {}}
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
                params = log_file.readline()
                if params[0] == '#':
                    params = params.replace('\n', '')
                    params = params.replace("#", '')
                    params = params.replace("'", '"')
                    try:
                        params = json.loads(params)
                    except Exception as e:
                        print('Something went wrong with the first line of the \
                               log file: ', e)
                        self.exit()
                    logs_data['params'] = self.params_checker(params)
                    for line in log_file:
                        print(line)
                        if line[0] == '{':
                            line = line.replace('\n', '')
                            line = line.replace("'", '"')
                            try:
                                order = json.loads(line)
                                if order['side'] == 'buy':
                                    logs_data['buy'].append(self.format_order(
                                        order['order'],
                                        order['price'],
                                        order['amount'],
                                        order['datetime']))
                                if order['side'] == 'sell':
                                    logs_data['sell'].append(self.format_order(
                                        order['order'],
                                        order['price'],
                                        order['amount'],
                                        order['datetime']))
                            except Exception as e:
                                print('Something went wrong with data formating in \
                                        the log file: ', e)
                                self.exit()
                    return logs_data

    def params_checker(self, params):
        """Check the integrity of all parameters.
        params: dict.
        return: dict, with valid parameters.
        """
        try:
            # Check if values exist
            if not params['datetime']:
                raise ValueError('Datetime isn\'t set')
            if not params['market']:
                raise ValueError('Market isn\'t set')
            if not params['range_bot']:
                raise ValueError('The bottom of the range isn\'t set')
            if not params['range_top']:
                raise ValueError('The top of the range isn\'t set')
            if not params['spread_bot']:
                raise ValueError('The bottom of the spread isn\'t set')
            if not params['spread_top']:
                raise ValueError('The bottom of the spread isn\'t set')
            if not params['increment_coef']:
                raise ValueError('Increment coeficient isn\'t set')
            if not params['amount']:
                raise ValueError('Amount isn\'t set')
            if not params['stop_at_bot']:
                raise ValueError('Stop at bottom isn\'t set')
            if not params['stop_at_top']:
                raise ValueError('Stop at top isn\'t set')
            if not params['nb_buy_displayed']:
                raise ValueError('Number of buy displayed isn\'t set')
            if not params['nb_sell_displayed']:
                raise ValueError('Number of sell displayed isn\'t set')
            # Convert values
            try:
                params['range_bot'] = Decimal(str(params['range_bot']))
            except Exception as e:
                print('params[\'range_bot\'] is not a string: ', e)
            try:
                params['range_top'] = Decimal(str(params['range_top']))
            except Exception as e:
                print('params[\'range_top\'] is not a string: ', e)
            try:
                params['spread_bot'] = Decimal(str(params['spread_bot']))
            except Exception as e:
                print('params[\'spread_bot\'] is not a string: ', e)
            try:
                params['spread_top'] = Decimal(str(params['spread_top']))
            except Exception as e:
                print('params[\'spread_top\'] is not a string: ', e)
            try:
                params['increment_coef'] = Decimal(str(params['increment_coef']))
            except Exception as e:
                print('params[\'increment_coef\'] is not a string: ', e)
            try:
                params['amount'] = Decimal(str(params['amount']))
            except Exception as e:
                print('params[\'amount\'] is not a string: ', e)
            try:
                params['stop_at_bot'] = self.str_to_bool(params['stop_at_bot'])
            except Exception as e:
                print('params[\'stop_at_bot\']: ', e)
            try:
                params['stop_at_top'] = self.str_to_bool(params['stop_at_top'])
            except Exception as e:
                print('params[\'stop_at_top\']: ', e)
            try:
                params['nb_buy_displayed'] = int(params['nb_buy_displayed'])
            except Exception as e:
                print('params[\'nb_buy_displayed\'] is not an int: ', e)
            try:
                params['nb_sell_displayed'] = int(params['nb_sell_displayed'])
            except Exception as e:
                print('params[\'nb_sell_displayed\'] is not an int: ', e)
            # Test if values is correct
            self.is_date(params['datetime'])
            if params['market'] not in self.exchange.symbols:
                raise ValueError('Market isn\'t set properly for this marketplace')
            market_test = self.limitation_to_btc_market(params['market'])
            if market_test is not True:
                raise ValueError(market_test[1])
            if params['range_bot'] < Decimal('0.000001'):
                raise ValueError('The bottom of the range is too low')
            if params['range_top'] > Decimal('100000'):
                raise ValueError('The top of the range is too high')
            if Decimal('1.01') > params['increment_coef'] or params['increment_coef'] >  Decimal('1.50'):
                raise ValueError('Increment is too low (<=1%) or high (>=50%)')
            self.intervals = self.interval_generator(params['range_bot'],
                                                     params['range_top'],
                                                     params['increment_coef'])
            if params['spread_bot'] not in self.intervals:
                raise ValueError('Spread_bot isn\'t properly configured')
            spread_bot_location = self.position_closest(self.intervals,\
                                                        params['spread_bot'])
            if params['spread_top'] != self.intervals[spread_bot_location + 1]:
                raise ValueError('Spread_top isn\'t properly configured')
            print(params['amount'])
            if Decimal('0.000001') > params['amount'] or params['amount'] > Decimal('10000000'):
                raise ValueError('Amount is too low (<0.000001) or high (>10000000)')
        except Exception as e:
            print('The LW parameters are not well configured: ', e)
            self.exit()
        return params

    def is_date(self, str_date):
        """Check if a date have a valid formating.
        str_date: string
        """
        try:
            datetime.strptime(str_date, '%Y-%m-%d %H:%M:%S.%f')
        except Exception as e:
            print(str_date, ' is not a valid date: ', e)
            self.exit()

    def limitation_to_btc_market(self, market):
        """Special limitation to BTC market : only ALT/BTC for now.
        market: string, market name.
        return: bool True or bool False + error message
        """
        if market[-3:] != 'BTC':
            return False, 'LW is limited to ALT/BTC markets' + market
        return True

    def interval_calculator(self, number1, increment):
        """Format a multiplication between deciaml correctly
        number1: Decimal.
        increment: Decimal, 2nd number of the multiplication.
        return: Decimal, multiplied number formated correctly
        """
        return (number1 * increment).quantize(Decimal('.00000001'),\
                                              rounding=ROUND_HALF_EVEN)

    def is_integer(self, s, text):
        """Test if a string can be converted in an int
        s: string.
        text: string, error message detail to display if fail.
        """
        try:
            int(s)
        except Exception as e:
            print(text, ' is not an integer: ', e)
            self.exit()

    def interval_generator(self, range_bottom, range_top, increment):
        """Generate a list of interval inside a range by incrementing values
        range_bottom: Decimal, bottom of the range
        range_top: Decimal, top of the range
        increment: Decimal, value used to increment from the bottom
        return: list, value from [range_bottom, range_top[
        """ 
        intervals = [range_bottom]
        intervals.append(self.interval_calculator(intervals[-1], increment))
        if range_top <= intervals[1]:
            raise ValueError('Range top value is too low')
        while intervals[-1] <= range_top:
            intervals.append(self.interval_calculator(intervals[-1], increment))
        intervals.pop()
        if len(intervals) < 6:
            raise ValueError('Range top value is tool low, or increment too high:\
                              need to generate at lease 6 intervals.')
        return intervals

    def str_to_bool(self, s):
        """Convert a string to boolean or rise an error
        s: string.
        return: bool.
        """
        try:
            if s == 'True':
                return True
            elif s == 'False':
                return False
            else:
                 raise ValueError('The String you entered isn\'t a boolean')
        except Exception as e:
            print('The LW parameters are not well configured: ', e)
            self.exit()

    def params_builder(self, range_bot, range_top, increment, amount):
        """TODO"""
        pass

    def increment_coef_buider(self, nb):
        """Formating increment_coef.
        nb: int, the value to increment in percentage.
        return: Decimal, formated value.
        """
        return Decimal('1') + Decimal(str(nb)) / Decimal('100')

    def simple_question(self, text):
        """Simple question prompted and response handling.
        text: string, the question to ask.
        return: bool True or None, yes of no
        """
        valid_choice = False
        while valid_choice is False:
            print(text)
            choice = input(' >> ')
            if choice == 'y':
                valid_choice = True
            if choice == 'n':
                valid_choice = None
        return valid_choice

    def position_closest(self, a_list, a_nb):
        """Find the closest position of a value in a list for a a_nb.
        a_list: list, a sorted list of number (int or float or Decimal).
        a_nb: int or float or Decimal, element to look for.

        return: int, position in a list. If two match are equally close,
        return the smallest number.
        """
        pos = bisect_left(a_list, a_nb)
        if pos == 0 or pos == len(a_list):
            return pos
        before = a_list[pos - 1]
        after = a_list[pos]
        if after - a_nb < a_nb - before:
           return pos
        else:
           return pos - 1

    def exit(self):
        """Clean program exit"""
        print("End the program")
        sys.exit(0)

    def lw_initialisation(self):
        """Initializing parameters, cehck parameter initializing the script
        """
        marketplace_name = self.select_marketplace() # temp modification
        #print('All of your balance for our balances on ', marketplace_name)
        #self.get_balances()
        self.selected_market = self.select_market() # temp modification
        #self.history = self.get_user_history(self.selected_market)
        #print('Your trading history for the market ', self.selected_market, ':')
        #self.display_user_trades(self.history)
        self.active_orders = self.get_orders(self.selected_market)
        #print('Your actives orders for the market ', self.selected_market, ':')
        #self.display_user_trades(self.active_orders)
        orders_in_logs = self.check_for_log_file()
        print(orders_in_logs)
        if orders_in_logs:
            text = 'Do you want to resume from previous LW (y) or start a new LW (n)'
            answer = self.simple_question(text)

    def main(self):
        print("Start the program")
        self.lw_initialisation()
        #self.check_for_log_file()
        #print(self.exchange.organize_my_trades('MANA/BTC'))
        self.exit()

LazyStarter = LazyStarter()
# Main Program
if __name__ == "__main__":
    # Launch main_menu
    LazyStarter.main()

# a = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')