from random import uniform
from decimal import Decimal

from main.order import Order
from utils.checkers import is_equal_decimal
import config.config as config
from utils.converters import multiplier


def get_random_decimal(bot, top):
    return Decimal(str(round(uniform(float(bot), float(top)), config.DECIMAL_PRECISION)))


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
        orders_filtered = [order for order in self.__buy_orders if is_equal_decimal(order.price, price)]
        return len(orders_filtered) > 0

    def find_sell_order_by_price(self, price):
        orders_filtered = [order for order in self.__sell_orders if is_equal_decimal(order.price, price)]
        return len(orders_filtered) > 0

    def generate_orders_by_amount(self, total_amount: Decimal, min_amount, count_order: int = 2) -> [dict]:
        """Returns orders(dict) with random price inside interval and with amount sum = total_amount
        Does not store this orders in Interval (cause they are not opened yet)
        """
        # TODO: redo this assert
        assert min_amount * count_order < total_amount

        random_amount = total_amount - min_amount * count_order
        rand_max = random_amount / Decimal(str(count_order))
        current_amount = Decimal('0')

        orders_to_open = []

        # populate with `count_order - 1` order
        for _ in range(count_order - 1):
            order_amount = min_amount + get_random_decimal(rand_max / Decimal('2'), rand_max)
            current_amount += order_amount
            price = self.get_random_price_in_interval()
            orders_to_open.append({
                "price": price,
                "amount": order_amount,
            })

        assert total_amount >= min_amount + current_amount
        # Add last order to have the sum of total_amount
        orders_to_open.append({
            "price": self.get_random_price_in_interval(),
            "amount": total_amount - current_amount,
        })

        return orders_to_open

    def get_random_price_in_interval(self):
        return get_random_decimal(self.__bottom, self.__top)

    def get_bottom(self) -> Decimal:
        return self.__bottom

    def get_top(self) -> Decimal:
        return self.__top

    def get_buy_sum_amount(self) -> Decimal:
        return self.__sell_sum_amount

    def get_sell_sum_amount(self) -> Decimal:
        return self.__buy_sum_amount

    def get_buy_orders_amount(self) -> Decimal:
        """Calculate amount of existing orders in interval
         use_filled - with calculating part of filled orders or with all orders"""
        if not self.__buy_orders:
            return Decimal('0')

        return sum([order.amount for order in self.__buy_orders])

    def get_sell_orders_amount(self) -> Decimal:
        """Calculate amount of existing orders in interval
         use_filled - with calculating part of filled orders or with all orders"""
        if not self.__sell_orders:
            return Decimal('0')

        return sum([order.amount for order in self.__sell_orders])

    def get_buy_orders(self) -> [Order]:
        return self.__buy_orders

    def get_sell_orders(self) -> [Order]:
        return self.__sell_orders

    def remove_buy_orders(self) -> None:
        self.__buy_orders = []

    def remove_sell_orders(self) -> None:
        self.__sell_orders = []

    def check_empty(self) -> bool:
        return len(self.__buy_orders) == 0 and len(self.__sell_orders) == 0

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
