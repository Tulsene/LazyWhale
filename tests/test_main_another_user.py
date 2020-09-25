from decimal import Decimal
import unittest
from unittest import TestCase
from unittest.mock import patch
from utils.logger import Logger
from unittest.mock import create_autospec

from main.lazy_whale import LazyWhale
import tests.keys as keys_config


class AnotherUserTests(TestCase):
    @patch('utils.helpers.set_root_path')
    def setUp(self, set_root_path_patch) -> None:
        set_root_path_patch.return_value = keys_config.PATH_TO_PROJECT_ROOT
        params = {"datetime": "2020-09-25 12:45:16.243709",
                  "marketplace": "zebitex_testnet",
                  "market": "DASH/BTC",
                  "range_bot": "0.01",
                  "range_top": "0.015",
                  "increment_coef": "1.0102",
                  "spread_bot": "39",
                  "spread_top": "42",
                  "amount": "0.2",
                  "stop_at_bot": "True",
                  "stop_at_top": "True",
                  "nb_buy_to_display": "3",
                  "nb_sell_to_display": "3",
                  "profits_alloc": "0",
                  "orders_per_interval": "2"}

        with patch.object(Logger, "__init__", lambda x, a: None):
            self.lazy_whale = LazyWhale(params)

    def test_1(self):
        self.assertEqual(1, 1)
