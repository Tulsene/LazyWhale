from decimal import Decimal
import unittest
from unittest import TestCase

from main.interval import Interval
from main.order import Order


class IntervalTests(TestCase):
    def setUp(self):
        self.interval = Interval(Decimal(0.01), Decimal(0.015))
        self.order1 = Order(
            "1", Decimal("0.011"), Decimal("0.01"), "buy/sell", "1", "_"
        )
        self.order2 = Order(
            "2", Decimal("0.014"), Decimal("0.014"), "buy/sell", "1", "_"
        )
        self.order3 = Order(
            "3", Decimal("0.012"), Decimal("0.012"), "buy/sell", "1", "_"
        )

    def test_insert_order(self):
        """Tests that inserted order in the interval are always ordered by 'order.price'"""
        self.assertEqual(len(self.interval.get_buy_orders()), 0)
        self.assertEqual(len(self.interval.get_buy_orders()), 0)

        self.interval.insert_buy_order(self.order1)
        self.interval.insert_buy_order(self.order2)
        self.interval.insert_buy_order(self.order3)
        self.assertEqual(self.interval.get_buy_orders()[0], self.order1)
        self.assertEqual(self.interval.get_buy_orders()[1], self.order3)
        self.assertEqual(self.interval.get_buy_orders()[2], self.order2)

        self.interval.insert_sell_order(self.order1)
        self.interval.insert_sell_order(self.order2)
        self.interval.insert_sell_order(self.order3)
        self.assertEqual(self.interval.get_sell_orders()[0], self.order1)
        self.assertEqual(self.interval.get_sell_orders()[1], self.order3)
        self.assertEqual(self.interval.get_sell_orders()[2], self.order2)

    def test_get_random_price(self):
        """Tests that price is generated in the correct interval"""
        price = self.interval.get_random_price_in_interval()
        self.assertTrue(price >= self.interval.get_bottom())
        self.assertTrue(price <= self.interval.get_top())

    def test_equal_interval(self):
        """Tests that the interval with all same attributes are the same"""
        same_interval = Interval(self.interval.get_bottom(), self.interval.get_top())
        self.assertEqual(same_interval, self.interval)

    def test_generate_orders_by_amount(self):
        """Tests that generates correct number of orders with correct sum amount"""
        total_amount = Decimal("1")
        count_of_orders = 5
        min_amount = Decimal("0.1")
        orders = self.interval.generate_orders_by_amount(
            total_amount, min_amount, count_of_orders
        )

        self.assertEqual(len(orders), 5)
        sum_amount = sum([order["amount"] for order in orders])
        self.assertEqual(sum_amount, total_amount)

    def test_get_orders_amount(self):
        """Test that amount of orders in interval is calculating correctly (depend on filled)"""
        self.interval.insert_buy_order(self.order1)
        self.interval.insert_buy_order(self.order2)
        self.interval.insert_buy_order(self.order3)
        self.interval.insert_sell_order(self.order1)
        self.interval.insert_sell_order(self.order2)

        amount_all_buy = self.interval.get_buy_orders_amount()
        amount_all_sell = self.interval.get_sell_orders_amount()

        self.assertEqual(amount_all_buy, Decimal("0.036"))
        self.assertEqual(amount_all_sell, Decimal("0.024"))

    def test_get_empty_amount_order(self):
        """Test, that check for empty amounts works"""
        self.assertFalse(self.interval.get_empty_amount_orders())
        self.interval.insert_buy_order(Order("12344321", Decimal("0E-8"), Decimal("0"), "buy/sell", "1", "_"))
        self.assertTrue(self.interval.get_empty_amount_orders())
        self.interval.remove_empty_amount_orders()
        self.assertFalse(self.interval.get_empty_amount_orders())

        self.interval.insert_sell_order(Order("12344321", Decimal("0E-8"), Decimal("0"), "buy/sell", "1", "_"))
        self.assertTrue(self.interval.get_empty_amount_orders())
        self.interval.remove_empty_amount_orders()
        self.assertFalse(self.interval.get_empty_amount_orders())
