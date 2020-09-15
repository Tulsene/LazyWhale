from decimal import Decimal
import unittest
from unittest import TestCase

from main.interval import Interval
from utils.checkers import is_equal_decimal
from utils.helpers import interval_generator


class CheckersTests(TestCase):

    def test_interval_generator(self):
        """Testing that intervals spawning correctly"""
        intervals = interval_generator(Decimal(0.01), Decimal(0.015), Decimal(1 + (1.02 / 100)))
        self.assertIsInstance(intervals[0], Interval)
        self.assertEqual(len(intervals), 40)

    def test_is_equal_decimal(self):
        """Test comparing decimal with precision set in config"""
        first = Decimal('0.000000000000000000010001')
        second = Decimal('0.00000000000000000010011')
        self.assertTrue(is_equal_decimal(first, second))

        self.assertFalse(is_equal_decimal(Decimal('1'), Decimal('2')))


if __name__ == "__main__":
    unittest.main()
