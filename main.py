import os, sys
import logging
import json
from decimal import Decimal
from datetime import datetime
from operator import itemgetter
from copy import deepcopy
from pathlib import Path
from copy import deepcopy
from time import sleep
import ccxt
import static_config
from utils.singleton import singleton
from utils.helper import UtilsMixin
from exchange_manager.api_manager import APIManager



@singleton
class BotConfiguration(UtilsMixin):

    def create_config(self, bot_obj, params={}, keys=(), test_mode=False):
        from logger.logger import Logger
        from logger.slack import Slack
        self.bot_obj = bot_obj
        self.test_mode = test_mode
        self.test_params = params
        self.test_keys = keys
        # Without assigning it first, it always return true
        self.script_position = os.path.dirname(sys.argv[0])
        self.root_path = f'{self.script_position}/' if self.script_position else ''
        self.keys_file = f'{self.root_path}/{static_config.KEYS_FILE}'
        self.stratlog = Logger(name='stratlogs',
                               log_file='strat.log',
                               log_formatter='%(message)s',
                               console_level=logging.DEBUG,
                               file_level=logging.INFO,
                               root_path=self.root_path+"logger/").create()
        self.applog = Logger(name='debugs',
                             log_file='app.log',
                             log_formatter='%(asctime)s - %(levelname)s - %(message)s',
                             console_level=logging.DEBUG,
                             file_level=logging.DEBUG,
                             root_path=self.root_path+"logger/").create()
        self.user_market_name_list = []
        self.exchanges_list = self._exchanges_list_init()
        self.keys = self._keys_initialisation(self.keys_file)
        self.slack = None
        self.slack = Slack(self.keys['webhook_url'])
        self.exchange = None
        self.fees_coef = Decimal(static_config.FEES_COEF)  # TODO: could be different for other exchanges?
        self.user_balance = {}
        self.selected_market = None
        self.open_orders = {'sell': [], 'buy': []}
        self.params = {}
        self.intervals = []
        self.id_list = []
        self.err_counter = 0
        self.now = 0
        self.safety_buy_value = Decimal(static_config.SAFETY_BUY_VALUE)
        self.safety_sell_value = Decimal(static_config.SAFETY_SELL_VALUE)
        self.max_sell_index = None
        self.is_kraken = False
        self.last_loop_datetime = None

    def get_config(self):
        return self

    def _exchanges_list_init(self):
        """Little hack to add zebitex to ccxt exchange list.
        return: list, list of exchanges."""
        exchanges_list = ccxt.exchanges
        return exchanges_list + ['zebitex', 'zebitex_testnet']

    def _keys_initialisation(self, keys_file, ):  # Need to be refactored
        """Check if a key.txt file exist and create one if none.
        return: dict, with all api keys found.
        """
        if not os.path.isfile(keys_file):
            Path(keys_file).touch()
            self.applog.critical(
                f'No file was found, an empty one has been created, '
                f'please fill it as indicated in the documentation')
            self.exit()
        else:
            keys = self._keys_file_reader(keys_file)
            if not keys:
                self.applog.critical(
                    f'Your key.txt file is empty, please '
                    f'fill it as indicated to the documentation')
                self.exit()
            else:
                return keys

    def _keys_file_reader(self, keys_file):  # Need to be refactored
        """Check the consistence of datas in key.txt.
        return: dict, api keys
        """
        name_list = deepcopy(self.exchanges_list)
        keys = {}
        with open(self.keys_file, mode='r', encoding='utf-8') as keys_file:
            for line in keys_file:
                line = line.replace('\n', '')
                line = line.replace("'", '"')
                try:
                    key = json.loads(line)
                    for k in key.keys():
                        if k in self.user_market_name_list:
                            raise KeyError(
                                f'You already have a key for this '
                                f'marketplace, please RTFM')
                        else:
                            self.user_market_name_list.append(k)
                        if k not in name_list:
                            raise NameError('The marketplace name is invalid!')
                except Exception as e:
                    self.applog.critical(f'Something went wrong : {e}')
                    self.exit()
                keys.update(key)
        return keys



