from random import uniform
from decimal import Decimal

from main.order import Order


class Interval:
    def __init__(self, bottom: Decimal, top: Decimal, buy_sum_amount: Decimal = None, sell_sum_amount: Decimal = None):
        self.__bottom = bottom
        self.__top = top
        self.__buy_sum_amount = buy_sum_amount
        self.__sell_sum_amount = sell_sum_amount
        self.__buy_orders = []
        self.__sell_orders = []

    def insert_buy_order(self, order) -> None:
        """Inserts order in self.__buy_orders with saving ordering by price"""
        idx_to_insert = 0
        while idx_to_insert < len(self.__buy_orders) and order.price > self.__buy_orders[idx_to_insert].price:
            idx_to_insert += 1

        self.__buy_orders.insert(idx_to_insert, order)

    def insert_sell_order(self, order) -> None:
        """Inserts order in self.__sell_orders with saving ordering by price"""
        idx_to_insert = 0
        while idx_to_insert < len(self.__sell_orders) and order.price > self.__sell_orders[idx_to_insert].price:
            idx_to_insert += 1

        self.__sell_orders.insert(idx_to_insert, order)

    def find_buy_order_by_price(self, price):
        orders_filtered = [order for order in self.__buy_orders if order.price == price]
        return len(orders_filtered) > 0

    def find_sell_order_by_price(self, price):
        orders_filtered = [order for order in self.__sell_orders if order.price == price]
        return len(orders_filtered) > 0

    def get_random_price_in_interval(self):
        return Decimal(uniform(float(self.__bottom), float(self.__top)))

    def get_bottom(self) -> Decimal:
        return self.__bottom

    def get_top(self) -> Decimal:
        return self.__top

    def get_buy_sum_amount(self) -> Decimal:
        return self.__sell_sum_amount

    def get_sell_sum_amount(self) -> Decimal:
        return self.__buy_sum_amount

    def get_buy_orders(self) -> [Order]:
        return self.__buy_orders

    def get_sell_orders(self) -> [Order]:
        return self.__sell_orders

    def __str__(self):
        return f"Interval({self.__bottom}, {self.__top})" \
               + f"\nbuy_orders:\n{self.__buy_orders}" if self.__buy_orders else "" \
               + f"\nsell_orders:\n{self.__sell_orders}\n" if self.__sell_orders else ""

    def __repr__(self):
        return str(self)
