from copy import deepcopy
from decimal import Decimal
import unittest
from unittest import TestCase

from exchanges.api_manager import APIManager
import tests.keys as keys_config
from mock import patch

from main.order import Order
from utils import helpers
from utils.helpers import interval_generator, populate_intervals, get_missing_buy_orders, get_missing_sell_orders
from utils.logger import Logger


def patch_log_formatter(*args, **kwargs):
    timestamp = 2134
    date = '_'
    return timestamp, date


class APIManagerTests(TestCase):
    def setUp(self) -> None:
        # cause an error with read-only file system
        # self.api_manager = \
        # APIManager(keys_config.SLACK_WEBHOOK, 1, 0.0001)
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
            self.api_manager.intervals = interval_generator(Decimal('0.01'), Decimal('0.015'),
                                                            Decimal('1') + Decimal('1.02') / Decimal('100'))
            self.api_manager.empty_intervals = deepcopy(self.api_manager.intervals)
            self.api_manager.market = ''
            self.api_manager.profits_alloc = 0
            keys = {
                "apiKey": keys_config.API_KEY,
                "secret": keys_config.SECRET,
            }
            self.api_manager.set_zebitex(keys, "zebitex_testnet")

            self.market = "DASH/BTC"
            self.raw_orders = [
                {
                    'id': '1',
                    'timestamp': 1,
                    'datetime': '_',
                    'lastTradeTimestamp': None,
                    'status': 'open',
                    'symbol': 'DASH/BTC',
                    'type': 'limit',
                    'side': 'buy',
                    'price': 0.0001,
                    'cost': 0.0049925,
                    'amount': 1,
                    'filled': 0.5,
                    'remaining': 1.49,
                    'trades': None,
                    'fee': 0.00075
                },
                {
                    'id': '1',
                    'timestamp': 1,
                    'datetime': '_',
                    'lastTradeTimestamp': None,
                    'status': 'open',
                    'symbol': 'DASH/BTC',
                    'type': 'limit',
                    'side': 'buy',
                    'price': 0.010104,
                    'cost': 0.0049925,
                    'amount': 1,
                    'filled': 0.5,
                    'remaining': 1.49,
                    'trades': None,
                    'fee': 0.00075
                },
                {
                    'id': '1',
                    'timestamp': 1,
                    'datetime': '_',
                    'lastTradeTimestamp': None,
                    'status': 'open',
                    'symbol': 'DASH/BTC',
                    'type': 'limit',
                    'side': 'buy',
                    'price': 0.01052081,
                    'cost': 0.0049925,
                    'amount': 1,
                    'filled': 0.5,
                    'remaining': 1.49,
                    'trades': None,
                    'fee': 0.00075
                },
                {
                    'id': '1',
                    'timestamp': 1,
                    'datetime': '_',
                    'lastTradeTimestamp': None,
                    'status': 'open',
                    'symbol': 'DASH/BTC',
                    'type': 'limit',
                    'side': 'buy',
                    'price': 1,
                    'cost': 0.0049925,
                    'amount': 1,
                    'filled': 0.5,
                    'remaining': 1.49,
                    'trades': None,
                    'fee': 0.00075
                },
                {
                    'id': '2',
                    'timestamp': 1,
                    'datetime': '_',
                    'lastTradeTimestamp': None,
                    'status': 'open',
                    'symbol': 'DASH/BTC',
                    'type': 'limit',
                    'side': 'buy',
                    'price': 0.010105,
                    'cost': 0.0049925,
                    'amount': 1,
                    'filled': 0.5,
                    'remaining': 1.49,
                    'trades': None,
                    'fee': 0.00075
                },
                {
                    'id': '1',
                    'timestamp': 1,
                    'datetime': '_',
                    'lastTradeTimestamp': None,
                    'status': 'open',
                    'symbol': 'DASH/BTC',
                    'type': 'limit',
                    'side': 'buy',
                    'price': 0.01020510,
                    'cost': 0.0049925,
                    'amount': 1,
                    'filled': 0.5,
                    'remaining': 1.49,
                    'trades': None,
                    'fee': 0.00075
                },
                {
                    'id': '1',
                    'timestamp': 1,
                    'datetime': '_',
                    'lastTradeTimestamp': None,
                    'status': 'open',
                    'symbol': 'DASH/BTC',
                    'type': 'limit',
                    'side': 'sell',
                    'price': 0.01041528,
                    'cost': 0.0049925,
                    'amount': 1,
                    'filled': 0.5,
                    'remaining': 1.49,
                    'trades': None,
                    'fee': 0.00075
                },
            ]
            self.interval_index = 1
            self.interval = self.api_manager.intervals[self.interval_index]
            self.api_manager.market = self.market
            self.api_manager.cancel_all(self.market)

    def tearDown(self) -> None:
        self.api_manager.cancel_all(self.market)

    def test_format_open_orders(self):
        orders = self.api_manager.format_open_orders(self.raw_orders)
        self.assertEqual(len(orders), len(self.raw_orders))

    def test_populate_intervals(self):
        """Testing part of get_intervals function that transform fetch_open_orders response to intervals interface"""
        self.assertEqual(len(self.api_manager.intervals[1].get_buy_orders()), 0)
        self.assertEqual(len(self.api_manager.intervals[2].get_buy_orders()), 0)
        self.assertEqual(len(self.api_manager.intervals[5].get_buy_orders()), 0)
        self.assertEqual(len(self.api_manager.intervals[4].get_buy_orders()), 0)

        orders = self.api_manager.format_open_orders(self.raw_orders)
        intervals = populate_intervals(self.api_manager.intervals, orders)

        self.assertEqual(len(intervals[1].get_buy_orders()), 2)
        self.assertEqual(len(intervals[2].get_buy_orders()), 1)
        self.assertEqual(len(intervals[5].get_buy_orders()), 1)
        self.assertEqual(len(intervals[4].get_sell_orders()), 1)

    def test_get_intervals(self):
        orders = self.api_manager.format_open_orders(self.raw_orders)
        self.assertEqual(len(orders), len(self.raw_orders))

        intervals = self.api_manager.get_intervals(self.market)
        self.assertEqual(self.api_manager.intervals[1], intervals[1])
        self.assertEqual(self.api_manager.intervals[2], intervals[2])
        self.assertEqual(self.api_manager.intervals[4], intervals[4])
        self.assertEqual(self.api_manager.intervals[5], intervals[5])

    def test_create_limit_order(self):
        """Tests that creating order is completed and order is open"""
        price = Decimal(0.01010101)
        count_orders = len(self.api_manager.fetch_open_orders(self.market))
        self.api_manager.create_limit_buy_order(self.market, Decimal(0.017), price)
        self.assertEqual(len(self.api_manager.fetch_open_orders(self.market)), count_orders + 1)
        self.assertTrue(self.api_manager.check_an_order_is_open(price, 'buy'))

    def test_get_order_book(self):
        """Tests response from user order_book"""
        order_book = self.api_manager.get_order_book(self.market)
        self.assertTrue('asks' in order_book and 'bids' in order_book)

    def test_cancel_all(self):
        """Tests that cancel_order cancel all orders from order_book"""
        self.api_manager.cancel_all(self.market)
        orders = self.api_manager.fetch_open_orders(self.market)
        self.assertEqual(len(orders), 0)

        self.api_manager.create_limit_buy_order(self.market, Decimal('1'), Decimal(0.001))
        orders = self.api_manager.fetch_open_orders(self.market)
        self.assertEqual(len(orders), 1)

        self.api_manager.cancel_all(self.market)
        orders = self.api_manager.fetch_open_orders(self.market)
        self.assertEqual(len(orders), 0)

    def test_interval_place_buy_order_random_price(self):
        """Tests that orders are placed correctly in the interval and exists in order_book"""
        count_order = 3
        self.interval.place_buy_order_random_price(self.api_manager, self.market, Decimal(0.02),
                                                   count_order=count_order)

        self.assertEqual(len(self.interval.get_buy_orders()), count_order)

        orders = self.api_manager.fetch_open_orders(self.market)
        self.assertEqual(len(orders), count_order)

        intervals = self.api_manager.get_intervals(self.market)
        self.assertEqual(intervals[self.interval_index], self.interval)

    def test_cancel_order(self):
        order = self.api_manager.create_limit_buy_order(self.market, Decimal('1'), Decimal(0.01))
        self.assertTrue(self.api_manager.check_an_order_is_open(order.price, 'buy'))

        self.api_manager.cancel_order(order)
        self.assertFalse(self.api_manager.check_an_order_is_open(order.price, 'buy'))

    def test_get_safety_orders(self):
        self.assertEqual(len(self.api_manager.get_safety_orders()), 0)

        self.api_manager.create_limit_buy_order(self.market, Decimal('1'), self.api_manager.safety_buy_value)
        self.assertEqual(len(self.api_manager.get_safety_orders()), 1)

        self.api_manager.create_limit_sell_order(self.market, Decimal(1), self.api_manager.safety_sell_value)
        self.assertEqual(len(self.api_manager.get_safety_orders()), 2)

    def test_get_missing_buy_orders(self):
        """Tests that missing orders are finding correctly"""
        first = deepcopy(self.interval)
        second = deepcopy(self.interval)

        order = Order(idx=1, amount=Decimal('0.0101'), price=Decimal('0.0101'), side='buy',
                      date='123', timestamp=123)

        first.insert_buy_order(order)

        self.assertEqual(get_missing_buy_orders(first, second), [order])

    def test_get_missing_sell_orders(self):
        """Tests that missing orders are finding correctly"""
        first = deepcopy(self.interval)
        second = deepcopy(self.interval)

        order = Order(idx=1, amount=Decimal('0.0101'), price=Decimal('0.0101'), side='sell',
                      date='123', timestamp=123)

        first.insert_sell_order(order)

        self.assertEqual(get_missing_sell_orders(first, second), [order])


if __name__ == "__main__":
    unittest.main()
