import time
from copy import deepcopy
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from exchanges.api_manager import APIManager
from exchanges.zebitexFormatted import ZebitexFormatted
from main.allocation import NoSpecificAllocation, LinearAllocation, CurvedAllocation, ProfitAllocation
from utils.checkers import is_equal_decimal
from utils.converters import multiplier
from utils.helpers import interval_generator, get_indexes_buy_intervals, get_indexes_sell_intervals, populate_intervals
import utils.logger_factory as lf

from main.lazy_whale import LazyWhale
import tests.keys as keys_config


class AnotherUserTests(TestCase):
    @patch('utils.helpers.set_root_path')
    def setUp(self, set_root_path_patch) -> None:
        self.time_to_sleep = 0.1
        self.market = "DASH/BTC"
        set_root_path_patch.return_value = keys_config.PATH_TO_PROJECT_ROOT
        lf.set_simple_logger(keys_config.PATH_TO_PROJECT_ROOT)
        params = {"datetime": "2020-09-25 12:45:16.243709",
                  "marketplace": "zebitex_testnet",
                  "market": "DASH/BTC",
                  "range_bot": Decimal('0.01'),
                  "range_top": Decimal('0.015'),
                  "increment_coef": Decimal('1.0102'),
                  "spread_bot": 3,
                  "spread_top": 6,
                  "amount": Decimal('0.02'),
                  "stop_at_bot": True,
                  "stop_at_top": True,
                  "nb_buy_to_display": 3,
                  "nb_sell_to_display": 3,
                  "profits_alloc": 0,
                  "orders_per_interval": 2}

        self.api_manager = APIManager(keys_config.SLACK_WEBHOOK, Decimal('1E-8'), Decimal('1'))
        self.lazy_whale = LazyWhale()

        self.lazy_whale.params = params
        self.lazy_whale.allocation = NoSpecificAllocation(self.lazy_whale.params['amount'])

        self.api_manager.log = lf.get_simple_logger("test.api_manager")
        self.lazy_whale.log = lf.get_simple_logger("test.lazy_whale")

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
        self.lazy_whale.set_min_amount()

        # create_allocations:
        self.linear_allocation = LinearAllocation(Decimal('0.02'), Decimal('0.04'), 40)
        self.curved_allocation = CurvedAllocation(Decimal('0.02'), Decimal('0.016'), Decimal('0.024'), 40)
        self.profit_allocation = ProfitAllocation(self.lazy_whale.intervals, 50,
                                                  self.lazy_whale.fees_coef, Decimal('0.2'))

    def tearDown(self) -> None:
        self.api_manager.cancel_all(self.market)
        self.user.cancel_all_orders()

    def helper_amount_by_indexes(self, start_index, end_index, side):
        return sum([self.lazy_whale.allocation.get_amount(j, side)
                    for j in range(start_index, end_index)])

    def helper_test_top_is_reached_small(self):
        """Tests scenario 1 - user buy LW orders until top is reached (buy small orders)"""
        self.lazy_whale.params['stop_at_top'] = True
        self.lazy_whale.params['spread_bot'] = len(self.intervals) - 7
        self.lazy_whale.params['spread_top'] = len(self.intervals) - 4

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        for i in range(self.lazy_whale.params['spread_top'], len(self.intervals)):
            orders_to_open = self.intervals[i] \
                .generate_orders_by_amount(self.lazy_whale.allocation.get_amount(i, "sell")
                                           + self.epsilon_amount,
                                           self.lazy_whale.min_amount, 2)

            self.user.create_limit_buy_order(self.market, orders_to_open[0]['amount'],
                                             self.intervals[i].get_top())
            self.lazy_whale.main_cycle()
            self.user.create_limit_buy_order(self.market, orders_to_open[1]['amount'],
                                             self.intervals[i].get_top())

            self.user.cancel_all_orders()
            if i == len(self.intervals) - 1:
                self.assertRaises(SystemExit, self.lazy_whale.main_cycle)
            else:
                self.lazy_whale.main_cycle()

    def helper_test_bottom_is_reached_small(self):
        """Tests scenario 2 - user sell orders to LW until bottom is reached (sell small orders)"""
        self.lazy_whale.params['stop_at_bot'] = True
        self.lazy_whale.params['spread_bot'] = 3
        self.lazy_whale.params['spread_top'] = 6

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        for i in range(self.lazy_whale.params['spread_bot'], -1, -1):
            orders_to_open = self.intervals[i] \
                .generate_orders_by_amount(self.lazy_whale.allocation.get_amount(i, "buy")
                                           + self.epsilon_amount,
                                           self.lazy_whale.min_amount, 2)
            self.user.create_limit_sell_order(self.market, orders_to_open[0]['amount'],
                                              self.intervals[i].get_bottom())
            self.lazy_whale.main_cycle()
            self.user.create_limit_sell_order(self.market, orders_to_open[1]['amount'],
                                              self.intervals[i].get_bottom())

            self.user.cancel_all_orders()
            if i == 0:
                self.assertRaises(SystemExit, self.lazy_whale.main_cycle)
            else:
                self.lazy_whale.main_cycle()

    def helper_test_top_is_reached_big(self):
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
            amount_to_open = self.helper_amount_by_indexes(spr_top + 4 * i, spr_top + 4 * (i + 1), 'sell')

            orders_to_open = self.intervals[0] \
                .generate_orders_by_amount(amount_to_open + self.epsilon_amount, self.lazy_whale.min_amount, 2)
            self.user.create_limit_buy_order(self.market,
                                             orders_to_open[0]['amount'],
                                             self.intervals[spr_top + 4 * (i + 1) - 1].get_top())
            time.sleep(self.time_to_sleep)

            self.lazy_whale.main_cycle()
            self.user.create_limit_buy_order(self.market, orders_to_open[1]['amount'],
                                             self.intervals[spr_top + 4 * (i + 1) - 1].get_top())
            time.sleep(self.time_to_sleep)
            self.user.cancel_all_orders()

            if i == iterations - 1:
                self.assertRaises(SystemExit, self.lazy_whale.main_cycle)
            else:
                self.lazy_whale.main_cycle()

    def helper_test_bottom_is_reached_big(self):
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
            amount_to_open = self.helper_amount_by_indexes(spr_bot - 4 * (i + 1) + 1, spr_bot - 4 * i + 1, 'buy')

            orders_to_open = self.intervals[0] \
                .generate_orders_by_amount(amount_to_open + self.epsilon_amount, self.lazy_whale.min_amount, 2)
            self.user.create_limit_sell_order(self.market,
                                              orders_to_open[0]['amount'],
                                              self.intervals[spr_bot - 4 * (i + 1) + 1].get_bottom())
            time.sleep(self.time_to_sleep)

            self.lazy_whale.main_cycle()
            self.user.create_limit_sell_order(self.market, orders_to_open[1]['amount'],
                                              self.intervals[spr_bot - 4 * (i + 1) + 1].get_bottom())
            time.sleep(self.time_to_sleep)
            self.user.cancel_all_orders()

            if i == iterations - 1:
                print(self.lazy_whale.intervals)
                self.assertRaises(SystemExit, self.lazy_whale.main_cycle)
            else:
                self.lazy_whale.main_cycle()

    def helper_test_mad_market_volatility_top_is_reached(self):
        """Tests scenario 5 - user buy all LW orders until top is reached (buy everything)"""
        self.lazy_whale.params['stop_at_top'] = True
        self.lazy_whale.params['spread_bot'] = len(self.intervals) - 10
        self.lazy_whale.params['spread_top'] = len(self.intervals) - 7
        self.lazy_whale.params['nb_buy_to_display'] = 3
        self.lazy_whale.params['nb_sell_to_display'] = 3

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        self.user.create_limit_buy_order(self.market, multiplier(self.lazy_whale.allocation.get_amount(0, 'buy'),
                                                                 Decimal(str(len(self.intervals)))),
                                         self.intervals[-1].get_top())
        time.sleep(self.time_to_sleep)
        self.lazy_whale.main_cycle()
        self.lazy_whale.main_cycle()
        self.assertRaises(SystemExit, self.lazy_whale.main_cycle)

    def helper_test_mad_market_volatility_bottom_is_reached(self):
        """Tests scenario 6 - user sell orders to LW until bot is reached (sell everything)"""
        self.lazy_whale.params['stop_at_bot'] = True
        self.lazy_whale.params['spread_bot'] = 6
        self.lazy_whale.params['spread_top'] = 9
        self.lazy_whale.params['nb_buy_to_display'] = 3
        self.lazy_whale.params['nb_sell_to_display'] = 3

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        self.user.create_limit_sell_order(self.market, multiplier(self.lazy_whale.allocation.get_amount(0, 'buy'),
                                                                  Decimal(str(len(self.intervals)))),
                                          self.intervals[0].get_bottom())
        time.sleep(self.time_to_sleep)
        self.lazy_whale.main_cycle()
        self.lazy_whale.main_cycle()
        self.assertRaises(SystemExit, self.lazy_whale.main_cycle)

    def helper_init_tests(self):
        self.lazy_whale.cancel_all_intervals()
        self.user.cancel_all_orders()
        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

    def helper_test_consume_buys_sells(self):
        """Tests scenario 7 - user should consume both buy and sell orders
        Important tests:
          check spread bot moving correctly
          check orders are opened with correct amount
          check there is always amount of intervals in [nb_to_display, nb_to_display + 1]
        """

        def test_amount():
            if isinstance(self.lazy_whale.allocation, LinearAllocation):
                for i in range(self.lazy_whale.params['spread_bot'] - self.lazy_whale.params['nb_buy_to_display'] + 1,
                               self.lazy_whale.params['spread_bot'] + 1):
                    self.assertTrue(is_equal_decimal(self.lazy_whale.intervals[i].get_buy_orders_amount(),
                                                     self.lazy_whale.allocation.get_amount(i, 'buy')))
                actual_total_amount = Decimal('0')
                min_total_amount = Decimal('0')
                max_total_amount = Decimal('0')
                for i in range(self.lazy_whale.params['spread_top'],
                               self.lazy_whale.params['spread_top'] + self.lazy_whale.params['nb_sell_to_display']):
                    actual_total_amount += self.lazy_whale.intervals[i].get_sell_orders_amount()
                    min_total_amount += self.lazy_whale.allocation.get_amount(i, 'buy')
                    max_total_amount += self.lazy_whale.allocation.get_amount(i, 'sell')

                self.assertGreaterEqual(actual_total_amount, min_total_amount)
                self.assertLessEqual(actual_total_amount, max_total_amount)

            elif isinstance(self.lazy_whale.allocation, CurvedAllocation):
                actual_total_amount = Decimal('0')
                min_total_amount = Decimal('0')
                max_total_amount = Decimal('0')
                for i in get_indexes_buy_intervals(self.lazy_whale.intervals):
                    actual_total_amount += self.lazy_whale.intervals[i].get_buy_orders_amount()
                    min_total_amount += self.lazy_whale.allocation.get_amount(i, 'sell')
                    max_total_amount += self.lazy_whale.allocation.get_amount(i, 'buy')

                self.assertGreaterEqual(actual_total_amount, min_total_amount)
                self.assertLessEqual(actual_total_amount, max_total_amount)

                for i in get_indexes_sell_intervals(self.lazy_whale.intervals):
                    self.assertTrue(is_equal_decimal(self.lazy_whale.intervals[i].get_sell_orders_amount(),
                                                     self.lazy_whale.allocation.get_amount(i, 'sell')))

            else:
                for i in range(self.lazy_whale.params['spread_bot'] - self.lazy_whale.params['nb_buy_to_display'] + 1,
                               self.lazy_whale.params['spread_bot'] + 1):
                    self.assertTrue(is_equal_decimal(self.lazy_whale.intervals[i].get_buy_orders_amount(),
                                                     self.lazy_whale.allocation.get_amount(i, 'buy')))

                for i in range(self.lazy_whale.params['spread_top'],
                               self.lazy_whale.params['spread_top'] + self.lazy_whale.params['nb_sell_to_display']):
                    self.assertTrue(is_equal_decimal(self.lazy_whale.intervals[i].get_sell_orders_amount(),
                                                     self.lazy_whale.allocation.get_amount(i, 'sell')))

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
                                         self.lazy_whale.allocation.get_amount(self.lazy_whale.params['spread_top'],
                                                                               'sell') + self.epsilon_amount,
                                         self.intervals[self.lazy_whale.params['spread_top']].get_top())

        self.user.cancel_all_orders()

        self.user.create_limit_sell_order(self.market,
                                          self.lazy_whale.allocation.get_amount(self.lazy_whale.params['spread_bot'],
                                                                                'buy') + self.epsilon_amount,
                                          self.intervals[self.lazy_whale.params['spread_bot']].get_bottom())

        time.sleep(self.time_to_sleep)
        self.user.cancel_all_orders()
        self.lazy_whale.main_cycle()

        self.assertEqual(self.lazy_whale.params['spread_bot'], spr_bot)
        self.assertEqual(self.lazy_whale.params['spread_top'], spr_top)

        test_amount()

        self.lazy_whale.params['spread_bot'] = 6
        self.lazy_whale.params['spread_top'] = 9
        self.helper_init_tests()
        amount_to_open = self.helper_amount_by_indexes(self.lazy_whale.params['spread_top'],
                                                       self.lazy_whale.params['spread_top'] + 3, 'sell')

        self.user.create_limit_buy_order(self.market,
                                         amount_to_open + self.epsilon_amount,
                                         self.intervals[self.lazy_whale.params['spread_top'] + 2].get_top())
        time.sleep(self.time_to_sleep)
        self.user.cancel_all_orders()

        amount_to_open = self.helper_amount_by_indexes(self.lazy_whale.params['spread_bot'] - 2,
                                                       self.lazy_whale.params['spread_bot'] + 1, 'buy')

        self.user.create_limit_sell_order(self.market,
                                          amount_to_open + self.epsilon_amount,
                                          self.intervals[self.lazy_whale.params['spread_bot'] - 2].get_bottom())

        time.sleep(self.time_to_sleep)
        self.user.cancel_all_orders()
        self.lazy_whale.main_cycle()
        self.assertEqual(self.lazy_whale.params['spread_bot'], spr_bot)
        self.assertEqual(self.lazy_whale.params['spread_top'], spr_top)

        test_amount()

        self.lazy_whale.params['spread_bot'] = 6
        self.lazy_whale.params['spread_top'] = 9
        self.helper_init_tests()

        amount_to_open = self.helper_amount_by_indexes(self.lazy_whale.params['spread_top'],
                                                       self.lazy_whale.params['spread_top'] + 2, 'sell')

        self.user.create_limit_buy_order(self.market,
                                         amount_to_open + self.epsilon_amount,
                                         self.intervals[self.lazy_whale.params['spread_top'] + 1].get_top())

        time.sleep(self.time_to_sleep)
        self.user.cancel_all_orders()

        amount_to_open = self.helper_amount_by_indexes(self.lazy_whale.params['spread_bot'] - 1,
                                                       self.lazy_whale.params['spread_bot'] + 1, 'buy')

        self.user.create_limit_sell_order(self.market,
                                          amount_to_open + self.epsilon_amount,
                                          self.intervals[self.lazy_whale.params['spread_bot'] - 1].get_bottom())

        time.sleep(self.time_to_sleep)
        self.user.cancel_all_orders()
        self.lazy_whale.main_cycle()

        self.assertEqual(self.lazy_whale.params['spread_bot'], spr_bot)
        self.assertEqual(self.lazy_whale.params['spread_top'], spr_top)

        test_amount()

        self.lazy_whale.params['spread_bot'] = 6
        self.lazy_whale.params['spread_top'] = 9
        self.helper_init_tests()

        self.user.create_limit_buy_order(self.market,
                                         self.lazy_whale.allocation.get_amount(self.lazy_whale.params['spread_top'],
                                                                               'sell') + self.epsilon_amount,
                                         self.intervals[self.lazy_whale.params['spread_top']].get_top())

        time.sleep(self.time_to_sleep)
        self.user.cancel_all_orders()

        amount_to_open = self.helper_amount_by_indexes(self.lazy_whale.params['spread_bot'] - 2,
                                                       self.lazy_whale.params['spread_bot'] + 1, 'buy')

        self.user.create_limit_sell_order(self.market,
                                          amount_to_open + self.epsilon_amount,
                                          self.intervals[self.lazy_whale.params['spread_bot'] - 2].get_bottom())

        time.sleep(self.time_to_sleep)
        self.user.cancel_all_orders()
        self.lazy_whale.main_cycle()

        if isinstance(self.lazy_whale.allocation, LinearAllocation):
            self.assertEqual(self.lazy_whale.params['spread_bot'], spr_bot - 1)
            self.assertEqual(self.lazy_whale.params['spread_top'], spr_top - 1)

        else:
            self.assertEqual(self.lazy_whale.params['spread_bot'], spr_bot - 2)
            self.assertEqual(self.lazy_whale.params['spread_top'], spr_top - 2)

    def helper_test_run_forever(self):
        """Tests scenario 8:
        going to bot, after to top, to bot with bigger step and to top once more (bigger step)
        Really large test and really slow test, but still important
        It will show the ability of bot to run forever, also if range bot or range bot
        has been reached (not to stop there)"""
        self.lazy_whale.params['stop_at_bot'] = False
        self.lazy_whale.params['stop_at_top'] = False
        self.lazy_whale.params['spread_bot'] = 20
        self.lazy_whale.params['spread_top'] = 23
        self.lazy_whale.params['nb_buy_to_display'] = 6
        self.lazy_whale.params['nb_sell_to_display'] = 6
        spr_bot = self.lazy_whale.params['spread_bot']

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()
        for i in reversed(range(spr_bot + 1)):
            self.assertEqual(self.lazy_whale.params['spread_bot'], i)
            self.user.create_limit_sell_order(self.market,
                                              self.lazy_whale.allocation.get_amount(i, 'buy') + self.epsilon_amount,
                                              self.intervals[i].get_bottom())
            self.user.cancel_all_orders()
            self.lazy_whale.main_cycle()

        # bot is reached but continue
        self.assertEqual(self.lazy_whale.params['spread_bot'], 0)

        # sell occurred after so much buys - LW can continue working
        self.user.create_limit_buy_order(self.market,
                                         self.lazy_whale.allocation.get_amount(2, 'sell') + self.epsilon_amount,
                                         self.intervals[2].get_top())
        self.user.cancel_all_orders()
        self.lazy_whale.main_cycle()

        if isinstance(self.lazy_whale.allocation, LinearAllocation) \
                or isinstance(self.lazy_whale.allocation, CurvedAllocation):
            self.lazy_whale.cancel_buy_interval_by_index(self.lazy_whale.intervals, 0)
            orders = self.lazy_whale.connector.set_several_buy(
                self.lazy_whale.intervals[0].generate_orders_by_amount(
                    self.lazy_whale.allocation.get_amount(0, 'buy'),
                    self.lazy_whale.min_amount
                )
            )
            populate_intervals(self.lazy_whale.intervals, orders)

        spr_top = self.lazy_whale.params['spread_top']
        for i in range(spr_top, len(self.intervals)):
            self.assertEqual(self.lazy_whale.params['spread_top'], i)
            self.user.create_limit_buy_order(self.market,
                                             self.lazy_whale.allocation.get_amount(i, 'sell') + self.epsilon_amount,
                                             self.intervals[i].get_top())
            self.user.cancel_all_orders()
            self.lazy_whale.main_cycle()

        self.user.create_limit_buy_order(self.market,
                                         self.lazy_whale.allocation.get_amount(0, 'buy'),
                                         self.intervals[-1].get_top())
        self.lazy_whale.main_cycle()

        # bot is reached but continue
        self.assertEqual(self.lazy_whale.params['spread_top'], len(self.intervals) - 1)
        self.user.cancel_all_orders()

        # buy occurred after so much sells - LW can continue working
        self.user.create_limit_sell_order(self.market,
                                          self.lazy_whale.allocation.get_amount(len(self.intervals) - 3, 'buy')
                                          + self.epsilon_amount,
                                          self.intervals[len(self.intervals) - 3].get_bottom())
        self.user.cancel_all_orders()
        self.lazy_whale.main_cycle()

        iterations = len(self.intervals) // self.lazy_whale.params['nb_buy_to_display'] + 1
        for i in range(iterations):
            self.assertEqual(self.lazy_whale.params['spread_bot'],
                             len(self.intervals) - 4 - self.lazy_whale.params['nb_buy_to_display'] * i)

            bottom_index = max(0,
                               len(self.intervals) - 4 - self.lazy_whale.params['nb_buy_to_display'] * (i + 1) + 1)
            amount_to_open = self.helper_amount_by_indexes(
                bottom_index,
                bottom_index + self.lazy_whale.params['nb_buy_to_display'],
                "buy"
            )
            self.user.create_limit_sell_order(self.market,
                                              amount_to_open + self.epsilon_amount,
                                              self.intervals[bottom_index].get_bottom())

            import time
            time.sleep(5)
            self.user.cancel_all_orders()
            self.lazy_whale.main_cycle()

        self.user.cancel_all_orders()
        # bot is reached once more time
        self.assertEqual(self.lazy_whale.params['spread_bot'], 0)

        intervals = self.lazy_whale.intervals
        # nothing should change
        self.lazy_whale.main_cycle()
        self.assertEqual(intervals, self.lazy_whale.intervals)

        # sell occurred after buys - LW can continue working
        self.user.create_limit_buy_order(self.market, self.lazy_whale.allocation.get_amount(2, 'sell')
                                         + self.epsilon_amount,
                                         self.intervals[2].get_top())
        self.user.cancel_all_orders()
        self.lazy_whale.main_cycle()

        iterations = len(self.intervals) // self.lazy_whale.params['nb_sell_to_display'] + 1
        for i in range(iterations):
            self.assertEqual(self.lazy_whale.params['spread_top'],
                             3 + self.lazy_whale.params['nb_buy_to_display'] * i)

            bottom_index = 3 + self.lazy_whale.params['nb_buy_to_display'] * i
            top_index = min(len(self.intervals) - 1, bottom_index + self.lazy_whale.params['nb_buy_to_display'])
            amount_to_open = self.helper_amount_by_indexes(
                bottom_index,
                top_index,
                "sell"
            )
            if amount_to_open > Decimal('0'):
                self.user.create_limit_buy_order(self.market,
                                                 amount_to_open + self.epsilon_amount,
                                                 self.intervals[top_index].get_top())

            import time
            time.sleep(5)
            self.user.cancel_all_orders()
            self.lazy_whale.main_cycle()

        self.assertEqual(self.lazy_whale.params['spread_top'], len(self.intervals) - 1)

    def helper_test_buy_after_startup(self):
        """Tests scenario 9:
        Before LW start-up, the user set a sell order with a price under LW spread_bot.
        When the bot start, it will consume the user order until:
        1: the user order is fully consume or,
        2: the spread_top go down enough
        """
        # 1
        self.lazy_whale.params['stop_at_bot'] = False
        self.lazy_whale.params['spread_bot'] = 5
        self.lazy_whale.params['spread_top'] = 8
        self.lazy_whale.params['nb_buy_to_display'] = 3
        self.lazy_whale.params['nb_sell_to_display'] = 3
        spr_bot = self.lazy_whale.params['spread_bot']

        # create sell order by the user
        amount_to_open = self.helper_amount_by_indexes(self.lazy_whale.params['spread_bot'] - 1,
                                                       self.lazy_whale.params['spread_bot'] + 1, 'buy')
        self.user.create_limit_sell_order(self.market,
                                          amount_to_open,
                                          self.intervals[0].get_bottom())

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        self.lazy_whale.main_cycle()
        self.assertEqual(self.lazy_whale.params['spread_bot'], spr_bot - 2)

        # 2
        self.lazy_whale.params['spread_bot'] = 7
        self.lazy_whale.params['spread_top'] = 10
        spr_bot = self.lazy_whale.params['spread_bot']
        self.lazy_whale.cancel_all_intervals()

        # create bigger sell order by the user
        amount_to_open = self.helper_amount_by_indexes(0, self.lazy_whale.params['spread_bot'], 'buy')
        self.user.create_limit_sell_order(self.market,
                                          amount_to_open,
                                          self.intervals[3].get_bottom())

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        self.lazy_whale.main_cycle()
        self.lazy_whale.main_cycle()

        self.assertEqual(self.lazy_whale.params['spread_bot'], spr_bot - 5)
        self.assertEqual(self.lazy_whale.params['spread_top'], spr_bot - 2)

    def helper_test_sell_after_startup(self):
        """Tests scenario 10:
        Before LW start-up, the user set a buy order with a price under LW spread_top.
        When the bot start, it will consume the user order until:
        the user order is fully consume or,
        the spread_bot go up enough
        """
        # 1
        self.lazy_whale.params['stop_at_top'] = False
        self.lazy_whale.params['spread_bot'] = len(self.intervals) - 8
        self.lazy_whale.params['spread_top'] = len(self.intervals) - 5
        self.lazy_whale.params['nb_buy_to_display'] = 3
        self.lazy_whale.params['nb_sell_to_display'] = 3
        spr_top = self.lazy_whale.params['spread_top']

        # create buy order by the user over the spread_top
        amount_to_open = self.helper_amount_by_indexes(self.lazy_whale.params['spread_top'],
                                                       self.lazy_whale.params['spread_top'] + 2, 'sell')
        self.user.create_limit_buy_order(self.market,
                                         amount_to_open,
                                         self.intervals[-1].get_top())

        # start up
        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        self.lazy_whale.main_cycle()
        self.assertEqual(self.lazy_whale.params['spread_top'], spr_top + 2)

        # 2
        self.lazy_whale.allocation = deepcopy(self.profit_allocation)
        self.lazy_whale.params['spread_bot'] = len(self.intervals) - 11
        self.lazy_whale.params['spread_top'] = len(self.intervals) - 8
        spr_top = self.lazy_whale.params['spread_top']
        self.lazy_whale.cancel_all_intervals()

        # create bigger sell order by the user over the spread_top
        amount_to_open = self.helper_amount_by_indexes(len(self.intervals) - 8, len(self.intervals), 'sell')
        self.user.create_limit_buy_order(self.market,
                                         amount_to_open,
                                         self.intervals[len(self.intervals) - 4].get_top())

        self.lazy_whale.strat_init()
        self.lazy_whale.set_safety_orders()

        self.lazy_whale.main_cycle()
        self.lazy_whale.main_cycle()

        self.assertEqual(self.lazy_whale.params['spread_bot'], spr_top + 2)
        self.assertEqual(self.lazy_whale.params['spread_top'], spr_top + 5)

    # SCENARIO 1
    def test_top_is_reached_small_no_specific_allocation(self):
        self.helper_test_top_is_reached_small()

    def test_top_is_reached_small_linear_allocation(self):
        self.lazy_whale.allocation = self.linear_allocation
        self.helper_test_top_is_reached_small()

    def test_top_is_reached_small_curved_allocation(self):
        self.lazy_whale.allocation = self.curved_allocation
        self.helper_test_top_is_reached_small()

    def test_top_is_reached_small_profit_allocation(self):
        self.lazy_whale.allocation = self.profit_allocation
        self.helper_test_top_is_reached_small()

    # SCENARIO 2
    def test_bottom_is_reached_small_no_specific_allocation(self):
        self.helper_test_bottom_is_reached_small()

    def test_bottom_is_reached_small_linear_allocation(self):
        self.lazy_whale.allocation = self.linear_allocation
        self.helper_test_bottom_is_reached_small()

    def test_bottom_is_reached_small_curved_allocation(self):
        self.lazy_whale.allocation = self.curved_allocation
        self.helper_test_bottom_is_reached_small()

    def test_bottom_is_reached_small_profit_allocation(self):
        self.lazy_whale.allocation = self.profit_allocation
        self.helper_test_bottom_is_reached_small()

    # SCENARIO 3
    def test_top_is_reached_big_no_specific_allocation(self):
        self.helper_test_top_is_reached_big()

    def test_top_is_reached_big_linear_allocation(self):
        self.lazy_whale.allocation = self.linear_allocation
        self.helper_test_top_is_reached_big()

    def test_top_is_reached_big_curved_allocation(self):
        self.lazy_whale.allocation = self.curved_allocation
        self.helper_test_top_is_reached_big()

    def test_top_is_reached_big_profit_allocation(self):
        self.lazy_whale.allocation = self.profit_allocation
        self.helper_test_top_is_reached_big()

    # SCENARIO 4
    def test_bottom_is_reached_big_no_specific_allocation(self):
        self.helper_test_bottom_is_reached_big()

    def test_bottom_is_reached_big_linear_allocation(self):
        self.lazy_whale.allocation = self.linear_allocation
        self.helper_test_bottom_is_reached_big()

    def test_bottom_is_reached_big_curved_allocation(self):
        self.lazy_whale.allocation = self.curved_allocation
        self.helper_test_bottom_is_reached_big()

    def test_bottom_is_reached_big_profit_allocation(self):
        self.lazy_whale.allocation = self.profit_allocation
        self.helper_test_bottom_is_reached_big()

    # SCENARIO 5
    def test_mad_market_volatility_tp_is_reached_no_specific_allocation(self):
        self.helper_test_mad_market_volatility_top_is_reached()

    def test_mad_market_volatility_top_is_reached_linear_allocation(self):
        self.lazy_whale.allocation = self.linear_allocation
        self.helper_test_mad_market_volatility_top_is_reached()

    def test_mad_market_volatility_tp_is_reached_curved_allocation(self):
        self.lazy_whale.allocation = self.curved_allocation
        self.helper_test_mad_market_volatility_top_is_reached()

    def test_mad_market_volatility_tp_is_reached_profit_allocation(self):
        self.lazy_whale.allocation = self.profit_allocation
        self.helper_test_mad_market_volatility_top_is_reached()

    # SCENARIO 6
    def test_mad_market_volatility_bottom_is_reached_no_specific_allocation(self):
        self.helper_test_mad_market_volatility_bottom_is_reached()

    def test_mad_market_volatility_bottom_is_reached_linear_allocation(self):
        self.lazy_whale.allocation = self.linear_allocation
        self.helper_test_mad_market_volatility_bottom_is_reached()

    def test_mad_market_volatility_bottom_is_reached_curved_allocation(self):
        self.lazy_whale.allocation = self.curved_allocation
        self.helper_test_mad_market_volatility_bottom_is_reached()

    def test_mad_market_volatility_bottom_is_reached_profit_allocation(self):
        self.lazy_whale.allocation = self.profit_allocation
        self.helper_test_mad_market_volatility_bottom_is_reached()

    # SCENARIO 7
    def test_consume_buys_sells_no_specific_allocation(self):
        self.helper_test_consume_buys_sells()

    def test_consume_buys_sells_linear_allocation(self):
        self.lazy_whale.allocation = self.linear_allocation
        self.helper_test_consume_buys_sells()

    def test_consume_buys_sells_curved_allocation(self):
        self.lazy_whale.allocation = self.curved_allocation
        self.helper_test_consume_buys_sells()

    def test_consume_buys_sells_profit_allocation(self):
        self.lazy_whale.allocation = self.profit_allocation
        self.helper_test_consume_buys_sells()

    # SCENARIO 8
    def test_run_forever_no_specific_allocation(self):
        self.helper_test_run_forever()

    def test_run_forever_linear_allocation(self):
        self.lazy_whale.allocation = self.linear_allocation
        self.helper_test_run_forever()

    # Using cheats here, for curved allocation to pass (it is close to no_specific when going up)
    def test_run_forever_curved_allocation(self):
        self.lazy_whale.allocation = self.curved_allocation
        self.helper_test_run_forever()

    def test_run_forever_profit_allocation(self):
        self.lazy_whale.allocation = self.profit_allocation
        self.helper_test_run_forever()

    # SCENARIO 9
    def test_buy_after_startup_no_specific_allocation(self):
        self.helper_test_buy_after_startup()

    def test_buy_after_startup_linear_allocation(self):
        self.lazy_whale.allocation = self.linear_allocation
        self.helper_test_buy_after_startup()

    def test_buy_after_startup_curved_allocation(self):
        self.lazy_whale.allocation = self.curved_allocation
        self.helper_test_buy_after_startup()

    def test_buy_after_startup_profit_allocation(self):
        self.lazy_whale.allocation = self.profit_allocation
        self.helper_test_buy_after_startup()

    # SCENARIO 10
    def test_sell_after_startup_no_specific_allocation(self):
        self.helper_test_sell_after_startup()

    def test_sell_after_startup_linear_allocation(self):
        self.lazy_whale.allocation = self.linear_allocation
        self.helper_test_sell_after_startup()

    def test_sell_after_startup_curved_allocation(self):
        self.lazy_whale.allocation = self.curved_allocation
        self.helper_test_sell_after_startup()

    def test_sell_after_startup_profit_allocation(self):
        self.lazy_whale.allocation = deepcopy(self.profit_allocation)
        self.helper_test_sell_after_startup()
