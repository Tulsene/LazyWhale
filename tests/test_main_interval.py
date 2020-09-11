from decimal import Decimal
import unittest
from unittest import TestCase

from main.interval import Interval
from main.order import Order


class IntervalTests(TestCase):
    def setUp(self):
        self.interval = Interval(Decimal(0.01), Decimal(0.015), Decimal(0.1), Decimal(0.1))

    def test_insert_order(self):
        """Tests that inserted order in the interval are always ordered by 'order.price'"""
        self.assertEqual(len(self.interval.get_buy_orders()), 0)
        self.assertEqual(len(self.interval.get_buy_orders()), 0)

        order1 = Order('1', Decimal(0.011), Decimal(0.01), "_", "_")
        order2 = Order('2', Decimal(0.014), Decimal(0.014), "_", "_")
        order3 = Order('3', Decimal(0.012), Decimal(0.012), "_", "_")

        self.interval.insert_buy_order(order1)
        self.interval.insert_buy_order(order2)
        self.interval.insert_buy_order(order3)
        self.assertEqual(self.interval.get_buy_orders()[0], order1)
        self.assertEqual(self.interval.get_buy_orders()[1], order3)
        self.assertEqual(self.interval.get_buy_orders()[2], order2)

        self.interval.insert_sell_order(order1)
        self.interval.insert_sell_order(order2)
        self.interval.insert_sell_order(order3)
        self.assertEqual(self.interval.get_sell_orders()[0], order1)
        self.assertEqual(self.interval.get_sell_orders()[1], order3)
        self.assertEqual(self.interval.get_sell_orders()[2], order2)

    def test_get_random_price(self):
        price = self.interval.get_random_price_in_interval()
        self.assertTrue(price >= self.interval.get_bottom())
        self.assertTrue(price <= self.interval.get_top())


if __name__ == "__main__":
    unittest.main()
