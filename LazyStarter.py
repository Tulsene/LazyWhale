# -*- coding: utf-8 -*-
# Command Line interface to interact with poloniex
# if you don't get it, don't use it
import ccxt
import logging
import logging.handlers
import json
import sys
import os
import zebitexFormatted
import copy
import time
from decimal import *
from pathlib import Path
from bisect import bisect_left
from datetime import datetime
from operator import itemgetter

class LazyStarter:
    getcontext().prec = 8

    def __init__(self):
        self.keys_file = "keys.txt"
        self.stratlog = None
        self.applog = self.logger_setup('debugs', 'logfiles/app.log',
            '%(asctime)s - %(levelname)s - %(message)s', logging.DEBUG,
            logging.DEBUG)
        self.user_market_name_list = []
        self.ccxt_exchanges_list = self.exchanges_list_init()
        self.keys = self.keys_initialisation()
        self.exchange = None
        self.fees_coef = Decimal('0.9975')
        self.user_balance = {}
        self.selected_market = None
        self.open_orders = {'sell': [], 'buy': []}
        self.history = {'sell': [], 'buy': []}
        self.params = {}
        self.intervals = []
        self.total_buy_funds_needed = None
        self.total_sell_funds_needed = None
        self.err_counter = 0
        self.now = 0
        self.safety_buy_value = '0.00000001'
        self.safety_sell_value = '1'
        self.max_sell_index = None

    """
    ########################## __INIT__ + MANDATORY ###########################
    """

    # I'm not sure if it work well
    def logger_setup(self, name, log_file, log_formatter, console_level,
        file_level, logging_level=logging.DEBUG):
        """Generate logging systems which display any level on the console
        and starting from INFO into logging file
        name: string, name of the logger,
        log_file: string, name of the file where to place the log datas.
        log_formatter: string, how the log is formated. See Formatter logging
            rules.
        console_level: logging object, the logging level to display in the
            console. Need to be superior to logging_level.
        file_level: logging object, the logging level to put in the
            logging file. Need to be superior to logging_level.
        logging_level: logging object, optional, the level of logging to catch.
        return: logging object, contain rules for logging.
        """
        self.create_dir_when_none('logfiles')
        logger = logging.getLogger(name)
        logger.setLevel(logging_level)
        formatter = logging.Formatter(log_formatter)
        # Console handler stream
        ch = logging.StreamHandler()
        ch.setLevel(console_level)
        ch.setFormatter(formatter)
        # File Handler stream
        fh = logging.FileHandler(log_file)
        fh.setLevel(file_level)
        fh.setFormatter(formatter)
        logger.addHandler(ch)
        logger.addHandler(fh)
        handler = logging.handlers.RotatingFileHandler(
                  log_file, maxBytes=2000000, backupCount=20)
        logger.addHandler(handler)
        return logger

    def exchanges_list_init(self):
        """Little hack to add zebitex to ccxt exchange list.
        return: list, list of exchanges."""
        ccxt_exchanges_list = ccxt.exchanges
        return ccxt_exchanges_list + ['zebitex', 'zebitex_testnet']

    def keys_initialisation(self): # Need to be refactored
        """Check if a key.txt file exist and create one if none.
        return: dict, with all api keys found.
        """
        if not os.path.isfile(self.keys_file):
            Path(self.keys_file).touch()
            self.applog.critical('No file was found, an empty one has been \
created, please fill it as indicated in the documentation')
            self.exit()
        else:
            keys = self.keys_file_reader()
            if not keys:
                self.applog.critical('Your key.txt file is empty, please \
fill it as indicated to the documentation')
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
                    self.applog.critical(f'Something went wrong : {e}')
                    self.exit()
                keys.update(key)
            return keys

    def select_marketplace(self):
        """Marketplace sélection menu, connect to the selected marketplace.
        return: string, the name of the selected marketplace
        """
        """
        q = 'Please select a market:'
        choice = self.ask_to_select_in_a_list(q, self.user_market_name_list)
        if self.user_market_name_list[choice] == 'zebitex':
            self.exchange = zebitexFormatted.ZebitexFormatted(
                self.keys[self.user_market_name_list[choice]]['apiKey'],
                self.keys[self.user_market_name_list[choice]]['secret'],
                False)
        elif self.user_market_name_list[choice] == 'zebitex_testnet':
            self.exchange = zebitexFormatted.ZebitexFormatted(
                self.keys[self.user_market_name_list[choice]]['apiKey'],
                self.keys[self.user_market_name_list[choice]]['secret'],
                True)
        else:
            self.exchange = eval('ccxt.' + self.user_market_name_list[choice] + \
             '(' + str(self.keys[self.user_market_name_list[choice]]) + ')')
        """
        self.exchange = zebitexFormatted.ZebitexFormatted(
                self.keys[self.user_market_name_list[2]]['apiKey'],
                self.keys[self.user_market_name_list[2]]['secret'],
                True)
        return  self.user_market_name_list[2] #self.user_market_name_list[choice]

    def select_market(self):
        """Market selection menu.
        return: string, selected market.
        """
        self.load_markets()
        """
        market_list = self.exchange.symbols
        valid_choice = False
        while valid_choice is False:
            self.applog.info(f'Please enter the name of a market: {market_list}')
            choice = input(' >> ').upper()
            limitation = self.limitation_to_btc_market(choice)
            if limitation is True:
                if choice in market_list:
                    self.selected_market = choice
                    valid_choice = True
            else:
                self.applog.info(limitation)"""
        return 'DASH/BTC' #choice

    def set_strat_log_file(self):
        """"""
        repo_name = 'logfiles'
        file_name_root = 'strat'
        file_type = '.log'
        params_file_name = None
        file_list = []
        # Make a list with all strat.log files name
        for file in os.listdir(repo_name):
            if file.startswith(file_name_root):
                file_list.append(file)
        repo_name += '/'
        file_name_root = repo_name + file_name_root + file_type
        # Care if there is none or only one strat.log file name
        if len(file_list) == 0:
            file_name = file_name_root
            Path(file_name).touch()
        elif len(file_list) == 1:
            if not self.logfile_not_empty(file_list[0]):
                file_name = file_name_root
            else:
                file_name = file_name_root + '.1'
                Path(file_name).touch()
                params_file_name = file_name_root
        else:
            if not self.logfile_not_empty(file_list[-1]):
                file_name = repo_name + file_list[-1]
                params_file_name = repo_name + file_list[-2]
            else:
                file_name = file_name_root + str(len(file_list) + 1)
                Path(file_name).touch()
                params_file_name = repo_name + file_list[-1]
        self.stratlog = self.logger_setup('logs', file_name,
            '%(message)s', logging.DEBUG, logging.INFO)
        return params_file_name

    """
    ######################## DATA CHECKER/FORMATTER ###########################
    """

    def log_file_reader(self, file_name):
        """Import data from logfile and organize it.
        file_name: string, path and name of the previous log file.
        return: None or dict containing : list of exectuted buy, 
                                          list of executed sell, 
                                          dict of parameters
        """
        logs_data = {'sell': [], 'buy': [], 'params': {}}        
        with open(file_name , mode='r', encoding='utf-8') as log_file:
            self.applog.debug("Reading the log file")
            params = log_file.readline()
            if params[0] == '#':
                params = params.replace('\n', '')
                params = params.replace("#", '')
                params = params.replace("'", '"')
                try:
                    params = json.loads(params)
                except Exception as e:
                    self.applog.critical(f'Something went wrong with the first \
line of the log file: {e}')
                    self.exit()
                params = self.params_checker(params)
                if params is False:
                    return False
                logs_data['params'] = params
                for line in log_file:
                    if line[0] == '{':
                        line = line.replace('\n', '')
                        line = line.replace("'", '"')
                        try:
                            order = json.loads(line)
                            formated_order = self.format_order(
                                    order['id'],
                                    order['price'],
                                    order['amount'],
                                    order['timestamp'],
                                    order['datetime'])
                            if order['side'] == 'buy'or\
                                order['side'] == 'canceled_buy':
                                logs_data['buy'].append(formated_order)
                            if order['side'] == 'sell' or\
                                order['side'] == 'canceled_sell':
                                logs_data['sell'].append(formated_order)
                        except Exception as e:
                            self.applog.warning(f'Something went wrong with data \
formating in the log file: {e}')
                            return False
                # Limit the number of history to keep to the last 20 trades
                while len(logs_data['buy']) > 20:
                    del logs_data['buy'][0]
                while len(logs_data['sell']) > 20:
                    del logs_data['sell'][0]
            else:
                raise ValueError('The first line of the log file do not \
contain parameters')
            self.applog.debug(logs_data)
            return logs_data

    def params_checker(self, params):
        """Check the integrity of all parameters and return False if it's not.
        params: dict.
        return: dict with valid parameters, or False.
        """
        self.applog.debug(f'param_checker, params: {params}')
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
            params['range_bot'] = self.str_to_decimal(
                params['range_bot'], error_message)
            error_message = 'params[\'range_top\'] is not a string for decimal: '
            params['range_top'] = self.str_to_decimal(
                params['range_top'], error_message)
            error_message = 'params[\'spread_bot\'] is not a string for \
                decimal: '
            params['spread_bot'] = self.str_to_decimal(params['spread_bot'],
                error_message)
            error_message = 'params[\'spread_top\'] is not a string for \
                decimal: '
            params['spread_top'] = self.str_to_decimal(params['spread_top'],
                error_message)
            error_message = 'params[\'increment_coef\'] is not a string for \
                decimal: '
            params['increment_coef'] = self.str_to_decimal(
                params['increment_coef'], error_message)
            error_message = 'params[\'amount\'] is not a string for decimal: '
            params['amount'] = self.str_to_decimal(
                params['amount'], error_message)
            error_message = 'params[\'stop_at_bot\'] is not a boolean: '
            params['stop_at_bot'] = self.str_to_bool(params['stop_at_bot'],
                error_message)
            error_message = 'params[\'stop_at_top\'] is not a boolean: '
            params['stop_at_top'] = self.str_to_bool(params['stop_at_top'],
                error_message)
            error_message = 'params[\'nb_buy_displayed\'] is not an int: '
            params['nb_buy_displayed'] = self.str_to_int(
                params['nb_buy_displayed'], error_message)
            error_message = 'params[\'nb_sell_displayed\'] is not an int: '
            params['nb_sell_displayed'] = self.str_to_int(
                params['nb_sell_displayed'], error_message)
            error_message = 'params[\'benef_alloc\'] is not an int: '
            params['benef_alloc'] = self.str_to_int(params['nb_sell_displayed'],
                error_message)
            self.applog.debug(f'param_checker, params: {params}')
            # Test if values are correct
            self.is_date(params['datetime'])
            if params['market'] not in self.exchange.symbols:
                raise ValueError('Market isn\'t set properly for this \
                    marketplace')
            if params['market'] != self.selected_market:
                raise ValueError(f'self.selected_market: \
{self.selected_market} != params["market"] {params["market"]}')
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
                raise ValueError('Range top value is too low, or increment too \
                    high: need to generate at lease 6 intervals.')
            if params['spread_bot'] not in self.intervals:
                raise ValueError('Spread_bot isn\'t properly configured')
            spread_bot_index = self.intervals.index(params['spread_bot'])
            if params['spread_top'] != self.intervals[spread_bot_index + 1]:
                raise ValueError('Spread_top isn\'t properly configured')
            self.param_checker_amount(params['amount'], params['spread_bot'])
            self.param_checker_benef_alloc(params['benef_alloc'])
        except Exception as e:
            self.applog.warning(f'The LW parameters are not well configured: {e}')
            return False
        return params

    def create_dir_when_none(self, dir_name):
        """Check if a directory exist or create one.
        return: bool."""
        if not os.path.isdir(dir_name):
            os.makedirs(dir_name)
            return False
        else:
            return True

    def create_file_when_none(self, file_name): # Need to be refactored
        """Check if a file exist or create one.
        return: bool.
        """
        if not os.path.isfile(file_name):
            Path(file_name).touch()
            return False
        else:
            return True

    def logfile_not_empty(self, file_name): # Need to be refactored
        """Check if there is data in the logfile.
        return : bool.
        """
        if os.path.getsize(file_name):
            return True
        else:
            self.applog.info('Logfile is empty!')
            return False

    def str_to_decimal(self, s, error_message=None):
        """Convert a string to Decimal or raise an error.
        s: string, element to convert
        error_message: string, error message detail to display if fail.
        return: Decimal."""
        try:
            return Decimal(str(s))
        except Exception as e:
            raise ValueError(f'{error_message} {e}')

    def is_date(self, str_date):
        """Check if a date have a valid formating.
        str_date: string
        """
        try:
            return datetime.strptime(str_date, '%Y-%m-%d %H:%M:%S.%f')
        except Exception as e:
            raise ValueError(f'{str_date} is not a valid date: {e}')

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
             raise ValueError(f'{error_message} {e}')

    def str_to_int(self, s, error_message=None):
        """Convert a string to an int or rise an error
        s: string.
        error_message: string, error message detail to display if fail.
        return: int.
        """
        try:
            return int(s)
        except Exception as e:
            raise ValueError(f'{error_message} {e}')

    def params_to_str(self, params):
        """Format params into a string.
        return: string, formated string for logfile."""
        return '#' + self.dict_to_str(params)

    def dict_to_str(self, dict):
        """Format dict into a string.
        return: string, formated string for logfile."""
        for key, value in dict.items():
            dict[key] = str(value)
        dict = str(dict)
        return dict.replace("'", '"')

    def timestamp_formater(self):
        """Format time.time() into the same format as timestamp
        used in ccxt: 13 numbers.
        return: int, formated timestamp"""
        timestamp = str(time.time()).split('.')
        return int(timestamp[0] + timestamp[1][:3])

    def limitation_to_btc_market(self, market):
        """Special limitation to BTC market : only ALT/BTC for now.
        market: string, market name.
        return: bool True or bool False + error message
        """
        if market[-3:] != 'BTC':
            return f'LW is limited to ALT/BTC markets : {market}'
        return True

    def param_checker_range_bot(self, range_bot):
        """Verifies the value of the bottom of the channel
        range_bot: decimal"""
        if range_bot < Decimal('0.000001'):
            raise ValueError('The bottom of the range is too low')
        return True

    def param_checker_range_top(self, range_top):
        """Verifies the value of the top of the channel
        range_top: decimal"""
        if range_top > Decimal('0.99'):
            raise ValueError('The top of the range is too high')
        return True

    def param_checker_interval(self, interval):
        """Verifies the value of interval between orders
        interval: decimal"""
        if Decimal('1.01') > interval or interval >  Decimal('1.50'):
            raise ValueError('Increment is too low (<=1%) or high (>=50%)')
        return True

    def param_checker_amount(self, amount, minimum_amount): 
        """Verifies the value of each orders 
        amount: decimal"""
        if amount < minimum_amount or amount > Decimal('10000000'):
            raise ValueError(f'Amount is too low (< {minimum_amount} \
                ) or high (>10000000)')

    def param_checker_nb_to_display(self, nb):
        """Verifie the nb of order to display
        nb: int"""
        if nb > len(self.intervals) and nb < 0:
            raise ValueError(f'The number of order to display is too low (<0) \
or high {len(self.intervals)}')
        return True

    def param_checker_benef_alloc(self, nb):
        """Verifie the nb for benefice allocation
        nb: int"""
        if 0 <= nb >= 100:
            raise ValueError(f'The benefice allocation too low (<0) or high \
(>100) {nb}')
        return True

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
        del intervals[-1]
        if len(intervals) < 6:
            raise ValueError('Range top value is too low, or increment too \
                high: need to generate at lease 6 intervals. Try again!')
        return intervals

    def increment_coef_buider(self, nb):
        """Formating increment_coef.
        nb: int, the value to increment in percentage.
        return: Decimal, formated value.
        """
        try:
            nb = Decimal(str(nb))
            nb = self.safety_sell_value + nb / Decimal('100')
            self.param_checker_interval(nb)
            return nb
        except Exception as e:
            raise ValueError(e)

    def check_for_enough_funds(self, params):
        """Check if the user have enough funds to run LW with he's actual
        parameters.
        Printed value can be negative!
        Ask for params change if there's not.
        params: dict, parameters for LW.
        return: dict, params"""
        is_valid = False
        # Force user to set strategy parameters in order to have enough funds
        # to run the whole strategy
        while is_valid is False:
            price = self.get_market_last_price(self.selected_market)
            self.get_balances()
            pair = self.selected_market.split('/')
            sell_balance = self.str_to_decimal(self.user_balance[pair[0]]['free'])
            buy_balance = self.str_to_decimal(self.user_balance[pair[1]]['free'])
            spread_bot_index = self.intervals.index(params['spread_bot'])
            spread_top_index = spread_bot_index + 1
            try:
                total_buy_funds_needed = self.calculate_buy_funds(
                    spread_bot_index, params['amount'])
                total_sell_funds_needed = self.calculate_sell_funds(
                    spread_top_index, params['amount'])
                # When the strategy will start with spread bot inferior or
                # equal to the actual market price
                if self.intervals[spread_bot_index] <= price:
                    incoming_buy_funds = Decimal('0')
                    i = spread_top_index
                    # When the whole strategy is lower than actual price
                    if params['range_top'] < price:
                        while i < len(self.intervals):
                            incoming_buy_funds += self.intervals[i] *\
                                params['amount'] * self.fees_coef
                            i +=1
                        # should it be kept?
                        incoming_buy_funds += params['range_top'] *\
                            params['amount'] * self.fees_coef
                    # When only few sell orders are planned to be under the
                    # actual price
                    else:
                        while self.intervals[i] <= price:
                            incoming_buy_funds += self.intervals[i] *\
                                params['amount'] * self.fees_coef
                            i +=1
                    total_buy_funds_needed = total_buy_funds_needed -\
                        incoming_buy_funds
                # When the strategy will start with spread bot superior to the
                # actual price on the market
                else:
                    incoming_sell_funds = Decimal('0')
                    i = spread_bot_index
                    # When the whole strategy is upper than actual price
                    if params['spread_bot'] > price:
                        while i >= 0:
                            incoming_sell_funds += params['amount'] *\
                                self.fees_coef
                            i -=1
                    # When only few buy orders are planned to be upper the
                    # actual price
                    else:
                        while self.intervals[i] >= price:
                            incoming_sell_funds += params['amount'] *\
                                self.fees_coef
                            i -=1
                    total_sell_funds_needed = total_sell_funds_needed - incoming_sell_funds
                # In case there is not enough funds, check if there is none stuck 
                # before asking to change params
                if total_buy_funds_needed > buy_balance:
                    buy_balance = self.look_for_moar_funds(total_buy_funds_needed,
                        buy_balance, 'buy')
                if total_sell_funds_needed > sell_balance:
                    sell_balance = self.look_for_moar_funds(
                        total_sell_funds_needed, sell_balance, 'sell')
                self.stratlog.debug(f'Your actual strategy require: {pair[1]} \
needed: {total_buy_funds_needed} and you have {buy_balance} {pair[1]}; \
{pair[0]} needed {total_sell_funds_needed} and you have {sell_balance} \
{pair[0]}.')
                if total_buy_funds_needed > buy_balance or\
                    total_sell_funds_needed > sell_balance:
                    raise ValueError('You don\'t own enough funds!')
                is_valid = True
            except ValueError as e:
                self.stratlog.warning('%s\nYou need to change some paramaters:', e)
                params = self.change_params(params)
        self.total_buy_funds_needed = total_buy_funds_needed
        self.total_sell_funds_needed = total_sell_funds_needed
        return params

    def calculate_buy_funds(self, index, amount):
        """Calculate the buy funds required to execute the strategy
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
        """Calculate the sell funds required to execute the strategy
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

    def look_for_moar_funds(self, funds_needed, funds, side):
        """Look into open orders how much funds there is, offer to cancel orders not
        in the strategy.
        funds_needed: Decimal, how much funds are needed for the strategy.
        funds: Decimal, sum of available funds for the strategy.
        side: string, buy or sell.
        return: Decimal, sum of available funds for the strategy."""
        orders = self.orders_price_ordering(
            self.get_orders(self.selected_market))
        orders = orders[side]
        orders_outside_strat = []
        # simple addition of funds stuck in open order and will be used for the
        # strategy
        if side == 'buy':
            for order in orders:
                if order[1] in self.intervals:
                    funds += order[1] * order[2]
                else:
                    orders_outside_strat += order
        else:
            for order in orders:
                if order[1] in self.intervals:
                    funds += order[2]
                else:
                    orders_outside_strat += order
        # If there is still not enough funds but there is open orders outside the
        # strategy 
        if funds_needed > funds:
            if orders_outside_strat:
                is_valid = False
                while is_valid is False:
                    if not orders_outside_strat:
                        is_valid = True
                    q = 'Do you want to remove some orders outside of the \
                    strategy to get enough funds to run it? (y or n)'
                    if self.simple_question(q):
                        q = 'Which order do you want to remove:'
                        rsp = self.ask_to_select_in_a_list(q, 
                            orders_outside_strat)
                        del orders_outside_strat[rsp]
                        rsp = self.cancel_order(orders_outside_strat[rsp][0],
                            orders_outside_strat[rsp][1],
                            orders_outside_strat[rsp][4], side)
                        if rsp:
                            if side == 'buy':
                                funds += order[1] * order[2]
                            else:
                                funds += order[2]
                            self.stratlog.info(f'You have now {funds} {side} \
funds and you need {funds_needed}.')
                    else:
                        is_valid = True
        return funds

    """
    ######################### USER INTERACTION ################################
    """

    def simple_question(self, q): #Fancy things can be added
        """Simple question prompted and response handling.
        q: string, the question to ask.
        return: boolean True or None, yes of no
        """
        while True:
            self.applog.info(q)
            choice = input(' >> ')
            self.applog.debug(choice)
            if choice == 'y':
                return True
            if choice == 'n':
                return False

    def ask_question(self, q, formater_func, control_func=None):
        """Ask any question to the user, control the value returned or ask again.
        q: string, question to ask to the user.
        formater_funct: function, format from string to the right datatype.
        control_funct: optional function, allow to check that the user's choice is 
                       within the requested parameters
        return: formated (int, decimal, ...) choice of the user
        """
        self.applog.info(q)
        while True:
            try:
                choice = input(' >> ')
                self.applog.debug(choice)
                choice = formater_func(choice)
                if control_func:
                    control_func(choice)
                return choice
            except Exception as e:
                self.applog.info(f'{q} invalid choice: {choice} -> {e}')

    def ask_to_select_in_a_list(self, q, a_list):
        """Ask to the user to choose between items in a list
        a_list: list.
        q: string.
        return: int, the position of this item """
        self.applog.info(q)
        q = ''
        for i, item in enumerate(a_list, start=1):
            q += f'{i}: {item}, '
        self.applog.info(q)
        while True:
            try:
                choice = input(' >> ')
                self.applog.debug(choice)
                choice = self.str_to_int(choice)
                if 0 < choice <= i:
                    return choice - 1
                else:
                    self.applog.info(f'You need to enter a number between 1 \
and {i}')
            except Exception as e:
                self.applog.info(f'{q} invalid choice: {choice} -> {e}')
        return choice

    def ask_param_range_bot(self):
        """Ask the user to enter a value for the bottom of the range.
        return: decimal."""
        q = 'Enter a value for the bottom of the range. It must be superior \
to 100 stats:'
        return self.ask_question(q, self.str_to_decimal,
            self.param_checker_range_bot)

    def ask_param_range_top(self):
        """Ask the user to enter a value for the top of the range.
        return: decimal."""
        q = 'Enter a value for the top of the range. It must be inferior to \
0.99 BTC:'
        return self.ask_question(q, self.str_to_decimal,
            self.param_checker_range_top)

    def ask_param_amount(self, range_bot):
        """Ask the user to enter a value of ALT to sell at each order.
        return: decimal."""
        minimum_amount = Decimal('0.001') / range_bot
        q = f'How much {self.selected_market[:4]} do you want to sell \
per order? It must be between {minimum_amount} and 10000000:'
        while True:
            try:
                amount = self.ask_question(q, self.str_to_decimal)
                self.param_checker_amount(amount, minimum_amount)
                return amount
            except Exception as e:
                self.applog.warning(e)

    def ask_param_increment(self):
        """Ask the user to enter a value for the spread between each order.
        return: decimal."""
        q = f'How much % of spread between two orders? It must be \
between 1% and 50%'
        return self.ask_question(q, self.increment_coef_buider)

    def ask_range_setup(self):
        """Ask to the user to enter the range and increment parameters.
        return: dict, asked parameters."""
        is_valid = False
        while is_valid is False:
            try:
                range_bot = self.ask_param_range_bot()
                range_top = self.ask_param_range_top()
                increment = self.ask_param_increment()
                intervals = self.interval_generator(range_bot, range_top,
                    increment)
                is_valid = True
            except Exception as e:
                self.applog.warning(e)
        self.intervals = intervals
        return {'range_bot': range_bot, 'range_top': range_top,
            'increment_coef': increment}

    def ask_params_spread(self):
        """Ask to the user to choose between value for spread bot and setup 
        spread top automatically
        return: dict, of decimal values
        """
        price = self.get_market_last_price(self.selected_market)
        msg = f'The actual price of {self.selected_market} is {price}'
        self.applog.info(msg)
        q = 'Please select the price of your highest buy order (spread_bot) \
in the list'
        position = self.ask_to_select_in_a_list(q, self.intervals)
        return {'spread_bot': self.intervals[position], 
                'spread_top': self.intervals[position + 1]} # Can be improved by suggesting a value

    def ask_nb_to_display(self):
        """Ask how much buy and sell orders are going to be in the book.
        return: dict, nb_buy_to_display + nb_sell."""
        q = f'How many buy orders do you want to display? It must be \
less than {len(self.intervals)}. 0 value = {len(self.intervals)} :'
        nb_buy_to_display = self.ask_question(q, self.str_to_int,
            self.param_checker_nb_to_display)
        q = f'How many sell orders do you want to display? It must be \
less than {len(self.intervals)}. 0 value = {len(self.intervals)} :'
        nb_sell_to_display = self.ask_question(q, self.str_to_int,
            self.param_checker_nb_to_display)
        return {'nb_buy_to_display': nb_buy_to_display, 
                'nb_sell_to_display': nb_sell_to_display}

    def ask_benef_alloc(self):
        """Ask for benefice allocation.
        return: int."""
        question = 'How do you want to allocate your benefice in %. It must \
be between 0 and 100, both included:'
        benef_alloc = self.ask_question(question, self.str_to_int, 
            self.param_checker_benef_alloc)
        return benef_alloc

    def ask_for_logfile(self):
        """Allow user to use previous parameter if they exist and backup it.
        At the end of this section, parameters are set and LW can be initialized.
        """
        q = 'Do you want to check if a previous parameter is in logfile?'
        if self.simple_question(q):
            file_name = self.set_strat_log_file()
            if file_name:
                log_file_datas = self.log_file_reader(file_name)
                if log_file_datas is not False:
                    self.applog.info(f'Your previous parameters are: \
{log_file_datas["params"]}')
                    q = 'Do you want to display history from logs?'
                    if self.simple_question(q):
                        self.display_user_trades(log_file_datas)
                    q = 'Do you want to use those params?'
                    if self.simple_question(q):
                        self.params = log_file_datas['params']
                else:
                    self.applog.warning('Your parameters are \
corrupted, please enter new one.')
            else:
                self.applog.warning('You don\'t have parameters in app.log')
        if not self.params:
            self.params = self.enter_params()
        self.stratlog.warning(self.params_to_str(self.params))
        return True

    def enter_params(self):
        """Series of questions to setup LW parameters.
        return: dict, valid parameters """
        params = {'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                  'market'  : self.selected_market}
        params.update(self.ask_range_setup())
        params.update({'amount': self.ask_param_amount(params['range_bot'])})
        params.update(self.ask_params_spread())
        params = self.check_for_enough_funds(params)
        q = 'Do you want to stop LW if range_bot is reach? (y) or (n) only.'
        params.update({'stop_at_bot': self.ask_question(q, self.str_to_bool)})
        q = 'Do you want to stop LW if range_top is reach? (y) or (n) only.'
        params.update({'stop_at_top': self.ask_question(q, self.str_to_bool)})
        params.update(self.ask_nb_to_display())
        params.update({'benef_alloc': self.ask_benef_alloc()})
        return params

    def change_params(self, params):
        """Allow the user to change one LW parameter.
        params: dict, all the parameter for LW.
        return: dict."""
        editable_params = (('range_bot', self.ask_param_range_bot),
                           ('range_top', self.ask_param_range_top),
                           ('increment_coef', self.ask_param_increment),
                           ('amount', self.ask_param_amount))
        question = 'What parameter do you want to change?'
        question_list = ['The bottom of the range?', 'The top of the range?',
                         'The value between order?', 
                         'The amount of alt per orders?',
                         'The value of your initial spread?', 
                         'Add funds to your account']
        is_valid = False
        while is_valid is False:
            try:
                choice = self.ask_to_select_in_a_list(question, question_list)
                if choice < 3:
                    params[editable_params[choice][0]] = \
                        editable_params[choice][1]()
                    self.intervals = self.interval_generator(
                        params['range_bot'], params['range_top'],
                        params['increment_coef'])
                    params = self.change_spread(params)
                elif choice == 3:
                    params[editable_params[choice][0]] = \
                        editable_params[choice][1](params['range_bot'])
                elif choice == 4:
                    params = self.change_spread(params)
                else:
                    self.wait_for_funds()
                is_valid = True
            except Exception as e:
                self.applog.warning(e)
        return params

    def change_spread(self, params):
        spread = self.ask_params_spread()
        for key, value in spread.items():
            params[key] = spread[key]
        return params

    def wait_for_funds(self):
        """The answer is in the question!"""
        q = 'Waiting for funds to arrive, (y) when you\'re ready, (n) to leave.'
        if not self.simple_question(q):
            self.exit()

    """
    ########################## API REQUESTS ###################################
    """

    def fetch_balance(self):
        """Get account balance from the marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        return: dict, formated balance by ccxt."""
        try:
            return self.exchange.fetch_balance()
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            time.sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                #send mail
                self.applog.warning('api error >= 10')
                self.err_counter = 0
            return self.fetch_balance()

    def load_markets(self):
        """Load the market list from a marketplace to self.exchange.
        Retry 1000 times when error and send a mail each 10 tries.
        """
        try:
            self.exchange.load_markets()
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            time.sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                #send mail
                self.applog.warning('api error >= 10')
                self.err_counter = 0
            self.load_markets()

    def fetch_open_orders(self, market):
        """Get open orders of a market from a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        market: string, market name.
        return: list, formatted open orders by ccxt."""
        try:
            return self.exchange.fetch_open_orders(market)
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            time.sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                #send mail
                self.applog.warning('api error >= 10')
                self.err_counter = 0
            return self.fetch_open_orders(market)

    def fetch_trades(self, market):
        """Get trading history of a market from a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        market: string, market name.
        return: list, formatted trade history by ccxt."""
        try:
            return self.exchange.fetch_trades(market)
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            time.sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                #send mail
                self.applog.warning('api error >= 10')
                self.err_counter = 0
            return self.fetch_trades(market)

    def fetch_ticker(self, market):
        """Get ticker info of a market from a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        market: string, market name.
        return: list, formatted trade history by ccxt."""
        try:
            return self.exchange.fetch_ticker(market)
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            time.sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                #send mail
                self.applog.warning('api error >= 10')
                self.err_counter = 0
            return self.fetch_ticker(market)

    def init_limit_buy_order(self, market, amount, price):
        """Generate a timestamp before creating a buy order."""
        self.now = self.timestamp_formater()
        return self.put_limit_buy_order(market, amount, price)

    def create_limit_buy_order(self, market, amount, price):
        """Create a limit buy order on a market of a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        market: string, market name.
        amount: string, amount of ALT to buy.
        price: string, price of the order.
        return: list, formatted trade history by ccxt."""
        try:
            order = self.exchange.create_limit_buy_order(market, amount, price)
            date = self.order_logger_formatter('buy', order['id'], price,
                amount, self.timestamp_formater(),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'))
            return self.format_order(order['id'], price, amount,
                date[0], date[1])
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            time.sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                #send mail
                self.applog.warning('api error >= 10')
                self.err_counter = 0
            rsp = self.check_limit_order(market, price,'buy')
            if not rsp:
                return self.create_limit_buy_order(market, amount, price)
            else:
                return rsp

    def set_several_buy(self, start_index, target, benef_alloc=None):
        """Loop for opening buy orders. It generate amount to split benef
        following benef alloc.
        market: string, market name.
        amount: string, amount of ALT to buy.
        price: string, price of the order.
        start_index: int, from where the loop start in self.intervals.
        target: int, from where the loop start in self.intervals.
        return: list, of executed orders.
        """
        buy_orders = []
        if benef_alloc:
            amount = []
            start_index_copy = start_index
            while start_index_copy <= target:
                btc_won = (self.intervals[start_index_copy + 1] *\
                    self.params['amount'] * self.fees_coef).quantize(
                        Decimal('.00000001'), rounding=ROUND_HALF_EVEN)
                btc_to_spend = (self.intervals[start_index_copy] *\
                    self.params['amount'] * self.fees_coef).quantize(
                        Decimal('.00000001'), rounding=ROUND_HALF_EVEN)
                amount.append((((btc_won - btc_to_spend) * Decimal(str(
                    params['benef_alloc'])) / Decimal('100')) * \
                    params['amount']).quantize(Decimal('.00000001'),
                        rounding=ROUND_HALF_EVEN) + self.params['amount'])
                start_index_copy += 1
        else:
            amount = [self.params['amount'] for x in range(target - start_index)]
        i = 0
        while start_index <= target:
            order = self.init_limit_buy_order(self.select_market, amount[i],
                self.intervals[start_index])
            buy_orders.append(order)
            start_index += 1
            i += 1
        return buy_orders

    def init_limit_sell_order(self, market, amount, price):
        """Generate a global timestamp before calling """
        self.now = self.timestamp_formater()
        return self.put_limit_sell_order(market, amount, price)

    def create_limit_sell_order(self, market, amount, price):
        """Create a limit sell order on a market of a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        market: string, market name.
        amount: string, amount of ALT to sell.
        price: string, price of the order.
        return: list, formatted trade history by ccxt
                or boolean True when the order is already filled"""
        try:
            order = self.exchange.create_limit_sell_order(market, amount, price)
            date = self.order_logger_formatter('sell', order['id'], price,
                amount, self.timestamp_formater(),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'))
            return self.format_order(order['id'], price, amount,
                date[0], date[1])
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            time.sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                #send mail
                self.applog.warning('api error >= 10')
                self.err_counter = 0
            rsp = self.check_limit_order(market, price,'sell')
            if not rsp:
                return self.create_limit_sell_order(market, amount, price)
            else:
                return rsp

    def set_several_sell(self, start_index, target):
        """Loop for opening sell orders.
        market: string, market name.
        amount: string, amount of ALT to sell.
        price: string, price of the order.
        start_index: int, from where the loop start in self.intervals.
        target: int, from where the loop start in self.intervals.
        return: list, of executed orders.
        """
        sell_orders = []
        while start_index <= target:
            order = self.init_limit_sell_order(self.select_market,
                self.params['amount'], self.intervals[start_index])
            buy_orders.append(order)
            start_index += 1
        return sell_orders

    def check_limit_order(self, market, price, side):
        """Verify if an order have been correctly created despite API error
        market: string, market name.
        price: string, price of the order.
        side: string, buy or sell
        return: list, in a formatted order"""
        time.sleep(0.5)
        orders = self.get_orders(market)[side]
        is_open = self.does_an_order_is_open(price, orders)
        if is_open:
            return is_open
        else:
            trades = self.get_user_history(market)[side]
            is_traded = self.order_in_history(price, trades, side, self.now)
            if is_traded:
                return is_traded
        return False

    def does_an_order_is_open(self, target, a_list):
        """Verify if an order is contained in a list
        target: decimal, price of an order.
        a_list: list, user trade history.
        return: boolean."""
        for item in a_list:
            if item[1] == target:
                return item
        return False

    def order_in_history(self, target, a_list, side, timestamp):
        """Verify that an order is in user history.
        target: decimal, price of an order.
        a_list: list, user trade history.
        side: string, buy or sell.
        timestamp: int, timestamp of the order.
        return: boolean."""
        if side == 'buy':
            coef = Decimal('2') - params['increment_coef'] + Decimal('0.001')
            for item in a_list:
                if item[4] >= timestamp:
                    if target * coef <= item[1] <= target:
                        return True
        if side == 'sell':
            coef = params['increment_coef'] - Decimal('0.001')
            for item in a_list:
                if item[4] >= timestamp:
                    if target * coef >= item[1] >= target:
                        return True
        return False

    def cancel_order(self, order_id, price, timestamp, side):
        """Cancel an order with it's id.
        Retry 1000 times, send an email each 10 tries.
        Warning : Not connard proofed!
        order_id: string, marketplace order id.
        price: string, price of the order.
        timestamp: int, timestamp of the order.
        side: string, buy or sell.
        return: boolean, True if the order is canceled correctly, False when the 
        order have been filled before it's cancellation"""
        cancel_side = 'cancel_buy' if side == 'buy' else 'cancel_sell'
        try:
            rsp = self.exchange.cancel_order(order_id)
            if rsp:
                self.order_logger_formatter(cancel_side, order_id, price,
                0, self.timestamp_formater(),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'))
                return True
            else:
                self.stratlog.warning(f'The {side} {order_id} have been filled \
before being canceled')
                return rsp
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            #return self.retry_cancel_order(order_id, side)
            time.sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                #send mail
                self.stratlog.warning('api error >= 10')
                self.err_counter = 0
            orders = self.get_orders(market)[side]
            is_open = self.does_an_order_is_open(price, orders)
            if is_open:
                rsp = self.exchange.cancel_order(order_id)
                if rsp:
                    self.err_counter = 0
                    return rsp
            trades = self.get_user_history(market)[side]
            is_traded = self.order_in_history(price, trades, side, timestamp)
            if is_traded:
                self.stratlog.warning(f'The {side} {order_id} have been filled \
before being canceled')
                return False
            else:
                self.order_logger_formatter(cancel_side, order['id'], price,
                    0, self.timestamp_formater(),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'))
                return True

    def cancel_all(self, new_open_orders):
        if open_orders['buy']:
            for item in open_orders['buy']:
                self.cancel_order(item[0], item[1], item[4], 'buy')
        if open_orders['sell']:
            self.cancel_order(item[0], item[1], item[4], 'sell')

    """
    ###################### API REQUESTS FORMATTERS ############################
    """

    def get_market_last_price(self, market):
        """Get the last price of a specific market
        market: str, need to have XXX/YYY ticker format 
        return: decimal"""
        return Decimal(f"{self.fetch_ticker(market)['last']:.8f}")

    def get_balances(self): # Need to be refactored
        """Get the non empty balance of a user on a marketplace and make it global"""
        balance = self.fetch_balance()
        user_balance = {}
        for key, value in balance.items():
            if 'total' in value:
                if value['total'] != 0.0:
                    for item in value:
                        value[item] = str(value[item])
                    user_balance.update({key: value})
        self.user_balance = user_balance
        return

    def display_user_balance(self):
        """Display the user balance"""
        for key, value in self.user_balance.items():
            self.stratlog.info(f'{key}: {value}')
        return

    def format_order(self, order_id, price, amount, timestamp, date):
        """Sort the information of an order in a list of 6 items.
        id: string, order unique identifier.
        price: float.
        amount: float.
        timestamp: int.
        date: string.
        return: list, containing: id, price, amount, value, timestamp and date.
        """
        return [order_id, Decimal(str(price)), Decimal(str(amount)),\
                Decimal(str(price)) * Decimal(str(amount)) * self.fees_coef,\
                timestamp, date]

    def get_orders(self, market):
        """Get actives orders from a marketplace and organize them.
        return: dict, containing list of buys & sells.
        """
        orders = {'sell': [], 'buy': []}
        raw_orders = self.fetch_open_orders(market)
        for order in raw_orders:
            formated_order = self.format_order(
                    order['id'],
                    order['price'],
                    order['amount'],
                    order['timestamp'],
                    order['datetime'])
            if order['side'] == 'buy':
                orders['buy'].append(formated_order)
            if order['side'] == 'sell':
                orders['sell'].append(formated_order)
        return orders

    def orders_price_ordering(self, orders):
        """Ordering open orders in their respective lists.
        orders: dict, containing list of buys & sells.
        return: dict, ordered lists of buys & sells."""
        self.stratlog.debug(f'def orders_price_ordering, orders: {orders}')
        if orders['buy']:
            orders['buy'] = sorted(orders['buy'], key=itemgetter(1))
        if orders['sell']:
            orders['sell'] = sorted(orders['sell'], key=itemgetter(1))
        self.stratlog.debug(f'def orders_price_ordering2, orders: {orders}')
        return orders

    def get_user_history(self, market):
        """Get orders history from a marketplace and organize them.
        return: dict, containing list of buy & list of sell.
        """
        orders = {'sell': [], 'buy': []}
        raw_orders = self.fetch_trades(market)
        for order in raw_orders:
            formated_order = self.format_order(
                    order['id'],
                    order['price'],
                    order['amount'],
                    order['timestamp'],
                    order['datetime'])
            if order['side'] == 'buy':
                orders['buy'].append(formated_order)
            if order['side'] == 'sell':
                orders['sell'].append(formated_order)
        return orders

    def display_user_trades(self, orders):
        """Pretify and display orders list.
        orders: dict, contain all orders.
        """
        if orders['buy']:
            for order in orders['buy']:
                self.stratlog.info(f'Buy on: {order[5]}, id: {order[0]}, \
price: {order[1]}, amount: {order[2]}, value: {order[3]}, timestamp: \
{order[4]}, date: {order[5]}')
        if orders['sell']:
            for order in orders['sell']:
                self.stratlog.info(f'Sell on: {order[5]}, id: {order[0]}, \
price: {order[1]}, amount: {order[2]}, value: {order[3]}, timestamp: \
{order[4]}, date: {order[5]}')
        return

    def order_logger_formatter(self, side, order_id, price, amount, timestamp,\
        datetime):
        """Format into a string an order for the logger
        side : string. buy, cancel_buy, sell or cancel_sell
        order_id: string, order id on the marketplace.
        price: Decimal.
        amount: Decimal.
        timestamp: int, formated timestamp.
        datetime: string, formated datetime.
        return: tuple with timestamp and datetime"""
        msg = '{' + f'"side": {side}, "order_id": {order_id}, "price": \
{price},  "amount": {amount}, "timestamp": {timestamp}, "datetime": {datetime}'\
+ '}'
        self.stratlog.warning(msg)
        return timestamp, datetime

    """
    ############################## FINALLY, LW ################################
    """

    def strat_init(self):
        """Prepare open orders on the market by asking to the user if he want
        to remove some outside the strategy or remove those that don't have
        the right amount of alts.
        return: dict, of open orders used for the strategy.
        """
        # Add funds locker in intervals
        self.intervals = [self.safety_buy_value] + self.intervals + \
            [self.safety_sell_value]
        self.stratlog.debug(f'strat_init, intervals: {self.intervals}')
        open_orders = self.orders_price_ordering(self.get_orders(
            self.selected_market))
        # In case there is an old safety orders
        open_orders = self.remove_safety_order(open_orders)
        remaining_orders_price = {'sell': [], 'buy': []}
        order = None
        order_to_select = []
        q = 'Do you want to remove this order ? (y or n)'
        q3 = f'Those orders have the same price that is used by the strategy. \
            Which one cancel : '
        # remove open orders outside the strategy
        for i, order in enumerate(open_orders['buy']):
            if order[1] not in self.intervals:
                self.stratlog.info(f'{order}')
                if self.simple_question(q):
                    self.cancel_order(order[0], order[1], order[4], 'buy')
                    del open_orders['buy'][i]
                else:
                    del open_orders['buy'][i]
            elif order[2] < self.params['amount']:
                q2 = f'This order {order} has an amount < \
                    to params[\'amount\']. Do you want to remove it? (y or no)'
                if self.simple_question(q2):
                    self.cancel_order(order[0], order[1], order[4], 'buy')
                    del open_orders['buy'][i]
            # When there is to order with the same price, remove one
            if order[1] == open_orders['buy'][i - 1][1]:
                order_to_select = [order, open_orders['buy'][i - 1]]
                rsp = self.ask_to_select_in_a_list(q3, order_to_select)
                if rsp == 0:
                    self.cancel_order(order[0], order[1], order[4], 'buy')
                else:
                    self.cancel_order(open_orders['buy'][i - 1][0],
                        open_orders['buy'][i - 1][1],
                        open_orders['buy'][i - 1][4], 'buy')
                    del open_orders['buy'][i - 1]
        for i, order in enumerate(open_orders['sell']):
            if order[1] not in self.intervals:
                self.stratlog.info(f'{order}')
                if self.simple_question(q):
                    self.cancel_order(order[0], order[1], order[4], 'sell')
                    del open_orders['sell'][i]
                else:
                    del open_orders['sell'][i]
            elif order[2] < self.params['amount']:
                q2 = f'This order {order} has an amount < \
                    to params[\'amount\']. Do you want to remove it? (y or no)'
                if self.simple_question(q2):
                    self.cancel_order(order[0], order[1], order[4], 'sell')
                    del open_orders['sell'][i]
            # When there is to order with the same price, remove one
            if order[1] == open_orders['sell'][i - 1][1]:
                order_to_select = [order, open_orders['buy'][i - 1]]
                rsp = self.ask_to_select_in_a_list(q3, order_to_select)
                if rsp == 0:
                    self.cancel_order(order[0], order[1], order[4], 'buy')
                else:
                    self.cancel_order(open_orders['buy'][i - 1][0],
                        open_orders['buy'][i - 1][1],
                        open_orders['buy'][i - 1][4], 'buy')
                    del open_orders['buy'][i - 1]
        # Create lists with all remaining orders price
        if open_orders['buy']:
            for order in open_orders['buy']:
                remaining_orders_price['buy'].append(order[1])
        if open_orders['sell']:
            for order in open_orders['sell']:
                remaining_orders_price['sell'].append(order[1])
        self.stratlog.debug(f'strat_init, open_orders: {open_orders}')
        return self.set_first_orders(remaining_orders_price, open_orders)

    def set_first_orders(self, remaining_orders_price, open_orders):
        """Open orders for the strategy.
        remaining_orders_price: dict.
        open_orders: dict.
        return: dict, of open orders used for the strategy."""
        buy_target = self.intervals.index(self.params['spread_bot'])
        lowest_sell_index = buy_target + 1
        self. max_sell_index = len(self.intervals) - 2
        new_orders = {'sell': [], 'buy': []}
        # params['nb_buy_displayed'] == 0 mean open orders as much as possible
        if params['nb_buy_displayed'] == 0:
            params['nb_buy_displayed'] = self.max_sell_index
        # Set the buy_target of order 
        if buy_target - params['nb_buy_displayed'] > 1:
            lowest_buy_index = buy_target - params['nb_buy_displayed']
        else:
            lowest_buy_index = 1
        # Open an order if needed or move an already existing order from
        # lowest buy price to highest buy price
        while lowest_buy_index <= buy_target:
            if self.intervals[lowest_buy_index] not in\
                remaining_orders_price['buy']:
                order = self.init_limit_buy_order(self.selected_market,
                    self.params['amount'], self.intervals[lowest_buy_index])
                new_orders['buy'] += order
            else:
                for i, item in enumerate(open_orders['buy']):
                    if item[1] == self.intervals[lowest_buy_index]:
                        new_orders['buy'] += item
                        del open_orders['buy'][i]
                        break
            lowest_buy_index += 1
        # Cancel buy orders that should not be opened
        for item in open_orders['buy']:
            self.cancel_order(order[0], order[1], order[4], 'buy')
            del open_orders['buy'][0]
        # Check that everything is fine
        if open_orders['buy']:
            raise ValueError('self.open_orders[\'buy\'] should be empty!')
        self.stratlog.debug(f'set_first_orders, remaining_orders_price buy: \
            {remaining_orders_price["buy"]}')
        # Now sell side
        if params['nb_sell_displayed'] == 0:
            params['nb_sell_displayed'] = self.max_sell_index
        if lowest_sell_index + params['nb_sell_displayed'] <\
            len(self.intervals.index) - 2:
            sell_target = lowest_sell_index + params['nb_sell_displayed']
        else:
            sell_target = len(self.intervals.index) - 2 
        # Open an order if needed or move an already existing order from
        # highest sell price to lowest sell price
        while lowest_sell_index <= sell_target:
            if self.intervals[sell_target] not in remaining_orders_price['sell']:
                order = self.init_limit_sell_order(self.selected_market,
                    self.params['amount'], self.intervals[sell_target])
                new_orders['sell'].append(order)
            else:
                for i, item in enumerate(open_orders['sell']):
                    if item[1] == self.intervals[sell_target]:
                        new_orders['sell'].append(item)
                        del open_orders['sell'][i]
                        break
            lowest_sell_index += 1
        # Cancel sell orders that should not be opened
        for item in open_orders['sell']:
            self.cancel_order(order[0], order[1], order[4], 'sell')
            del open_orders['sell'][0]
        # Check that everything is fine
        if open_orders['sell']:
            raise ValueError('self.open_orders[\'sell\'] should be empty!')
        self.stratlog.debug(f'set_first_orders, remaining_orders_price sell: \
            {remaining_orders_price["sell"]}')
        return new_orders

    def remove_safety_order(self, open_orders):
        """Remove safety orders if there is any.
        open_orders: dict.
        return: dict.
        """
        self.stratlog.debug(f'def remove_safety_order, open_orders: {open_orders}')
        if open_orders['buy']:
            if open_orders['buy'][0][1] == self.safety_buy_value:
                if open_orders['buy'][0][0]:
                    self.cancel_order(open_orders['buy'][0][0],
                        open_orders['buy'][0][1], open_orders['buy'][0][4],
                        'buy')
                del open_orders['buy'][0]
        if open_orders['sell']:
            if open_orders['sell'][-1][1] == self.safety_sell_value:
                if open_orders['sell'][-1][0]:
                    self.cancel_order(open_orders['sell'][-1][0],
                        open_orders['sell'][-1][1], open_orders['sell'][-1][4],
                        'sell')
                del open_orders['sell'][-1]

        self.stratlog.debug(f'def remove_safety_order, open_orders: {open_orders}')
        return open_orders

    def set_safety_orders(self, lowest_buy_index, highest_sell_index):
        """Add safety orders to luck funds for the strategy.
        lowest_buy_index: int.
        highest_sell_index: int."""
        if lowest_buy_index > 1:
            buy_sum = Decimal('0')
            while lowest_buy_index > 1:
                buy_sum += self.params['amount']
                lowest_buy_index -= 1
            self.open_orders['buy'].insert(0, self.init_limit_buy_order(
                self.selected_market, buy_sum, self.intervals[0]))
        else:
            if self.open_orders['buy'][0][1] != self.safety_buy_value:
                self.open_orders['buy'].insert(0, self.create_fake_buy())
        highest_target = self.max_sell_index
        if highest_sell_index < highest_target:
            sell_sum = Decimal('0')
            while highest_sell_index < highest_target:
                sell_sum += params['amount']
                highest_sell_index += 1
            self.open_orders['sell'].append(self.init_limit_sell_order(
                self.selected_market, sell_sum, self.intervals[-1]))
        else:
            if self.open_orders['sell'][-1][1] != self.safety_sell_value:
                self.open_orders['sell'].append(self.create_fake_sell())
        self.stratlog.debug(f'set_safety_orders, safety buy: \
            {self.open_orders["buy"][0]}, safety sell: \
            {self.open_orders["sell"][-1]}')
        return

    def create_fake_buy(self):
        """Create a fake buy order.
        return: list"""
        return [None, self.safety_buy_value, 0, 0, \
            self.timestamp_formater(),\
            datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')]

    def create_fake_sell(self):
        """Create a fake sell order.
        return: list"""
        return [None, self.safety_sell_value, 0, 0, self.timestamp_formater(),\
            datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')]

    def remove_orders_off_strat(self, new_open_orders):
        """Remove all orders that are not included in the strategy
        new_open_orders: dict, every open orders on the market
        return: dict, open orders wich are included in the strategy"""
        self.stratlog.debug('remove_orders_off_strat')
        if new_open_orders['buy']:
            for i, order in enumarate(new_open_orders['buy']):
                if order[1] not in self.intervals:
                    del new_open_orders['buy'][i]
        if new_open_orders['sell']:
            for i, order in enumerate(new_open_orders['sell']):
                if order[1] not in self.intervals:
                    del new_open_orders['sell'][i]
                i += 1
        return self.remove_safety_order(new_open_orders)

    def check_if_no_orders(self, new_open_orders):
        """Open orders when there is no orders open on the market
        return: dict"""
        self.stratlog.debug(f'check_if_no_orders, new_open_orders: \
            {new_open_orders}')
        if not new_open_orders['buy']:
            # Take care of fake orders
            if len(self.open_orders['buy']) > 1:
                target = self.intervals.index(
                    self.open_orders['buy'][1]) - 1
            else:
                target = 0
            # Create a fake order if needed or stop LW
            if self.open_orders['buy'][0][2] == 0:
                new_open_orders['buy'].append(self.create_fake_buy())
            elif target < 1:
                if self.params['stop_at_bot']:
                    self.cancel_all(self.remove_orders_off_strat(
                        self.get_orders(self.select_marketplace)))
                    self.stratlog.critical('Bottom target reached!')
                    self.exit()
                else:
                    new_open_orders['buy'].append(self.create_fake_buy())
            else:
                # Set the number of orders to execute
                if target - params['nb_buy_displayed'] >= 1:
                    start_index = target - params['nb_buy_displayed']
                else:
                    start_index = target -1
                # Create orders
                if start_index != 0:
                    orders = self.set_several_buy(start_index, target)
                    for order in orders:
                        new_open_orders['buy'].append(order)
                else:
                    self.open_orders['buy'].insert(0, self.create_fake_buy())
            self.stratlog.debug(f'check_if_no_orders, updated buy orders: \
                {new_open_orders["buy"]}')
        if not new_open_orders['sell']:
            # Take care of fake order
            if len(self.open_orders['sell']) > 1:
                start_index = self.intervals.index(
                    self.open_orders['sell'][-2]) + 1
            else:
                start_index = len(self.intervals)
            # Create a fake order id needed or stop LW
            if self.open_orders['sell'][0][2] == 0:
                new_open_orders['sell'].append(self.create_fake_sell())
            elif start_index > self.max_sell_index:
                if self.params['stop_at_top']:
                    self.cancel_all(self.remove_orders_off_strat(
                        self.get_orders(self.select_marketplace)))
                    self.stratlog.critical('Top target reached!')
                    self.exit()
                else:
                    new_open_orders['sell'].append(self.create_fake_sell())
            else:
                # Set the number of orders to execute
                if start_index + self.params['nb_sell_displayed'] >=\
                    self.max_sell_index:
                    target = start_index + self.params['nb_sell_displayed']
                else:
                    target = self.max_sell_index
                # Create orders
                if start_index < target:
                    orders = self.set_several_sell(start_index, target)
                    for order in orders:
                        new_open_orders['sell'].append(order)
                else:
                    self.open_orders['sell'].append(self.create_fake_sell())
            self.stratlog.debug(f'check_if_no_orders, updated sell orders: \
                {new_open_orders["sell"]}')
        return new_open_orders

    def compare_orders(self, new_open_orders):
        """Compare between open order know by LW and buy order from the
        marketplace.
        """
        executed_orders = {'buy': [], 'sell': []}
        missing_orders = copy.deepcopy(self.open_orders)
        # When a buy has occurred
        if new_open_orders['buy'][-1][1] != self.open_orders['buy'][-1][1]:
            self.stratlog.info('A buy has occurred')
            for order in self.open_orders['buy']:
                rsp = any(new_order[1] == order[1] \
                    for new_order in new_open_orders['buy'])
                if rsp:
                    missing_orders['buy'].remove(order)
            start_index = self.intervals.index(new_open_orders['buy'][-1][1])
            target = self.intervals.index(self.open_orders['buy'][-1][1])
            if target - start_index > 0:
                executed_orders['sell'] = self.set_several_sell(start_index,
                    target)
        # When a sell has occurred
        if new_open_orders['sell'][0][1] != self.open_orders['sell'][0][1]:
            self.stratlog.info('A sell has occurred')
            for order in self.open_orders['sell']:
                rsp = any(new_order[1] == order[1] \
                    for new_order in new_open_orders['sell'])
                if rsp:
                    missing_orders['sell'].remove(order)
            start_index = self.intervals.index([self.open_orders['sell'][0][1]])
            target = self.intervals.index(new_orders['sell'][0][1]) - 1
            if target - start_index > 0:
                executed_orders['buy'] = self.set_several_buy(start_index,
                    target, True)
        self.stratlog.debug(f'compare_orders, missing_orders: {missing_orders} \
            executed_orders: {executed_orders}')
        self.update_open_orders(missing_orders, executed_orders)
        return

    def update_open_orders(self, missing_orders, executed_orders):
        """Update self.open_orders with orders missing and executed orders.
        missing_orders: dict, all the missing orders since the last LW cycle.
        executed_order: dict, all the executed orders since the last LW cycle"""
        if executed_orders['buy']:
            self.stratlog.debug('Update self.open_orders[\'buy\']')
            for order in missing_orders['sell']:
                self.open_orders['sell'].remove(order)
            for order in executed_orders['buy']:
                self.open_orders['buy'].append(order)
            self.stratlog.debug(f'update_open_orders, self.open_orders buy: \
                {self.open_orders["buy"]}')
        if executed_orders['sell']:
            self.stratlog.debug('Update self.open_orders[\'sell\']')
            for order in missing_orders['buy']:
                self.open_orders['buy'].remove(item)
            for i, order in enumerate(executed_orders['sell']):
                self.open_orders['sell'].insert(i, order)
            self.stratlog.debug(f'update_open_orders, self.open_orders sell: \
                {self.open_orders["sell"]}')
        return

    def limit_nb_orders(self):
        """Cancel open orders if there is too many, open orders if there is 
        not enough of it"""
        new_open_orders = self.orders_price_ordering(self.get_orders(
                self.select_market))
        self.stratlog.debug(f'Limit nb orders, new_open_orders: \
            {new_open_orders}')
        # Don't mess up if all buy orders have been filled during the cycle
        if new_open_orders['buy']:
            nb_orders = len(new_open_orders['buy'])
        else:
            nb_orders = 0
        # When there is too much buy orders on the order book
        if nb_orders > self.params['nb_buy_displayed']:
            self.stratlog.debug(f'nb_orders > params[\'nb_buy_displayed\']')
            # Care of the fake order
            if not self.open_orders['buy'][0][0]:
                del self.open_orders['buy'][0]
            nb_orders -= self.params['nb_buy_displayed']
            while nb_orders > 0:
                self.cancel_order(new_open_orders['buy'][0][0],
                    new_open_orders['buy'][0][1], new_open_orders['buy'][0][4],
                    'buy')
                del self.open_orders['buy'][0]
                nb_orders -= 1
        # When there is not enough buy order in the order book
        elif nb_orders < self.params['nb_buy_displayed']:
            self.stratlog.debug(f'nb_orders < params[\'nb_buy_displayed\']')
            # Ignore if the bottom of the range is reached
            if self.open_orders['buy'][0][0]:
                # Set the range of buy orders to create
                target = self.intervals.index(self.open_orders['buy'][0][1]) - 1
                if target - self.params['nb_buy_displayed'] >= 1:
                    start_index = target - self.params['nb_buy_displayed']
                else:
                    start_index = target - 1
                # Care if there is no buy orders to create
                if start_index != 0:
                    orders = self.set_several_buy(start_index, target)
                    for i, order in enumerate(orders):
                        self.open_orders['buy'].insert(i, order)
        # Don't mess up if all sell orders have been filled during the cycle
        if new_open_orders['sell']:
            nb_orders = len(new_open_orders['sell'])
        else:
            nb_orders = 0
        # When there is too much buy orders on the order book
        if nb_orders > self.params['nb_sell_displayed']:
            self.stratlog.debug(f'nb_orders > params[\'nb_sell_displayed\']')
            # Care of th fake order
            if not self.open_orders['sell'][-1][0]:
                del self.open_orders['sell'][-1]
            nb_orders -= self.params['nb_sell_displayed']
            while nb_orders > 0:
                self.cancel_order(new_open_orders['sell'][-1][0],
                    new_open_orders['sell'][-1][1], 
                    new_open_orders['sell'][-1][4],
                    'sell')
                del self.open_orders['sell'][-1]
                nb_orders -= 1
        # When there is not enough buy order in the order book
        elif nb_orders < self.params['nb_sell_displayed']:
            self.stratlog.debug(f'nb_orders < params[\'nb_sell_displayed\']')
            # Ignore if the top of the range is reached
            if self.open_orders['sell'][-1][0]:
                # Set the range of buy orders to create
                start_index = self.intervals.index(
                    self.open_orders['sell'][-1][1]) + 1
                if start_index + self.params['nb_sell_displayed'] <=\
                    self.max_sell_index:
                    target = start_index + self.params['nb_sell_displayed']
                else:
                    target = self.max_sell_index
                # Care if there is no sell orders to create
                if start_index != target:
                    orders = self.set_several_sell(start_index, target)
                    for order in orders:
                        self.open_orders.append(order)
        self.stratlog.debug(f'limit_nb_orders, self.open_orders: \
            {self.open_orders}')
        return

    def exit(self):
        """Clean program exit"""
        self.applog.critical("End the program")
        sys.exit(0)

    def lw_initialisation(self):
        """Initializing parameters, check parameters then initialize LW.
        """
        marketplace_name = self.select_marketplace() # temp modification
        self.selected_market = self.select_market() # temp modification
        self.ask_for_logfile()
        self.open_orders = self.strat_init()
        self.set_safety_orders(self.intervals.index(self.open_orders['buy'][0]),
            self.intervals.index(self.open_orders['sell'][-1]))
        self.main_loop()

    def main_loop(self):
        """Do the lazy whale strategy.
        Simple execution loop.
        """
        while True:
            self.applog.debug('CYCLE START')
            self.compare_orders(self.check_if_no_orders(
                self.remove_orders_off_strat(
                    self.orders_price_ordering(
                        self.get_orders(self.select_market)))))
            self.limit_nb_orders()
            self.set_safety_orders(self.intervals.index(self.open_orders['buy'][0]),
                self.intervals.index(self.open_orders['sell'][-1]))
            self.applog.debug('CYCLE STOP')
            time.sleep(5)

    def main(self):
        self.applog.info("Program starting!")
        self.lw_initialisation()
        self.exit()

LazyStarter = LazyStarter()

if __name__ == "__main__":
    LazyStarter.main()