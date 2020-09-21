import os
import sys
import json
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from time import sleep

import ccxt

import utils.helpers as helper
import utils.converters as convert
from main.interval import Interval
from ui.user_interface import UserInterface
from utils.logger import Logger
import config.config as config


class LazyWhale:
    """Core strategy for LW.
    open order = [id, price, amount, value, timestamp, date]"""

    def __init__(self, preset_params=False):
        self.logger = Logger('main')
        self.log = self.logger.log
        self.preset_params = preset_params
        self.root_path = helper.set_root_path()
        self.keys = self.keys_initialisation()

        self.fees_coef = config.FEES_COEFFICIENT

        self.safety_buy_value = config.SAFETY_BUY_VALUE
        self.safety_sell_value = config.SAFETY_SELL_VALUE
        self.ui = UserInterface(self.keys,
                                self.fees_coef,
                                self.safety_buy_value,
                                self.safety_sell_value)
        self.open_orders = {'sell': [], 'buy': []}
        self.params = {}
        self.connector = None
        self.intervals: [Interval] = []
        self.amounts = []
        self.id_list = []
        self.max_sell_index = 0
        self.sides = ('buy', 'sell')
        # TODO: calculate min_amount correctly
        self.min_amount = Decimal('0')

    def keys_initialisation(self):
        """Check if a key.json file exist and create one if none.
        return: dict, with all api keys found.
        """
        keys_path = f'{self.root_path}config/keys.json'
        if helper.create_file_when_none(keys_path):
            self.log(('No file keys.json was found, an empty one has been created, '
                      'please fill it as indicated in the documentation'),
                     level='critical')
            raise SystemExit

        else:
            api_keys = self.keys_file_reader(keys_path)
            if not api_keys:
                self.log(('Your keys.json file is empty, please '
                          'fill it as indicated to the documentation'),
                         level='critical')
                raise SystemExit

        return api_keys

    def keys_file_reader(self, keys_path):
        """Check the consistence of datas in keys.json.
        return: dict, api keys
        """
        name_list = ccxt.exchanges + ['zebitex', 'zebitex_testnet', 'slack_webhook']
        api_keys = {}
        with open(keys_path, mode='r', encoding='utf-8') as keys_file:
            try:
                keys_json = json.load(keys_file)

            except Exception as e:
                self.log(f'keys.json file is not correct : {e}', level='critical')
                raise SystemExit

            try:
                if 'marketPlaces' not in keys_json:
                    raise IndexError("json is not formatted correctly: marketPlaces key not exists")

                for market_place_name, market_place_info in keys_json['marketPlaces'].items():
                    if market_place_name not in name_list:
                        raise NameError('The marketplace name is invalid!')

                    api_keys[market_place_name] = market_place_info

                if 'slack_webhook' not in keys_json:
                    raise IndexError("json is not formatted correctly: slack_webhook key not exists")

                self.logger.set_slack(keys_json['slack_webhook'])
                self.log = self.logger.log
                api_keys['slack_webhook'] = keys_json['slack_webhook']

            except Exception as e:
                self.log(f'Something went wrong : {e}', level='critical')
                raise SystemExit

        return api_keys

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
        self.log(f'self.id_list: {self.id_list}')

    def remove_safety_before_init(self, open_orders):
        """Remove safety orders before strat init if there is some.
        open_orders: dict.
        return: dict."""
        if open_orders['buy']:
            if open_orders['buy'][0][1] == self.safety_buy_value:
                self.connector.cancel_order(
                    self.params['market'],
                    open_orders['buy'][0][0],
                    open_orders['buy'][0][1],
                    open_orders['buy'][0][4],
                    'buy')
                del open_orders['buy'][0]

        if open_orders['sell']:
            if open_orders['sell'][-1][1] == self.safety_sell_value:
                self.connector.cancel_order(
                    self.params['market'],
                    open_orders['sell'][-1][0],
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
        self.log('strat_init()')
        self.intervals = [self.safety_buy_value] + self.intervals + \
                         [self.safety_sell_value]
        self.amounts = helper.generate_list(len(self.intervals), self.params['amount'])
        self.connector.intervals = self.intervals
        self.max_sell_index = len(self.intervals) - 2
        orders_to_remove = {'sell': [], 'buy': []}
        remaining_orders_price = {'buy': [], 'sell': []}

        lowest_buy, highest_sell = self.init_open_orders_price_target()

        self.log(
            f'self.intervals: {self.intervals}, open_orders: {open_orders}, '
            f'self.max_sell_index: {self.max_sell_index}, '
            f'lowest_buy: {lowest_buy}, self.params["spread_bot"]: '
            f"{self.params['spread_bot']}, self.params['spread_top']: "
            f"{self.params['spread_top']}, highest_sell: {highest_sell}",
            level='info', print_=True)

        orders_to_remove['buy'] = self.init_remove_orders('buy',
                                                          open_orders['buy'],
                                                          lowest_buy,
                                                          self.params['spread_bot'],
                                                          orders_to_remove['buy'])
        orders_to_remove['sell'] = self.init_remove_orders('sell',
                                                           open_orders['sell'],
                                                           self.params['spread_top'],
                                                           highest_sell,
                                                           orders_to_remove['sell'])

        for side in self.sides:
            open_orders, remaining_orders_price = self.update_orders(side,
                                                                     open_orders, orders_to_remove,
                                                                     remaining_orders_price)

        self.log(
            f'orders_to_remove: {orders_to_remove}, open_orders: {open_orders}'
            f', remaining_orders_price: {remaining_orders_price}',
            level='debug')

        return self.set_first_orders(remaining_orders_price, open_orders)

    def init_open_orders_price_target(self):
        """Get price at the edge of open orders during strategy initialization,
        in the limit choose with nb_orders_to_display.
        return: Decimals."""
        if self.intervals.index(self.params['spread_bot']) \
                - self.params['nb_buy_to_display'] + 1 > 1 \
                and self.params['nb_buy_to_display'] != 0:
            lowest_buy = self.intervals[self.intervals.index(
                self.params['spread_bot'])
                                        - self.params['nb_buy_to_display'] + 1]

        else:
            lowest_buy = self.intervals[1]

        if self.intervals.index(self.params['spread_top']) \
                + self.params['nb_sell_to_display'] - 1 < self.max_sell_index \
                and self.params['nb_sell_to_display'] != 0:
            highest_sell = self.intervals[self.intervals.index(
                self.params['spread_top'])
                                          + self.params['nb_sell_to_display'] - 1]
        else:
            highest_sell = self.intervals[self.max_sell_index]

        return lowest_buy, highest_sell

    def init_remove_orders(self, side, open_orders, lowest_price, highest_price, orders_to_remove):
        """Remove unwanted buys orders for the strategy.
        open_orders: dict.
        lowest_buy: Decimal.
        orders_to_remove: dict.
        q, q2, q3: string.
        return: dict """
        q = 'Do you want to remove this order ? (y or n)'
        q2 = (f"This order has an amount inferior or superior to "
              f"{self.params['amount']}. Do you want to cancel it? (y or no)")
        for i, order in enumerate(open_orders):
            if order[1] in self.intervals:
                if not lowest_price <= order[1] <= highest_price:
                    self.connector.cancel_order(self.params['market'], order[0], order[1], order[4], side)
                    orders_to_remove.append(i)
                    continue

                if order[2] != self.params['amount']:
                    if not self.preset_params:
                        if self.ui.simple_question(f'{order} {q2}'):
                            self.connector.cancel_order(self.params['market'], order[0], order[1], order[4], side)
                            orders_to_remove.append(i)
                            continue

            else:
                if not self.preset_params:
                    if self.ui.simple_question(f'{q} {order}'):
                        self.connector.cancel_order(self.params['market'], order[0], order[1], order[4], side)

                orders_to_remove.append(i)
                continue

            # Two order of the same price could crash the bot
            if i > 0:
                if order[1] == open_orders[i - 1][1] \
                        and i - 1 not in orders_to_remove:
                    orders_to_remove = self.remove_one_of_two_orders(side, open_orders, order, i, orders_to_remove)

        return orders_to_remove

    def remove_one_of_two_orders(self, side, open_orders, order, i, orders_to_remove):
        q = 'Those two orders have the same price, which one do you want to cancel : '
        order_to_select = [order, open_orders[i - 1]]

        if self.preset_params:
            rsp = 1
        else:
            rsp = int(self.ui.ask_to_select_in_a_list(q, order_to_select))

        if rsp == 1:
            self.connector.cancel_order(self.params['market'], order[0], order[1], order[4], side)
            orders_to_remove.append(i)
        else:
            self.connector.cancel_order(self.params['market'], order_to_select[1][0],
                                        order_to_select[1][1],
                                        order_to_select[1][4], side)
            orders_to_remove.append(i - 1)

        return orders_to_remove

    def update_orders(self, side, open_orders, orders_to_remove, remaining_orders_price):
        """Remove canceled orders from open_orders and generate list of prices
        from remaining orders.
        open_orders: dict.
        order_to_remove: dict.
        return: dicts"""
        if orders_to_remove[side]:
            for i, index in enumerate(orders_to_remove[side]):
                del open_orders[side][index - i]

        if open_orders[side]:
            for order in open_orders[side]:
                remaining_orders_price[side].append(order[1])

        return open_orders, remaining_orders_price

    def set_first_orders(self, remaining_orders_price, open_orders):
        """Open orders for the strategy.
        remaining_orders_price: dict.
        open_orders: dict.
        return: dict, of open orders used for the strategy."""
        self.log('set_first_orders()')
        buy_target = self.intervals.index(self.params['spread_bot'])
        lowest_sell_index = buy_target + 2
        new_orders = {'sell': [], 'buy': []}
        lowest_buy_index, sell_target = self.set_first_orders_indexes(buy_target, lowest_sell_index)

        self.log(
            f'buy target: {buy_target}, lowest_buy_index: '
            f'{lowest_buy_index}, lowest_sell_index: {lowest_sell_index}, '
            f'sell_target: {sell_target}, max_sell_index: '
            f'{self.max_sell_index}')

        for side in self.sides:
            new_orders[side] = self.open_first_orders(open_orders[side],
                                                      remaining_orders_price[side],
                                                      new_orders[side],
                                                      eval(f'lowest_{side}_index'),
                                                      eval(f'{side}_target'),
                                                      side)

        self.log(f'new_orders: {new_orders}')
        return new_orders

    def set_first_orders_indexes(self, buy_target, lowest_sell_index):
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

        return lowest_buy_index, sell_target

    def open_first_orders(self, open_orders, remaining_orders_price, new_orders, lowest_index, target_index, side):
        """Open a buy order if needed or use an already existing open order.
        From the lowest price to the highest price.
        open_orders, remaining_orders_price, new_orders: dict.
        lowest_buy_index, buy_target: int.
        return: dict."""
        api_call = self.connector.init_limit_buy_order if side == 'buy' else self.connector.init_limit_sell_order
        while lowest_index <= target_index:
            if self.intervals[lowest_index] \
                    not in remaining_orders_price:
                order = api_call(self.params['market'],
                                 self.amounts[lowest_index],
                                 self.intervals[lowest_index])
                new_orders.append(order)
                sleep(0.2)

            else:
                for item in open_orders:
                    if item[1] == self.intervals[lowest_index]:
                        new_orders.append(item)
                        break

            lowest_index += 1

        return new_orders

    def safety_orders_checkpoint(self, open_orders):
        """Main function of remove safety orders strategy.
        open_orders: dict.
        return: dict.
        """
        self.log(f'safety_orders_checkpoint()')
        open_orders = self.safety_failsafe(open_orders)

        if self.main_loop_abort(open_orders):
            return False

        open_orders = self.remove_safety_orders(open_orders)

        return open_orders

    def remove_safety_orders(self, open_orders):
        for side in self.sides:
            if open_orders[side]:
                open_orders[side] = self.remove_safety_order(open_orders[side], side)

        return open_orders

    def safety_failsafe(self, open_orders):
        """Empty lists break the strategy, add fake orders.
        open_orders: dict.
        return: dict."""
        for side in self.sides:
            index = -1 if side == 'buy' else 0
            create_fake = self.create_fake_buy if side == 'buy' else self.create_fake_sell

            if self.open_orders[side]:
                if not open_orders[side] and not self.open_orders[side][index][2]:
                    open_orders[side].append(create_fake())

        return open_orders

    def main_loop_abort(self, open_orders):
        """Abort main loop when there is no order fulfilled.
        open_orders: dict.
        return: bool."""
        if open_orders['buy'] and open_orders['sell']:
            if self.open_orders['buy'] and self.open_orders['sell']:
                if open_orders['buy'][-1][0] == self.open_orders['buy'][-1][0] \
                        and open_orders['sell'][0][0] == self.open_orders['sell'][0][0]:
                    return True

        return False

    def remove_safety_order(self, open_orders, side):
        """Remove safety orders and it's associated order ID.
        open_orders: dict.
        return: dict."""
        index = 0 if side == 'buy' else -1
        if open_orders[index][0] == self.id_list[index]:
            # The safety order can be a fake order
            if open_orders[index][2]:
                self.connector.cancel_order(self.params['market'],
                                            open_orders[index][0],
                                            open_orders[index][1],
                                            open_orders[index][4],
                                            side)

            del open_orders[index]

        if self.open_orders[side][index][0] == self.id_list[index]:
            del self.open_orders[side][index]
            self.id_list[index] = None

        return open_orders

    def set_safety_orders(self):
        """Add safety orders to lock funds for the strategy.
        lowest_buy_index: int.
        highest_sell_index: int."""
        lowest_buy_index = self.intervals.index(self.open_orders['buy'][0][1])
        highest_sell_index = self.intervals.index(self.open_orders['sell'][-1][1])
        self.log(
            f'set_safety_orders(), lowest_buy_index: {lowest_buy_index}, '
            f'highest_sell_index: {highest_sell_index}')

        if lowest_buy_index > 1:
            self.create_safety_buy(lowest_buy_index)

        else:
            if self.open_orders['buy'][0][1] != self.safety_buy_value:
                self.open_orders['buy'].insert(0, self.create_fake_buy())

        if highest_sell_index < self.max_sell_index:
            self.create_safety_sell(highest_sell_index)

        else:
            if self.open_orders['sell'][-1][1] != self.safety_sell_value:
                self.open_orders['sell'].append(self.create_fake_sell())

        self.log(
            f'safety buy: {self.open_orders["buy"][0]} , '
            f'safety sell: {self.open_orders["sell"][-1]}')

    def create_safety_buy(self, lowest_buy_index):
        buy_sum = Decimal('0')
        lowest_buy_index -= 1
        self.log(f'lowest_buy_index: {lowest_buy_index}')
        while lowest_buy_index > 0:
            buy_sum += convert.divider(
                convert.multiplier(self.amounts[lowest_buy_index],
                                   self.intervals[lowest_buy_index]),
                self.safety_buy_value)
            lowest_buy_index -= 1

        self.log(f'buy_sum: {buy_sum}, lowest_buy_index: {lowest_buy_index}',
                 level='debug')
        self.open_orders['buy'].insert(
            0, self.connector.init_limit_buy_order(
                self.params['market'], buy_sum, f'{self.intervals[0]:8f}'))

    def create_safety_sell(self, highest_sell_index):
        sell_sum = Decimal('0')
        highest_sell_index += 1
        self.log(f'highest_sell_index: {highest_sell_index}')
        while highest_sell_index <= self.max_sell_index:
            sell_sum += self.amounts[highest_sell_index]
            highest_sell_index += 1

        self.log(f'sell_sum: {sell_sum}, highest_sell_index: '
                 f'{highest_sell_index}, self.max_sell_index: '
                 f'{self.max_sell_index}')
        self.open_orders['sell'].append(self.connector.init_limit_sell_order(
            self.params['market'], sell_sum, self.intervals[-1]))

    def create_fake_buy(self):
        """Create a fake buy order.
        return: list"""
        return ['FB', self.safety_buy_value, None, None,
                convert.timestamp_formater(),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')]

    def create_fake_sell(self):
        """Create a fake sell order.
        return: list"""
        return ['FS', self.safety_sell_value, None, None,
                convert.timestamp_formater(),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')]

    def remove_orders_off_strat(self, new_open_orders):
        """Remove all orders that are not included in the strategy
        new_open_orders: dict, every open orders on the market
        return: dict, open orders wich are included in the strategy"""
        self.log(f'remove_orders_off_strat(), new_open_orders: {new_open_orders}',
                 level='debug')
        orders_to_remove = {'sell': [], 'buy': []}

        for side in self.sides:
            if new_open_orders[side]:
                for i, order in enumerate(new_open_orders[side]):
                    if order[0] not in self.id_list:
                        orders_to_remove[side].append(i)

        for side in self.sides:
            if orders_to_remove[side]:
                for i, index in enumerate(orders_to_remove[side]):
                    del new_open_orders[side][index - i]

        self.log(f'orders_to_remove: {orders_to_remove}')
        return new_open_orders

    def check_if_no_orders(self, new_open_orders):
        """Open orders when there is none on the market otherwise
        compare_orders() will fail.
        new_open_orders: dict.
        return: dict"""
        order_oppened = False
        self.log('check_if_no_orders()')
        if not new_open_orders['buy']:
            target = self.set_empty_buy_target()
            if target < 1:
                new_open_orders = self.when_bottom_is_reached(target, new_open_orders)

            else:
                new_open_orders = self.add_buy_when_none(target, new_open_orders)
                order_oppened = True

            self.log(f'updated new_buy_orders: {new_open_orders["buy"]}',
                     level='debug')

        if not new_open_orders['sell']:
            start_index = self.set_empty_sell_start_index()
            if start_index > self.max_sell_index:
                new_open_orders = self.when_top_is_reached(start_index, new_open_orders)

            else:
                new_open_orders = self.add_sell_when_none(start_index, new_open_orders)
                order_oppened = True

            self.log(f'updated new_sell_orders: {new_open_orders["sell"]}',
                     level='debug')

        if order_oppened:
            new_open_orders = self.check_if_no_orders(
                self.connector.orders_price_ordering(
                    self.connector.get_orders(
                        self.params['market'])))
            # Fake buy Handler when range_bot/top is reached
            self.update_id_list()

        return new_open_orders

    def set_empty_buy_target(self):
        """From where in self.intervals do we start.
        return: int"""
        self.log("no new_open_orders['buy']")
        if len(self.open_orders['buy']) > 0:
            target = self.intervals.index(
                self.open_orders['buy'][0][1]) - 1
        else:
            target = 0

        return target

    def when_bottom_is_reached(self, target, new_open_orders):
        """Stop or add a fake order.
        start_index: int.
        new_open_orders: dict.
        return: dict"""
        if self.params['stop_at_bot']:
            self.log(f'Bottom target reached! target: {target}',
                     level='critical', slack=True, print_=True)

            self.connector.cancel_all(self.params['market'], self.remove_safety_orders(
                self.remove_orders_off_strat(
                    self.connector.get_orders(self.params['market']))))
            raise SystemExit()

        else:
            order = self.create_fake_buy()
            new_open_orders['buy'].insert(0, order)
            self.open_orders['buy'].insert(0, order)

        return new_open_orders

    def add_buy_when_none(self, target, new_open_orders):
        """Fulfill buy side when it's empty.
        start_index: int.
        new_open_orders: dict.
        return: dict"""
        self.log('Buys side is empty',
                 level='warning', slack=True, print_=True)

        if target - self.params['nb_buy_to_display'] + 1 >= 1:
            start_index = target - self.params['nb_buy_to_display'] + 1
        else:
            start_index = 1

        orders = self.connector.set_several_buy(start_index, target, self.amounts)
        for i, order in enumerate(orders):
            new_open_orders['buy'].insert(i, order)
            self.open_orders['buy'].insert(i, order)
            # update_id_list() do not work properly inside check_if_no_orders()
            self.id_list[self.intervals.index(order[1])] = order[0]

        return new_open_orders

    def set_empty_sell_start_index(self):
        """From where in self.intervals do we start.
        return: int"""
        self.log("no new_open_orders['sell']")
        if len(self.open_orders['sell']) > 0:
            start_index = self.intervals.index(
                self.open_orders['sell'][-1][1]) + 1
        else:
            start_index = self.max_sell_index

        return start_index

    def when_top_is_reached(self, start_index, new_open_orders):
        """Stop or add a fake order.
        start_index: int.
        new_open_orders: dict.
        return: dict"""
        if self.params['stop_at_top']:
            self.log(f'Top target reached! start_index: {start_index}, '
                     f'self.max_sell_index: {self.max_sell_index}',
                     level='critical', slack=True, print_=True)

            self.connector.cancel_all(self.params['market'], self.remove_safety_orders(
                self.remove_orders_off_strat(self.connector.get_orders(
                    self.params['market']))))
            raise SystemExit

        else:
            order = self.create_fake_sell()
            new_open_orders['sell'].append(order)
            self.open_orders['sell'].append(order)

        return new_open_orders

    def add_sell_when_none(self, start_index, new_open_orders):
        """Fulfill sell side when it's empty.
        start_index: int.
        new_open_orders: dict.
        return: dict"""
        self.log('Sell side is empty',
                 level='warning', slack=True, print_=True)

        if start_index + self.params['nb_sell_to_display'] - 1 \
                <= self.max_sell_index:
            target = start_index + self.params['nb_sell_to_display'] - 1

        else:
            target = self.max_sell_index

        orders = self.connector.set_several_sell(start_index, target, self.amounts)
        for order in orders:
            new_open_orders['sell'].append(order)
            self.open_orders['sell'].append(order)
            self.id_list[self.intervals.index(order[1])] = order[0]

        return new_open_orders

    def amount_compare_intervals(self, new_intervals: [Interval]) -> [dict]:
        """Compare intervals and return amount of orders to open on correct interval with correct side"""
        interval_index = 0
        # check length of intervals are same

        amounts_to_open = []

        while interval_index < len(new_intervals):
            if self.intervals[interval_index] != new_intervals[interval_index]:
                amount_to_open_sell = helper.get_amount_to_open(self.intervals[interval_index].get_buy_orders(),
                                                                new_intervals[interval_index].get_buy_orders(), )

                amount_to_open_buy = helper.get_amount_to_open(self.intervals[interval_index].get_sell_orders(),
                                                               new_intervals[interval_index].get_sell_orders())

                if amount_to_open_sell > Decimal('0'):
                    if interval_index + 2 >= len(new_intervals):
                        # TODO: top is reached
                        assert 1 == 0

                    amounts_to_open.append({
                        "interval_idx": interval_index + 2,
                        "side": 'sell',
                        "amount": amount_to_open_sell
                    })

                if amount_to_open_buy > Decimal('0'):
                    if interval_index - 2 < 0:
                        # TODO: bottom is reached
                        assert 1 == 0

                    amounts_to_open.append({
                        "interval_idx": interval_index - 2,
                        "side": 'buy',
                        "amount": amount_to_open_buy
                    })

            interval_index += 1

        return amounts_to_open

    def prepare_new_orders(self, amounts_to_open):
        """Generate orders based on interval index and amount to open
        and return them"""
        sell_orders_to_open = []
        buy_orders_to_open = []

        for amount_to_open in amounts_to_open:
            if amount_to_open['side'] == 'buy':
                # get existing amount of orders in interval
                existing_amount = self.intervals[amount_to_open['interval_idx']].get_buy_orders_amount(use_filled=True)
                # cancel existing orders
                self.connector.cancel_orders(self.intervals[amount_to_open['interval_idx']].get_buy_orders())

                # prepare new orders for opening
                buy_orders_to_open.extend(
                    self.intervals[amount_to_open['interval_idx']]
                        .generate_orders_by_amount(amount_to_open['amount'] + existing_amount,
                                                   self.min_amount,
                                                   self.params['orders_per_interval'])
                )
            else:
                existing_amount = self.intervals[amount_to_open['interval_idx']].get_sell_orders_amount(use_filled=True)
                self.connector.cancel_orders(self.intervals[amount_to_open['interval_idx']].get_sell_orders())

                sell_orders_to_open.extend(
                    self.intervals[amount_to_open['interval_idx']]
                        .generate_orders_by_amount(amount_to_open['amount'] + existing_amount,
                                                   self.min_amount,
                                                   self.params['orders_per_interval'])
                )

        return sell_orders_to_open, buy_orders_to_open

    def execute_new_orders(self, new_intervals, sell_orders_to_open, buy_orders_to_open):
        """Open orders saved them in new_intervals and return new_intervals"""
        if sell_orders_to_open:
            sell_orders = self.connector.set_several_sell(sell_orders_to_open)

            if sell_orders:
                new_intervals = helper.populate_intervals(new_intervals, sell_orders)

        if buy_orders_to_open:
            buy_orders = self.connector.set_several_buy(buy_orders_to_open)

            if buy_orders:
                new_intervals = helper.populate_intervals(new_intervals, buy_orders)

        return new_intervals

    def compare_intervals(self, new_intervals: [Interval]) -> None:
        """Compares intervals and opens new orders and saves them in self.intervals"""
        assert len(self.intervals) == len(new_intervals)
        amounts_to_open = self.amount_compare_intervals(new_intervals)
        sell_orders_to_open, buy_orders_to_open = self.prepare_new_orders(amounts_to_open)

        self.intervals = self.execute_new_orders(new_intervals, sell_orders_to_open, buy_orders_to_open)

    def compare_orders(self, new_open_orders):
        """Compare between open order know by LW and buy order from the
        marketplace.
        """
        self.log('compare_orders()')
        executed_orders = {'sell': [], 'buy': []}
        missing_orders = self.get_missing_orders(new_open_orders)

        for side in self.sides:
            if missing_orders[side]:
                self.set_amounts(missing_orders)
                executed_orders = self.execute_orders(side, new_open_orders, missing_orders, executed_orders)

        self.log(f'compare_orders, missing_orders: {missing_orders} '
                 f'executed_orders: {executed_orders}')
        self.update_open_orders(missing_orders, executed_orders)
        self.backup_spread_value(executed_orders)

    def get_missing_orders(self, new_open_orders):
        missing_orders = deepcopy(self.open_orders)

        for side in self.sides:
            for order in self.open_orders[side]:
                rsp = any(new_order[0] == order[0] for new_order in new_open_orders[side])
                if rsp:
                    missing_orders[side].remove(order)

        return missing_orders

    def set_amounts(self, missing_orders):
        if missing_orders['buy']:
            for order in missing_orders['buy']:
                self.amounts[self.intervals.index(order[1]) + 1] = self.params['amount']

        if missing_orders['sell']:
            for order in missing_orders['sell']:
                self.amounts[self.intervals.index(order[1]) - 1] = self.set_buy_amount(order)

    def set_buy_amount(self, order):
        if self.params['profits_alloc'] != 0:
            btc_won = convert.multiplier(order[1], self.params['amount'], self.fees_coef)
            btc_to_spend = convert.multiplier(self.intervals[self.intervals.index(order[1]) - 2],
                                              self.params['amount'], self.fees_coef)
            return convert.quantizator(((btc_won - btc_to_spend) *
                                        self.params['profits_alloc'] / Decimal('100') +
                                        btc_to_spend) / self.intervals[self.intervals.index(order[1]) - 2])
        else:
            return self.params['amount']

    def execute_orders(self, side, new_open_orders, missing_orders, executed_orders):
        list_index = -1 if side == 'buy' else 0
        coef = 1 if side == 'buy' else -1
        opposite_side = 'sell' if side == 'buy' else 'buy'
        api_call = self.connector.set_several_sell if side == 'buy' else self.connector.set_several_buy
        self.log(f'{len(missing_orders[side])} {side}(s) has occurred',
                 level='warning', slack=True, print_=True)
        start_index = self.id_list.index(new_open_orders[side][list_index][0]) + convert.int_multiplier(2, coef)
        target = start_index + convert.int_multiplier(len(missing_orders[side]), coef) - convert.int_multiplier(1, coef)
        if side == 'sell':
            start_index, target = target, start_index
        self.log(f'start_index: {start_index}, target: {target}')
        executed_orders[opposite_side] = api_call(start_index, target, self.amounts)

        return executed_orders

    def update_open_orders(self, missing_orders, executed_orders):
        """Update self.open_orders with orders missing and executed orders.
        missing_orders: dict, all the missing orders since the last LW cycle.
        executed_order: dict, all the executed orders since the last LW cycle"""
        self.log('update_open_orders()')
        if executed_orders['buy']:
            for order in missing_orders['sell']:
                self.open_orders['sell'].remove(order)
            for order in executed_orders['buy']:
                self.open_orders['buy'].append(order)

        if executed_orders['sell']:
            for order in missing_orders['buy']:
                self.open_orders['buy'].remove(order)
            for i, order in enumerate(executed_orders['sell']):
                self.open_orders['sell'].insert(i, order)

    def backup_spread_value(self, executed_orders):
        if executed_orders['buy'] or executed_orders['sell']:
            index = self.intervals.index(self.open_orders['buy'][-1][1])
            self.params['spread_bot'] = self.intervals[index]
            self.params['spread_top'] = self.intervals[index + 2]
            helper.params_writer(f'{self.root_path}config/params.json', self.params)

    def limit_nb_orders(self):
        """Cancel open orders if there is too many, open orders if there is
        not enough of it"""
        new_open_orders = self.remove_orders_off_strat(
            self.connector.orders_price_ordering(
                self.connector.get_orders(
                    self.params['market'])))

        nb_orders = self.how_much_buys(new_open_orders)
        if nb_orders > self.params['nb_buy_to_display']:
            self.cancel_some_buys(nb_orders, new_open_orders)

        elif nb_orders < self.params['nb_buy_to_display']:
            self.open_some_buys(nb_orders)

        nb_orders = self.how_much_sells(new_open_orders)
        if nb_orders > self.params['nb_sell_to_display']:
            self.cancel_some_sells(nb_orders, new_open_orders)

        elif nb_orders < self.params['nb_sell_to_display']:
            self.open_some_sells(nb_orders)

        self.log(f'self.open_orders: {self.open_orders}')

    def how_much_buys(self, new_open_orders):
        # Don't mess up if all buy orders have been filled during the cycle
        if new_open_orders['buy']:
            nb_orders = len(new_open_orders['buy'])
            if new_open_orders['buy'][0][1] == self.safety_buy_value:
                nb_orders -= 1
        else:
            nb_orders = 0

        self.log(
            f'nb_orders: {nb_orders}, params["nb_buy_to_display"]: '
            f"{self.params['nb_buy_to_display']}")

        return nb_orders

    def cancel_some_buys(self, nb_orders, new_open_orders):
        """When there is too much buy orders in the order book
        nb_orders: int.
        new_open_orders: dict.
        return: dict."""
        self.log(f'nb_orders > params["nb_buy_to_display"]')
        # Care of the fake order
        if not self.open_orders['buy'][0][0]:
            del self.open_orders['buy'][0]

        nb_orders -= self.params['nb_buy_to_display']

        while nb_orders > 0:
            self.connector.cancel_order(self.params['market'],
                                        self.open_orders['buy'][0][0],
                                        self.open_orders['buy'][0][1],
                                        self.open_orders['buy'][0][4],
                                        'buy')

            # I consider that if there is a fucked up at this stage LW will crash
            if self.open_orders['buy'][0][0] == new_open_orders['buy'][0][0]:
                if new_open_orders['buy'][0][2] != self.params['amount']:
                    # Amount should be saved in order to not open an order with
                    # full amount. That could be costly during long range.
                    self.amounts[self.id_list.index(new_open_orders['buy'][0][0])] = new_open_orders['buy'][0][2]
                del new_open_orders['buy'][0]

            del self.open_orders['buy'][0]
            nb_orders -= 1

    def open_some_buys(self, nb_orders):
        """When there is not enough buy order in the order book
        Ignore if the bottom of the range is reached. It's value is None"""
        if self.open_orders['buy'][0][2]:
            self.log(
                f"{self.open_orders['buy'][0][1]} > {self.intervals[1]}")
            # Set the range of buy orders to create
            target = self.intervals.index(self.open_orders['buy'][0][1]) - 1
            start_index = target - self.params['nb_buy_to_display'] \
                          + len(self.open_orders['buy']) + 1
            if start_index <= 1:
                start_index = 1
            self.log(f'start_index: {start_index}, target: {target}')

            orders = self.connector.set_several_buy(start_index, target, self.amounts)
            for i, order in enumerate(orders):
                self.open_orders['buy'].insert(i, order)

    def how_much_sells(self, new_open_orders):
        """Don't mess up if all sell orders have been filled during the cycle"""
        if new_open_orders['sell']:
            nb_orders = len(new_open_orders['sell'])
            if new_open_orders['sell'][-1][1] == self.safety_sell_value:
                nb_orders -= 1

        else:
            nb_orders = 0

        self.log(
            f'nb_orders: {nb_orders}; params["nb_sell_to_display"]: '
            f"{self.params['nb_sell_to_display']}")

        return nb_orders

    def cancel_some_sells(self, nb_orders, new_open_orders):
        """When there is too much sell orders in the order book
        Care of fake order"""
        if not self.open_orders['sell'][-1][0]:
            del self.open_orders['sell'][-1]
        nb_orders -= self.params['nb_sell_to_display']
        self.log(f'nb_orders to delete: {nb_orders}')
        while nb_orders > 0:
            self.connector.cancel_order(self.params['market'],
                                        self.open_orders['sell'][-1][0],
                                        self.open_orders['sell'][-1][1],
                                        self.open_orders['sell'][-1][4],
                                        'sell')

            if self.open_orders['sell'][-1][0] == new_open_orders['sell'][-1][0]:
                if new_open_orders['sell'][-1][2] != self.params['amount']:
                    self.amounts[self.id_list.index(new_open_orders['sell'][-1][0])] = new_open_orders['sell'][-1][2]

                del new_open_orders['sell'][-1]

            del self.open_orders['sell'][-1]
            nb_orders -= 1

    def open_some_sells(self, nb_orders):
        """When there is not enough sell order in the order book
        Ignore if the top of the range is reached"""
        if self.open_orders['sell'][-1][0]:
            # Set the range of sell orders to create
            start_index = self.intervals.index(
                self.open_orders['sell'][-1][1]) + 1
            target = start_index + self.params['nb_sell_to_display'] \
                     - len(self.open_orders['sell']) - 1
            if target > len(self.intervals) - 2:
                target = len(self.intervals) - 2

            self.log(f'start_index: {start_index}, target: {target}')
            if target > self.max_sell_index:
                target = self.max_sell_index

            orders = self.connector.set_several_sell(start_index, target, self.amounts)
            for order in orders:
                self.open_orders['sell'].append(order)

    def lw_initialisation(self):
        """Initializing parameters, check parameters then initialize LW.
        """
        if self.preset_params:
            params = self.ui.check_params(self.preset_params)
            self.params = self.ui.check_for_enough_funds(params)
        else:
            self.params = self.ui.ask_for_params()  # f'{self.root_path}config/params.txt')

        self.connector = self.params['api_connector']
        self.intervals = self.params['intervals']
        self.connector.set_params(self.params)

        self.log('LW is starting', slack=True)

        open_orders = self.remove_safety_before_init(
            self.connector.orders_price_ordering(
                self.connector.get_orders(
                    self.params['market'])))
        self.open_orders = self.strat_init(open_orders)
        self.set_safety_orders()
        self.id_list = helper.generate_list(len(self.intervals))
        self.update_id_list()

    def main(self):
        self.lw_initialisation()
        while True:
            self.log(f'{convert.datetime_to_string(datetime.now())} CYCLE START',
                     level='info', print_=True)
            orders = self.safety_orders_checkpoint(self.remove_orders_off_strat(
                self.connector.orders_price_ordering(
                    self.connector.get_orders(
                        self.params['market']))))

            if orders:
                orders = self.check_if_no_orders(orders)
                self.compare_orders(orders)
                self.update_id_list()
                self.limit_nb_orders()
                self.set_safety_orders()
                self.update_id_list()

            self.log(f'{convert.datetime_to_string(datetime.now())} CYCLE STOP',
                     level='info', print_=True)
            sleep(5)


if __name__ == "__main__":
    LazyWhale().main()
