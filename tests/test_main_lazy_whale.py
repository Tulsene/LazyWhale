from copy import deepcopy
from decimal import Decimal
from unittest import TestCase

from mock import patch

from exchanges.api_manager import APIManager
from exchanges.zebitexFormatted import ZebitexFormatted
from main.lazy_whale import LazyWhale
from utils import helpers
from utils.converters import multiplier, divider
from utils.helpers import interval_generator
from utils.logger import Logger

import tests.keys as keys_config


def patch_log_formatter(*args, **kwargs):
    timestamp = 12345
    date = 'test'
    return timestamp, date


class LazyWhaleTests(TestCase):
    @patch('utils.helpers.set_root_path')
    def setUp(self, set_root_path_patch) -> None:
        set_root_path_patch.return_value = keys_config.PATH_TO_PROJECT_ROOT

        self.market = "DASH/BTC"
        self.intervals = interval_generator(Decimal('0.01'), Decimal('0.015'),
                                            Decimal('1') + Decimal('1.02') / Decimal('100'))

        # Another user for testing purpose
        self.user = ZebitexFormatted(keys_config.ANOTHER_USER_API_KEY, keys_config.ANOTHER_USER_SECRET, True)

        with patch.object(Logger, "__init__", lambda x, name, slack_webhook=None: None):
            self.api_manager = APIManager(keys_config.SLACK_WEBHOOK, Decimal('1E-8'), Decimal('1'))
            self.lazy_whale = LazyWhale()

        self.api_manager.log = Logger(name='api_manager',
                                      slack_webhook=keys_config.SLACK_WEBHOOK,
                                      common_path=keys_config.PATH_TO_PROJECT_ROOT).log
        self.api_manager.intervals = deepcopy(self.intervals)
        self.api_manager.empty_intervals = deepcopy(self.api_manager.intervals)
        keys = {
            "apiKey": keys_config.BOT_API_KEY,
            "secret": keys_config.BOT_SECRET,
        }
        self.api_manager.set_zebitex(keys, "zebitex_testnet")
        self.api_manager.market = self.market
        self.api_manager.cancel_all(self.market)
        self.api_manager.fees_coef = Decimal('0.9975')
        self.lazy_whale.intervals = deepcopy(self.intervals)
        self.lazy_whale.sides = ('buy', 'sell')
        self.lazy_whale.connector = self.api_manager

        self.api_manager.cancel_all(self.market)
        self.lazy_whale.fees_coef = Decimal('0.9975')
        self.lazy_whale.min_amount = Decimal('0')
        self.lazy_whale.log = Logger(name='main',
                                     slack_webhook=keys_config.SLACK_WEBHOOK,
                                     common_path=keys_config.PATH_TO_PROJECT_ROOT).log
        self.lazy_whale.params = {
            "orders_per_interval": 2,
        }

    def tearDown(self) -> None:
        self.api_manager.cancel_all(self.market)

    def test_amount_compare_intervals(self):
        """Testing amount compare intervals with only fully consumed orders and in range"""
        old_interval = deepcopy(self.intervals[3])
        new_interval = deepcopy(self.intervals[3])
        order1 = self.api_manager.create_limit_buy_order(self.market, Decimal('1'), Decimal('0.010324'))
        order2 = self.api_manager.create_limit_buy_order(self.market, Decimal('0.5'), Decimal('0.010364'))
        order3 = self.api_manager.create_limit_buy_order(self.market, Decimal('1'), Decimal('0.010394'))

        order4 = self.api_manager.create_limit_sell_order(self.market, Decimal('1'), Decimal('0.0104014'))
        order5 = self.api_manager.create_limit_sell_order(self.market, Decimal('1'), Decimal('0.0104094'))

        self.assertEqual(len(self.api_manager.get_open_orders()), 5)

        old_interval.insert_buy_order(order1)
        old_interval.insert_buy_order(order2)
        old_interval.insert_buy_order(order3)
        old_interval.insert_sell_order(order4)
        old_interval.insert_sell_order(order5)

        new_interval.insert_buy_order(order1)
        new_interval.insert_sell_order(order4)

        intervals = deepcopy(self.lazy_whale.intervals)

        self.lazy_whale.intervals[3] = old_interval
        intervals[3] = new_interval

        amounts_to_open = self.lazy_whale.amount_compare_intervals(intervals)

        correct_amounts_to_open = [
            {
                "interval_idx": 5,
                "side": 'sell',
                "amount": Decimal('1.5'),
            },
            {
                "interval_idx": 1,
                "side": 'buy',
                "amount": Decimal('1'),
            },
        ]

        self.assertEqual(amounts_to_open, correct_amounts_to_open)

    def test_compare_intervals(self):
        """Tests that comparing intervals is correct and is doing by the strategy
        When order, known by LW, have been consumed or not fully consumed,
        LW should open a new opposite order +2/-2 intervals higher/lower
        """
        initial_buy_orders = [
            {
                "price": Decimal("0.01022234"),
                "amount": Decimal("0.01"),
            },
            {
                "price": Decimal("0.01022345"),
                "amount": Decimal("0.02"),
            },
            {
                "price": Decimal("0.0102244"),
                "amount": Decimal("0.01"),
            },
        ]

        initial_sell_orders = [
            {
                "price": Decimal("0.01023234"),
                "amount": Decimal("0.01"),
            },
            {
                "price": Decimal("0.01023345"),
                "amount": Decimal("0.02"),
            },
            {
                "price": Decimal("0.01023534"),
                "amount": Decimal("0.01"),
            },
        ]

        buy_orders = self.api_manager.set_several_buy(initial_buy_orders)
        sell_orders = self.api_manager.set_several_sell(initial_sell_orders)
        self.assertEqual(len(self.api_manager.get_open_orders()), 6)

        self.lazy_whale.intervals = self.api_manager.get_intervals(self.market)

        # Set buy order by another user to consume LW order
        self.user.create_limit_buy_order(self.market, price=Decimal("0.01023234"), amount=Decimal("0.01"))
        self.assertEqual(len(self.api_manager.get_open_orders()), 5)

        self.lazy_whale.compare_intervals(self.api_manager.get_intervals(self.market))
        self.assertEqual(self.lazy_whale.intervals, self.api_manager.get_intervals(self.market))

        self.assertEqual(len(self.api_manager.get_open_orders()), 7)
        self.assertEqual(len(self.lazy_whale.intervals[0].get_buy_orders()), 2)
        self.assertEqual(self.lazy_whale.intervals[0].get_buy_orders_amount(), sell_orders[0].amount)

        # Set sell order by another user to consume the half of LW order
        self.user.create_limit_sell_order(self.market, price=Decimal("0.0102244"), amount=Decimal("0.004"))
        self.assertEqual(len(self.api_manager.get_open_orders()), 7)

        self.lazy_whale.compare_intervals(self.api_manager.get_intervals(self.market))
        self.assertEqual(self.lazy_whale.intervals, self.api_manager.get_intervals(self.market))

        self.assertEqual(len(self.api_manager.get_open_orders()), 9)
        self.assertEqual(len(self.lazy_whale.intervals[4].get_sell_orders()), 2)
        self.assertEqual(self.lazy_whale.intervals[4].get_sell_orders_amount(), Decimal('0.004'))

        # Set one more buy order to check, if orders will be canceled and reopened when compare intervals happen
        self.user.create_limit_buy_order(self.market, price=Decimal("0.01023345"), amount=Decimal("0.01"))
        self.assertEqual(len(self.api_manager.get_open_orders()), 9)

        self.lazy_whale.compare_intervals(self.api_manager.get_intervals(self.market))
        self.assertEqual(self.lazy_whale.intervals, self.api_manager.get_intervals(self.market))

        self.assertEqual(len(self.api_manager.get_open_orders()), 9)
        self.assertEqual(len(self.lazy_whale.intervals[0].get_buy_orders()), 2)
        self.assertEqual(self.lazy_whale.intervals[0].get_buy_orders_amount(), Decimal('0.02'))

    def test_set_first_intervals(self):
        """Tests that first intervals are set using params"""
        spread_bot = 4
        spread_top = 7
        buy_display = 3
        sell_display = 3
        amount = Decimal('0.01')
        orders_per_interval = 2

        self.lazy_whale.params['spread_bot'] = spread_bot  # index of interval
        self.lazy_whale.params['spread_top'] = spread_top  # index of interval

        self.lazy_whale.params['nb_buy_to_display'] = buy_display  # number intervals to buy
        self.lazy_whale.params['nb_sell_to_display'] = sell_display  # number intervals to sell

        self.lazy_whale.params['amount'] = amount  # total amount to open in each interval (except not fully)
        self.lazy_whale.params['orders_per_interval'] = orders_per_interval  # amount of orders in each intervals (
        # except not fully)

        self.lazy_whale.set_first_intervals()

        intervals = self.api_manager.get_intervals(self.market)

        self.assertEqual(
            len(self.api_manager.get_open_orders(self.market)),
            (buy_display + sell_display) * orders_per_interval
        )

        for i in range(spread_bot - buy_display + 1, spread_bot + 1):
            self.assertEqual(len(intervals[i].get_buy_orders()), orders_per_interval)
            self.assertEqual(intervals[i].get_buy_orders_amount(), amount)

        for i in range(spread_top, spread_top + sell_display):
            self.assertEqual(len(intervals[i].get_sell_orders()), orders_per_interval)
            self.assertEqual(intervals[i].get_sell_orders_amount(), amount)

    def test_create_safety_buy(self):
        lowest_buy_index = 3
        amount = Decimal('0.01')
        self.lazy_whale.params['amount'] = amount
        self.lazy_whale.params['market'] = 'DASH/BTC'
        self.lazy_whale.safety_buy_value = Decimal('0.00000001')
        correct_amount = Decimal('0')

        for i in range(0, lowest_buy_index):
            correct_amount += multiplier(self.lazy_whale.params['amount'], self.intervals[i].get_top())

        correct_amount = divider(correct_amount, self.lazy_whale.safety_buy_value)

        self.assertIsNone(self.api_manager.get_safety_buy())
        self.lazy_whale.create_safety_buy(lowest_buy_index)
        self.assertIsNotNone(self.api_manager.get_safety_buy())
        self.assertEqual(self.api_manager.get_safety_buy().price, self.lazy_whale.safety_buy_value)
        self.assertEqual(self.api_manager.get_safety_buy().amount, correct_amount)

    def test_create_safety_sell(self):
        highest_sell_value = 7
        amount = Decimal('0.01')
        self.lazy_whale.params['amount'] = amount
        self.lazy_whale.params['market'] = 'DASH/BTC'
        self.lazy_whale.safety_sell_value = Decimal('1')

        self.assertIsNone(self.api_manager.get_safety_sell())
        self.lazy_whale.create_safety_sell(highest_sell_value)
        self.assertIsNotNone(self.api_manager.get_safety_sell())
        self.assertEqual(self.api_manager.get_safety_sell().price, self.lazy_whale.safety_sell_value)
        self.assertEqual(self.api_manager.get_safety_sell().amount,
                         multiplier(amount, Decimal(str(len(self.intervals) - highest_sell_value - 1))))

    def test_limit_nb_intervals(self):
        """Test that nb of intervals is always beetween nb_to_display and nb_to_display + 1
        (except bot/top is reached)"""

        spread_bot = 4
        spread_top = 7
        buy_display = 3
        sell_display = 3
        amount = Decimal('0.01')
        orders_per_interval = 2

        self.lazy_whale.params['spread_bot'] = spread_bot  # index of interval
        self.lazy_whale.params['spread_top'] = spread_top  # index of interval

        self.lazy_whale.params['nb_buy_to_display'] = buy_display  # number intervals to buy
        self.lazy_whale.params['nb_sell_to_display'] = sell_display  # number intervals to sell

        self.lazy_whale.params['amount'] = amount  # total amount to open in each interval (except not fully)
        self.lazy_whale.params['orders_per_interval'] = orders_per_interval  # amount of orders in each intervals (
        # except not fully)

        self.lazy_whale.set_first_intervals()

        # fulfill one sell interval
        self.api_manager.create_limit_buy_order(self.market, amount, self.intervals[spread_top].get_top())

        self.assertEqual(len(self.api_manager.get_open_orders(self.market)),
                         (sell_display + buy_display - 1) * orders_per_interval)

        self.lazy_whale.compare_intervals(self.api_manager.get_intervals())

        self.assertEqual(len(self.api_manager.get_open_orders(self.market)),
                         (sell_display + buy_display) * orders_per_interval)

        self.assertEqual(len(self.lazy_whale.get_indexes_buy_intervals()), 4)
        self.assertEqual(len(self.lazy_whale.get_indexes_sell_intervals()), 2)

        self.lazy_whale.limit_nb_intervals()

        self.assertEqual(len(self.lazy_whale.get_indexes_buy_intervals()), 3)
        self.assertEqual(len(self.lazy_whale.get_indexes_sell_intervals()), 3)

        self.assertEqual(self.lazy_whale.intervals, self.api_manager.get_intervals())

        # TODO: this breaks params.json if tested
        # self.lazy_whale.backup_spread_value()
        #
        # self.assertEqual(self.lazy_whale.params['spread_bot'], spread_bot + 1)
        # self.assertEqual(self.lazy_whale.params['spread_top'], spread_top + 1)
