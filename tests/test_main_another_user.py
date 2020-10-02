from copy import deepcopy
from decimal import Decimal
import unittest
from unittest import TestCase
from unittest.mock import patch

from exchanges.api_manager import APIManager
from exchanges.zebitexFormatted import ZebitexFormatted
from ui.user_interface import UserInterface
from utils.checkers import is_equal_decimal
from utils.converters import multiplier
from utils.helpers import interval_generator
from utils.logger import Logger
from unittest.mock import create_autospec

from main.lazy_whale import LazyWhale
import tests.keys as keys_config


class AnotherUserTests(TestCase):
    @patch('utils.helpers.set_root_path')
    def setUp(self, set_root_path_patch) -> None:
        self.market = "DASH/BTC"
        set_root_path_patch.return_value = keys_config.PATH_TO_PROJECT_ROOT
        params = {"datetime": "2020-09-25 12:45:16.243709",
                  "marketplace": "zebitex_testnet",
                  "market": "DASH/BTC",
                  "range_bot": Decimal('0.01'),
                  "range_top":  Decimal('0.015'),
                  "increment_coef": Decimal('1.0102'),
                  "spread_bot": 3,
                  "spread_top": 6,
                  "amount": Decimal('0.2'),
                  "stop_at_bot": True,
                  "stop_at_top": True,
                  "nb_buy_to_display": 3,
                  "nb_sell_to_display": 3,
                  "profits_alloc": 0,
                  "orders_per_interval": 2}

        with patch.object(Logger, "__init__", lambda x, name, slack_webhook=None: None):
            self.api_manager = APIManager(keys_config.SLACK_WEBHOOK, Decimal('1E-8'), Decimal('1'))
            self.lazy_whale = LazyWhale()

        self.lazy_whale.params = params

        self.api_manager.logger = Logger(name='api_manager',
                                         slack_webhook=keys_config.SLACK_WEBHOOK,
                                         common_path=keys_config.PATH_TO_PROJECT_ROOT)
        self.lazy_whale.logger = Logger(name='main',
                                        slack_webhook=keys_config.SLACK_WEBHOOK,
                                        common_path=keys_config.PATH_TO_PROJECT_ROOT)
        self.api_manager.log = self.api_manager.logger.log
        self.lazy_whale.log = self.lazy_whale.logger.log

        self.intervals = interval_generator(params['range_bot'], params['range_top'],
                                            params['increment_coef'])

        self.api_manager.intervals = deepcopy(self.intervals)
        self.api_manager.empty_intervals = deepcopy(self.api_manager.intervals)
        keys = {
            "apiKey": keys_config.BOT_API_KEY,
            "secret": keys_config.BOT_SECRET,
        }
        self.api_manager.set_zebitex(keys, "zebitex_testnet")
        self.api_manager.market = self.market

        self.lazy_whale.intervals = deepcopy(self.intervals)
        self.lazy_whale.connector = self.api_manager
        self.lazy_whale.connector.cancel_all(self.lazy_whale.params['market'])

        # Another user for testing purpose
        self.user = ZebitexFormatted(keys_config.ANOTHER_USER_API_KEY, keys_config.ANOTHER_USER_SECRET, True)
        self.user.cancel_all_orders()

        self.epsilon_amount = Decimal('0.00000005')

    def tearDown(self) -> None:
        self.api_manager.cancel_all(self.market)
        self.user.cancel_all_orders()

    def test_top_is_reached_small(self):
        """Tests scenario 1 - user buy LW orders until top is reached (buy small orders)"""
        self.lazy_whale.params['stop_at_top'] = True
        self.lazy_whale.params['spread_bot'] = len(self.intervals) - 7
        self.lazy_whale.params['spread_top'] = len(self.intervals) - 4

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        for i in range(self.lazy_whale.params['spread_top'], len(self.intervals)):
            orders_to_open = self.intervals[i].generate_orders_by_amount(self.lazy_whale.params['amount'],
                                                                         Decimal('0'), 2)
            self.user.create_limit_buy_order(self.market, orders_to_open[0]['amount'],
                                             self.intervals[i].get_top())
            self.lazy_whale.main_cycle()
            self.user.create_limit_buy_order(self.market, orders_to_open[1]['amount'],
                                             self.intervals[i].get_top())

            if i == len(self.intervals) - 1:
                self.assertRaises(SystemExit, self.lazy_whale.main_cycle)
            else:
                self.lazy_whale.main_cycle()

    def test_bottom_is_reached_small(self):
        """Tests scenario 2 - user sell orders to LW until bottom is reached (sell small orders)"""
        self.lazy_whale.params['stop_at_bot'] = True
        self.lazy_whale.params['spread_bot'] = 3
        self.lazy_whale.params['spread_top'] = 6

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        for i in range(self.lazy_whale.params['spread_bot'], -1, -1):
            orders_to_open = self.intervals[i].generate_orders_by_amount(self.lazy_whale.params['amount'],
                                                                         Decimal('0'), 2)
            self.user.create_limit_sell_order(self.market, orders_to_open[0]['amount'],
                                              self.intervals[i].get_bottom())
            self.lazy_whale.main_cycle()
            self.user.create_limit_sell_order(self.market, orders_to_open[1]['amount'],
                                              self.intervals[i].get_bottom())
            if i == 0:
                self.assertRaises(SystemExit, self.lazy_whale.main_cycle)
            else:
                self.lazy_whale.main_cycle()

    def test_top_is_reached_big(self):
        """Tests scenario 3 - user buy LW orders until top is reached (buy big orders)"""
        self.lazy_whale.params['stop_at_top'] = True
        self.lazy_whale.params['spread_bot'] = len(self.intervals) - 15
        self.lazy_whale.params['spread_top'] = len(self.intervals) - 12
        self.lazy_whale.params['nb_buy_to_display'] = 5
        self.lazy_whale.params['nb_sell_to_display'] = 5

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()
        spr_top = self.lazy_whale.params['spread_top']

        iterations = (len(self.intervals) - self.lazy_whale.params['spread_top']) // 4
        for i in range(iterations):
            orders_to_open = self.intervals[0]\
                .generate_orders_by_amount(multiplier(Decimal('4'), self.lazy_whale.params['amount'])
                                           + self.epsilon_amount, Decimal('0'), 2)
            order1 = self.user.create_limit_buy_order(self.market,
                                                      orders_to_open[0]['amount'],
                                                      self.intervals[spr_top + 4 * (i + 1) - 1].get_top())

            self.lazy_whale.main_cycle()
            order2 = self.user.create_limit_buy_order(self.market, orders_to_open[1]['amount'],
                                                      self.intervals[spr_top + 4 * (i + 1) - 1].get_top())
            self.user.cancel_all_orders()

            if i == iterations - 1:
                self.assertRaises(SystemExit, self.lazy_whale.main_cycle)
            else:
                self.lazy_whale.main_cycle()

    def test_bottom_is_reached_big(self):
        """Tests scenario 4 - user sell orders to LW until bottom is reached (sell big orders)"""
        self.lazy_whale.params['stop_at_top'] = True
        self.lazy_whale.params['spread_bot'] = 11
        self.lazy_whale.params['spread_top'] = 14
        self.lazy_whale.params['nb_buy_to_display'] = 5
        self.lazy_whale.params['nb_sell_to_display'] = 5
        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()
        spr_bot = self.lazy_whale.params['spread_bot']

        iterations = (spr_bot + 1) // 4
        for i in range(iterations):
            orders_to_open = self.intervals[0] \
                .generate_orders_by_amount(multiplier(Decimal('4'), self.lazy_whale.params['amount'])
                                           + self.epsilon_amount, Decimal('0'), 2)
            order1 = self.user.create_limit_sell_order(self.market,
                                                       orders_to_open[0]['amount'],
                                                       self.intervals[spr_bot - 4 * (i + 1) + 1].get_bottom())

            self.lazy_whale.main_cycle()
            order2 = self.user.create_limit_sell_order(self.market, orders_to_open[1]['amount'],
                                                       self.intervals[spr_bot - 4 * (i + 1) + 1].get_bottom())
            self.user.cancel_all_orders()

            if i == iterations - 1:
                self.assertRaises(SystemExit, self.lazy_whale.main_cycle)
            else:
                self.lazy_whale.main_cycle()

    def test_mad_market_volatility_top_is_reached(self):
        """Tests scenario 5 - user buy all LW orders until top is reached (buy everything)"""
        self.lazy_whale.params['stop_at_top'] = True
        self.lazy_whale.params['spread_bot'] = len(self.intervals) - 10
        self.lazy_whale.params['spread_top'] = len(self.intervals) - 7
        self.lazy_whale.params['nb_buy_to_display'] = 3
        self.lazy_whale.params['nb_sell_to_display'] = 3

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        self.user.create_limit_buy_order(self.market, multiplier(self.lazy_whale.params['amount'],
                                         Decimal(str(len(self.intervals)))),
                                         self.intervals[-1].get_top())
        self.lazy_whale.main_cycle()
        self.lazy_whale.main_cycle()
        self.assertRaises(SystemExit, self.lazy_whale.main_cycle)

    def test_mad_market_volatility_bot_is_reached(self):
        """Tests scenario 6 - user sell orders to LW until bot is reached (sell everything)"""
        self.lazy_whale.params['stop_at_bot'] = True
        self.lazy_whale.params['spread_bot'] = 6
        self.lazy_whale.params['spread_top'] = 9
        self.lazy_whale.params['nb_buy_to_display'] = 3
        self.lazy_whale.params['nb_sell_to_display'] = 3

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        self.user.create_limit_sell_order(self.market, multiplier(self.lazy_whale.params['amount'],
                                          Decimal(str(len(self.intervals)))),
                                          self.intervals[0].get_bottom())
        self.lazy_whale.main_cycle()
        self.lazy_whale.main_cycle()
        self.assertRaises(SystemExit, self.lazy_whale.main_cycle)

    def test_consume_buys_sells(self):
        """Tests scenario 7 - user should consume both buy and sell orders
        Important tests:
          check spread bot moving correctly
          check orders are opened with correct amount
          check there is always amount of intervals in [nb_to_display, nb_to_display + 1]
        """
        def test_amount():
            for i in range(self.lazy_whale.params['spread_bot'] - self.lazy_whale.params['nb_buy_to_display'] + 1,
                           self.lazy_whale.params['spread_bot'] + 1):
                self.assertTrue(is_equal_decimal(self.lazy_whale.intervals[i].get_buy_orders_amount(), self.lazy_whale.params['amount']))

            for i in range(self.lazy_whale.params['spread_top'],
                           self.lazy_whale.params['spread_top'] + self.lazy_whale.params['nb_sell_to_display']):
                self.assertTrue(is_equal_decimal(self.lazy_whale.intervals[i].get_sell_orders_amount(),
                                self.lazy_whale.params['amount']))

        self.lazy_whale.params['stop_at_bot'] = True
        self.lazy_whale.params['stop_at_top'] = True
        self.lazy_whale.params['spread_bot'] = 6
        self.lazy_whale.params['spread_top'] = 9
        self.lazy_whale.params['nb_buy_to_display'] = 3
        self.lazy_whale.params['nb_sell_to_display'] = 3
        spr_bot = self.lazy_whale.params['spread_bot']
        spr_top = self.lazy_whale.params['spread_top']

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        self.user.create_limit_buy_order(self.market,
                                         Decimal('1') * self.lazy_whale.params['amount'],
                                         self.intervals[-1].get_top())

        self.user.create_limit_sell_order(self.market,
                                          Decimal('1') * self.lazy_whale.params['amount'],
                                          self.intervals[0].get_bottom())

        self.lazy_whale.main_cycle()
        self.assertEqual(self.lazy_whale.params['spread_bot'], spr_bot)
        self.assertEqual(self.lazy_whale.params['spread_top'], spr_top)

        test_amount()

        self.user.create_limit_buy_order(self.market,
                                         Decimal('3') * self.lazy_whale.params['amount'],
                                         self.intervals[-1].get_top())

        self.user.create_limit_sell_order(self.market,
                                          Decimal('3') * self.lazy_whale.params['amount'],
                                          self.intervals[0].get_bottom())

        self.lazy_whale.main_cycle()
        self.assertEqual(self.lazy_whale.params['spread_bot'], spr_bot)
        self.assertEqual(self.lazy_whale.params['spread_top'], spr_top)

        test_amount()

        self.user.create_limit_buy_order(self.market,
                                         Decimal('2') * self.lazy_whale.params['amount'],
                                         self.intervals[-1].get_top())

        self.user.create_limit_sell_order(self.market,
                                          Decimal('2') * self.lazy_whale.params['amount'],
                                          self.intervals[0].get_bottom())

        self.lazy_whale.main_cycle()
        self.assertEqual(self.lazy_whale.params['spread_bot'], spr_bot)
        self.assertEqual(self.lazy_whale.params['spread_top'], spr_top)

        test_amount()

        self.user.create_limit_buy_order(self.market,
                                         Decimal('1') * self.lazy_whale.params['amount'],
                                         self.intervals[-1].get_top())

        self.user.create_limit_sell_order(self.market,
                                          Decimal('3') * self.lazy_whale.params['amount'],
                                          self.intervals[0].get_bottom())

        self.lazy_whale.main_cycle()
        self.assertEqual(self.lazy_whale.params['spread_bot'], spr_bot - 2)
        self.assertEqual(self.lazy_whale.params['spread_top'], spr_top - 2)