@singleton
class Bot(UtilsMixin):
    def __init__(self, params={}, keys=(), test_mode=False):
        self.config = BotConfiguration()
        self.config.create_config(params, keys, test_mode)
        from strategy import Strategy
        from user_interface import UserInterface
        self.user_interface = UserInterface(self, self.config)
        self.strategy = Strategy()
        self.api = APIManager(self.config)

    def launch(self):
        self.set_params()
        self.place_init_orders()
        self.main_loop()

    def set_params(self):
        if self.config.test_mode:
            params = self.user_interface.check_params(self.config.test_params)
            self.config.params = self.check_for_enough_funds(params)
        else:
            self.user_interface.ask_for_params()   #check_for_enough_funds called inside

    def place_init_orders(self):
        """
        - delete priv orders
        - create new orders according config
        - create safety orders
        - update list of order ids
        """
        open_orders = self.remove_safety_before_init(self.orders_price_ordering(
            self.get_orders(
                self.config.selected_market)))
        self.config.open_orders = self.strat_init(open_orders)
        self.set_safety_orders(self.config.intervals.index(self.config.open_orders['buy'][0][1]),
                               self.config.intervals.index(self.config.open_orders['sell'][-1][1]))
        self.set_id_list_according_intervals()
        self.update_id_list()

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
            price = self.api.get_market_last_price(self.config.selected_market)
            self.api.get_balances()
            pair = self.config.selected_market.split('/')
            sell_balance = self.str_to_decimal(self.config.user_balance[pair[0]]['free'])
            buy_balance = self.str_to_decimal(self.config.user_balance[pair[1]]['free'])
            spread_bot_index = self.config.intervals.index(params['spread_bot'])
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
                self.config.applog.debug(msg)
                # When the strategy will start with spread bot inferior or
                # equal to the actual market price
                if params['spread_bot'] <= price:
                    incoming_buy_funds = Decimal('0')
                    i = spread_top_index
                    # When the whole strategy is lower than actual price
                    if params['range_top'] < price:
                        while i < len(self.config.intervals):
                            incoming_buy_funds += self.multiplier(
                                self.config.intervals[i], params['amount'],
                                self.config.fees_coef)
                            i += 1
                    # When only few sell orders are planned to be under the
                    # actual price
                    else:
                        while self.config.intervals[i] <= price:
                            incoming_buy_funds += self.multiplier(
                                self.config.intervals[i], params['amount'],
                                self.config.fees_coef)
                            i += 1
                            # It crash when price >= range_top
                            if i == len(self.config.intervals):
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
                                params['amount'], self.config.fees_coef)
                            i -= 1
                    # When only few buy orders are planned to be upper the
                    # actual price
                    else:
                        while self.intervals[i] >= price:
                            incoming_sell_funds += self.multiplier(
                                params['amount'], self.config.fees_coef)
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
                self.config.applog.debug(msg)
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
                self.config.stratlog.warning('%s\nYou need to change some parameters:', e)
                params = self.user_interface.change_params(params)
        return params


    """
    ############################## FINALLY, LW ################################
    """

    def remove_safety_before_init(self, open_orders):
        """Remove safety orders before strat init if there is some.
        open_orders: dict.
        return: dict."""
        if open_orders['buy']:
            if open_orders['buy'][0][1] == self.config.safety_buy_value:
                self.api.cancel_order(open_orders['buy'][0][0],
                                  open_orders['buy'][0][1],
                                  open_orders['buy'][0][4],
                                  'buy')
                del open_orders['buy'][0]
        if open_orders['sell']:
            if open_orders['sell'][-1][1] == self.config.safety_sell_value:
                self.api.cancel_order(open_orders['sell'][-1][0],
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
        self.config.stratlog.debug('strat_init()')
        # Add funds locker value in intervals
        self.config.intervals = [self.config.safety_buy_value] + self.config.intervals + \
                         [self.config.safety_sell_value]
        self.config.max_sell_index = len(self.config.intervals) - 2
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

        if self.config.intervals.index(self.config.params['spread_bot']) \
                - self.config.params['nb_buy_to_display'] + 1 > 1 \
                and self.config.params['nb_buy_to_display'] != 0:
            lowest_buy = self.config.intervals[self.config.intervals.index(
                self.config.params['spread_bot']) - self.config.params['nb_buy_to_display'] + 1]
        else:
            lowest_buy = self.config.intervals[1]

        if self.config.intervals.index(self.config.params['spread_top']) \
                + self.config.params['nb_sell_to_display'] - 1 < self.config.max_sell_index \
                and self.config.params['nb_sell_to_display'] != 0:
            highest_sell = self.config.intervals[self.config.intervals.index(
                self.config.params['spread_top']) + self.config.params['nb_sell_to_display'] - 1]
        else:
            highest_sell = self.config.intervals[self.config.max_sell_index]
        self.config.stratlog.debug(
            f'self.intervals: {self.config.intervals}, open_orders: {open_orders}, '
            f'self.max_sell_index: {self.config.max_sell_index}, '
            f'lowest_buy: {lowest_buy}, self.params["spread_bot"]: '
            f"{self.config.params['spread_bot']}, self.params['spread_top']: "
            f"{self.config.params['spread_top']}, highest_sell: {highest_sell}")

        # Unwanted buy orders for the strategy handler
        for i, order in enumerate(open_orders['buy']):
            if order[1] in self.config.intervals:
                if not lowest_buy <= order[1] <= self.config.params['spread_bot']:
                    self.api.cancel_order(order[0], order[1], order[4], 'buy')
                    orders_to_remove['buy'].append(i)
                    continue
                if order[2] != self.config.params['amount']:
                    if not self.config.test_mode:
                        if self.user_interface.simple_question(f'{order} {q2}'):
                            self.api.cancel_order(order[0], order[1], order[4], 'buy')
                            orders_to_remove['buy'].append(i)
                            continue
            else:
                if not self.config.test_mode:
                    if self.user_interface.simple_question(f'{q} {order}'):
                        self.api.cancel_order(order[0], order[1], order[4], 'buy')
                orders_to_remove['buy'].append(i)
                continue

            # Two order of the same price could crash the bot
            if i > 0:
                if order[1] == open_orders['buy'][i - 1][1] \
                        and i - 1 not in orders_to_remove['buy']:
                    order_to_select = [order, open_orders['buy'][i - 1]]
                    if self.config.test_mode:
                        rsp = 1
                    else:
                        rsp = int(self.user_interface.ask_to_select_in_a_list(q3, order_to_select))
                    if rsp == 1:
                        self.api.cancel_order(order[0], order[1], order[4], 'buy')
                        orders_to_remove['buy'].append(i)
                    else:
                        self.api.cancel_order(order_to_select[1][0],
                                          order_to_select[1][1],
                                          order_to_select[1][4], 'buy')
                        orders_to_remove['buy'].append(i - 1)

        # Unwanted sell orders for the strategy handler
        for i, order in enumerate(open_orders['sell']):
            if order[1] in self.config.intervals:
                if not self.config.params['spread_top'] <= order[1] <= highest_sell:
                    self.api.cancel_order(order[0], order[1], order[4], 'sell')
                    orders_to_remove['sell'].append(i)
                    continue
                if order[2] != self.config.params['amount']:
                    if not self.test_mode:
                        if self.user_interface.simple_question(f'{order} {q2}'):
                            self.api.cancel_order(order[0], order[1], order[4], 'sell')
                            orders_to_remove['sell'].append(i)
                            continue
            else:
                if not self.test_mode:
                    if self.user_interface.simple_question(f'{q} {order}'):
                        self.api.cancel_order(order[0], order[1], order[4], 'sell')
                orders_to_remove['sell'].append(i)
                continue

            if i > 0:
                if order[1] == open_orders['sell'][i - 1][1] \
                        and i - 1 not in orders_to_remove['sell']:
                    order_to_select = [order, open_orders['sell'][i - 1]]
                    if self.test_mode:
                        rsp = 1
                    else:
                        rsp = int(self.user_interface.ask_to_select_in_a_list(q3, order_to_select))
                    if rsp == 1:
                        self.api.cancel_order(order[0], order[1], order[4], 'sell')
                        orders_to_remove['sell'].append(i)
                    else:
                        self.api.cancel_order(open_orders['sell'][i - 1][0],
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

        self.config.stratlog.debug(
            f'orders_to_remove: {orders_to_remove}, open_orders: {open_orders}'
            f', remaining_orders_price: {remaining_orders_price}')
        return self.set_first_orders(remaining_orders_price, open_orders)

    def set_first_orders(self, remaining_orders_price, open_orders):
        """Open orders for the strategy.
        remaining_orders_price: dict.
        open_orders: dict.
        return: dict, of open orders used for the strategy."""
        self.config.stratlog.debug('set_first_orders()')
        buy_target = self.config.intervals.index(self.config.params['spread_bot'])
        lowest_sell_index = buy_target + 1
        new_orders = {'sell': [], 'buy': []}

        if self.config.params['nb_buy_to_display'] == 0:
            self.config.params['nb_buy_to_display'] = self.config.max_sell_index
        if self.config.params['nb_sell_to_display'] == 0:
            self.config.params['nb_sell_to_display'] = self.config.max_sell_index

        # At which index do we need to stop to add orders
        if buy_target - self.config.params['nb_buy_to_display'] > 1:
            lowest_buy_index = buy_target - self.config.params['nb_buy_to_display'] + 1
        else:
            lowest_buy_index = 1
        if lowest_sell_index + self.config.params['nb_sell_to_display'] \
                < len(self.config.intervals) - 2:
            sell_target = lowest_sell_index + self.config.params['nb_sell_to_display'] - 1
        else:
            sell_target = len(self.config.intervals) - 2

        self.config.stratlog.debug(
            f'buy target: {buy_target}, lowest_buy_index: '
            f'{lowest_buy_index}, lowest_sell_index: {lowest_sell_index}, '
            f'sell_target: {sell_target}, max_sell_index: '
            f'{self.config.max_sell_index}')

        # Open an order if needed or move an already existing open order. From
        # the lowest price to the highest price
        while lowest_buy_index <= buy_target:
            if self.config.intervals[lowest_buy_index] \
                    not in remaining_orders_price['buy']:
                order = self.api.init_limit_buy_order(self.config.selected_market,
                                                  self.config.params['amount'],
                                                  self.config.intervals[lowest_buy_index])
                new_orders['buy'].append(order)
                sleep(0.2)
            else:
                for i, item in enumerate(open_orders['buy']):
                    if item[1] == self.config.intervals[lowest_buy_index]:
                        new_orders['buy'].append(item)
                        del open_orders['buy'][i]
                        break
            lowest_buy_index += 1

        # Now sell side
        while lowest_sell_index <= sell_target:
            if self.config.intervals[lowest_sell_index] \
                    not in remaining_orders_price['sell']:
                order = self.api.init_limit_sell_order(self.config.selected_market,
                                                   self.config.params['amount'], self.config.intervals[lowest_sell_index])
                new_orders['sell'].append(order)
            else:
                for i, item in enumerate(open_orders['sell']):
                    if item[1] == self.config.intervals[lowest_sell_index]:
                        new_orders['sell'].append(item)
                        del open_orders['sell'][i]
                        break
            lowest_sell_index += 1

        self.config.stratlog.debug(f'new_orders: {new_orders}')
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
        self.config.applog.debug(f'remove_safety_order()')

        # To not to a complete cycle when we reach range top or bot at a previous cycle
        if self.config.open_orders['buy']:
            if not open_orders['buy'] and not self.config.open_orders['buy'][-1][2]:
                open_orders['buy'].append(self.create_fake_buy())
        if self.config.open_orders['sell']:
            if not open_orders['sell'] and not self.config.open_orders['sell'][0][2]:
                open_orders['sell'].append(self.create_fake_sell())
        if open_orders['buy'] and open_orders['sell']:
            if self.config.open_orders['buy'] and self.config.open_orders['sell']:
                if open_orders['buy'][-1][0] == self.config.open_orders['buy'][-1][0] \
                        and open_orders['sell'][0][0] == self.config.open_orders['sell'][0][0]:
                    return

        if open_orders['buy']:
            if open_orders['buy'][0][0] == self.config.id_list[0]:
                # The safety order can be a fake order
                if open_orders['buy'][0][2]:
                    self.api.cancel_order(open_orders['buy'][0][0],
                                      open_orders['buy'][0][1],
                                      open_orders['buy'][0][4],
                                      'buy')
                self.config.stratlog.debug(
                    f"delete open_orders['buy'][0]: "
                    f"{open_orders['buy'][0]}")
                del open_orders['buy'][0]

        if open_orders['sell']:
            if open_orders['sell'][-1][0] == self.config.id_list[-1]:
                if open_orders['sell'][-1][2]:
                    self.api.cancel_order(open_orders['sell'][-1][0],
                                      open_orders['sell'][-1][1],
                                      open_orders['sell'][-1][4],
                                      'sell')
                self.config.stratlog.debug(
                    f"delete open_orders['sell'][-1]: "
                    f"{open_orders['sell'][-1]}")
                del open_orders['sell'][-1]

        if self.config.open_orders['buy'][0][0] == self.config.id_list[0]:
            del self.config.open_orders['buy'][0]
            self.config.id_list[0] = None
        if self.config.open_orders['sell'][-1][0] == self.config.id_list[-1]:
            del self.config.open_orders['sell'][-1]
            self.config.id_list[-1] = None
        if self.config.open_orders['buy']:
            self.config.stratlog.debug(
                f"self.config.open_orders['buy'][0]: "
                f"{self.config.open_orders['buy'][0]}")
        if self.config.open_orders['sell']:
            self.config.stratlog.debug(
                f"self.config.open_orders['sell'][-1]: "
                f"{self.config.open_orders['sell'][-1]}")
        return open_orders

    def set_safety_orders(self, lowest_buy_index, highest_sell_index):
        """Add safety orders to lock funds for the strategy.
        lowest_buy_index: int.
        highest_sell_index: int."""
        self.config.stratlog.debug(
            f'set_safety_orders(), lowest_buy_index: {lowest_buy_index}, '
            f'highest_sell_index: {highest_sell_index}')

        if lowest_buy_index > 1:
            buy_sum = Decimal('0')
            self.config.stratlog.debug(f'lowest_buy_index: {lowest_buy_index}')
            while lowest_buy_index > 0:
                buy_sum += self.multiplier(self.config.params['amount'],
                                           self.config.intervals[lowest_buy_index]) / self.config.safety_buy_value
                lowest_buy_index -= 1
            self.config.stratlog.debug(
                f'buy_sum: {buy_sum}, lowest_buy_index: {lowest_buy_index}')
            self.config.open_orders['buy'].insert(0, self.api.init_limit_buy_order(
                self.config.selected_market, buy_sum, f'{self.config.intervals[0]:8f}'))
        else:
            if self.config.open_orders['buy'][0][1] != self.config.safety_buy_value:
                self.config.open_orders['buy'].insert(0, self.create_fake_buy())

        if highest_sell_index < self.config.max_sell_index + 1:
            sell_sum = Decimal('0')
            self.config.stratlog.debug(f'highest_sell_index: {highest_sell_index}')
            while highest_sell_index < self.config.max_sell_index:
                sell_sum += self.config.params['amount']
                highest_sell_index += 1
            self.config.stratlog.debug(
                f'sell_sum: {sell_sum}, highest_sell_index: '
                f'{highest_sell_index}, self.max_sell_index: '
                f'{self.config.max_sell_index}')
            self.config.open_orders['sell'].append(self.api.init_limit_sell_order(
                self.config.selected_market, sell_sum, self.config.intervals[-1]))
        else:
            if self.config.open_orders['sell'][-1][1] != self.config.safety_sell_value:
                self.config.open_orders['sell'].append(self.create_fake_sell())

        self.config.stratlog.debug(
            f'safety buy: {self.config.open_orders["buy"][0]} , '
            f'safety sell: {self.config.open_orders["sell"][-1]}')
        return

    def create_fake_buy(self):
        """Create a fake buy order.
        return: list"""
        return ['FB', self.config.safety_buy_value, None, None, self.timestamp_formater(), \
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')]

    def create_fake_sell(self):
        """Create a fake sell order.
        return: list"""
        return ['FS', self.config.safety_sell_value, None, None, self.timestamp_formater(), \
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')]

    def remove_orders_off_strat(self, new_open_orders):
        """Remove all orders that are not included in the strategy
        new_open_orders: dict, every open orders on the market
        return: dict, open orders wich are included in the strategy"""
        self.config.stratlog.debug(
            f'remove_orders_off_strat(), new_open_orders: {new_open_orders}')
        orders_to_remove = {'sell': [], 'buy': []}

        if new_open_orders['buy']:
            for i, order in enumerate(new_open_orders['buy']):
                if order[0] not in self.config.id_list:
                    orders_to_remove['buy'].append(i)

        if new_open_orders['sell']:
            for i, order in enumerate(new_open_orders['sell']):
                if order[0] not in self.config.id_list:
                    orders_to_remove['sell'].append(i)

        if orders_to_remove['buy']:
            for i, index in enumerate(orders_to_remove['buy']):
                del new_open_orders['buy'][index - i]

        if orders_to_remove['sell']:
            for i, index in enumerate(orders_to_remove['sell']):
                del new_open_orders['sell'][index - i]

        self.config.stratlog.debug(f'orders_to_remove: {orders_to_remove}')
        return new_open_orders

    def check_if_no_orders(self, new_open_orders):
        """Open orders when there is none on the market.
        return: dict"""
        self.config.stratlog.debug('check_if_no_orders()')

        # compare_orders() will fail without any open orders
        if not new_open_orders['buy']:
            self.config.stratlog.debug("no new_open_orders['buy']")
            if len(self.config.open_orders['buy']) > 0:
                target = self.config.intervals.index(
                    self.config.open_orders['buy'][0][1]) - 1
            else:
                target = 0

            # When the bottom of the range is reached
            if target < 1:
                if self.config.params['stop_at_bot']:
                    msg = (f'Bottom target reached! target: {target}')
                    if self.slack:
                        self.slack.send_slack_message(msg)
                    else:
                        self.config.stratlog.critical(msg)

                    self.api.cancel_all(self.remove_safety_order(
                        self.remove_orders_off_strat(
                            self.get_orders(self.selected_market))))
                    self.exit()

                else:
                    order = self.create_fake_buy()
                    new_open_orders['buy'].insert(0, order)
                    self.config.open_orders['buy'].insert(0, order)

            else:
                # Or create the right number of new orders
                msg = 'Buys side is empty'
                if self.slack.channel:
                    self.slack.send_slack_message(msg)
                else:
                    self.config.stratlog.warning(msg)
                if target - self.config.params['nb_buy_to_display'] + 1 >= 1:
                    start_index = target - self.config.params['nb_buy_to_display'] + 1
                else:
                    start_index = 1

                orders = self.api.set_several_buy(start_index, target)
                for i, order in enumerate(orders):
                    new_open_orders['buy'].insert(i, order)
                    self.config.open_orders['buy'].insert(i, order)
            self.config.stratlog.debug(
                f'updated new_buy_orders: {new_open_orders["buy"]}')
            self.update_id_list()

        if not new_open_orders['sell']:
            self.config.stratlog.debug("no new_open_orders['sell']")
            if len(self.config.open_orders['sell']) > 0:
                start_index = self.config.intervals.index(
                    self.config.open_orders['sell'][-1][1]) + 1
            else:
                start_index = self.config.max_sell_index

            if start_index > self.config.max_sell_index:
                if self.config.params['stop_at_top']:
                    msg = (
                        f'Top target reached! start_index: {start_index}, '
                        f'self.max_sell_index: {self.config.max_sell_index}')
                    if self.slack:
                        self.slack.send_slack_message(msg)
                    else:
                        self.stratlog.critical(msg)

                    self.api.cancel_all(self.remove_safety_order(
                        self.remove_orders_off_strat(self.get_orders(
                            self.config.selected_market))))
                    self.exit()

                else:
                    order = self.create_fake_sell()
                    new_open_orders['sell'].append(order)
                    self.config.open_orders['sell'].append(order)

            else:
                msg = 'Buys side is empty'
                if self.slack.channel:
                    self.slack.send_slack_message(msg)
                else:
                    self.config.stratlog.warning(msg)

                if start_index + self.config.params['nb_sell_to_display'] - 1 \
                        <= self.config.max_sell_index:
                    target = start_index + self.config.params['nb_sell_to_display'] - 1
                else:
                    target = self.config.max_sell_index

                orders = self.api.set_several_sell(start_index, target)
                for order in orders:
                    new_open_orders['sell'].append(order)
                    self.config.open_orders['sell'].append(order)
            self.config.stratlog.debug(
                f'updated new_sell_orders: {new_open_orders["sell"]}')
            self.update_id_list()
        return new_open_orders

    def compare_orders(self, new_open_orders):
        """Compare between open order know by LW and buy order from the
        marketplace.
        """
        missing_orders = deepcopy(self.config.open_orders)
        executed_orders = {'sell': [], 'buy': []}
        self.config.applog.debug('compare_orders()')
        for order in self.config.open_orders['buy']:
            rsp = any(new_order[0] == order[0] for new_order in new_open_orders['buy'])
            if rsp:
                missing_orders['buy'].remove(order)
        for order in self.config.open_orders['sell']:
            rsp = any(new_order[0] == order[0] for new_order in new_open_orders['sell'])
            if rsp:
                missing_orders['sell'].remove(order)

        if missing_orders['buy']:
            msg = 'A buy has occurred'
            if self.config.slack:
                self.config.slack.send_slack_message(msg)
            else:
                self.config.stratlog.warning(msg)
            start_index = self.config.id_list.index(new_open_orders['buy'][-1][0]) + 1
            target = start_index + len(missing_orders['buy']) - 1
            self.config.stratlog.debug(f'start_index: {start_index}, target: {target}')
            executed_orders['sell'] = self.api.set_several_sell(start_index, target)

        if missing_orders['sell']:
            msg = 'A sell has occurred'
            if self.slack.channel:
                self.config.slack.send_slack_message(msg)
            else:
                self.config.stratlog.warning(msg)
            target = self.config.id_list.index(new_open_orders['sell'][0][0]) - 1
            start_index = target - len(missing_orders['sell']) + 1
            self.config.stratlog.debug(f'start_index: {start_index}, target: {target}')
            executed_orders['buy'] = self.set_several_buy(start_index, target, True)

        self.config.stratlog.debug(
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
            'id': 0,
            'price': 1,
            'amount': 2
        }
        validation_value = order[order_map[validation_key]]
        if validation_key in ['price', 'amount'] and type(validation_value) is not Decimal:
            validation_value = Decimal(str(validation_value))
        for o in order_list:
            if validation_value in ['price', 'amount']:
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
        self.config.stratlog.debug('update_open_orders()')
        if executed_orders['buy']:
            for order in missing_orders['sell']:
                self.config.open_orders['sell'].remove(order)
            for order in executed_orders['buy']:
                self.config.open_orders['buy'].append(order)
            # self.stratlog.debug(
            #    f'self.open_orders buy: {self.open_orders["buy"]}')
        if executed_orders['sell']:
            for order in missing_orders['buy']:
                self.config.open_orders['buy'].remove(order)
            for i, order in enumerate(executed_orders['sell']):
                self.config.open_orders['sell'].insert(i, order)
            # self.stratlog.debug(
            #    f'self.open_orders sell: {self.open_orders["sell"]}')
        return

    def limit_nb_orders(self):
        """Cancel open orders if there is too many, open orders if there is
        not enough of it"""
        new_open_orders = self.remove_orders_off_strat(
            self.orders_price_ordering(self.get_orders(
                self.config.selected_market)))
        # self.stratlog.debug(
        #    f'Limit nb orders(), new_open_orders: {new_open_orders}')
        # Don't mess up if all buy orders have been filled during the cycle
        if new_open_orders['buy']:
            nb_orders = len(new_open_orders['buy'])
            if new_open_orders['buy'][0][1] == self.config.safety_buy_value:
                nb_orders -= 1
        else:
            nb_orders = 0
        self.config.stratlog.debug(
            f'nb_orders: {nb_orders}, params["nb_buy_to_display"]: '
            f"{self.config.params['nb_buy_to_display']}")
        # When there is too much buy orders on the order book
        if nb_orders > self.config.params['nb_buy_to_display']:
            self.config.stratlog.debug(f'nb_orders > params["nb_buy_to_display"]')
            # Care of the fake order
            if not self.config.open_orders['buy'][0][0]:
                del self.config.open_orders['buy'][0]
            nb_orders -= self.config.params['nb_buy_to_display']
            while nb_orders > 0:
                self.config.cancel_order(new_open_orders['buy'][0][0],
                                  new_open_orders['buy'][0][1], new_open_orders['buy'][0][4],
                                  'buy')
                del new_open_orders['buy'][0]
                del self.config.open_orders['buy'][0]
                nb_orders -= 1
        # When there is not enough buy order in the order book
        elif nb_orders < self.config.params['nb_buy_to_display']:
            # Ignore if the bottom of the range is reached. It's value is None
            if self.config.open_orders['buy'][0][2]:
                self.config.stratlog.debug(
                    f"{self.config.open_orders['buy'][0][1]} > {self.config.intervals[1]}")
                # Set the range of buy orders to create
                target = self.config.intervals.index(self.config.open_orders['buy'][0][1]) - 1
                start_index = target - self.config.params['nb_buy_to_display'] \
                              + len(self.config.open_orders['buy']) + 1
                if start_index <= 1:
                    start_index = 1
                self.config.stratlog.debug(f'start_index: {start_index}, target: {target}')
                orders = self.set_several_buy(start_index, target)
                for i, order in enumerate(orders):
                    self.config.open_orders['buy'].insert(i, order)
        # Don't mess up if all sell orders have been filled during the cycle
        if new_open_orders['sell']:
            nb_orders = len(new_open_orders['sell'])
            if new_open_orders['sell'][-1][1] == self.config.safety_sell_value:
                nb_orders -= 1
        else:
            nb_orders = 0
        self.config.stratlog.debug(
            f'nb_orders: {nb_orders}; params["nb_sell_to_display"]: '
            f"{self.config.params['nb_sell_to_display']}")
        # When there is too much sell orders on the order book
        if nb_orders > self.config.params['nb_sell_to_display']:
            # Care of fake order
            if not self.config.open_orders['sell'][-1][0]:
                del self.config.open_orders['sell'][-1]
            nb_orders -= self.config.params['nb_sell_to_display']
            self.config.stratlog.debug(f'nb_orders to delete: {nb_orders}')
            while nb_orders > 0:
                self.api.cancel_order(new_open_orders['sell'][-1][0],
                                  new_open_orders['sell'][-1][1],
                                  new_open_orders['sell'][-1][4],
                                  'sell')
                del new_open_orders['sell'][-1]
                del self.config.open_orders['sell'][-1]
                nb_orders -= 1
        # When there is not enough sell order in the order book
        elif nb_orders < self.config.params['nb_sell_to_display']:
            # Ignore if the top of the range is reached
            if self.config.open_orders['sell'][-1][0]:
                # Set the range of sell orders to create
                start_index = self.config.intervals.index(
                    self.config.open_orders['sell'][-1][1]) + 1
                target = start_index + self.params['nb_sell_to_display'] \
                         - len(self.config.open_orders['sell']) - 1
                if target > len(self.config.intervals) - 2:
                    target = len(self.config.intervals) - 2
                self.config.stratlog.debug(f'start_index: {start_index}, target: {target}')
                if target > self.config.max_sell_index:
                    target = self.config.max_sell_index
                orders = self.api.set_several_sell(start_index, target)
                for order in orders:
                    self.config.open_orders['sell'].append(order)
        self.config.stratlog.debug(f'self.config.open_orders: {self.config.open_orders}')
        return

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
                btc_won = self.multiplier(self.config.intervals[start_index_copy + 1],
                                          self.config.params['amount'], self.config.fees_coef)
                btc_to_spend = self.multiplier(self.config.intervals[start_index_copy],
                                               self.config.params['amount'], self.config.fees_coef)
                total = ((btc_won - btc_to_spend) * Decimal(
                    self.config.params['profits_alloc']) / Decimal('100') + \
                         btc_to_spend) / self.config.intervals[start_index_copy]
                amount.append(self.quantizator(total))
                start_index_copy += 1
        else:
            if target - start_index > 0:
                amount = [self.config.params['amount'] for x in \
                          range(target - start_index + 1)]
            else:
                amount = [self.config.params['amount']]
        i = 0
        while start_index <= target:
            order = self.api.init_limit_buy_order(self.config.selected_market, amount[i],
                                              self.config.intervals[start_index])
            buy_orders.append(order)
            start_index += 1
            i += 1
        return buy_orders

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

    def set_id_list_according_intervals(self):
        self.config.id_list = [None for _ in range(len(self.config.intervals))]
        return

    def update_id_list(self):
        """
        :return: None
        """
        id_list = []
        for side in self.config.open_orders:
            for order in self.config.open_orders[side]:
                try:
                    interval_index = self.config.intervals.index(order[1])
                except ValueError as e:
                    raise ValueError(f'Wrong order price for self.intervals, '
                                     f'intervals: {str(self.config.intervals)}, got: '
                                     f'{str(order[1])}, raw error: {e}')
                self.config.id_list[interval_index] = order[0]
                id_list.append(order[0])
        # Remove id or orders no longer in open_order.
        self.config.id_list[:] = [None if x not in id_list else x for x in self.config.id_list]
        self.config.stratlog.debug(f'self.config.id_list: {self.config.id_list}')
        return

    def calculate_buy_funds(self, index, amount):
        """Calculate the buy funds required to execute the strategy
        amount: Decimal, allocated ALT per order
        return: Decimal, funds needed
        """
        buy_funds_needed = Decimal('0')
        i = 0
        while i <= index:
            buy_funds_needed += self.config.intervals[i] * amount
            i += 1
        return buy_funds_needed

    def calculate_sell_funds(self, index, amount):
        """Calculate the sell funds required to execute the strategy
        amount: Decimal, allocated ALT per order
        return: Decimal, funds needed
        """
        sell_funds_needed = Decimal('0')
        i = len(self.config.intervals) - 1
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
                if order[1] in self.config.intervals \
                        or order[1] == self.config.safety_buy_value:
                    funds += order[1] * order[2]
                else:
                    orders_outside_strat.append(order)
        else:
            for order in orders['sell']:
                if order[1] in self.config.intervals \
                        or order[1] == self.config.safety_sell_value:
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
                    if self.user_interface.simple_question(q):
                        q = 'Which order do you want to remove:'
                        rsp = self.user_interface.ask_to_select_in_a_list(q,
                                                           orders_outside_strat)
                        del orders_outside_strat[rsp]
                        rsp = self.api.cancel_order(orders_outside_strat[rsp][0],
                                                orders_outside_strat[rsp][1],
                                                orders_outside_strat[rsp][4], side)
                        if rsp:
                            if side == 'buy':
                                funds += order[1] * order[2]
                            else:
                                funds += order[2]
                            self.config.stratlog.debug(
                                f'You have now {funds} {side} '
                                f'funds and you need {funds_needed}.')
                    else:
                        is_valid = True
        return funds

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

    def get_orders(self, market):
        """Get actives orders from a marketplace and organize them.
        return: dict, containing list of buys & sells.
        """
        orders = {'sell': [], 'buy': []}
        raw_orders = self.api.fetch_open_orders(market)
        for order in raw_orders:
            formated_order = self.api.format_order(
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

    def lw_initialisation(self):
        """Initializing parameters, check parameters then initialize LW.
        """
        if self.config.test_mode:
            params = self.check_params(self.config.testing_params)
            self.config.params = self.check_for_enough_funds(params)
        else:
            self.ask_for_params()
        open_orders = self.remove_safety_before_init(self.orders_price_ordering(
            self.get_orders(
                self.config.selected_market)))
        self.config.open_orders = self.strat_init(open_orders)
        self.set_safety_orders(self.config.intervals.index(self.config.open_orders['buy'][0][1]),
                               self.config.intervals.index(self.config.open_orders['sell'][-1][1]))
        self.set_id_list_according_intervals()
        self.update_id_list()
        self.main_loop()

    def main_loop(self):
        """Do the lazy whale strategy.
        Simple execution loop.
        """
        while True:
            self.config.applog.debug('CYCLE START')
            orders = self.remove_safety_order(self.remove_orders_off_strat(
                self.orders_price_ordering(self.get_orders(
                    self.config.selected_market))))  # for comparing by Id
            if orders:
                orders = self.check_if_no_orders(orders)
                self.compare_orders(orders)
                self.update_id_list()
                self.limit_nb_orders()
                self.set_safety_orders(self.config.intervals.index(
                    self.config.open_orders['buy'][0][1]),
                    self.config.intervals.index(
                        self.config.open_orders['sell'][-1][1]))
                self.update_id_list()
            self.config.applog.debug('CYCLE STOP')
            self.last_loop_datetime = datetime.now().timestamp()
            sleep(5)











