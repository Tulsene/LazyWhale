from decimal import Decimal
import unittest
from unittest import TestCase

from main.interval import Interval
from utils.checkers import interval_generator


class CheckersTests(TestCase):

    def test_interval_generator(self):
        """Testing that intervals spawning correctly"""
        intervals = interval_generator(Decimal(0.01), Decimal(0.015), Decimal(1 + (1.02 / 100)))
        self.assertIsInstance(intervals[0], Interval)
        self.assertEqual(len(intervals), 40)


if __name__ == "__main__":
    unittest.main()
