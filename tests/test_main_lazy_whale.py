from copy import deepcopy
from decimal import Decimal
from unittest import TestCase

from mock import patch

from exchanges.api_manager import APIManager
from exchanges.zebitexFormatted import ZebitexFormatted
from main.interval import Interval
from main.main import LazyWhale
from main.order import Order
from utils import helpers
from utils.helpers import interval_generator
from utils.logger import Logger

import tests.keys as keys_config


def patch_log_formatter(*args, **kwargs):
    timestamp = 12345
    date = 'test'
    return timestamp, date


class LazyWhaleTests(TestCase):
    def setUp(self) -> None:
        self.market = "DASH/BTC"
        self.intervals = interval_generator(Decimal('0.01'), Decimal('0.015'),
                                            Decimal('1') + Decimal('1.02') / Decimal('100'))

        # Another user for testing purpose
        self.user = ZebitexFormatted(keys_config.ANOTHER_USER_API_KEY, keys_config.ANOTHER_USER_SECRET, True)

        with patch.object(APIManager, "__init__", lambda x, y, z, a: None):
            # patch APIManager because Logger cant be created in test mode
            self.api_manager = APIManager(None, None, None)
            self.api_manager.log = Logger(name='api_manager',
                                          slack_webhook=keys_config.SLACK_WEBHOOK,
                                          common_path=keys_config.PATH_TO_PROJECT_ROOT).log
            self.api_manager.order_logger_formatter = patch_log_formatter
            self.api_manager.safety_buy_value = Decimal('1E-8')
            self.api_manager.safety_sell_value = Decimal('1')
            self.api_manager.root_path = helpers.set_root_path()
            self.api_manager.exchange = None
            self.api_manager.err_counter = 0
            self.api_manager.is_kraken = False
            self.api_manager.now = 0
            self.api_manager.fees_coef = 0
            self.api_manager.intervals = deepcopy(self.intervals)
            self.api_manager.empty_intervals = deepcopy(self.api_manager.intervals)
            self.api_manager.market = ''
            self.api_manager.profits_alloc = 0
            keys = {
                "apiKey": keys_config.BOT_API_KEY,
                "secret": keys_config.BOT_SECRET,
            }
            self.api_manager.set_zebitex(keys, "zebitex_testnet")
            self.api_manager.market = self.market
            self.api_manager.fees_coef = Decimal('0.9975')

        with patch.object(LazyWhale, "__init__", lambda x, y: None):
            self.lazy_whale = LazyWhale(False)
            self.lazy_whale.log = Logger(name='main',
                                         slack_webhook=keys_config.SLACK_WEBHOOK,
                                         common_path=keys_config.PATH_TO_PROJECT_ROOT).log

            self.lazy_whale.intervals = deepcopy(self.intervals)
            self.lazy_whale.sides = ('buy', 'sell')
            self.lazy_whale.connector = self.api_manager

            self.api_manager.cancel_all(self.market)
            self.lazy_whale.fees_coef = Decimal('0.9975')
            self.lazy_whale.min_amount = Decimal('0')
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

    # def test_compare_intervals_2(self):
    #     """More powerful test to check compare_intervals"""
    #     self.assertEqual(len(self.api_manager.get_open_orders()), 0)
    #     new_intervals = deepcopy(self.intervals)
    #
    #     count_orders = 10
    #     interval_len = len(self.intervals)
    #     for i in range(count_orders):
    #         buy_order = Order(idx=i, price=self.intervals[i].get_random_price_in_interval(),
    #                           amount=Decimal(i + 1) / Decimal(100),
    #                           side='buy', timestamp=i, date="1234")
    #
    #         self.lazy_whale.intervals[i].insert_buy_order(buy_order)
    #         new_intervals[i].insert_buy_order(buy_order)
    #
    #         sell_order = Order(idx=i, price=self.intervals[interval_len - i - 1].get_random_price_in_interval(),
    #                            amount=Decimal(i + 1) / Decimal(100),
    #                            side='sell', timestamp=i, date="1234")
    #
    #         self.lazy_whale.intervals[interval_len - i - 1].insert_sell_order(sell_order)
    #
    #     self.lazy_whale.compare_intervals(new_intervals)
    #     self.assertEqual(len(self.api_manager.get_open_orders()), count_orders)
    #     self.assertEqual(len(self.lazy_whale.intervals[interval_len - 1].get_sell_orders()), 0)
    #     self.assertEqual(len(self.lazy_whale.intervals[interval_len - count_orders].get_sell_orders()), 0)
    #     self.assertEqual(len(self.lazy_whale.intervals[interval_len - 1 - 2].get_buy_orders()), 1)
    #     self.assertEqual(len(self.lazy_whale.intervals[interval_len - count_orders - 2].get_buy_orders()), 1)
    #     self.assertEqual(len(self.lazy_whale.intervals[0].get_buy_orders()), 1)
    #     self.assertEqual(len(self.lazy_whale.intervals[count_orders - 1].get_buy_orders()), 1)
    #
    #     orders = self.api_manager.get_open_orders()
    #     order_amounts = sorted([order.amount for order in orders])
    #     for idx, amount in enumerate(order_amounts):
    #         self.assertTrue(amount, Decimal(idx + 1) / Decimal(100))
