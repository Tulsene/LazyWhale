import unittest
from decimal import Decimal
import random

from main.allocation import NoSpecificAllocation, LinearAllocation, CurvedAllocation, ProfitAllocation
from utils.converters import divider
from utils.helpers import interval_generator

EPSILON = Decimal('0.01')
INTERVALS_COUNT = 41
TEST_CASES = 200


def is_equal_big_decimal(first, second, epsilon=EPSILON):
    return abs(first - second) < epsilon


def get_random_decimal(bot, top):
    return Decimal(str(round(random.uniform(float(bot), float(top)), 8)))


class TestNoSpecificAllocation(unittest.TestCase):
    def setUp(self):
        self.intervals_count = INTERVALS_COUNT
        self.test_cases = TEST_CASES
        self.interval_indexes = range(self.intervals_count)
        self.min_amount = Decimal('10000')
        self.allocation = allocation = NoSpecificAllocation(self.min_amount)

    def test_no_specific_allocation(self):

        for _ in range(self.test_cases):
            interval_index = random.choice(self.interval_indexes)
            self.assertEqual(self.allocation.get_amount(interval_index), self.min_amount)

    def test_get_buy_sell_to_open(self):
        for _ in range(self.test_cases):
            interval_index = random.choice(self.interval_indexes)
            self.assertEqual(self.allocation.get_buy_to_open(interval_index, self.min_amount), self.min_amount)
            self.assertEqual(self.allocation.get_sell_to_open(interval_index, self.min_amount), self.min_amount)


