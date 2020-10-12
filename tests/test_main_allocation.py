import unittest
from decimal import Decimal
import random

from main.allocation import NoSpecificAllocation, LinearAllocation, CurvedAllocation, LinearCurvedAllocation, \
    ProfitAllocation
from utils.converters import divider, quantizator
from utils.helpers import interval_generator


class TestAllocations(unittest.TestCase):
    @staticmethod
    def is_equal_big_decimal(first, second, epsilon=Decimal('0.01')):
        return abs(first - second) < epsilon

    def setUp(self):
        self.intervals_count = 41
        self.test_cases = 200
        self.interval_indexes = range(self.intervals_count)
        self.min_amount = Decimal('10000')
        self.max_amount = Decimal('20000')
        self.middle_interval_amount = Decimal('8000')
        self.highest_interval_amount = Decimal('12000')

    def test_no_specific_allocation(self):
        allocation = NoSpecificAllocation(self.min_amount, self.intervals_count)
        for _ in range(self.test_cases):
            interval_index = random.choice(self.interval_indexes)
            self.assertEqual(allocation.get_amount(interval_index), self.min_amount)

    def test_linear_allocation(self):
        allocation_from_the_beginning = LinearAllocation(min_amount=self.min_amount, max_amount=self.max_amount,
                                                         intervals_count=self.intervals_count, start_index=0)

        self.assertEqual(allocation_from_the_beginning.linear_coefficient, Decimal('250'))
        self.assertEqual(allocation_from_the_beginning.get_amount(0), self.min_amount)
        self.assertEqual(allocation_from_the_beginning.get_amount(self.intervals_count // 2),
                         divider((self.min_amount + self.max_amount), 2))
        self.assertEqual(allocation_from_the_beginning.get_amount(self.intervals_count - 1), self.max_amount)

        allocation_from_the_middle = LinearAllocation(min_amount=self.min_amount, max_amount=self.max_amount,
                                                      intervals_count=self.intervals_count,
                                                      start_index=self.intervals_count // 2)

        self.assertEqual(allocation_from_the_middle.linear_coefficient, Decimal('500'))
        self.assertEqual(allocation_from_the_middle.get_amount(self.intervals_count // 2), self.min_amount)
        self.assertEqual(allocation_from_the_middle.get_amount(((self.intervals_count // 2) +
                                                                self.intervals_count - 1) // 2),
                         divider((self.min_amount + self.max_amount), 2))
        self.assertEqual(allocation_from_the_middle.get_amount(self.intervals_count - 1), self.max_amount)

        for index in range(self.intervals_count // 2, self.intervals_count):
            self.assertEqual(allocation_from_the_beginning.get_amount((index - self.intervals_count // 2) * 2),
                             allocation_from_the_middle.get_amount(index))

    def test_curved_allocation(self):
        allocation_from_the_beginning = CurvedAllocation(min_amount=self.min_amount, max_amount=self.max_amount,
                                                         intervals_count=self.intervals_count, start_index=0)

        self.assertEqual(allocation_from_the_beginning.exponent_coefficient,
                         quantizator(Decimal('2') ** (Decimal('1') / Decimal('40'))))
        self.assertEqual(allocation_from_the_beginning.get_amount(0), self.min_amount)
        self.assertLess(allocation_from_the_beginning.get_amount(self.intervals_count // 2),
                        divider((self.min_amount + self.max_amount), 2))
        self.assertTrue(self.is_equal_big_decimal(allocation_from_the_beginning.get_amount(self.intervals_count - 1),
                                                  self.max_amount))

        allocation_from_the_middle = CurvedAllocation(min_amount=self.min_amount, max_amount=self.max_amount,
                                                      intervals_count=self.intervals_count,
                                                      start_index=self.intervals_count // 2)

        self.assertEqual(allocation_from_the_middle.exponent_coefficient,
                         quantizator(Decimal('2') ** (Decimal('1') / Decimal('20'))))
        self.assertEqual(allocation_from_the_middle.get_amount(self.intervals_count // 2), self.min_amount)
        self.assertLess(allocation_from_the_middle.get_amount(((self.intervals_count // 2) +
                                                               self.intervals_count - 1) // 2),
                        divider((self.min_amount + self.max_amount), 2))
        self.assertTrue(self.is_equal_big_decimal(allocation_from_the_middle.get_amount(self.intervals_count - 1),
                                                  self.max_amount))

        for index in range(self.intervals_count // 2, self.intervals_count):
            self.assertTrue(self.is_equal_big_decimal(
                allocation_from_the_beginning.get_amount((index - self.intervals_count // 2) * 2),
                allocation_from_the_middle.get_amount(index)))

    def test_linear_curved_allocation(self):
        allocation = LinearCurvedAllocation(self.min_amount, self.middle_interval_amount, self.highest_interval_amount,
                                            self.intervals_count)

        self.assertTrue(self.is_equal_big_decimal(allocation.get_amount(0, 'buy'), self.min_amount))
        self.assertEqual(allocation.get_amount(0, 'sell'), self.middle_interval_amount)
        self.assertEqual(allocation.get_amount(self.intervals_count // 2, 'buy'), self.middle_interval_amount)
        self.assertEqual(allocation.get_amount(self.intervals_count // 2, 'sell'), self.middle_interval_amount)
        self.assertEqual(allocation.get_amount(self.intervals_count - 1, 'buy'), self.middle_interval_amount)
        self.assertTrue(self.is_equal_big_decimal(allocation.get_amount(self.intervals_count - 1, 'sell'),
                                                  self.highest_interval_amount))

        for index in range(self.intervals_count // 2):
            self.assertLessEqual(allocation.get_amount(index, 'buy'), self.min_amount)
            self.assertGreaterEqual(allocation.get_amount(index, 'buy'), self.middle_interval_amount)
            self.assertLessEqual(allocation.get_amount(self.intervals_count - index, 'sell'), self.max_amount)
            self.assertGreaterEqual(allocation.get_amount(self.intervals_count - index, 'sell'),
                                    self.middle_interval_amount)

    def test_profit_allocation(self):
        self.intervals_count = 40
        allocation = ProfitAllocation(interval_generator(Decimal('0.01'), Decimal('0.015'), Decimal('1.0102')),
                                      50, Decimal('0.0025'), self.min_amount)
        self.assertEqual(len(allocation.benefits), 40)
        for i in range(1, 4):
            self.assertEqual(allocation.benefits[self.intervals_count - i].get_max_benefit(), 0)

        for i in range(0, self.intervals_count):
            self.assertEqual(allocation.benefits[i].get_actual_benefit(), 0)
            if i >= 4:
                self.assertNotEqual(allocation.benefits[self.intervals_count - i].get_max_benefit(), 0)
