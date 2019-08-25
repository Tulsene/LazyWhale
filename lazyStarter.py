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
from time import time, sleep
from copy import deepcopy
from decimal import *
from pathlib import Path
from datetime import datetime
from operator import itemgetter
import pdb


class LazyStarter:
    getcontext().prec = 15

    def __init__(self, is_testing=False):
        self.is_testing = is_testing
        # Without assigning it first, it always return true
        self.script_position = os.path.dirname(sys.argv[0])
        self.root_path = f'{self.script_position}/' if self.script_position else ''
        self.keys_file = f'{self.root_path}keys.txt'
        self.stratlog = self.logger_setup('stratlogs', 'strat.log',
                                          '%(message)s', logging.DEBUG, logging.INFO)
        self.applog = self.logger_setup('debugs', 'app.log',
                                        '%(asctime)s - %(levelname)s - %(message)s', logging.DEBUG,
                                        logging.DEBUG)
        self.user_market_name_list = []
        self.exchanges_list = self.exchanges_list_init()
        self.keys = self.keys_initialisation()
        self.exchange = None
        self.fees_coef = Decimal('0.9975')
        self.user_balance = {}
        self.selected_market = None
        self.open_orders = {'sell': [], 'buy': []}
        self.params = {}
        self.intervals = []
        self.id_list = []
        self.err_counter = 0
        self.now = 0
        self.safety_buy_value = Decimal('0.00000001')
        self.safety_sell_value = Decimal('1')
        self.max_sell_index = None
        self.is_kraken = False
        self.last_loop_datetime = None

    """
    ########################## __INIT__ + MANDATORY ###########################
    """

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
        dir_name = f'{self.root_path}logfiles'
        self.create_dir_when_none('logfiles')
        log_file = f'{dir_name}/{log_file}'
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
        exchanges_list = ccxt.exchanges
        return exchanges_list + ['zebitex', 'zebitex_testnet']

    def keys_initialisation(self):  # Need to be refactored
        """Check if a key.txt file exist and create one if none.
        return: dict, with all api keys found.
        """
        if not os.path.isfile(self.keys_file):
            Path(self.keys_file).touch()
            msg = (
                f'No file was found, an empty one has been created, '
                f'please fill it as indicated in the documentation'
            )
            self.applog.critical(msg)
            self.exit()
        else:
            keys = self.keys_file_reader()
            if not keys:
                msg = (
                    f'Your key.txt file is empty, please '
                    f'fill it as indicated to the documentation'
                )
                self.applog.critical(msg)
                self.exit()
            else:
                return keys

    def keys_file_reader(self):  # Need to be refactored
        """Check the consistence of datas in key.txt.
        return: dict, api keys
        """
        keys = {}
        with open(self.keys_file, mode='r', encoding='utf-8') as keys_file:
            for line in keys_file:
                line = line.replace('\n', '')
                line = line.replace("'", '"')
                try:
                    key = json.loads(line)
                    for k in key.keys():
                        if k in self.user_market_name_list:
                            msg = (
                                f'You already have a key for this '
                                f'marketplace, please RTFM'
                            )
                            raise KeyError(msg)
                        else:
                            self.user_market_name_list.append(k)
                        if k not in self.exchanges_list:
                            raise NameError('The marketplace name is invalid!')
                except Exception as e:
                    self.applog.critical(f'Something went wrong : {e}')
                    self.exit()
                keys.update(key)
            return keys

    def select_marketplace(self, marketplace=None):
        """Select a marketplace among the loaded keys.
        Connect to the selected marketplace.
        return: String, name of the selected marketplace.
        """
        if not marketplace:
            q = 'Please select a market:'
            choice = self.ask_to_select_in_a_list(q, self.user_market_name_list)
        else:
            choice = self.user_market_name_list.index(marketplace)
        # Because kraken balance has no free and used balance
        self.is_kraken = True if self.user_market_name_list[choice] == 'kraken' \
            else False

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
            msg = (
                f'ccxt.{self.user_market_name_list[choice]}'
                f'({str(self.keys[self.user_market_name_list[choice]])})'
            )
            self.exchange = eval(msg)
        self.load_markets()
        return self.user_market_name_list[choice]

    def select_market(self, market=None):
        """Market selection menu.
        return: string, selected market.
        """
        if market:
            if market not in self.exchange.symbols:
                raise ValueError(f'{market} not in self.exchange.symbols')
            limitation = self.limitation_to_btc_market(market)
            if limitation != True:
                raise ValueError(limitation)
        else:
            valid_choice = False
            while valid_choice is False:
                self.applog.info(
                    f'Please enter the name of a market: {self.exchange.symbols}')
                market = input(' >> ').upper()
                limitation = self.limitation_to_btc_market(market)
                if limitation is True:
                    if market in self.exchange.symbols:
                        valid_choice = True
                else:
                    self.applog.info(limitation)
        self.selected_market = market
        return market

    """
    ######################## DATA CHECKER/FORMATTER ###########################
    """

    def log_file_reader(self):
        """Import the last 20 order from strat.log and organize it.
        return: None or dict containing : list of exectuted buy, 
                                          list of executed sell, 
                                          dict of parameters
        """
        strat_log_file = f'{self.root_path}logfiles/strat.log'
        raw_data = []
        logs_data = {'buy': [], 'sell': []}
        # In case there is no log file
        if not self.create_file_when_none(strat_log_file):
            self.applog.warning("params.txt file have been created")
            return
        self.applog.debug("Reading the strat.log file")
        nb_of_lines = self.file_line_counter(strat_log_file)
        # In case the log file is empty
        if not nb_of_lines:
            self.applog.warning('Your strat.log file was empty')
            return
        target = nb_of_lines - 20 if nb_of_lines > 20 else 0
        # Get the last 20 orders saved in log file
        while target < nb_of_lines:
            line = self.read_one_line(strat_log_file, nb_of_lines)
            try:
                line = json.loads(line)
                raw_data.append(line)
            except Exception as e:
                target = target - 1 if target - 1 >= 0 else target
            nb_of_lines -= 1
        # It's better when it's pretty to display
        for order in raw_data:
            formated_order = self.format_log_order(
                order['side'],
                order['order_id'],
                order['price'],
                order['amount'],
                order['timestamp'],
                order['datetime'])
            if order['side'] == 'buy' or \
                    order['side'] == 'canceled_buy':
                logs_data['buy'].append(formated_order)
            if order['side'] == 'sell' or \
                    order['side'] == 'canceled_sell':
                logs_data['sell'].append(formated_order)
        self.display_user_trades(logs_data)
        return logs_data

    def params_reader(self, file_path):
        """Check the integrity of all parameters and return False if it's not.
        file_path: string, params.txt relative path.
        return: dict with valid parameters, or False.
        """
        if not self.create_file_when_none(file_path):
            self.applog.warning('There was no params.txt. One have been created')
            return
        try:
            params = json.loads(self.read_one_line(file_path, 0))
        except Exception as e:
            msg = f'Something went wrong when loading params: {e}'
            self.applog.warning(msg)
            return
        try:
            # Check if values exist
            if not params['datetime']:
                raise ValueError('Datetime isn\'t set')
            if not params['marketplace']:
                raise ValueError('Market isn\'t set')
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
            if not params['nb_buy_to_display']:
                raise ValueError('Number of buy displayed isn\'t set')
            if not params['nb_sell_to_display']:
                raise ValueError('Number of sell displayed isn\'t set')
            if not params['profits_alloc']:
                raise ValueError('Benefices allocation isn\'t set')
            # Convert values
            error_message = f"params['range_bot'] is not a string:"
            params['range_bot'] = self.str_to_decimal(
                params['range_bot'], error_message)
            error_message = f"params['range_top'] is not a string:"
            params['range_top'] = self.str_to_decimal(
                params['range_top'], error_message)
            error_message = f"params['spread_bot'] is not a string:"
            params['spread_bot'] = self.str_to_decimal(params['spread_bot'],
                                                       error_message)
            error_message = f"params['spread_top'] is not a string:"
            params['spread_top'] = self.str_to_decimal(params['spread_top'],
                                                       error_message)
            error_message = f"params['increment_coef'] is not a string:"
            params['increment_coef'] = self.str_to_decimal(
                params['increment_coef'], error_message)
            error_message = f"params['amount'] is not a string:"
            params['amount'] = self.str_to_decimal(
                params['amount'], error_message)
            error_message = f"params['stop_at_bot'] is not a boolean:"
            params['stop_at_bot'] = self.str_to_bool(params['stop_at_bot'],
                                                     error_message)
            error_message = f"params['stop_at_top'] is not a boolean:"
            params['stop_at_top'] = self.str_to_bool(params['stop_at_top'],
                                                     error_message)
            error_message = f"params['nb_buy_to_display'] is not an int:"
            params['nb_buy_to_display'] = self.str_to_int(
                params['nb_buy_to_display'], error_message)
            error_message = f"params['nb_sell_to_display'] is not an int:"
            params['nb_sell_to_display'] = self.str_to_int(
                params['nb_sell_to_display'], error_message)
            error_message = f"params['profits_alloc'] is not an int:"
            params['profits_alloc'] = self.str_to_decimal(params['profits_alloc'],
                                                          error_message)
            self.applog.debug(f'param_checker, params: {params}')
            # Test if values are correct
            self.is_date(params['datetime'])
            if params['marketplace'] not in self.exchanges_list:
                raise ValueError(f"You can't choose {params['marketplace']}"
                                 f" as marketplace")
            if params['marketplace'] not in self.keys:
                raise ValueError(f"You don't own api key for"
                                 f" {params['marketplace']}")
            self.select_marketplace(params['marketplace'])
            self.select_market(params['market'])
            self.param_checker_range_bot(params['range_bot'])
            self.param_checker_range_top(params['range_top'])
            self.param_checker_interval(params['increment_coef'])
            self.intervals = self.interval_generator(params['range_bot'],
                                                     params['range_top'],
                                                     params['increment_coef'])
            if self.intervals is False:
                raise ValueError(
                    f'Range top value is too low, or increment too '
                    f'high: need to generate at lease 6 intervals.')
            if params['spread_bot'] not in self.intervals:
                raise ValueError('Spread_bot isn\'t properly configured')
            spread_bot_index = self.intervals.index(params['spread_bot'])
            if params['spread_top'] != self.intervals[spread_bot_index + 1]:
                raise ValueError('Spread_top isn\'t properly configured')
            self.param_checker_amount(params['amount'], params['spread_bot'])
            self.param_checker_profits_alloc(params['profits_alloc'])
        except Exception as e:
            self.applog.warning(f'The LW parameters are not well configured: {e}')
            return False
        return params

    def set_id_list_according_intervals(self):
        self.id_list = [None for _ in range(len(self.intervals))]
        return

    def update_id_list(self):
        """
        :return: None
        """
        id_list = []
        for side in self.open_orders:
            for order in self.open_orders[side]:
                try:
                    interval_index = self.intervals.index(order[1])
                except ValueError as e:
                    raise ValueError(f'Wrong order price for self.intervals, '
                        f'intervals: {str(self.intervals)}, got: '
                        f'{str(order[1])}, raw error: {e}')
                self.id_list[interval_index] = order[0]
                id_list.append(order[0])
        # Remove id or orders no longer in open_order.
        self.id_list[:] = [None if x not in id_list else x for x in self.id_list]
        self.stratlog.debug(f'self.id_list: {self.id_list}')
        return

    def create_dir_when_none(self, dir_name):
        """Check if a directory exist or create one.
        return: bool."""
        if not os.path.isdir(dir_name):
            os.makedirs(dir_name)
            return False
        else:
            return True

    def create_file_when_none(self, file_name):  # Need to be refactored
        """Check if a file exist or create one.
        return: bool.
        """
        if not os.path.isfile(file_name):
            Path(file_name).touch()
            return False
        else:
            return True

    def logfile_not_empty(self, file_name):  # Need to be refactored
        """Check if there is data in the logfile.
        return : bool.
        """
        if os.path.getsize(file_name):
            return True
        else:
            self.applog.info('Logfile is empty!')
            return False

    def read_one_line(self, file_name, line_nb):
        """Read and return a specific line in a file.
        return: string."""
        with open(file_name) as f:
            return f.readlines()[line_nb].replace('\n', '').replace("'", '"')

    def file_line_counter(self, file_name):
        """Line counter for any file.
        return: int, number of line. Start at 0."""
        try:
            with open(file_name, mode='r', encoding='utf-8') as log_file:
                for i, l in enumerate(log_file):
                    pass
            return i
        except NameError:
            self.applog.info(f'{file_name} is empty')
            return

    def simple_file_writer(self, file_name, text):
        """Write a text in a file.
        file_name: string, full path of the file.
        text: string.
        return: boolean.
        """
        try:
            with open(file_name, mode='w', encoding='utf-8') as file:
                file.write(text)
            return True
        except Exception as e:
            self.applog.critical(f'File writer error: {e}')
            self.exit()

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

    def str_to_bool(self, s, error_message=None):  # Fancy things can be added
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

    def dict_to_str(self, a_dict):
        """Format dict into a string.
        return: string, formated string for logfile."""
        b_dict = deepcopy(a_dict)
        for key, value in b_dict.items():
            b_dict[key] = str(value)
        b_dict = str(b_dict)
        return b_dict.replace("'", '"')

    def timestamp_formater(self):
        """Format time.time() into the same format as timestamp.
        used in ccxt: 13 numbers.
        return: string, formated timestamp"""
        timestamp = str(time()).split('.')
        return f'{timestamp[0]}{timestamp[1][:3]}'

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
        if range_bot < Decimal('0.00000001'):
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
        if Decimal('1.01') > interval or interval > Decimal('1.50'):
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
            msg = (
                f'The number of order to display is too low (<0) '
                f'or high {len(self.intervals)}'
            )
            raise ValueError(msg)
        return True

    def param_checker_profits_alloc(self, nb):
        """Verifie the nb for benefice allocation
        nb: int"""
        if Decimal('0') <= nb >= Decimal('100'):
            msg = (
                f'The benefice allocation too low (<0) or high '
                f'(>100) {nb}'
            )
            raise ValueError(msg)
        return True

    def multiplier(self, nb1, nb2, nb3=Decimal('1')):
        """Do a simple multiplication between Decimal.
        nb1: Decimal.
        nb2: Decimal.
        nb3: Decimal, optional.
        return: Decimal.
        """
        return self.quantizator(nb1 * nb2 * nb3)

    def quantizator(self, nb):
        """Format a Decimal object to 8 decimals
        return: Decimal"""
        return nb.quantize(Decimal('.00000001'), rounding=ROUND_HALF_EVEN)

    def interval_generator(self, range_bottom, range_top, increment):
        """Generate a list of interval inside a range by incrementing values
        range_bottom: Decimal, bottom of the range
        range_top: Decimal, top of the range
        increment: Decimal, value used to increment from the bottom
        return: list, value from [range_bottom, range_top[
        """
        intervals = [range_bottom]
        intervals.append(self.multiplier(intervals[-1], increment))
        if range_top <= intervals[1]:
            raise ValueError('Range top value is too low')
        while intervals[-1] <= range_top:
            intervals.append(self.multiplier(intervals[-1], increment))
        del intervals[-1]
        if len(intervals) < 6:
            msg = (
                f'Range top value is too low, or increment too '
                f'high: need to generate at lease 6 intervals. Try again!'
            )
            raise ValueError(msg)
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
                msg = (
                    f'check_for_enough_funds total_buy_funds_needed: '
                    f'{total_buy_funds_needed}, buy_balance: {buy_balance}, '
                    f'total_sell_funds_needed: {total_sell_funds_needed}, '
                    f'sell_balance: {sell_balance}, price: {price}'
                )
                self.applog.debug(msg)
                # When the strategy will start with spread bot inferior or
                # equal to the actual market price
                if params['spread_bot'] <= price:
                    incoming_buy_funds = Decimal('0')
                    i = spread_top_index
                    # When the whole strategy is lower than actual price
                    if params['range_top'] < price:
                        while i < len(self.intervals):
                            incoming_buy_funds += self.multiplier(
                                self.intervals[i], params['amount'],
                                self.fees_coef)
                            i += 1
                    # When only few sell orders are planned to be under the
                    # actual price
                    else:
                        while self.intervals[i] <= price:
                            incoming_buy_funds += self.multiplier(
                                self.intervals[i], params['amount'],
                                self.fees_coef)
                            i += 1
                            # It crash when price >= range_top
                            if i == len(self.intervals):
                                break
                    total_buy_funds_needed = total_buy_funds_needed - \
                                             incoming_buy_funds
                # When the strategy will start with spread bot superior to the
                # actual price on the market
                else:
                    incoming_sell_funds = Decimal('0')
                    i = spread_bot_index
                    # When the whole strategy is upper than actual price
                    if params['spread_bot'] > price:
                        while i >= 0:
                            incoming_sell_funds += self.multiplier(
                                params['amount'], self.fees_coef)
                            i -= 1
                    # When only few buy orders are planned to be upper the
                    # actual price
                    else:
                        while self.intervals[i] >= price:
                            incoming_sell_funds += self.multiplier(
                                params['amount'], self.fees_coef)
                            i -= 1
                            if i < 0:
                                break
                    total_sell_funds_needed = total_sell_funds_needed \
                                              - incoming_sell_funds
                msg = (
                    f'Your actual strategy require: {pair[1]} needed: '
                    f'{total_buy_funds_needed} and you have {buy_balance} '
                    f'{pair[1]}; {pair[0]} needed: {total_sell_funds_needed}'
                    f' and you have {sell_balance} {pair[0]}.'
                )
                self.applog.debug(msg)
                # In case there is not enough funds, check if there is none stuck 
                # before asking to change params
                if total_buy_funds_needed > buy_balance:
                    buy_balance = self.look_for_moar_funds(total_buy_funds_needed,
                                                           buy_balance, 'buy')
                if total_sell_funds_needed > sell_balance:
                    sell_balance = self.look_for_moar_funds(
                        total_sell_funds_needed, sell_balance, 'sell')
                if total_buy_funds_needed > buy_balance or \
                        total_sell_funds_needed > sell_balance:
                    raise ValueError('You don\'t own enough funds!')
                is_valid = True
            except ValueError as e:
                self.stratlog.warning('%s\nYou need to change some parameters:', e)
                params = self.change_params(params)
        return params

    def calculate_buy_funds(self, index, amount):
        """Calculate the buy funds required to execute the strategy
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
        amount: Decimal, allocated ALT per order
        return: Decimal, funds needed
        """
        sell_funds_needed = Decimal('0')
        i = len(self.intervals) - 1
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
        orders_outside_strat = []
        # simple addition of funds stuck in open order and will be used for the
        # strategy
        if side == 'buy':
            for order in orders['buy']:
                if order[1] in self.intervals \
                        or order[1] == self.safety_buy_value:
                    funds += order[1] * order[2]
                else:
                    orders_outside_strat.append(order)
        else:
            for order in orders['sell']:
                if order[1] in self.intervals \
                        or order[1] == self.safety_sell_value:
                    funds += order[2]
                else:
                    orders_outside_strat.append(order)
        # If there is still not enough funds but there is open orders outside the
        # strategy 
        if funds > Decimal('0'):
            if orders_outside_strat:
                is_valid = False
                while is_valid is False:
                    if not orders_outside_strat:
                        is_valid = True
                    q = (
                        f'Do you want to remove some orders outside of the '
                        f'strategy to get enough funds to run it? (y or n)'
                    )
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
                            self.stratlog.debug(
                                f'You have now {funds} {side} '
                                f'funds and you need {funds_needed}.')
                    else:
                        is_valid = True
        return funds

    """
    ######################### USER INTERACTION ################################
    """

    def simple_question(self, q):  # Fancy things can be added
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
                    msg = f'You need to enter a number between 1 and {i}'
                    self.applog.info(msg)
            except Exception as e:
                self.applog.info(f'{q} invalid choice: {choice} -> {e}')
        return choice

    def ask_param_range_bot(self):
        """Ask the user to enter a value for the bottom of the range.
        return: decimal."""
        q = (
            f'Enter a value for the bottom of the range. It must be '
            f'superior to 1 stats:')
        return self.ask_question(q, self.str_to_decimal,
                                 self.param_checker_range_bot)

    def ask_param_range_top(self):
        """Ask the user to enter a value for the top of the range.
        return: decimal."""
        q = (
            f'Enter a value for the top of the range. It must be '
            f'inferior to 0.99 BTC:')
        return self.ask_question(q, self.str_to_decimal,
                                 self.param_checker_range_top)

    def ask_param_amount(self, range_bot):
        """Ask the user to enter a value of ALT to sell at each order.
        return: decimal."""
        minimum_amount = Decimal('0.001') / range_bot
        q = (
            f'How much {self.selected_market[:4]} do you want to sell '
            f'per order? It must be between {minimum_amount} and 10000000:')
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
        q = (
            f'How much % of spread between two orders? It must be '
            f'between 1% and 50%')
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
        q = (
            f'Please select the price of your highest buy order '
            f'(spread_bot) in the list')
        position = self.ask_to_select_in_a_list(q, self.intervals)
        return {'spread_bot': self.intervals[position],
                'spread_top': self.intervals[position + 1]}  # Can be improved by suggesting a value

    def ask_nb_to_display(self):
        """Ask how much buy and sell orders are going to be in the book.
        return: dict, nb_buy_to_display + nb_sell."""
        q = (
            f'How many buy orders do you want to display? It must be '
            f'less than {len(self.intervals)}. 0 value = '
            f'{len(self.intervals)} :')
        nb_buy_to_display = self.ask_question(q, self.str_to_int,
                                              self.param_checker_nb_to_display)
        q = (
            f'How many sell orders do you want to display? It must be '
            f'less than {len(self.intervals)}. 0 value = '
            f'{len(self.intervals)} :')
        nb_sell_to_display = self.ask_question(q, self.str_to_int,
                                               self.param_checker_nb_to_display)
        return {'nb_buy_to_display': nb_buy_to_display,
                'nb_sell_to_display': nb_sell_to_display}

    def ask_profits_alloc(self):
        """Ask for profits allocation.
        return: int."""
        q = (
            f'How do you want to allocate your profits in %. It must '
            f'be between 0 and 100, both included:')
        profits_alloc = self.ask_question(q, self.str_to_int,
                                          self.param_checker_profits_alloc)
        return profits_alloc

    def ask_for_params(self):
        """Allow user to use previous parameter if they exist and backup it.
        At the end of this section, parameters are set and LW can be initialized.
        """
        q = 'Do you want to check if a previous parameter is in params.txt?'
        file_path = f'{self.root_path}params.txt'
        if self.simple_question(q):
            params = self.params_reader(file_path)
            if params:
                self.applog.info(f'Your previous parameters are: {params}')
                q = 'Do you want to display history from logs?'
                if self.simple_question(q):
                    self.log_file_reader()
                q = 'Do you want to use those params?'
                if self.simple_question(q):
                    self.params = self.check_for_enough_funds(params)
            else:
                msg = 'Your parameters are corrupted, please enter new one!'
                self.applog.warning(msg)
        if not self.params:
            self.params = self.enter_params()
        self.simple_file_writer(file_path, self.dict_to_str(self.params))
        return True

    def enter_params(self):
        """Series of questions to setup LW parameters.
        return: dict, valid parameters """
        params = {'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}
        params.update({'marketplace': self.select_marketplace()})
        params.update({'market': self.select_market()})
        params.update(self.ask_range_setup())
        params.update({'amount': self.ask_param_amount(params['range_bot'])})
        params.update(self.ask_params_spread())
        params = self.check_for_enough_funds(params)
        q = 'Do you want to stop LW if range_bot is reach? (y) or (n) only.'
        params.update({'stop_at_bot': self.ask_question(q, self.str_to_bool)})
        q = 'Do you want to stop LW if range_top is reach? (y) or (n) only.'
        params.update({'stop_at_top': self.ask_question(q, self.str_to_bool)})
        params.update(self.ask_nb_to_display())
        params.update({'profits_alloc': self.ask_profits_alloc()})
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
            sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                # send mail
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
            sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                # send mail
                self.applog.warning('api error >= 10')
                self.err_counter = 0
            self.load_markets()

    def fetch_open_orders(self, market=None):
        """Get open orders of a market from a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        market: string, market name.
        return: list, formatted open orders by ccxt."""
        try:
            return self.exchange.fetch_open_orders(market)
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                # send mail
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
            sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                # send mail
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
            sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                # send mail
                self.applog.warning('api error >= 10')
                self.err_counter = 0
            return self.fetch_ticker(market)

    def init_limit_buy_order(self, market, amount, price):
        """Generate a timestamp before creating a buy order."""
        self.now = self.timestamp_formater()
        return self.create_limit_buy_order(market, amount, price)

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
                                               amount)
            return self.format_order(order['id'], price, amount,
                                     date[0], date[1])
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                # send mail
                self.applog.warning('api error >= 10')
                self.err_counter = 0
            rsp = self.check_limit_order(market, price, 'buy')
            if not rsp:
                return self.create_limit_buy_order(market, amount, price)
            else:
                return rsp

    def set_several_buy(self, start_index, target, profits_alloc=None):
        """Loop for opening buy orders. It generate amount to split benef
        following benef alloc.
        start_index: int, from where the loop start in self.intervals.
        target: int, from where the loop start in self.intervals.
        profits_alloc: boolean, optional.
        return: list, of executed orders.
        """
        buy_orders = []
        if profits_alloc:
            amount = []
            start_index_copy = start_index
            while start_index_copy <= target:
                btc_won = self.multiplier(self.intervals[start_index_copy + 1],
                                          self.params['amount'], self.fees_coef)
                btc_to_spend = self.multiplier(self.intervals[start_index_copy],
                                               self.params['amount'], self.fees_coef)
                total = ((btc_won - btc_to_spend) * Decimal(
                    self.params['profits_alloc']) / Decimal('100') + \
                         btc_to_spend) / self.intervals[start_index_copy]
                amount.append(self.quantizator(total))
                start_index_copy += 1
        else:
            if target - start_index > 0:
                amount = [self.params['amount'] for x in \
                          range(target - start_index + 1)]
            else:
                amount = [self.params['amount']]
        i = 0
        while start_index <= target:
            order = self.init_limit_buy_order(self.selected_market, amount[i],
                                              self.intervals[start_index])
            buy_orders.append(order)
            start_index += 1
            i += 1
        return buy_orders

    def init_limit_sell_order(self, market, amount, price):
        """Generate a global timestamp before calling """
        self.now = self.timestamp_formater()
        return self.create_limit_sell_order(market, amount, price)

    def create_limit_sell_order(self, market, amount, price):
        """Create a limit sell order on a market of a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        market: string, market name.
        amount: string, amount of ALT to sell.
        price: string, price of the order.
        return: list, formatted trade history by ccxt
                or boolean True when the order is already filled"""
        try:
            order = self.exchange.create_limit_sell_order(market,
                                                          amount,
                                                          price)
            date = self.order_logger_formatter('sell', order['id'], price,
                                               amount)
            return self.format_order(order['id'], price, amount,
                                     date[0], date[1])
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                # send mail
                self.applog.warning('api error >= 10')
                self.err_counter = 0
            rsp = self.check_limit_order(market, price, 'sell')
            if not rsp:
                return self.create_limit_sell_order(market, amount, price)
            else:
                return rsp

    def set_several_sell(self, start_index, target):
        """Loop for opening sell orders.
        start_index: int, from where the loop start in self.intervals.
        target: int, from where the loop start in self.intervals.
        return: list, of executed orders.
        """
        sell_orders = []
        while start_index <= target:
            order = self.init_limit_sell_order(self.selected_market,
                                               self.params['amount'],
                                               self.intervals[start_index])
            sell_orders.append(order)
            start_index += 1
        return sell_orders

    def check_limit_order(self, market, price, side):
        """Verify if an order have been correctly created despite API error
        market: string, market name.
        price: string, price of the order.
        side: string, buy or sell
        return: list, in a formatted order"""
        sleep(0.5)
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
            coef = Decimal('2') - Decimal(self.params['increment_coef']) + \
                   Decimal('0.001')
            for item in a_list:
                if item[4] >= timestamp:
                    if target * coef <= item[1] <= target:
                        return True
        if side == 'sell':
            coef = self.params['increment_coef'] - Decimal('0.001')
            for item in a_list:
                if item[4] >= timestamp:
                    if target * coef >= item[1] >= target:
                        return True
        return False

    def trade_history(self):
        try:
            history = self.exchange.fetch_trades(self.selected_market)
            if type(history) == list:
                return history
            else:
                logging.warning(f'WARNING: Unexpected order history: {history}')
        except Exception as e:
            logging.warning(f'WARNING: {e}')

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
            self.applog.debug(f'Init cancel {side} order {order_id} {price}')
            rsp = self.exchange.cancel_order(order_id)
            if rsp:
                self.order_logger_formatter(cancel_side, order_id, price, 0)
                return True
            else:
                msg = (
                    f'The {side} {order_id} have been filled '
                    f'before being canceled'
                )
                self.stratlog.warning(msg)
                return rsp
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            sleep(0.5)
            self.err_counter += 1
            if self.err_counter >= 10:
                # send mail
                self.stratlog.warning('api error >= 10')
                self.err_counter = 0
            orders = self.get_orders(self.selected_market)[side]
            is_open = self.does_an_order_is_open(price, orders)
            if is_open:
                rsp = self.exchange.cancel_order(order_id)
                if rsp:
                    self.err_counter = 0
                    return rsp
            trades = self.get_user_history(self.selected_market)[side]
            is_traded = self.order_in_history(price, trades, side, timestamp)
            if is_traded:
                msg = (
                    f'The {side} {order_id} have been filled '
                    f'before being canceled'
                )
                self.stratlog.warning(msg)
                return False
            else:
                self.order_logger_formatter(cancel_side, order_id, price, 0)
                return True

    def cancel_all(self, open_orders):
        if open_orders['buy']:
            for item in open_orders['buy']:
                self.cancel_order(item[0], item[1], item[4], 'buy')
        if open_orders['sell']:
            for item in open_orders['sell']:
                self.cancel_order(item[0], item[1], item[4], 'sell')

    """
    ###################### API REQUESTS FORMATTERS ############################
    """

    def get_market_last_price(self, market):
        """Get the last price of a specific market
        market: str, need to have XXX/YYY ticker format 
        return: decimal"""
        return Decimal(f"{self.fetch_ticker(market)['last']:.8f}")

    def get_balances(self):  # Need to be refactored
        """Get the non empty balance of a user on a marketplace and make 
        it global."""
        balance = self.fetch_balance()
        user_balance = {}
        for key, value in balance.items():
            if 'total' in value:
                if float(value['total']) != 0.0:
                    for item in value:
                        value[item] = str(value[item])
                    user_balance.update({key: value})
        if self.is_kraken:
            orders = self.fetch_open_orders()
            for order in orders:
                if order['side'] == 'buy':
                    coin = order['symbol'].split('/')[1]
                    if user_balance[coin]['used'] == 'None':
                        user_balance[coin]['used'] = Decimal(order['price']) \
                                                     * Decimal(order['amount'])
                    else:
                        user_balance[coin]['used'] = user_balance[coin]['used'] \
                                                     + Decimal(order['price']) * Decimal(order['amount'])
                else:
                    coin = order['symbol'].split('/')[0]
                    if user_balance[coin]['used'] == 'None':
                        user_balance[coin]['used'] = Decimal(order['amount'])
                    else:
                        user_balance[coin]['used'] = user_balance[coin]['used'] \
                                                     + Decimal(order['amount'])
            for coin in user_balance:
                if user_balance[coin]['used'] != 'None':
                    user_balance[coin]['free'] = str(
                        Decimal(user_balance[coin]['total']) \
                        - user_balance[coin]['used'])
                    user_balance[coin]['used'] = str(user_balance[coin]['used'])
                else:
                    user_balance[coin]['used'] = '0.0'
                    user_balance[coin]['free'] = user_balance[coin]['total']
                if user_balance[coin]['free'] == 'None':
                    user_balance[coin]['free'] = '0.0'
        print(user_balance)
        self.user_balance = user_balance
        return user_balance

    def display_user_balance(self):
        """Display the user balance"""
        for key, value in self.user_balance.items():
            self.stratlog.info(f'{key}: {value}')
        return

    def format_order(self, order_id, price, amount, timestamp, date):
        """Sort the information of an order in a list of 6 items.
        id: string, order unique identifier.
        price: Decimal or string.
        amount: Decimal.
        timestamp: string.
        date: string.
        return: list, containing: id, price, amount, value, timestamp and date.
        """
        return [order_id, Decimal(price), amount, self.multiplier(
            Decimal(price), amount, self.fees_coef), timestamp, date]

    def format_log_order(self, side, order_id, price, amount, timestamp, date):
        """Sort the information of an order in a list of 6 items.
        id: string, order unique identifier.
        price: Decimal or string.
        amount: Decimal.
        timestamp: string.
        date: string.
        return: list, containing: id, price, amount, value, timestamp and date.
        """
        return [side, order_id, price, amount, str(self.multiplier(
            Decimal(price), Decimal(amount), self.fees_coef)), \
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
                Decimal(str(order['price'])),
                Decimal(str(order['amount'])),
                str(order['timestamp']),
                order['datetime'])
            if order['side'] == 'buy':
                orders['buy'].append(formated_order)
            if order['side'] == 'sell':
                orders['sell'].append(formated_order)
        return orders

    def orders_price_ordering(self, orders):
        """Ordering open orders in their respective lists.
        list[0][1] is the lowest value.
        orders: dict, containing list of buys & sells.
        return: dict, ordered lists of buys & sells."""
        if orders['buy']:
            orders['buy'] = sorted(orders['buy'], key=itemgetter(1))
        if orders['sell']:
            orders['sell'] = sorted(orders['sell'], key=itemgetter(1))
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
                Decimal(str(order['price'])),
                Decimal(str(order['amount'])),
                str(order['timestamp']),
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
                self.stratlog.info(self.format_order_to_display(order))
        if orders['sell']:
            for order in orders['sell']:
                self.stratlog.info(self.format_order_to_display(order))
        return

    def format_order_to_display(self, order):
        """To format an order as a string.
        order: dict.
        return: string."""
        return (
            f'{order[0]} on: {order[6]}, id: {order[1]}, price: {order[2]}, '
            f'amount: {order[3]}, value: {order[4]}, timestamp: {order[5]}'
        )

    def order_logger_formatter(self, side, order_id, price, amount):
        """Format into a string an order for the logger
        side : string. buy, cancel_buy, sell or cancel_sell
        order_id: string, order id on the marketplace.
        price: Decimal.
        amount: Decimal.
        return: tuple with strings."""
        timestamp = self.timestamp_formater()
        date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        self.stratlog.warning(
            f'{{"side": "{str(side)}", "order_id": "{str(order_id)}", '
            f'"price": "{str(price)}", "amount": "{str(amount)}", '
            f'"timestamp": "{timestamp}", "datetime": "{date_time}" }}')
        return timestamp, date_time

    """
    ############################## FINALLY, LW ################################
    """

    def remove_safety_before_init(self, open_orders):
        """Remove safety orders before strat init if there is some.
        open_orders: dict.
        return: dict."""
        if open_orders['buy']:
            if open_orders['buy'][0][1] == self.safety_buy_value:
                self.cancel_order(open_orders['buy'][0][0],
                                  open_orders['buy'][0][1],
                                  open_orders['buy'][0][4],
                                  'buy')
                del open_orders['buy'][0]
        if open_orders['sell']:
            if open_orders['sell'][-1][1] == self.safety_sell_value:
                self.cancel_order(open_orders['sell'][-1][0],
                                      open_orders['sell'][-1][1],
                                      open_orders['sell'][-1][4],
                                      'sell')
                del open_orders['sell'][-1]
        return open_orders

    def strat_init(self, open_orders):
        """Prepare open orders on the market by asking to the user if he want
        to remove some outside the strategy or remove those that don't have
        the right amount of alts.
        return: dict, of open orders used for the strategy.
        """
        self.stratlog.debug('strat_init()')
        # Add funds locker value in intervals
        self.intervals = [self.safety_buy_value] + self.intervals + \
                         [self.safety_sell_value]
        self.max_sell_index = len(self.intervals) - 2
        # self.stratlog.debug(f'strat_init, open_orders: {open_orders}')
        remaining_orders_price = {'sell': [], 'buy': []}
        orders_to_remove = {'sell': [], 'buy': []}
        q = 'Do you want to remove this order ? (y or n)'
        q2 = (
            f"This order has an amount inferior or superior to "
            f"params['amount']. Do you want to cancel it? (y or no)")
        q3 = (
            f'Those orders have the same price that is used by the strategy. '
            f'Which one of the two do you want to cancel : ')

        if self.intervals.index(self.params['spread_bot']) \
                - self.params['nb_buy_to_display'] + 1 > 1 \
                and self.params['nb_buy_to_display'] != 0:
            lowest_buy = self.intervals[self.intervals.index(
                self.params['spread_bot']) - self.params['nb_buy_to_display'] + 1]
        else:
            lowest_buy = self.intervals[1]

        if self.intervals.index(self.params['spread_top']) \
                + self.params['nb_sell_to_display'] - 1 < self.max_sell_index \
                and self.params['nb_sell_to_display'] != 0:
            highest_sell = self.intervals[self.intervals.index(
                self.params['spread_top']) + self.params['nb_sell_to_display'] - 1]
        else:
            highest_sell = self.intervals[self.max_sell_index]
        self.stratlog.debug(
            f'self.intervals: {self.intervals}, open_orders: {open_orders}, '
            f'self.max_sell_index: {self.max_sell_index}, '
            f'lowest_buy: {lowest_buy}, self.params["spread_bot"]: '
            f"{self.params['spread_bot']}, self.params['spread_top']: "
            f"{self.params['spread_top']}, highest_sell: {highest_sell}")

        # Unwanted buy orders for the strategy handler
        for i, order in enumerate(open_orders['buy']):
            if order[1] in self.intervals:
                if not lowest_buy <= order[1] <= self.params['spread_bot']:
                    self.cancel_order(order[0], order[1], order[4], 'buy')
                    orders_to_remove['buy'].append(i)
                    continue
                if order[2] != self.params['amount']:
                    if not self.is_testing:
                        if self.simple_question(f'{order} {q2}'):
                            self.cancel_order(order[0], order[1], order[4], 'buy')
                            orders_to_remove['buy'].append(i)
                            continue
            else:
                if not self.is_testing:
                    if self.simple_question(f'{q} {order}'):
                        self.cancel_order(order[0], order[1], order[4], 'buy')
                orders_to_remove['buy'].append(i)
                continue

            # Two order of the same price could crash the bot
            if i > 0:
                if order[1] == open_orders['buy'][i - 1][1] \
                        and i - 1 not in orders_to_remove['buy']:
                    order_to_select = [order, open_orders['buy'][i - 1]]
                    if self.is_testing:
                        rsp = 1
                    else:
                        rsp = int(self.ask_to_select_in_a_list(q3, order_to_select))
                    if rsp == 1:
                        self.cancel_order(order[0], order[1], order[4], 'buy')
                        orders_to_remove['buy'].append(i)
                    else:
                        self.cancel_order(order_to_select[1][0],
                                          order_to_select[1][1],
                                          order_to_select[1][4], 'buy')
                        orders_to_remove['buy'].append(i - 1)

        # Unwanted sell orders for the strategy handler
        for i, order in enumerate(open_orders['sell']):
            if order[1] in self.intervals:
                if not self.params['spread_top'] <= order[1] <= highest_sell:
                    self.cancel_order(order[0], order[1], order[4], 'sell')
                    orders_to_remove['sell'].append(i)
                    continue
                if order[2] != self.params['amount']:
                    if not self.is_testing:
                        if self.simple_question(f'{order} {q2}'):
                            self.cancel_order(order[0], order[1], order[4], 'sell')
                            orders_to_remove['sell'].append(i)
                            continue
            else:
                if not self.is_testing:
                    if self.simple_question(f'{q} {order}'):
                        self.cancel_order(order[0], order[1], order[4], 'sell')
                orders_to_remove['sell'].append(i)
                continue

            if i > 0:
                if order[1] == open_orders['sell'][i - 1][1] \
                        and i - 1 not in orders_to_remove['sell']:
                    order_to_select = [order, open_orders['sell'][i - 1]]
                    if self.is_testing:
                        rsp = 1
                    else:
                        rsp = int(self.ask_to_select_in_a_list(q3, order_to_select))
                    if rsp == 1:
                        self.cancel_order(order[0], order[1], order[4], 'sell')
                        orders_to_remove['sell'].append(i)
                    else:
                        self.cancel_order(open_orders['sell'][i - 1][0],
                                          open_orders['sell'][i - 1][1],
                                          open_orders['sell'][i - 1][4], 'sell')
                        orders_to_remove['sell'].append(i - 1)

        if orders_to_remove['buy']:
            for i, index in enumerate(orders_to_remove['buy']):
                del open_orders['buy'][index - i]
        if orders_to_remove['sell']:
            for i, index in enumerate(orders_to_remove['sell']):
                del open_orders['sell'][index - i]

        if open_orders['buy']:
            for order in open_orders['buy']:
                remaining_orders_price['buy'].append(order[1])
        if open_orders['sell']:
            for order in open_orders['sell']:
                remaining_orders_price['sell'].append(order[1])

        self.stratlog.debug(
            f'orders_to_remove: {orders_to_remove}, open_orders: {open_orders}'
            f', remaining_orders_price: {remaining_orders_price}')
        return self.set_first_orders(remaining_orders_price, open_orders)

    def set_first_orders(self, remaining_orders_price, open_orders):
        """Open orders for the strategy.
        remaining_orders_price: dict.
        open_orders: dict.
        return: dict, of open orders used for the strategy."""
        self.stratlog.debug('set_first_orders()')
        buy_target = self.intervals.index(self.params['spread_bot'])
        lowest_sell_index = buy_target + 1
        new_orders = {'sell': [], 'buy': []}

        if self.params['nb_buy_to_display'] == 0:
            self.params['nb_buy_to_display'] = self.max_sell_index
        if self.params['nb_sell_to_display'] == 0:
            self.params['nb_sell_to_display'] = self.max_sell_index

        # At which index do we need to stop to add orders
        if buy_target - self.params['nb_buy_to_display'] > 1:
            lowest_buy_index = buy_target - self.params['nb_buy_to_display'] + 1
        else:
            lowest_buy_index = 1
        if lowest_sell_index + self.params['nb_sell_to_display'] \
                < len(self.intervals) - 2:
            sell_target = lowest_sell_index + self.params['nb_sell_to_display'] - 1
        else:
            sell_target = len(self.intervals) - 2

        self.stratlog.debug(
            f'buy target: {buy_target}, lowest_buy_index: '
            f'{lowest_buy_index}, lowest_sell_index: {lowest_sell_index}, '
            f'sell_target: {sell_target}, max_sell_index: '
            f'{self.max_sell_index}')

        # Open an order if needed or move an already existing open order. From
        # the lowest price to the highest price
        while lowest_buy_index <= buy_target:
            if self.intervals[lowest_buy_index] \
                    not in remaining_orders_price['buy']:
                order = self.init_limit_buy_order(self.selected_market,
                                                  self.params['amount'],
                                                  self.intervals[lowest_buy_index])
                new_orders['buy'].append(order)
                sleep(0.2)
            else:
                for i, item in enumerate(open_orders['buy']):
                    if item[1] == self.intervals[lowest_buy_index]:
                        new_orders['buy'].append(item)
                        del open_orders['buy'][i]
                        break
            lowest_buy_index += 1

        # Now sell side
        while lowest_sell_index <= sell_target:
            if self.intervals[lowest_sell_index] \
                    not in remaining_orders_price['sell']:
                order = self.init_limit_sell_order(self.selected_market,
                                                   self.params['amount'], self.intervals[lowest_sell_index])
                new_orders['sell'].append(order)
            else:
                for i, item in enumerate(open_orders['sell']):
                    if item[1] == self.intervals[lowest_sell_index]:
                        new_orders['sell'].append(item)
                        del open_orders['sell'][i]
                        break
            lowest_sell_index += 1

        self.stratlog.debug(f'new_orders: {new_orders}')
        return new_orders

    def remove_safety_order(self, open_orders):
        """Fill empty open_orders[side] when the top/bot of the range have been
        reached at a previous cycle.
        Compare orders ID to Cancel a full compare cycle when it's possible.
        Otherwise it remove safety orders.
        open_orders: dict.
        local: boolean, optional, when you want to also remove safety orders
            from self.open_orders set it as True
        return: dict.
        """
        self.applog.debug(f'remove_safety_order()')

        # To not to a complete cycle when we reach range top or bot at a previous cycle
        if self.open_orders['buy']:
            if not open_orders['buy'] and not self.open_orders['buy'][-1][2]:
                open_orders['buy'].append(self.create_fake_buy())
        if self.open_orders['sell']:
            if not open_orders['sell'] and not self.open_orders['sell'][0][2]:
                open_orders['sell'].append(self.create_fake_sell())
        if open_orders['buy'] and open_orders['sell']:
            if self.open_orders['buy'] and self.open_orders['sell']:
                if open_orders['buy'][-1][0] == self.open_orders['buy'][-1][0] \
                    and open_orders['sell'][0][0] == self.open_orders['sell'][0][0]:
                    return
        
        if open_orders['buy']:
            if open_orders['buy'][0][0] == self.id_list[0]:
                # The safety order can be a fake order
                if open_orders['buy'][0][2]:
                    self.cancel_order(open_orders['buy'][0][0],
                                      open_orders['buy'][0][1],
                                      open_orders['buy'][0][4],
                                      'buy')
                self.stratlog.debug(
                    f"delete open_orders['buy'][0]: "
                    f"{open_orders['buy'][0]}")
                del open_orders['buy'][0]

        if open_orders['sell']:
            if open_orders['sell'][-1][0] == self.id_list[-1]:
                if open_orders['sell'][-1][2]:
                    self.cancel_order(open_orders['sell'][-1][0],
                                      open_orders['sell'][-1][1],
                                      open_orders['sell'][-1][4],
                                      'sell')
                self.stratlog.debug(
                    f"delete open_orders['sell'][-1]: "
                    f"{open_orders['sell'][-1]}")
                del open_orders['sell'][-1]

        if self.open_orders['buy'][0][0] == self.id_list[0]:
            del self.open_orders['buy'][0]
            self.id_list[0] = None
        if self.open_orders['sell'][-1][0] == self.id_list[-1]:
            del self.open_orders['sell'][-1]
            self.id_list[-1] = None
        if self.open_orders['buy']:
            self.stratlog.debug(
                f"self.open_orders['buy'][0]: "
                f"{self.open_orders['buy'][0]}")
        if self.open_orders['sell']:
            self.stratlog.debug(
                f"self.open_orders['sell'][-1]: "
                f"{self.open_orders['sell'][-1]}")
        return open_orders

    def set_safety_orders(self, lowest_buy_index, highest_sell_index):
        """Add safety orders to lock funds for the strategy.
        lowest_buy_index: int.
        highest_sell_index: int."""
        self.stratlog.debug(
            f'set_safety_orders(), lowest_buy_index: {lowest_buy_index}, '
            f'highest_sell_index: {highest_sell_index}')

        if lowest_buy_index > 1:
            buy_sum = Decimal('0')
            self.stratlog.debug(f'lowest_buy_index: {lowest_buy_index}')
            while lowest_buy_index > 0:
                buy_sum += self.multiplier(self.params['amount'],
                                           self.intervals[lowest_buy_index]) / self.safety_buy_value
                lowest_buy_index -= 1
            self.stratlog.debug(
                f'buy_sum: {buy_sum}, lowest_buy_index: {lowest_buy_index}')
            self.open_orders['buy'].insert(0, self.init_limit_buy_order(
                self.selected_market, buy_sum, f'{self.intervals[0]:8f}'))
        else:
            if self.open_orders['buy'][0][1] != self.safety_buy_value:
                self.open_orders['buy'].insert(0, self.create_fake_buy())

        if highest_sell_index < self.max_sell_index + 1:
            sell_sum = Decimal('0')
            self.stratlog.debug(f'highest_sell_index: {highest_sell_index}')
            while highest_sell_index < self.max_sell_index:
                sell_sum += self.params['amount']
                highest_sell_index += 1
            self.stratlog.debug(
                f'sell_sum: {sell_sum}, highest_sell_index: '
                f'{highest_sell_index}, self.max_sell_index: '
                f'{self.max_sell_index}')
            self.open_orders['sell'].append(self.init_limit_sell_order(
                self.selected_market, sell_sum, self.intervals[-1]))
        else:
            if self.open_orders['sell'][-1][1] != self.safety_sell_value:
                self.open_orders['sell'].append(self.create_fake_sell())

        self.stratlog.debug(
            f'safety buy: {self.open_orders["buy"][0]} , '
            f'safety sell: {self.open_orders["sell"][-1]}')
        return

    def create_fake_buy(self):
        """Create a fake buy order.
        return: list"""
        return ['FB', self.safety_buy_value, None, None, self.timestamp_formater(), \
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')]

    def create_fake_sell(self):
        """Create a fake sell order.
        return: list"""
        return ['FS', self.safety_sell_value, None, None, self.timestamp_formater(), \
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')]

    def remove_orders_off_strat(self, new_open_orders):
        """Remove all orders that are not included in the strategy
        new_open_orders: dict, every open orders on the market
        return: dict, open orders wich are included in the strategy"""
        self.stratlog.debug(
            f'remove_orders_off_strat(), new_open_orders: {new_open_orders}')
        orders_to_remove = {'sell': [], 'buy': []}

        if new_open_orders['buy']:
            for i, order in enumerate(new_open_orders['buy']):
                if order[0] not in self.id_list:
                    orders_to_remove['buy'].append(i)

        if new_open_orders['sell']:
            for i, order in enumerate(new_open_orders['sell']):
                if order[0] not in self.id_list:
                    orders_to_remove['sell'].append(i)

        if orders_to_remove['buy']:
            for i, index in enumerate(orders_to_remove['buy']):
                del new_open_orders['buy'][index - i]

        if orders_to_remove['sell']:
            for i, index in enumerate(orders_to_remove['sell']):
                del new_open_orders['sell'][index - i]

        self.stratlog.debug(f'orders_to_remove: {orders_to_remove}')
        return new_open_orders

    def check_if_no_orders(self, new_open_orders):
        """Open orders when there is none on the market.
        return: dict"""
        self.stratlog.debug('check_if_no_orders()')

        # compare_orders() will fail without any open orders
        if not new_open_orders['buy']:
            self.stratlog.debug("no new_open_orders['buy']")
            if len(self.open_orders['buy']) > 0:
                target = self.intervals.index(
                    self.open_orders['buy'][0][1]) - 1
            else:
                target = 0

            # When the bottom of the range is reached
            if target < 1:
                if self.params['stop_at_bot']:
                    self.stratlog.critical(
                        f'Bottom target reached! target: {target}')
                    self.cancel_all(self.remove_safety_order(
                        self.remove_orders_off_strat(
                            self.get_orders(self.selected_market))))
                    self.exit()
                else:
                    order = self.create_fake_buy()
                    new_open_orders['buy'].insert(0, order)
                    self.open_orders['buy'].insert(0, order)
            else:
                # Or create the right number of new orders
                if target - self.params['nb_buy_to_display'] + 1 >= 1:
                    start_index = target - self.params['nb_buy_to_display'] + 1
                else:
                    start_index = 1

                orders = self.set_several_buy(start_index, target)
                for i, order in enumerate(orders):
                    new_open_orders['buy'].insert(i, order)
                    self.open_orders['buy'].insert(i, order)
            self.stratlog.debug(
                f'updated new_buy_orders: {new_open_orders["buy"]}')
            self.update_id_list()

        if not new_open_orders['sell']:
            self.stratlog.debug("no new_open_orders['sell']")
            if len(self.open_orders['sell']) > 0:
                start_index = self.intervals.index(
                    self.open_orders['sell'][-1][1]) + 1
            else:
                start_index = self.max_sell_index

            if start_index > self.max_sell_index:
                if self.params['stop_at_top']:
                    self.stratlog.critical(
                        f'Top target reached! start_index: {start_index}, '
                        f'self.max_sell_index: {self.max_sell_index}')
                    self.cancel_all(self.remove_safety_order(
                        self.remove_orders_off_strat(self.get_orders(
                            self.selected_market))))
                    self.exit()
                else:
                    order = self.create_fake_sell()
                    new_open_orders['sell'].append(order)
                    self.open_orders['sell'].append(order)
            else:
                if start_index + self.params['nb_sell_to_display'] - 1 \
                        <= self.max_sell_index:
                    target = start_index + self.params['nb_sell_to_display'] - 1
                else:
                    target = self.max_sell_index

                orders = self.set_several_sell(start_index, target)
                for order in orders:
                    new_open_orders['sell'].append(order)
                    self.open_orders['sell'].append(order)
            self.stratlog.debug(
                f'updated new_sell_orders: {new_open_orders["sell"]}')
            self.update_id_list()
        return new_open_orders

    def compare_orders(self, new_open_orders):
        """Compare between open order know by LW and buy order from the
        marketplace.
        """
        missing_orders = deepcopy(self.open_orders)
        executed_orders = {'sell': [], 'buy': []}
        self.applog.debug('compare_orders()')
        for order in self.open_orders['buy']:
            rsp = any(new_order[0] == order[0] for new_order in new_open_orders['buy'])
            if rsp:
                missing_orders['buy'].remove(order)
        for order in self.open_orders['sell']:
            rsp = any(new_order[0] == order[0] for new_order in new_open_orders['sell'])
            if rsp:
                missing_orders['sell'].remove(order)

        if missing_orders['buy']:
            self.stratlog.info('A buy has occurred')
            start_index = self.id_list.index(new_open_orders['buy'][-1][0]) + 1
            target = start_index + len(missing_orders['buy']) - 1
            self.stratlog.debug(f'start_index: {start_index}, target: {target}')
            executed_orders['sell'] = self.set_several_sell(start_index, target)

        if missing_orders['sell']:
            self.stratlog.info('A sell has occurred')
            target = self.id_list.index(new_open_orders['sell'][0][0]) - 1
            start_index = target - len(missing_orders['sell']) + 1
            self.stratlog.debug(f'start_index: {start_index}, target: {target}')
            executed_orders['buy'] = self.set_several_buy(start_index, target, True)

        self.stratlog.debug(
            f'compare_orders, missing_orders: {missing_orders} '
            f'executed_orders: {executed_orders}')
        """
        if self.last_loop_datetime is not None:
            trade_history = self.trade_history()
            for side in ['buy','sell']:
                for order in missing_orders[side]:
                    if self.is_order_in_list(order_list=trade_history, order=order, validation_key='price'):
                        executed_orders[side].append(order)"""
        self.update_open_orders(missing_orders, executed_orders)

    def is_order_in_list(self, order_list, order, validation_key):
        order_map = {
            'id':0,
            'price':1,
            'amount':2
        }
        validation_value = order[order_map[validation_key]]
        if validation_key in ['price','amount'] and type(validation_value) is not Decimal:
            validation_value = Decimal(str(validation_value))
        for o in order_list:
            if validation_value in ['price','amount']:
                if Decimal(str(o[validation_key])) == validation_value:
                    return True
            elif validation_value == 'id':
                if o[validation_key] == validation_value:
                    return True
            else:
                raise ValueError(f"Unexpected validation key: {validation_key}")
        return False

    def update_open_orders(self, missing_orders, executed_orders):
        """Update self.open_orders with orders missing and executed orders.
        missing_orders: dict, all the missing orders since the last LW cycle.
        executed_order: dict, all the executed orders since the last LW cycle"""
        self.stratlog.debug('update_open_orders()')
        if executed_orders['buy']:
            for order in missing_orders['sell']:
                self.open_orders['sell'].remove(order)
            for order in executed_orders['buy']:
                self.open_orders['buy'].append(order)
            #self.stratlog.debug(
            #    f'self.open_orders buy: {self.open_orders["buy"]}')
        if executed_orders['sell']:
            for order in missing_orders['buy']:
                self.open_orders['buy'].remove(order)
            for i, order in enumerate(executed_orders['sell']):
                self.open_orders['sell'].insert(i, order)
            #self.stratlog.debug(
            #    f'self.open_orders sell: {self.open_orders["sell"]}')
        return

    def limit_nb_orders(self):
        """Cancel open orders if there is too many, open orders if there is 
        not enough of it"""
        new_open_orders = self.remove_orders_off_strat(
            self.orders_price_ordering(self.get_orders(
                self.selected_market)))
        #self.stratlog.debug(
        #    f'Limit nb orders(), new_open_orders: {new_open_orders}')
        # Don't mess up if all buy orders have been filled during the cycle
        if new_open_orders['buy']:
            nb_orders = len(new_open_orders['buy'])
            if new_open_orders['buy'][0][1] == self.safety_buy_value:
                nb_orders -= 1
        else:
            nb_orders = 0
        self.stratlog.debug(
            f'nb_orders: {nb_orders}, params["nb_buy_to_display"]: '
            f"{self.params['nb_buy_to_display']}")
        # When there is too much buy orders on the order book
        if nb_orders > self.params['nb_buy_to_display']:
            self.stratlog.debug(f'nb_orders > params["nb_buy_to_display"]')
            # Care of the fake order
            if not self.open_orders['buy'][0][0]:
                del self.open_orders['buy'][0]
            nb_orders -= self.params['nb_buy_to_display']
            while nb_orders > 0:
                self.cancel_order(new_open_orders['buy'][0][0],
                                  new_open_orders['buy'][0][1], new_open_orders['buy'][0][4],
                                  'buy')
                del new_open_orders['buy'][0]
                del self.open_orders['buy'][0]
                nb_orders -= 1
        # When there is not enough buy order in the order book
        elif nb_orders < self.params['nb_buy_to_display']:
            # Ignore if the bottom of the range is reached. It's value is None
            if self.open_orders['buy'][0][2]:
                self.stratlog.debug(
                    f"{self.open_orders['buy'][0][1]} > {self.intervals[1]}")
                # Set the range of buy orders to create
                target = self.intervals.index(self.open_orders['buy'][0][1]) - 1
                start_index = target - self.params['nb_buy_to_display'] \
                              + len(self.open_orders['buy']) + 1
                if start_index <= 1:
                    start_index = 1
                self.stratlog.debug(f'start_index: {start_index}, target: {target}')
                orders = self.set_several_buy(start_index, target)
                for i, order in enumerate(orders):
                    self.open_orders['buy'].insert(i, order)
        # Don't mess up if all sell orders have been filled during the cycle
        if new_open_orders['sell']:
            nb_orders = len(new_open_orders['sell'])
            if new_open_orders['sell'][-1][1] == self.safety_sell_value:
                nb_orders -= 1
        else:
            nb_orders = 0
        self.stratlog.debug(
            f'nb_orders: {nb_orders}; params["nb_sell_to_display"]: '
            f"{self.params['nb_sell_to_display']}")
        # When there is too much sell orders on the order book
        if nb_orders > self.params['nb_sell_to_display']:
            # Care of fake order
            if not self.open_orders['sell'][-1][0]:
                del self.open_orders['sell'][-1]
            nb_orders -= self.params['nb_sell_to_display']
            self.stratlog.debug(f'nb_orders to delete: {nb_orders}')
            while nb_orders > 0:
                self.cancel_order(new_open_orders['sell'][-1][0],
                                  new_open_orders['sell'][-1][1],
                                  new_open_orders['sell'][-1][4],
                                  'sell')
                del new_open_orders['sell'][-1]
                del self.open_orders['sell'][-1]
                nb_orders -= 1
        # When there is not enough sell order in the order book
        elif nb_orders < self.params['nb_sell_to_display']:
            # Ignore if the top of the range is reached
            if self.open_orders['sell'][-1][0]:
                # Set the range of sell orders to create
                start_index = self.intervals.index(
                    self.open_orders['sell'][-1][1]) + 1
                target = start_index + self.params['nb_sell_to_display'] \
                         - len(self.open_orders['sell']) - 1
                if target > len(self.intervals) - 2:
                    target = len(self.intervals) - 2
                self.stratlog.debug(f'start_index: {start_index}, target: {target}')
                if target > self.max_sell_index:
                    target = self.max_sell_index
                orders = self.set_several_sell(start_index, target)
                for order in orders:
                    self.open_orders['sell'].append(order)
        self.stratlog.debug(f'self.open_orders: {self.open_orders}')
        return

    def exit(self):
        """Clean program exit"""
        self.applog.critical("End the program")
        sys.exit(0)

    def lw_initialisation(self):
        """Initializing parameters, check parameters then initialize LW.
        """
        # marketplace_name = self.select_marketplace()
        # self.selected_market = self.select_market()
        if self.is_testing:
            params = self.params_reader(f'{self.root_path}params.txt')
            self.params = self.check_for_enough_funds(params)
        else:
            self.ask_for_params()
        open_orders = self.remove_safety_before_init(self.orders_price_ordering(
                                                     self.get_orders(
                                                        self.selected_market)))
        self.open_orders = self.strat_init(open_orders)
        self.set_safety_orders(self.intervals.index(self.open_orders['buy'][0][1]),
                               self.intervals.index(self.open_orders['sell'][-1][1]))
        self.set_id_list_according_intervals()
        self.update_id_list()
        self.main_loop()

    def main_loop(self):
        """Do the lazy whale strategy.
        Simple execution loop.
        """
        while True:
            self.applog.debug('CYCLE START')
            orders = self.remove_safety_order(self.remove_orders_off_strat(
                self.orders_price_ordering(self.get_orders(
                    self.selected_market))))  # for comparing by Id
            if orders:
                orders = self.check_if_no_orders(orders)
                self.compare_orders(orders)
                self.update_id_list()
                self.limit_nb_orders()
                self.set_safety_orders(self.intervals.index(
                                            self.open_orders['buy'][0][1]),
                                       self.intervals.index(
                                            self.open_orders['sell'][-1][1]))
                self.update_id_list()
            self.applog.debug('CYCLE STOP')
            self.last_loop_datetime = datetime.now().timestamp()
            sleep(5)

    def main(self):
        self.applog.info("Program starting!")
        self.lw_initialisation()
        self.exit()



if __name__ == "__main__":
    LazyStarter = LazyStarter(is_testing=False)
    LazyStarter.main()