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

    def place_buy_order_random_price(self, manager, market, total_amount: Decimal, count_order: int = 2):
        rand_max = total_amount / (count_order - 1)
        for _ in range(count_order):
            order_amount = Decimal(uniform(float(rand_max / 2), float(rand_max)))
            price = self.get_random_price_in_interval()
            new_order = manager.create_limit_buy_order(market, order_amount, price)
            self.insert_buy_order(new_order)

    def place_sell_order_random_price(self, manager, market, total_amount: Decimal, count_order: int = 2):
        rand_max = total_amount / (count_order - 1)
        for _ in range(count_order):
            order_amount = Decimal(uniform(float(rand_max / 2), float(rand_max)))
            new_order = manager.create_limit_sell_order(market, order_amount, self.get_random_price_in_interval())
            self.insert_buy_order(new_order)

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

    def __eq__(self, other):
        return self.__bottom == other.__bottom and self.__top == other.__top \
               and self.__buy_orders == other.get_buy_orders() \
               and self.__sell_orders == other.get_sell_orders() \
               and self.__buy_sum_amount == other.get_buy_sum_amount() \
               and self.__sell_sum_amount == other.get_sell_sum_amount()

    def __str__(self):
        str_interval = f"Interval({self.__bottom}, {self.__top})"
        str_interval += f"\nbuy_orders:\n{self.__buy_orders}" if self.__buy_orders else ""
        str_interval += f"\nsell_orders:\n{self.__sell_orders}\n" if self.__sell_orders else ""
        return str_interval

    def __repr__(self):
        return str(self)
