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
        self.log_file_name = 'debug.log'
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

    def keys_initialisation(self): # Need to be refactored
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

    def keys_file_reader(self): # Need to be refactored
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
        """
        question = 'Please select a market:'
        choice = self.ask_to_select_in_a_list(self.user_market_name_list, question)
        """
        self.exchange = eval('ccxt.' + self.user_market_name_list[1] + \
             '(' + str(self.keys[self.user_market_name_list[1]]) + ')')
        """
        self.exchange = eval('ccxt.' + self.user_market_name_list[choice] + \
             '(' + str(self.keys[self.user_market_name_list[choice]]) + ')')
             """
        return self.user_market_name_list[1] #self.user_market_name_list[choice-1]

    def get_balances(self):
        """Get the non empty balance of a user on a marketplace and make it global"""
        balance = self.exchange.fetchBalance()
        user_balance = {}
        for key, value in balance.items():
            if 'total' in value:
                if value['total'] != 0.0:
                    for item in value:
                        value[item] = str(value[item])
                    user_balance.update({key: value})
        self.user_balance = user_balance # Need to be refactored

    def display_user_balance(self):
        """Display the user balance"""
        for key, value in self.user_balance.items():
            print(key, ': ', value)

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
            limitation = self.limitation_to_btc_market(choice)
            if limitation is True:
                if choice in market_list:
                    self.selected_market = choice
                    valid_choice = True
            else:
                print(limitation[1])"""
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

    def get_market_last_price(self, market):
        """Get the last price of a specific market
        market: str, need to have XXX/YYY ticker format 
        return: decimal"""
        return Decimal(f"{self.exchange.fetchTicker(market)['last']:.8f}")

    def display_user_trades(self, orders):
        """Pretify and display orders list.
        orders: dict, contain all orders.
        """
        for order in orders['sell']:
            print('Sell on: ', order[4], ', id: ', order[0], ', price: ',\
                order[1], ', amount: ', order[2], ', value: ', order[3])
        for order in orders['buy']:
            print('Buy on: ', order[4], ', id: ', order[0], ', price: ',\
                order[1], ', amount: ', order[2], ', value: ', order[3])

    def log_file_reader(self): # Need refactorisation
        """Import data from logfile and organize it.
        return: None or dict containing : list of exectuted buy, 
                                          list of executed sell, 
                                          dict of parameters
        """
        logs_data = {'sell': [], 'buy': [], 'params': {}}        
        with open(self.log_file_name , mode='r', encoding='utf-8') as log_file:
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
                            return False
            else:
                raise ValueError('The first line of the log file do not contain parameters')
                return logs_data

    def check_logfile_existence(self): # Need to be refactored
        """Check if the log file exist.
        return: bool True or None.
        """
        if not os.path.isfile(self.log_file_name):
            Path(self.log_file_name).touch()
            print('No file was found, an empty one has been created!')
            return None
        else:
            return True

    def logfile_not_empty(self): # Need to be refactored
        """Check if there is data in the logfile.
        return : bool True or None.
        """
        if os.path.getsize(self.log_file_name):
            return True
        else:
            print('Logfile is empty!')
            return None

    def params_checker(self, params):
        """Check the integrity of all parameters and return False if it's not.
        params: dict.
        return: dict with valid parameters, or False.
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
            if not params['benef_alloc']:
                raise ValueError('Benefices allocation isn\'t set')
            # Convert values
            error_message = 'params[\'range_bot\'] is not a string for decimal: '
            params['range_bot'] = self.str_to_decimal(params['range_bot'], error_message)
            error_message = 'params[\'range_top\'] is not a string for decimal: '
            params['range_top'] = self.str_to_decimal(params['range_top'], error_message)
            error_message = 'params[\'spread_bot\'] is not a string for decimal: '
            params['spread_bot'] = self.str_to_decimal(params['spread_bot'], error_message)
            error_message = 'params[\'spread_top\'] is not a string for decimal: '
            params['spread_top'] = self.str_to_decimal(params['spread_top'], error_message)
            error_message = 'params[\'increment_coef\'] is not a string for decimal: '
            params['increment_coef'] = self.str_to_decimal(params['increment_coef'], error_message)
            error_message = 'params[\'amount\'] is not a string for decimal: '
            params['amount'] = self.str_to_decimal(params['amount'], error_message)
            error_message = 'params[\'stop_at_bot\'] is not a boolean: '
            params['stop_at_bot'] = self.str_to_bool(params['stop_at_bot'], error_message)
            error_message = 'params[\'stop_at_top\'] is not a boolean: '
            params['stop_at_top'] = self.str_to_bool(params['stop_at_top'], error_message)
            error_message = 'params[\'nb_buy_displayed\'] is not an int: '
            params['nb_buy_displayed'] = self.str_to_int(params['nb_buy_displayed'], error_message)
            error_message = 'params[\'nb_sell_displayed\'] is not an int: '
            params['nb_sell_displayed'] = self.str_to_int(params['nb_sell_displayed'], error_message)
            error_message = 'params[\'benef_alloc\'] is not an int: '
            params['benef_alloc'] = self.str_to_int(params['nb_sell_displayed'], error_message)
            # Test if values is correct
            self.is_date(params['datetime'])
            if params['market'] not in self.exchange.symbols:
                raise ValueError('Market isn\'t set properly for this marketplace')
            if params['market'] != self.selected_market:
                raise ValueError('self.selected_market: ', self.selected_market,\
                                 ' != params[\'market\']', params['market'])
            market_test = self.limitation_to_btc_market(params['market'])
            if market_test is not True:
                raise ValueError(market_test[1])
            self.param_checker_range_bot(params['range_bot'])
            self.param_checker_range_top(params['range_top'])
            self.param_checker_interval(params['increment_coef'])
            self.intervals = self.interval_generator(params['range_bot'],
                                                     params['range_top'],
                                                     params['increment_coef'])
            if self.intervals is False:
                raise ValueError('Range top value is too low, or increment too high:\
                                  need to generate at lease 6 intervals.')
            if params['spread_bot'] not in self.intervals:
                raise ValueError('Spread_bot isn\'t properly configured')
            spread_bot_location = self.intervals.index(params['spread_bot'])
            if params['spread_top'] != self.intervals[spread_bot_location + 1]:
                raise ValueError('Spread_top isn\'t properly configured')
            self.param_checker_amount(params['amount'])
            self.param_checker_benef_alloc(params['benef_alloc'])
        except Exception as e:
            print('The LW parameters are not well configured: ', e)
            return False
        return params

    def str_to_decimal(self, s, error_message=None):
        """Convert a string to Decimal or raise an error.
        s: string, element to convert
        error_message: string, error message detail to display if fail.
        return: Decimal."""
        try:
            return Decimal(str(s))
        except Exception as e:
            raise ValueError(error_message, e)

    def is_date(self, str_date):
        """Check if a date have a valid formating.
        str_date: string
        """
        try:
            datetime.strptime(str_date, '%Y-%m-%d %H:%M:%S.%f')
        except Exception as e:
            raise ValueError(str_date, ' is not a valid date: ', e)

    def str_to_bool(self, s, error_message=None): #Fancy things can be added
        """Convert a string to boolean or rise an error
        s: string.
        error_message: string, error message detail to display if fail.
        return: bool.
        """
        if s == 'True' or s == 'y':
            return True
        elif s == 'False' or s == 'n':
            return False
        else:
             raise ValueError(error_message, e)

    def str_to_int(self, s, error_message=None):
        """Convert a string to an int or rise an error
        s: string.
        error_message: string, error message detail to display if fail.
        return: int.
        """
        try:
            return int(s)
        except Exception as e:
            raise ValueError(error_message, e)

    def limitation_to_btc_market(self, market):
        """Special limitation to BTC market : only ALT/BTC for now.
        market: string, market name.
        return: bool True or bool False + error message
        """
        if market[-3:] != 'BTC':
            return False, 'LW is limited to ALT/BTC markets : ' + market
        return True

    def param_checker_range_bot(self, range_bot):
        """Verifies the value of the bottom of the channel
        range_bot: decimal"""
        if range_bot < Decimal('0.000001'):
            raise ValueError('The bottom of the range is too low')

    def param_checker_range_top(self, range_top):
        """Verifies the value of the top of the channel
        range_top: decimal"""
        if range_top > Decimal('100000'):
            raise ValueError('The top of the range is too high')

    def param_checker_interval(self, interval):
        """Verifies the value of interval between orders
        interval: decimal"""
        print(interval)
        if Decimal('1.01') > interval or interval >  Decimal('1.50'):
            raise ValueError('Increment is too low (<=1%) or high (>=50%)')

    def param_checker_amount(self, amount): #Need to add minimal order threshold
        """Verifies the value of each orders 
        amount: decimal"""
        if Decimal('0.000001') > amount or amount > Decimal('10000000'):
            raise ValueError('Amount is too low (<0.000001) or high (>10000000)')

    def param_checker_nb_to_display(self, nb):
        """Verifie the nb of order to display
        nb: int"""
        if nb > len(self.intervals) and nb < 0:
            raise ValueError('The number of order to display is too low (<0) or high ',
                len(self.intervals))

    def param_checker_benef_alloc(self, nb):
        """Verifie the nb for benefice allocation
        nb: int"""
        if 0 <= nb <= 100:
            raise ValueError('The benefice allocation too low (<0) or high (>100)',
                len(self.intervals))

    def interval_calculator(self, number1, increment):
        """Format a multiplication between decimal correctly
        number1: Decimal.
        increment: Decimal, 2nd number of the multiplication.
        return: Decimal, multiplied number formated correctly
        """
        return (number1 * increment).quantize(Decimal('.00000001'),
                                              rounding=ROUND_HALF_EVEN)

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
            print('Range values are too thin')
            return False
        return intervals

    def increment_coef_buider(self, nb):
        """Formating increment_coef.
        nb: int, the value to increment in percentage.
        return: Decimal, formated value.
        """
        try:
            nb = Decimal(str(nb))
            nb = Decimal('1') + nb / Decimal('100')
            self.param_checker_interval(nb)
            return nb
        except Exception as e:
            raise ValueError(e)

    def simple_question(self, question): #Fancy things can be added
        """Simple question prompted and response handling.
        question: string, the question to ask.
        return: bool True or None, yes of no
        """
        valid_choice = False
        while valid_choice is False:
            print(question)
            choice = input(' >> ')
            if choice == 'y':
                valid_choice = True
            if choice == 'n':
                valid_choice = None
        return valid_choice

    def ask_question(self, question, formater_func, control_func=None):
        """Ask any question to the user, control the value returned or ask again.
        question: string, question to ask to the user.
        formater_funct: function, format from string to the right datatype.
        control_funct: optional function, allow to check that the user's choice is 
                       within the requested parameters
        return: formated (int, decimal, ...) choice of the user
        """
        print(question)
        is_valid = False
        while is_valid is False:
            try:
                choice = input(' >> ')
                choice = formater_func(choice)
                if control_func:
                    control_func(choice)
                is_valid = True
            except Exception as e:
                print(question, 'invalid choice: ', choice, ' -> ', e)
        return choice

    def ask_to_select_in_a_list(self, question, a_list):
        """Ask to the user to choose between items in a list
        a_list: list.
        question: string.
        return: int, the position of this item """
        i = 1
        is_valid = False
        print(question)
        question = ''
        for item in a_list:
            question += str(i) + ': ' + str(item) + ', '
            i += 1
        print(question)
        while is_valid is False:
            try:
                choice = input(' >> ')
                choice = self.str_to_int(choice)
                if choice <= i:
                    choice -= 1
                    is_valid = True
                else:
                    print('You need to enter a nuber between 1 and ', i)
            except Exception as e:
                print(question, 'invalid choice: ', choice, ' -> ', e)
        return choice

    def ask_param_range_bot(self):
        """Ask the user to enter a value for the bottom of the range.
        return: decimal."""
        question = 'Enter a value for the bottom of the range. It must be superior to 100 stats:'
        range_bot = self.ask_question(question, self.str_to_decimal, 
                                      self.param_checker_range_bot)
        return range_bot

    def ask_param_range_top(self):
        """Ask the user to enter a value for the top of the range.
        return: decimal."""
        question = 'Enter a value for the top of the range. It must be inferior to 1000000 BTC:'
        range_top = self.ask_question(question, self.str_to_decimal, 
                                      self.param_checker_range_top)
        return range_top

    def ask_param_amount(self): #Need to add minimlal order threshold
        """Ask the user to enter a value of ALT to sell at each order.
        return: decimal."""
        question = 'How much ', self.selected_market[:4], ' do you want to sell per order? It must be between 0.000001 and 10000000:'
        return self.ask_question(question, self.str_to_decimal, self.param_checker_amount)

    def ask_param_increment(self):
        """Ask the user to enter a value for the spread between each order.
        return: decimal."""
        question = 'How much % of spread between two orders? It must be between 1% and 50%'
        return self.ask_question(question, self.increment_coef_buider)

    def ask_range_setup(self):
        """Ask to the user to enter the range and increment parameters.
        return: dict, asked parameters."""
        is_valid = False
        while is_valid is False:
            range_bot = self.ask_param_range_bot()
            range_top = self.ask_param_range_top()
            increment = self.ask_param_increment()
            intervals = self.interval_generator(range_bot, range_top, increment)
            if intervals is False:
                print('Range top value is too low, or increment too high:\
                       need to generate at lease 6 intervals. Try again!')
            else:
                is_valid = True
        self.intervals = intervals
        return {'range_bot': range_bot, 'range_top': range_top, 'increment': increment}

    def ask_params_spread(self):
        """Ask to the user to choose between value for spread bot and setup 
        spread top automatically
        return: dict, of decimal values
        """
        price = self.get_market_last_price(self.selected_market)
        print('The actual price of', self.selected_market, ' is ', price)
        question = 'Please select the price of your highest buy order (spread_bot) in the list'
        position = self.ask_to_select_in_a_list(question, self.intervals)
        return {'spread_bot': self.intervals[position], 
                'spread_top': self.intervals[position + 1]} # Can be improved by suggestiong a value

    def ask_nb_to_display(self):
        """Ask how much buy and sell orders are going to be in the book.
        return: dict, nb_buy_to_display + nb_sell."""
        question = 'How many buy orders do you want to display? It must be less than'\
                   + len(self.intervals) + '. 0 = ' + len(self.intervals) + ':'
        nb_buy_to_display = self.ask_question(question, self.str_to_int, 
                                              self.param_checker_nb_to_display)
        question = 'How many sell orders do you want to display? It must be less than'\
                   + len(self.intervals) + '. 0 = ' + len(self.intervals) + ':'
        nb_sell_to_display = self.ask_question(question, self.str_to_int, 
                                               self.param_checker_nb_to_display)
        return {'nb_buy_to_display': nb_buy_to_display, 
                'nb_sell_to_display': nb_sell_to_display}

    def ask_benef_alloc(self):
        """Ask for benefice allocation.
        return: int."""
        question = 'How do you want to allocate your benefice in %. It must be between 0 and 100, both included:'
        benef_alloc = self.ask_question(question, self.str_to_int, 
                                        self.param_checker_benef_alloc)
        return benef_alloc

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

    def ask_for_logfile(self): #TODO
        """Ask and verify LW logfile parameters
        """
        question = 'Do you want to check if a previous parameter is in logfile?'
        if self.simple_question(question) is True:
            if self.check_logfile_existence() is True:
                if self.logfile_not_empty() is True:
                    log_file_datas = self.log_file_reader()
                    if log_file_datas is not False:
                        print('Your previous parameters are:')
                        for item in log_file_datas['params'].items():
                            print(item)
                        question = 'Do you want to display history from logs?'
                        if self.simple_question(question) is True:
                            self.display_user_trades(log_file_datas)
                        question = 'Do you want to use those params?'
                        if self.simple_question(question) is True:
                            self.params = log_file_datas['params']
                            self.start_from_old_params()
                    else:
                        print('Your params are corrupted, please enter new one.')
        self.enter_params()

    def enter_params(self):
        """Serie of questions to setup LW parameters and put local params to global"""
        params = {'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                  'market'  : self.selected_market}
        params.update(self.ask_range_setup())
        amount = self.ask_param_amount()
        params.update({'amount': amount})
        params.update(self.ask_params_spread())
        params = self.check_for_enough_funds(params)
        question = 'Do you want to stop LW if range_bot is reach? (y) or (n) only.'
        params.update({'stop_at_bot': self.ask_question(question, self.str_to_bool)})
        question = 'Do you want to stop LW if range_top is reach? (y) or (n) only.'
        params.update({'stop_at_top': self.ask_question(question, self.str_to_bool)})
        params.update({'nb_buy_displayed', self.ask_nb_to_display()})
        params.update({'benef_alloc', self.ask_benef_alloc()})
        self.params = params
        
    def check_for_enough_funds(self, params):
        """Check if the user have enough funds to run LW with he's actual parameters.
        Printed value can be negative!
        Ask for params change if there's not.
        params: dict, parameters for LW.
        return: dict, params"""
        is_valid = False
        while is_valid is False:
            price = self.get_market_last_price(self.selected_market)
            self.get_balances()
            pair = self.selected_market.split('/')
            sell_balance = self.str_to_decimal(self.user_balance[pair[0]]['free'])
            buy_balance = self.str_to_decimal(self.user_balance[pair[1]]['free'])
            spread_bot_location = self.intervals.index(params['spread_bot'])
            spread_top_location = spread_bot_location + 1
            try:
                if self.intervals[spread_bot_location] <= price:
                    incoming_buy_funds = Decimal('0')
                    buy_funds_needed = self.calculate_buy_funds(spread_bot_location, params['amount'])
                    if self.intervals[spread_top_location] < price:
                        i = spread_top_location
                        while self.intervals[i] < price:
                            incoming_buy_funds += self.intervals[i] * params['amount']
                            i +=1
                    total_buy_funds_needed = buy_funds_needed - incoming_buy_funds
                    total_sell_funds_needed = self.calculate_sell_funds(spread_top_location, params['amount'])
                else:
                    incoming_sell_funds = Decimal('0')
                    total_buy_funds_needed = self.calculate_buy_funds(spread_bot_location, params['amount'])
                    if self.intervals[spread_bot_location] > price:
                        while self.intervals[spread_bot_location] < price:
                            incoming_sell_funds += params['amount']
                            spread_bot_location +=1
                    sell_funds_needed = self.calculate_sell_funds(spread_top_location, params['amount'])
                    total_sell_funds_needed = sell_funds_needed - incoming_sell_funds
                if total_buy_funds_needed > buy_balance or total_sell_funds_needed > sell_balance:
                    raise ValueError('total_buy_funds_needed (', total_buy_funds_needed, 
                        ') > buy_balance (', buy_balance, ') or total_sell_funds_needed (',
                        total_sell_funds_needed, ') > sell_balance (', sell_balance, ')!')
                is_valid = True
            except Exception as e:
                print(e, '\nYou need to change some paramaters')
                params = self.change_params(params)
        print('Your parameters will require ', total_buy_funds_needed, ' ', pair[1], ' and ', total_sell_funds_needed, ' ', pair[0], '.')
        print(params)
        return params

    def calculate_buy_funds(self, index, amount):
        """Calcul the buy funds required to execute the strategy
        price: Decimal, the actual market price
        amount: Decimal, allocated ALT per order
        return: Decimal, funds needed
        """
        buy_funds_needed = Decimal('0')
        i = 0
        while i <= index:
            buy_funds_needed += self.intervals[i] * amount
            i += 1
        return buy_funds_needed

    def calculate_sell_funds(self, index, amount):
        """Calcul the sell funds required to execute the strategy
        price: Decimal, the actual market price
        amount: Decimal, allocated ALT per order
        return: Decimal, funds needed
        """
        sell_funds_needed = Decimal('0')
        i = len(self.intervals) -1
        while i >= index:
            sell_funds_needed += amount
            i -= 1
        return sell_funds_needed

    def change_params(self, params):
        """Allow the user to change one LW parameter.
        params: dict, all the parameter for LW.
        return: dict."""
        editable_params = (('range_bot', self.ask_param_range_bot),
                           ('range_top', self.ask_param_range_top),
                           ('increment_coef', self.ask_param_increment),
                           ('amount', self.ask_param_amount))
        question = 'What parameter do you want to change?'
        question_list = ['The bottome of the range?', 'The top of the range?',
                         'The value between order?', 'The amount of alt per orders?',
                         'The value of your initial spread?', 'Add funds to your account']
        choice = self.ask_to_select_in_a_list(question, question_list)
        print(type(choice), choice)
        print(params[editable_params[choice][0]])
        print(editable_params[choice][1].__name__)
        if choice < 4:
            params[editable_params[choice][0]] = editable_params[choice][1]()
            print(type(params[editable_params[choice][0]]), 'params[editable_params[choice][0]]', params[editable_params[choice][0]])
            print('params', params)
            if choice < 3:
                self.intervals = self.interval_generator(params['range_bot'], params['range_top'], params['increment_coef'])
                print('self.intervals ', self.intervals)
            if choice is 0 or choice is 1:
                params = self.change_spread(params)
        elif choice == 4:
            params = self.change_spread(params)
        else:
            self.wait_for_funds()
        return params

    def change_spread(self, params):

        spread = self.ask_params_spread()
        for key, value in spread.items():
            params[key] = spread[value]
        return params

    def wait_for_funds(self):
        """The answer is in the question!"""
        question = 'Waiting for funds to arrive, (y) when you\'re ready, (n) to leave.'
        choice = self.simple_question(question)
        if not choice:
            self.exit()

    def start_from_old_params(self): #TODO
        pass

    def exit(self):
        """Clean program exit"""
        print("End the program")
        sys.exit(0)

    def lw_initialisation(self):
        """Initializing parameters, check parameters then initializing LW.
        """
        marketplace_name = self.select_marketplace() # temp modification
        #print('All of your balance for our balances on ', marketplace_name)
        #self.get_balances()
        self.selected_market = self.select_market() # temp modification
        self.intervals = [Decimal('0.00001'), Decimal('0.00001010'), Decimal('0.00001020'), Decimal('0.00001030'), Decimal('0.00001040'), Decimal('0.00001050'), Decimal('0.00001060'), Decimal('0.00001071'), Decimal('0.00001082'), Decimal('0.00001093'), Decimal('0.00001104'), Decimal('0.00001115'), Decimal('0.00001126'), Decimal('0.00001137'), Decimal('0.00001148'), Decimal('0.00001159'), Decimal('0.00001171'), Decimal('0.00001183'), Decimal('0.00001195'), Decimal('0.00001207'), Decimal('0.00001219'), Decimal('0.00001231'), Decimal('0.00001243'), Decimal('0.00001255'), Decimal('0.00001268'), Decimal('0.00001281'), Decimal('0.00001294'), Decimal('0.00001307'), Decimal('0.00001320'), Decimal('0.00001333'), Decimal('0.00001346'), Decimal('0.00001359'), Decimal('0.00001373'), Decimal('0.00001387'), Decimal('0.00001401'), Decimal('0.00001415'), Decimal('0.00001429'), Decimal('0.00001443'), Decimal('0.00001457'), Decimal('0.00001472'), Decimal('0.00001487')]
        self.check_for_enough_funds({"datetime": "2019-03-23 09:38:05.316085", "market": "MANA/BTC", "range_bot": Decimal("0.00001"), "range_top": Decimal("0.000015"), "spread_bot": Decimal("0.00001255"), "spread_top": Decimal("0.00001268"), "increment_coef": Decimal("1.1"), "amount": Decimal("6000")})
        #self.ask_for_logfile()

    def main(self):
        print("Start the program")
        self.lw_initialisation()
        self.exit()

LazyStarter = LazyStarter()

if __name__ == "__main__":
    LazyStarter.main()