from copy import deepcopy
from decimal import Decimal
from unittest import TestCase

from mock import patch

from exchanges.api_manager import APIManager
from main.interval import Interval
from main.main import LazyWhale
from main.order import Order
from utils import helpers
from utils.helpers import interval_generator
from utils.logger import Logger

import tests.keys as keys_config


def patch_log_formatter(*args, **kwargs):
    timestamp = 2134
    date = '_'
    return timestamp, date


class LazyWhaleTests(TestCase):
    def setUp(self) -> None:
        self.market = "DASH/BTC"
        self.intervals = interval_generator(Decimal('0.01'), Decimal('0.015'),
                                            Decimal('1') + Decimal('1.02') / Decimal('100'))

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
                "apiKey": keys_config.API_KEY,
                "secret": keys_config.SECRET,
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

    def tearDown(self) -> None:
        self.api_manager.cancel_all(self.market)

    # def test_compare_intervals_1(self):
    #     """Tests that comparing intervals is correct and is doing by the strategy
    #     When order, known by LW, have been consumed,
    #     LW should open a new opposite order +2/-2 intervals higher/lower
    #     """
    #     # Easy test
    #     self.assertEqual(len(self.api_manager.get_open_orders()), 0)
    #
    #     amount = Decimal(1)
    #     buy_order = Order(idx=1, amount=amount, price=Decimal('0.0101'), side='buy', timestamp='123', date='123')
    #
    #     self.lazy_whale.intervals[0].insert_buy_order(buy_order)
    #
    #     self.lazy_whale.compare_intervals(self.intervals)
    #     self.assertEqual(len(self.api_manager.get_open_orders()), 1)
    #     self.assertEqual(len(self.lazy_whale.intervals[0].get_buy_orders()), 0)
    #     self.assertEqual(len(self.lazy_whale.intervals[2].get_sell_orders()), 1)
    #
    #     order = self.api_manager.get_open_orders()[0]
    #     self.assertEqual(order.amount, amount)
    #     self.assertEqual(order.side, 'sell')
    #
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