class TestLinearAllocation(unittest.TestCase):
    def setUp(self) -> None:
        self.min_amount = Decimal('10000')
        self.max_amount = Decimal('20000')
        self.intervals_count = INTERVALS_COUNT
        self.allocation_from_the_beginning = LinearAllocation(min_amount=self.min_amount, max_amount=self.max_amount,
                                                              intervals_count=self.intervals_count, start_index=0)

        self.allocation_from_the_middle = LinearAllocation(min_amount=self.min_amount, max_amount=self.max_amount,
                                                           intervals_count=self.intervals_count,
                                                           start_index=self.intervals_count // 2)

    def test_linear_allocation(self):

        self.assertEqual(self.allocation_from_the_beginning.linear_coefficient, Decimal('250'))
        self.assertEqual(self.allocation_from_the_beginning.get_amount(0), self.min_amount)
        self.assertEqual(self.allocation_from_the_beginning.get_amount(self.intervals_count // 2),
                         divider((self.min_amount + self.max_amount), 2))
        self.assertEqual(self.allocation_from_the_beginning.get_amount(self.intervals_count - 1), self.max_amount)

        self.assertEqual(self.allocation_from_the_middle.linear_coefficient, Decimal('500'))
        self.assertEqual(self.allocation_from_the_middle.get_amount(self.intervals_count // 2), self.min_amount)
        self.assertEqual(self.allocation_from_the_middle.get_amount(((self.intervals_count // 2) +
                                                                     self.intervals_count - 1) // 2),
                         divider((self.min_amount + self.max_amount), 2))
        self.assertEqual(self.allocation_from_the_middle.get_amount(self.intervals_count - 1), self.max_amount)

        for index in range(self.intervals_count // 2, self.intervals_count):
            self.assertEqual(self.allocation_from_the_beginning.get_amount((index - self.intervals_count // 2) * 2),
                             self.allocation_from_the_middle.get_amount(index))

    def test_get_buy_to_open(self):
        amount_to_open_buy = self.allocation_from_the_beginning.get_buy_to_open(0, Decimal('1000'))
        self.assertEqual(amount_to_open_buy, Decimal('1000'))

        amount_to_open_buy = self.allocation_from_the_beginning \
            .get_buy_to_open(self.intervals_count - 1, Decimal('2000'))

        self.assertEqual(amount_to_open_buy, Decimal('1000'))

        amount_to_open_buy = self.allocation_from_the_beginning \
            .get_buy_to_open(self.intervals_count // 2, Decimal('1500'))
        self.assertEqual(amount_to_open_buy, Decimal('1000'))

    def test_get_sell_to_open(self):
        for _ in range(TEST_CASES):
            interval_index = random.choice(range(self.intervals_count))
            self.assertEqual(self.allocation_from_the_beginning.get_sell_to_open(interval_index, self.min_amount),
                             self.min_amount)
            self.assertEqual(self.allocation_from_the_middle.get_sell_to_open(interval_index, self.min_amount),
                             self.min_amount)


class TestCurvedAllocation(unittest.TestCase):
    def setUp(self) -> None:
        self.lowest_interval_amount = Decimal('10000')
        self.middle_interval_amount = Decimal('8000')
        self.highest_interval_amount = Decimal('12000')
        self.intervals_count = INTERVALS_COUNT
        self.allocation = CurvedAllocation(self.lowest_interval_amount, self.middle_interval_amount,
                                           self.highest_interval_amount,
                                           self.intervals_count)

    def test_curved_allocation(self):
        self.assertTrue(is_equal_big_decimal(self.allocation.get_amount(0, 'buy'), self.lowest_interval_amount))
        self.assertEqual(self.allocation.get_amount(0, 'sell'), self.middle_interval_amount)
        self.assertEqual(self.allocation.get_amount(self.intervals_count // 2, 'buy'), self.middle_interval_amount)
        self.assertEqual(self.allocation.get_amount(self.intervals_count // 2, 'sell'), self.middle_interval_amount)
        self.assertEqual(self.allocation.get_amount(self.intervals_count - 1, 'buy'), self.middle_interval_amount)
        self.assertTrue(is_equal_big_decimal(self.allocation.get_amount(self.intervals_count - 1, 'sell'),
                                             self.highest_interval_amount))

        for index in range(self.intervals_count // 2):
            self.assertLessEqual(self.allocation.get_amount(index, 'buy'), self.lowest_interval_amount)
            self.assertGreaterEqual(self.allocation.get_amount(index, 'buy'), self.middle_interval_amount)
            self.assertLessEqual(self.allocation.get_amount(self.intervals_count - index - 1, 'sell'),
                                 self.highest_interval_amount)
            self.assertGreaterEqual(self.allocation.get_amount(self.intervals_count - index - 1, 'sell'),
                                    self.middle_interval_amount)

    def test_get_buy_to_open(self):
        self.assertEqual(self.allocation.get_buy_to_open(0, Decimal('1000')), Decimal('1000'))
        self.assertEqual(self.allocation.get_buy_to_open(self.intervals_count // 4, Decimal('870')), Decimal('870'))
        self.assertEqual(self.allocation.get_buy_to_open(self.intervals_count // 2, Decimal('1000')), Decimal('1000'))
        self.assertEqual(self.allocation.get_buy_to_open(self.intervals_count // 2 - 1, Decimal('100')), Decimal('100'))
        self.assertEqual(
            self.allocation.get_buy_to_open(self.intervals_count // 4 * 3,
                                            self.allocation.get_amount(self.intervals_count // 4 * 3, 'sell')),
            Decimal('8000'))
        self.assertLess(self.allocation.get_buy_to_open(self.intervals_count // 4 * 3, Decimal('2000')),
                        Decimal('1700'))

        self.assertTrue(is_equal_big_decimal(self.allocation.get_buy_to_open(self.intervals_count - 1, Decimal('1200')),
                        Decimal('800')))

    def test_get_sell_to_open(self):
        self.assertEqual(self.allocation.get_sell_to_open(0, Decimal('1000')), Decimal('800'))
        self.assertLess(self.allocation.get_sell_to_open(self.intervals_count // 4, Decimal('870')), Decimal('780'))
        self.assertEqual(self.allocation.get_sell_to_open(self.intervals_count // 4,
                                                          self.allocation.get_amount(self.intervals_count // 4, 'buy')),
                         Decimal('8000'))
        self.assertEqual(self.allocation.get_sell_to_open(self.intervals_count // 2, Decimal('1000')), Decimal('1000'))
        self.assertEqual(self.allocation.get_sell_to_open(self.intervals_count // 2 + 1, Decimal('100')),
                         Decimal('100'))

        self.assertEqual(self.allocation.get_sell_to_open(self.intervals_count // 4 * 3, Decimal('2000')),
                         Decimal('2000'))

        self.assertEqual(self.allocation.get_sell_to_open(self.intervals_count - 1, Decimal('8000')),
                         Decimal('8000'))


class TestProfitAllocation(unittest.TestCase):
    def setUp(self) -> None:
        self.min_amount = Decimal('10000')
        self.intervals_count = 40
        self.allocation = ProfitAllocation(interval_generator(Decimal('0.01'), Decimal('0.015'), Decimal('1.0102')),
                                      50, Decimal('0.9975'), self.min_amount)

    def test_profit_allocation(self):

        self.assertEqual(len(self.allocation.benefits), 40)
        for i in range(1, 4):
            self.assertEqual(self.allocation.benefits[self.intervals_count - i].get_max_benefit(), 0)

        for i in range(0, self.intervals_count):
            self.assertEqual(self.allocation.benefits[i].get_actual_benefit(), 0)
            if i >= 4:
                self.assertNotEqual(self.allocation.benefits[self.intervals_count - i].get_max_benefit(), 0)

    def test_get_buy_to_open(self):
        for _ in range(TEST_CASES):
            interval_index = random.choice(range(self.intervals_count))
            self.assertEqual(self.allocation.get_buy_to_open(interval_index, self.min_amount),
                             self.min_amount)
            self.assertEqual(self.allocation.get_buy_to_open(interval_index, self.min_amount),
                             self.min_amount)

    def test_get_sell_to_open(self):
        for _ in range(TEST_CASES):
            interval_index = random.choice(range(self.intervals_count))
            self.assertEqual(self.allocation.get_sell_to_open(interval_index, self.min_amount),
                             self.min_amount)
            self.assertEqual(self.allocation.get_sell_to_open(interval_index, self.min_amount),
                             self.min_amount)

        self.allocation.benefits[30].add_actual_benefit(Decimal('0.00001'))
        self.assertEqual(self.allocation.benefits[30].get_actual_benefit(), Decimal('0.00001'))
        self.allocation.get_sell_to_open(30, Decimal('10000.000001'))
        self.assertEqual(self.allocation.benefits[30].get_actual_benefit(), Decimal('0.000009'))
        self.allocation.get_sell_to_open(30, Decimal('10000.000005'))
        self.assertEqual(self.allocation.benefits[30].get_actual_benefit(), Decimal('0.000004'))
        self.allocation.get_sell_to_open(30, Decimal('10000.000005'))
        self.assertEqual(self.allocation.benefits[30].get_actual_benefit(), Decimal('0'))
