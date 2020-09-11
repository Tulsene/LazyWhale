from decimal import Decimal
import unittest
from unittest import TestCase

from exchanges.api_manager import APIManager
from exchanges.zebitexFormatted import ZebitexFormatted
import tests.keys as keys_config
from mock import patch

from utils import helpers
from utils.checkers import interval_generator


def patch_log(*args, **kwargs):
    pass


class APIManagerTests(TestCase):

    def setUp(self) -> None:
        with patch.object(APIManager, "__init__", lambda x, y, z, a: None):
            # patch APIManager because Logger cant be created in test mode
            self.api_manager = APIManager(None, None, None)
            self.api_manager.log = patch_log
            self.api_manager.safety_buy_value = 1
            self.api_manager.safety_sell_value = 1e-8
            self.api_manager.root_path = helpers.set_root_path()
            self.api_manager.exchange = None
            self.api_manager.err_counter = 0
            self.api_manager.is_kraken = False
            self.api_manager.now = 0
            self.api_manager.fees_coef = 0
            self.api_manager.intervals = interval_generator(Decimal(0.01), Decimal(0.015), Decimal(1 + (1.02 / 100)))
            self.api_manager.market = ''
            self.api_manager.profits_alloc = 0
            keys = {
                "apiKey": keys_config.API_KEY,
                "secret": keys_config.SECRET,
            }
            self.api_manager.set_zebitex(keys, "zebitex_testnet")

            self.market = "DASH/BTC"
            self.orders_to_populate = [
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

    def test_populate_intervals(self):
        self.assertEqual(len(self.api_manager.intervals[1].get_buy_orders()), 0)
        self.api_manager.populate_intervals(self.orders_to_populate)
        self.assertEqual(len(self.api_manager.intervals[1].get_buy_orders()), 2)
        self.assertEqual(len(self.api_manager.intervals[2].get_buy_orders()), 1)
        self.assertEqual(len(self.api_manager.intervals[5].get_buy_orders()), 1)
        self.assertEqual(len(self.api_manager.intervals[4].get_sell_orders()), 1)

    def test_create_limit_order(self):
        price = Decimal(0.01010101)
        count_orders = len(self.api_manager.fetch_open_orders(self.market))
        self.api_manager.create_limit_buy_order(self.market, Decimal(0.017), price)
        self.assertEqual(len(self.api_manager.fetch_open_orders(self.market)), count_orders + 1)
        self.assertTrue(self.api_manager.check_an_order_is_open(price, self.api_manager.intervals, 'buy'))


if __name__ == "__main__":
    unittest.main()
