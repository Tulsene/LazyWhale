from decimal import Decimal
import unittest
from unittest import TestCase

from main.interval import Interval
from main.order import Order
from utils.converters import floor_decimal
from utils.checkers import is_equal_decimal_amount, get_random_decimal
from utils.helpers import interval_generator, get_amount_to_open


class UtilsTests(TestCase):
    def test_interval_generator(self):
        """Testing that intervals spawning correctly"""
        intervals = interval_generator(
            Decimal(0.01), Decimal(0.015), Decimal(1 + (1.02 / 100))
        )
        self.assertIsInstance(intervals[0], Interval)
        self.assertEqual(len(intervals), 40)

    def test_is_equal_decimal_amount(self):
        """Test comparing decimal with precision set in config"""
        first = Decimal("0.000000000000000001010001")
        second = Decimal("0.00000000000000001010011")
        self.assertTrue(is_equal_decimal_amount(first, second))

        first = Decimal("0.01999999")
        second = Decimal("0.02000000")
        self.assertTrue(is_equal_decimal_amount(first, second))

        self.assertFalse(is_equal_decimal_amount(Decimal("1"), Decimal("2")))

        self.assertTrue(is_equal_decimal_amount(Decimal("100"), Decimal("97"), allow_percent_difference=Decimal("5")))
        self.assertFalse(is_equal_decimal_amount(Decimal("100"), Decimal("97"), allow_percent_difference=Decimal("2")))

    def test_get_amount_to_open(self):
        """Test that missing orders that are in prev_orders but not in new_orders are found correctly
        Note that We use this function only for orders in one interval"""
        prev_orders = [
            Order(
                idx=1,
                amount=Decimal("0.1"),
                price=Decimal("0.1"),
                side="buy",
                timestamp="1",
                date="1234",
                filled=Decimal("0"),
            ),
            Order(
                idx=2,
                amount=Decimal("0.9"),
                price=Decimal("0.125"),
                side="buy",
                timestamp="1",
                date="1234",
                filled=Decimal("0.1"),
            ),
            Order(
                idx=3,
                amount=Decimal("0.5"),
                price=Decimal("0.15"),
                side="buy",
                timestamp="1",
                date="1234",
                filled=Decimal("0.1"),
            ),
        ]

        new_orders = [
            Order(
                idx=1,
                amount=Decimal("0.1"),
                price=Decimal("0.1"),
                side="buy",
                timestamp="1",
                date="1234",
                filled=Decimal("0"),
            ),
            Order(
                idx=2,
                amount=Decimal("0.5"),
                price=Decimal("0.125"),
                side="buy",
                timestamp="1",
                date="1234",
                filled=Decimal("0.5"),
            ),
        ]

        self.assertEqual(get_amount_to_open(prev_orders, new_orders), Decimal("0.9"))

    def test_get_random_decimal(self):
        """Test getting random decimal with correct precision"""
        for _ in range(100):
            self.assertLess(get_random_decimal(Decimal('1'), Decimal('2')), Decimal('2'))
            self.assertGreater(get_random_decimal(Decimal('1'), Decimal('2')), Decimal('1'))

            random_decimal = get_random_decimal(Decimal('1'), Decimal('2'), Decimal('1E-5'))
            self.assertEqual(str(random_decimal)[-3:], "000")

            random_decimal = get_random_decimal(Decimal('1000'), Decimal('2000'), Decimal('10'))
            self.assertEqual(random_decimal % 10, 0)

    def test_floor_decimal(self):
        self.assertEqual(floor_decimal(Decimal('12345.12345'), Decimal('1e-3')), Decimal('12345.123'))
        self.assertEqual(floor_decimal(Decimal('12345.12345'), Decimal('1000')), Decimal('12000'))
