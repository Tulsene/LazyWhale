import json
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from time import sleep

import ccxt

import utils.helpers as helper
import utils.converters as convert
from main.allocation import NoSpecificAllocation, LinearAllocation, CurvedAllocation, \
    ProfitAllocation, AbstractAllocation
from main.interval import Interval
from main.order import Order
from ui.user_interface import UserInterface
from utils.checkers import is_equal_decimal
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
        # calculated properly in set_min_amount
        self.min_amount = Decimal('0')
        self.remaining_amount_to_open_buy = Decimal('0')
        self.remaining_amount_to_open_sell = Decimal('0')
        self.allocation = None

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

    def strat_init(self):
        """Prepare open orders on the market by asking to the user if he want
        to remove some outside the strategy or remove those that don't have
        the right amount of alts.
        return: dict, of open orders used for the strategy.
        """
        self.log('strat_init()')
        self.set_min_amount()
        self.connector.intervals = self.intervals

        lowest_buy, highest_sell = self.get_lowest_highest_interval_index()

        self.log(
            f'self.intervals: {self.intervals}, '
            f'lowest_buy: {lowest_buy}, self.params["spread_bot"]: '
            f"{self.params['spread_bot']}, self.params['spread_top']: "
            f"{self.params['spread_top']}, highest_sell: {highest_sell}",
            level='info', print_=True)

        # TODO: understand, what this code does
        # orders_to_remove = {'sell': [], 'buy': []}
        # remaining_orders_price = {'buy': [], 'sell': []}
        # orders_to_remove['buy'] = self.init_remove_orders('buy',
        #                                                   open_orders['buy'],
        #                                                   lowest_buy,
        #                                                   self.params['spread_bot'],
        #                                                   orders_to_remove['buy'])
        # orders_to_remove['sell'] = self.init_remove_orders('sell',
        #                                                    open_orders['sell'],
        #                                                    self.params['spread_top'],
        #                                                    highest_sell,
        #                                                    orders_to_remove['sell'])
        #
        # for side in self.sides:
        #     open_orders, remaining_orders_price = self.update_orders(side,
        #                                                              open_orders, orders_to_remove,
        #                                                              remaining_orders_price)
        #
        # self.log(
        #     f'orders_to_remove: {orders_to_remove}, open_orders: {open_orders}'
        #     f', remaining_orders_price: {remaining_orders_price}',
        #     level='debug')

        self.set_first_intervals()

    # TODO: rewrite due to new functionality
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

    def get_lowest_highest_interval_index(self):
        lowest_interval = max(0, self.params['spread_bot'] - self.params['nb_buy_to_display'] + 1)
        highest_interval = min(len(self.intervals), self.params['spread_top'] + self.params['nb_sell_to_display'] - 1)
        return lowest_interval, highest_interval

    def set_first_intervals(self) -> None:
        """Open intervals due to parameters and store in the self.intervals:
        spread_bot - index of bottom interval
        spread_top - index of top interval
        nb_buy_to_display - number intervals to buy
        nb_sell_to_display - number intervals to sell
        amount - total amount of MANA in each interval (except not fulfilled)
        orders_per_interval - amount of orders in each intervals (except not fully)
        """
        lowest_interval, highest_interval = self.get_lowest_highest_interval_index()
        existing_intervals = self.connector.get_intervals()

        opened_buy = []
        opened_sell = []

        for interval_idx in reversed(range(lowest_interval, self.params['spread_bot'] + 1)):
            if not is_equal_decimal(existing_intervals[interval_idx].get_buy_orders_amount()
                                    + existing_intervals[interval_idx + 2].get_sell_orders_amount(),
                                    self.allocation.get_amount(interval_index=interval_idx, side='buy')):

                # TODO: redo here canceling all orders
                if existing_intervals[interval_idx].get_buy_orders():
                    self.connector.cancel_orders(existing_intervals[interval_idx].get_buy_orders())

                opened_buy.extend(self.connector.set_several_buy(
                    self.intervals[interval_idx]
                        .generate_orders_by_amount(self.allocation.get_amount(interval_index=interval_idx, side='buy'),
                                                   self.min_amount,
                                                   self.params['orders_per_interval'])
                ))

        for interval_idx in range(self.params['spread_top'], highest_interval + 1):
            if not is_equal_decimal(existing_intervals[interval_idx].get_sell_orders_amount()
                                    + existing_intervals[interval_idx - 2].get_buy_orders_amount(),
                                    self.allocation.get_amount(interval_index=interval_idx, side='sell')):

                # TODO: redo here canceling all orders
                if existing_intervals[interval_idx].get_sell_orders():
                    self.connector.cancel_orders(existing_intervals[interval_idx].get_sell_orders())

                opened_sell.extend(self.connector.set_several_sell(
                    self.intervals[interval_idx]
                        .generate_orders_by_amount(self.allocation.get_amount(interval_index=interval_idx, side='sell'),
                                                   self.min_amount,
                                                   self.params['orders_per_interval'])
                ))

        helper.populate_intervals(self.intervals, opened_buy)
        helper.populate_intervals(self.intervals, opened_sell)

    def set_safety_orders(self):
        """Add safety orders to lock funds for the strategy.
        lowest_buy_index: int.
        highest_sell_index: int."""
        lowest_interval, highest_interval = self.get_lowest_highest_interval_index()
        self.log(
            f'set_safety_orders(), lowest_buy_index: {lowest_interval}, '
            f'highest_sell_index: {highest_interval}')

        if lowest_interval > 0:
            self.create_safety_buy(lowest_interval)

        if highest_interval < len(self.intervals) - 1:
            self.create_safety_sell(highest_interval)

        self.log(
            f'safety buy: {self.connector.get_safety_buy()} , '
            f'safety sell: {self.connector.get_safety_sell()}')

    def create_safety_buy(self, lowest_buy_index):
        buy_sum = Decimal('0')
        index = lowest_buy_index - 1
        while index >= 0:
            buy_sum += convert.divider(
                convert.multiplier(self.allocation.get_amount(interval_index=index, side='buy'),
                                   self.intervals[index].get_top()),
                self.safety_buy_value)
            index -= 1

        self.log(f'buy_sum: {buy_sum}, lowest_buy_index: {lowest_buy_index}',
                 level='debug')

        self.connector.init_limit_buy_order(self.params['market'], buy_sum, self.safety_buy_value)

    def create_safety_sell(self, highest_sell_index):
        sell_sum = Decimal('0')
        index = highest_sell_index + 1

        while index < len(self.intervals):
            sell_sum += self.allocation.get_amount(interval_index=index, side='sell')
            index += 1

        self.log(f'sell_sum: {sell_sum}, highest_sell_index: '
                 f'{highest_sell_index}, max_index: '
                 f'{index}')

        self.connector.init_limit_sell_order(self.params['market'], sell_sum, self.safety_sell_value)

    def cancel_safety_orders(self):
        self.cancel_safety_buy()
        self.cancel_safety_sell()

    def cancel_safety_buy(self):
        safety_buy = self.connector.get_safety_buy()
        if safety_buy:
            self.connector.cancel_order(safety_buy)

    def cancel_safety_sell(self):
        safety_sell = self.connector.get_safety_sell()
        if safety_sell:
            self.connector.cancel_order(safety_sell)

    # TODO: rewrite due to new functionality
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

    def cancel_all_intervals(self):
        """Cancel all orders inside all intervals and make self.intervals empty"""
        for interval in self.intervals:
            self.connector.cancel_orders(interval.get_buy_orders())
            self.connector.cancel_orders(interval.get_sell_orders())

        self.intervals = deepcopy(self.connector.empty_intervals)
        self.cancel_safety_orders()

    def cancel_buy_interval_by_index(self, intervals, index):
        """Cancel all buys inside interval from market and from intervals"""
        self.connector.cancel_orders(intervals[index].get_buy_orders())
        intervals[index].remove_buy_orders()

    def cancel_sell_interval_by_index(self, intervals, index):
        """Cancel all sells inside interval from market and from intervals"""
        self.connector.cancel_orders(intervals[index].get_sell_orders())
        intervals[index].remove_sell_orders()

    def when_bottom_is_reached(self):
        """Stop if stop_at_bot"""
        if self.params['stop_at_bot']:
            self.cancel_safety_orders()
            self.cancel_all_intervals()
            self.log(f'Bottom target reached!',
                     level='critical', slack=True, print_=True)
            raise SystemExit()

    def when_top_is_reached(self):
        """Stop if stop_at_top"""
        if self.params['stop_at_bot']:
            self.cancel_safety_orders()
            self.cancel_all_intervals()
            self.log(f'Top target reached!',
                     level='critical', slack=True, print_=True)
            raise SystemExit()

    def amount_compare_intervals(self, new_intervals: [Interval]) -> (Decimal, Decimal):
        """Compare intervals and return amount of MANA to open with correct side"""
        interval_index = 0
        amount_to_open_sell = Decimal('0')
        amount_to_open_buy = Decimal('0')

        while interval_index < len(new_intervals):
            if self.intervals[interval_index] != new_intervals[interval_index]:
                amount_consumed_buy = helper.get_amount_to_open(self.intervals[interval_index].get_buy_orders(),
                                                                new_intervals[interval_index].get_buy_orders())
                amount_to_open_sell += amount_consumed_buy

                if isinstance(self.allocation, ProfitAllocation):
                    if amount_consumed_buy > self.allocation.amount:
                        self.allocation.benefits[interval_index] \
                            .subtract_actual_benefit(amount_consumed_buy - self.allocation.amount)

                amount_to_open_buy += helper.get_amount_to_open(self.intervals[interval_index].get_sell_orders(),
                                                                new_intervals[interval_index].get_sell_orders())

            interval_index += 1

        return amount_to_open_buy, amount_to_open_sell

    def get_spread_bot(self, intervals: [Interval]) -> int:
        """Returns highest buy interval with amount >= params['amount']"""
        buy_indexes = helper.get_indexes_buy_intervals(intervals)

        for index in reversed(buy_indexes):
            if intervals[index].get_buy_orders_amount() > self.allocation.get_amount(index, 'buy') \
                    or is_equal_decimal(intervals[index].get_buy_orders_amount(),
                                        self.allocation.get_amount(index, 'buy')):
                return index

        # fail safe
        if buy_indexes:
            return buy_indexes[-1]
        else:
            # TODO: should not be at all
            assert 1 == 0

    def get_spread_top(self, intervals: [Interval]) -> int:
        """Returns lowest sell interval with amount >= params['amount']"""
        sell_indexes = helper.get_indexes_sell_intervals(intervals)
        for index in sell_indexes:
            if intervals[index].get_sell_orders_amount() > self.allocation.get_amount(index, 'sell') \
                    or is_equal_decimal(intervals[index].get_sell_orders_amount(),
                                        self.allocation.get_amount(index, 'sell')):
                return index

        # fail safe
        if sell_indexes:
            return sell_indexes[-1]
        else:
            # TODO: should be at all
            assert 1 == 0

    def where_to_open_buys(self, new_intervals: [Interval], amount_to_open_buy: Decimal):
        """Decide, depending on amount_to_open and new_intervals, where to open intervals"""
        buy_intervals_to_open = []
        buy_indexes = helper.get_indexes_buy_intervals(new_intervals)
        buy_step = 1
        if buy_indexes:
            highest_buy_index = buy_indexes[-1]
        else:
            buy_step *= -1
            sell_indexes = helper.get_indexes_sell_intervals(new_intervals)
            if sell_indexes:
                highest_buy_index = self.get_spread_top(new_intervals) - 3
            else:
                highest_buy_index = self.params['spread_bot']

        intervals_opened_counter = 0
        while amount_to_open_buy > convert.multiplier(self.min_amount, self.params['orders_per_interval']):
            # fail safe, if interval will go so high
            if highest_buy_index >= len(new_intervals):
                self.when_top_is_reached()

            # fail safe, if interval will go so low
            elif highest_buy_index < 0 and not buy_indexes:
                highest_buy_index = self.params['spread_bot']
                buy_step *= -1

            # if opened more that enough, when there were no more buy_indexes
            elif intervals_opened_counter >= self.params['nb_buy_to_display'] and not buy_indexes:
                index_to_open = max(self.params['spread_bot'], highest_buy_index) + 1
                amount_to_open = min(self.allocation.get_amount(index_to_open, 'buy'), amount_to_open_buy)
                buy_intervals_to_open.append({
                    "interval_index": index_to_open,
                    "amount": amount_to_open,
                })
                amount_to_open_buy -= amount_to_open

            # main purpose - when each order just at correct position
            else:
                highest_buy_amount = new_intervals[highest_buy_index].get_buy_orders_amount()
                missing_amount = self.allocation.get_amount(highest_buy_index, 'buy') - highest_buy_amount
                if missing_amount > Decimal('0'):
                    self.cancel_buy_interval_by_index(new_intervals, highest_buy_index)
                    amount_to_open = min(self.allocation.get_amount(highest_buy_index, 'buy'),
                                         highest_buy_amount + amount_to_open_buy)
                    buy_intervals_to_open.append({
                        "interval_index": highest_buy_index,
                        "amount": amount_to_open,
                    })

                    amount_to_open_buy -= missing_amount

            highest_buy_index += buy_step
            intervals_opened_counter += 1

        # end while
        if amount_to_open_buy > Decimal('0'):
            self.remaining_amount_to_open_buy += amount_to_open_buy

        return buy_intervals_to_open

    def where_to_open_sells(self, new_intervals: [Interval], amount_to_open_sell: Decimal):
        """Decide, depending on amount_to_open and new_intervals, where to open intervals"""
        sell_intervals_to_open = []
        sell_indexes = helper.get_indexes_sell_intervals(new_intervals)
        sell_step = -1
        if sell_indexes:
            lowest_sell_index = sell_indexes[0]
        else:
            sell_step *= -1
            buy_indexes = helper.get_indexes_buy_intervals(new_intervals)
            if buy_indexes:
                lowest_sell_index = self.get_spread_bot(new_intervals) + 3
            else:
                lowest_sell_index = self.params['spread_top']

        intervals_opened_counter = 0
        while amount_to_open_sell > convert.multiplier(self.min_amount, self.params['orders_per_interval']):
            # fail safe, if interval will go so low
            if lowest_sell_index < 0:
                self.when_bottom_is_reached()

            # fail safe, if interval will go so high
            elif lowest_sell_index >= len(self.intervals) and not sell_indexes:
                lowest_sell_index = self.params['spread_top']
                sell_step *= -1

            # if opened more that enough, when there were no more sell_indexes
            elif intervals_opened_counter >= self.params['nb_buy_to_display'] and not sell_indexes:
                index_to_open = min(self.params['spread_top'], lowest_sell_index) - 1
                amount_to_open = min(self.allocation.get_amount(index_to_open, 'sell'), amount_to_open_sell)
                sell_intervals_to_open.append({
                    "interval_index": index_to_open,
                    "amount": amount_to_open,
                })
                amount_to_open_sell -= amount_to_open

            # main purpose - when each order just at correct position
            else:
                lowest_sell_amount = new_intervals[lowest_sell_index].get_sell_orders_amount()
                missing_amount = self.allocation.get_amount(lowest_sell_index, 'sell') - lowest_sell_amount
                if missing_amount > Decimal('0'):
                    # cancel existing orders
                    self.cancel_sell_interval_by_index(new_intervals, lowest_sell_index)
                    amount_to_open = min(self.allocation.get_amount(lowest_sell_index, 'sell'),
                                         lowest_sell_amount + amount_to_open_sell)
                    sell_intervals_to_open.append({
                        "interval_index": lowest_sell_index,
                        "amount": amount_to_open,
                    })
                    amount_to_open_sell -= missing_amount

            lowest_sell_index += sell_step
            intervals_opened_counter += 1

        # end while
        if amount_to_open_sell > Decimal('0'):
            self.remaining_amount_to_open_sell += amount_to_open_sell

        return sell_intervals_to_open

    def update_benefits(self, buy_intervals_to_open: [dict]) -> None:
        """Set benefits for profit allocation for intervals to open, changes amount due to profit rules
        buy_intervals_to_open: {
            'interval_index': index,
            'amount': amount,
        }
        """
        assert isinstance(self.allocation, ProfitAllocation)
        for interval in buy_intervals_to_open:
            prev_actual_benefit = self.allocation.benefits[interval['interval_index']].get_actual_benefit()
            self.allocation.set_benefit(interval['interval_index'], interval['amount'])
            additional_benefit = self.allocation.benefits[interval['interval_index']] \
                                     .get_actual_benefit() - prev_actual_benefit
            interval['amount'] += additional_benefit

    def prepare_orders(self, intervals: [dict]) -> [Order]:
        """Prepare orders for opening
        intervals: {
            'interval_index': index,
            'amount': amount,
        }
        """
        orders = []
        for interval in intervals:
            orders.extend(self.intervals[interval['interval_index']]
                          .generate_orders_by_amount(interval['amount'],
                                                     self.min_amount,
                                                     self.params['orders_per_interval']))

        return orders

    def execute_new_orders(self, new_intervals, buy_orders_to_open, sell_orders_to_open):
        """Open orders saved them in new_intervals and return new_intervals"""
        if buy_orders_to_open:
            buy_orders = self.connector.set_several_buy(buy_orders_to_open)

            if buy_orders:
                new_intervals = helper.populate_intervals(new_intervals, buy_orders)

        if sell_orders_to_open:
            sell_orders = self.connector.set_several_sell(sell_orders_to_open)

            if sell_orders:
                new_intervals = helper.populate_intervals(new_intervals, sell_orders)

        return new_intervals

    def compare_intervals(self, new_intervals: [Interval]) -> None:
        """Compares intervals and opens new orders and saves them in self.intervals"""
        assert len(self.intervals) == len(new_intervals)
        amount_to_open_buy, amount_to_open_sell = self.amount_compare_intervals(new_intervals)
        if amount_to_open_buy == amount_to_open_sell == Decimal('0'):
            return

        if self.remaining_amount_to_open_buy > Decimal('0'):
            amount_to_open_buy += self.remaining_amount_to_open_buy
            self.remaining_amount_to_open_buy = Decimal('0')

        if self.remaining_amount_to_open_sell > Decimal('0'):
            amount_to_open_sell += self.remaining_amount_to_open_sell
            self.remaining_amount_to_open_sell = Decimal('0')

        amount_buys = len(helper.get_indexes_buy_intervals(new_intervals))
        amount_sells = len(helper.get_indexes_sell_intervals(new_intervals))

        # some cheats to use things, that spread_bot - spread_top = 3
        if amount_buys > 0 and amount_sells > 0:
            buy_intervals_to_open = self.where_to_open_buys(new_intervals, amount_to_open_buy)
            sell_intervals_to_open = self.where_to_open_sells(new_intervals, amount_to_open_sell)

        elif amount_buys > 0:
            buy_intervals_to_open = self.where_to_open_buys(new_intervals, amount_to_open_buy)
            if isinstance(self.allocation, ProfitAllocation):
                self.update_benefits(buy_intervals_to_open)

            buy_orders_to_open = self.prepare_orders(buy_intervals_to_open)
            self.execute_new_orders(new_intervals, buy_orders_to_open, [])
            buy_intervals_to_open = []
            sell_intervals_to_open = self.where_to_open_sells(new_intervals, amount_to_open_sell)

        elif amount_sells > 0:
            sell_intervals_to_open = self.where_to_open_sells(new_intervals, amount_to_open_sell)
            sell_orders_to_open = self.prepare_orders(sell_intervals_to_open)
            self.execute_new_orders(new_intervals, [], sell_orders_to_open)
            sell_intervals_to_open = []
            buy_intervals_to_open = self.where_to_open_buys(new_intervals, amount_to_open_buy)

        else:
            sell_intervals_to_open = self.where_to_open_sells(new_intervals, amount_to_open_sell)
            buy_intervals_to_open = self.where_to_open_buys(new_intervals, amount_to_open_buy)

        if isinstance(self.allocation, ProfitAllocation):
            self.update_benefits(buy_intervals_to_open)

        buy_orders_to_open = self.prepare_orders(buy_intervals_to_open)
        sell_orders_to_open = self.prepare_orders(sell_intervals_to_open)
        self.intervals = self.execute_new_orders(new_intervals, buy_orders_to_open, sell_orders_to_open)

    def backup_spread_value(self):
        """Set correct spread bot and spread top depending on currently opened intervals"""
        buy_indexes = helper.get_indexes_buy_intervals(self.intervals)
        sell_indexes = helper.get_indexes_sell_intervals(self.intervals)

        if not buy_indexes:
            self.when_bottom_is_reached()
            self.params['spread_bot'] = 0
            self.params['spread_top'] = 3
        elif not sell_indexes:
            self.when_top_is_reached()
            self.params['spread_bot'] = len(self.intervals) - 4
            self.params['spread_top'] = len(self.intervals) - 1
        else:
            self.params['spread_bot'] = self.get_spread_bot(self.intervals)
            self.params['spread_top'] = self.params['spread_bot'] + 3

        helper.params_writer(f'{self.root_path}config/params.json', self.params)

    def cancel_extra_buy_interval(self):
        """When there is more than needed buy intervals are active - close it"""
        buy_indexes = helper.get_indexes_buy_intervals(self.intervals)
        self.cancel_buy_interval_by_index(self.intervals, buy_indexes[0])

    def cancel_extra_sell_interval(self):
        """When there is more than needed sell intervals are active - close it"""
        sell_indexes = helper.get_indexes_sell_intervals(self.intervals)
        self.cancel_sell_interval_by_index(self.intervals, sell_indexes[-1])

    def open_deficit_buy_interval(self):
        """When there is less than needed buy intervals are active - open it"""
        sell_indexes = helper.get_indexes_sell_intervals(self.intervals)
        buy_indexes = helper.get_indexes_buy_intervals(self.intervals)
        buy_orders = []
        if len(buy_indexes) > 0:
            if buy_indexes[0] - 1 >= 0:
                buy_orders = self.connector.set_several_buy(
                    self.intervals[buy_indexes[0] - 1]
                        .generate_orders_by_amount(self.allocation.get_amount(buy_indexes[0] - 1, 'buy'),
                                                   self.min_amount)
                )
        elif len(sell_indexes) >= 0 and sell_indexes[0] - 3 >= 0:
            buy_orders = self.connector.set_several_buy(
                self.intervals[sell_indexes[0] - 3]
                    .generate_orders_by_amount(self.allocation.get_amount(sell_indexes[0] - 3, 'buy'),
                                               self.min_amount)
            )

        helper.populate_intervals(self.intervals, buy_orders)

    def open_deficit_sell_interval(self):
        """When there is more than needed sell intervals are active - open it"""
        sell_indexes = helper.get_indexes_sell_intervals(self.intervals)
        buy_indexes = helper.get_indexes_buy_intervals(self.intervals)
        sell_orders = []
        if len(sell_indexes) > 0:
            if sell_indexes[-1] + 1 < len(self.intervals):
                sell_orders = self.connector.set_several_sell(
                    self.intervals[sell_indexes[-1] + 1]
                        .generate_orders_by_amount(self.allocation.get_amount(sell_indexes[-1] + 1, 'sell'),
                                                   self.min_amount)
                )
        elif len(buy_indexes) >= 0 and buy_indexes[-1] + 3 < len(self.intervals):
            sell_orders = self.connector.set_several_sell(
                self.intervals[buy_indexes[-1] + 3]
                    .generate_orders_by_amount(self.allocation.get_amount(buy_indexes[-1] + 3, 'sell'),
                                               self.min_amount)
            )
        helper.populate_intervals(self.intervals, sell_orders)

    def limit_nb_intervals(self):
        buy_indexes = helper.get_indexes_buy_intervals(self.intervals)
        sell_indexes = helper.get_indexes_sell_intervals(self.intervals)
        nb_buy_intervals = len(buy_indexes)
        nb_sell_intervals = len(sell_indexes)

        # TODO: think about non-fully filled - cause it will close, if they exist
        for _ in range(abs(nb_buy_intervals - nb_sell_intervals)):
            if nb_buy_intervals > self.params['nb_buy_to_display'] \
                    and buy_indexes[-1] == self.get_spread_bot(self.intervals):
                self.cancel_extra_buy_interval()

            if nb_sell_intervals > self.params['nb_sell_to_display'] \
                    and sell_indexes[0] == self.get_spread_top(self.intervals):
                self.cancel_extra_sell_interval()

            if self.params['spread_bot'] - self.params['nb_buy_to_display'] + 1 >= 0 \
                    and nb_buy_intervals < self.params['nb_buy_to_display']:
                self.open_deficit_buy_interval()

            if self.params['spread_top'] + self.params['nb_sell_to_display'] - 1 < len(self.intervals) \
                    and nb_sell_intervals < self.params['nb_sell_to_display']:
                self.open_deficit_sell_interval()

            nb_buy_intervals = len(helper.get_indexes_buy_intervals(self.intervals))
            nb_sell_intervals = len(helper.get_indexes_sell_intervals(self.intervals))

    def check_intervals_equal(self, new_intervals):
        return self.intervals == new_intervals

    def set_min_amount(self):
        """In crypto there is a minimal value for each order to open
        Due to this - lets calculate minimal amount for order to open"""
        lowest_price = self.intervals[0].get_bottom()
        self.min_amount = convert.divider(config.MIN_VALUE_ORDER, lowest_price)

    def choose_allocation(self) -> AbstractAllocation:
        if self.params['allocation_type'] == 'no_specific_allocation':
            return NoSpecificAllocation(self.params['amount'])

        if self.params['allocation_type'] == 'linear_allocation':
            return LinearAllocation(self.params['amount'],
                                    convert.multiplier(self.params['amount'], config.MAX_AMOUNT_COEFFICIENT),
                                    len(self.intervals), start_index=0)

        if self.params['allocation_type'] == 'curved_allocation':
            return CurvedAllocation(convert.multiplier(self.params['amount'], config.LOWEST_AMOUNT_COEFFICIENT),
                                    convert.multiplier(self.params['amount'], config.MIDDLE_AMOUNT_COEFFICIENT),
                                    convert.multiplier(self.params['amount'], config.HIGHEST_AMOUNT_COEFFICIENT),
                                    len(self.intervals))

        if self.params['allocation_type'] == 'profit_allocation':
            return ProfitAllocation(self.intervals, self.params['profits_alloc'], self.fees_coef, self.params['amount'])

    def lw_initialisation(self):
        """Initializing parameters, check parameters then initialize LW.
        """
        if self.preset_params:
            params = self.ui.check_params(self.preset_params)
            self.params = self.ui.check_for_enough_funds(params)
        else:
            self.params = self.ui.ask_for_params()  # f'{self.root_path}config/params.json')

        self.connector = self.params['api_connector']
        self.intervals = self.params['intervals']
        self.connector.set_params(self.params)
        self.allocation = self.choose_allocation()

        # TODO: do not cancel all existing orders
        self.connector.cancel_all(self.params['market'])

        self.log('LW is starting', slack=True)

        self.strat_init()
        self.set_safety_orders()

    def main_cycle(self):
        """One cycle of LW activity"""
        new_intervals = self.connector.get_intervals()
        is_equal = self.check_intervals_equal(new_intervals)
        if not is_equal:
            self.cancel_safety_orders()
            self.compare_intervals(new_intervals)

            self.limit_nb_intervals()
            self.backup_spread_value()

            self.set_safety_orders()

    def main(self):
        self.lw_initialisation()
        while True:
            self.log(f'{convert.datetime_to_string(datetime.now())} CYCLE START',
                     level='info', print_=True)
            # orders = self.safety_orders_checkpoint(self.remove_orders_off_strat(
            #     self.connector.orders_price_ordering(
            #         self.connector.get_orders(
            #             self.params['market']))))

            # core functionality is here
            self.main_cycle()

            self.log(f'{convert.datetime_to_string(datetime.now())} CYCLE STOP',
                     level='info', print_=True)
            sleep(config.LW_CYCLE_SLEEP_TIME)
