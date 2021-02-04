from decimal import Decimal

from config import config
from main.order import Order
from utils.checkers import get_random_decimal
from utils.converters import floor_decimal


class Interval:
    def __init__(self, bottom: Decimal, top: Decimal):
        self.__bottom = bottom
        self.__top = top
        self.__buy_orders = []
        self.__sell_orders = []

    def insert_buy_order(self, order) -> None:
        """Inserts order in self.__buy_orders with saving ordering by price"""
        idx_to_insert = 0
        while (
            idx_to_insert < len(self.__buy_orders)
            and order.price > self.__buy_orders[idx_to_insert].price
        ):
            idx_to_insert += 1

        self.__buy_orders.insert(idx_to_insert, order)

    def insert_sell_order(self, order) -> None:
        """Inserts order in self.__sell_orders with saving ordering by price"""
        idx_to_insert = 0
        while (
            idx_to_insert < len(self.__sell_orders)
            and order.price > self.__sell_orders[idx_to_insert].price
        ):
            idx_to_insert += 1

        self.__sell_orders.insert(idx_to_insert, order)

    def find_buy_order_by_id(self, order_id):
        orders_filtered = [order for order in self.__buy_orders if order.id == order_id]
        return len(orders_filtered) > 0

    def find_sell_order_by_id(self, order_id):
        orders_filtered = [
            order for order in self.__sell_orders if order.id == order_id
        ]
        return len(orders_filtered) > 0

    def find_buy_order_by_price(self, price):
        orders_filtered = [order for order in self.__buy_orders if order.price == price]
        return len(orders_filtered) > 0

    def find_sell_order_by_price(self, price):
        orders_filtered = [
            order for order in self.__sell_orders if order.price == price
        ]
        return len(orders_filtered) > 0

    def get_random_price_not_in_array(self, orders):
        price = self.get_random_price_in_interval()

        # failsafe if there is 2 orders with the same price happens (really low frequency, but still)
        while price in [order["price"] for order in orders]:
            price = self.get_random_price_in_interval()

        return price

    def generate_orders_by_amount(
        self, total_amount: Decimal, min_amount, count_order: int = 2
    ) -> [dict]:
        """Returns orders(dict) with random price inside interval and with amount sum = total_amount
        Does not store this orders in Interval (cause they are not opened yet)
        """
        # for all orders to have correct rounded amount
        total_amount = floor_decimal(total_amount, config.AMOUNT_RANDOM_PRECISION)
        # TD: redo this assert if needed
        assert min_amount * count_order < total_amount

        random_amount = total_amount - min_amount * count_order
        rand_max = random_amount / Decimal(str(count_order))
        current_amount = Decimal("0")

        orders_to_open = []

        # populate with `count_order - 1` order
        for _ in range(count_order - 1):
            order_amount = min_amount + get_random_decimal(
                rand_max / Decimal("2"), rand_max, config.AMOUNT_RANDOM_PRECISION
            )
            current_amount += order_amount

            orders_to_open.append(
                {
                    "price": self.get_random_price_not_in_array(orders_to_open),
                    "amount": order_amount,
                }
            )

        assert total_amount >= min_amount + current_amount

        # Add last order to have the sum of total_amount
        orders_to_open.append(
            {
                "price": self.get_random_price_not_in_array(orders_to_open),
                "amount": total_amount - current_amount,
            }
        )

        return orders_to_open

    def get_random_price_in_interval(self):
        return get_random_decimal(
            self.__bottom, self.__top, config.PRICE_RANDOM_PRECISION
        )

    def get_bottom(self) -> Decimal:
        return self.__bottom

    def get_top(self) -> Decimal:
        return self.__top

    def get_buy_orders_amount(self) -> Decimal:
        """Calculate amount of existing orders in interval
        use_filled - with calculating part of filled orders or with all orders"""
        if not self.__buy_orders:
            return Decimal("0")

        return sum([order.amount for order in self.__buy_orders])

    def get_sell_orders_amount(self) -> Decimal:
        """Calculate amount of existing orders in interval
        use_filled - with calculating part of filled orders or with all orders"""
        if not self.__sell_orders:
            return Decimal("0")

        return sum([order.amount for order in self.__sell_orders])

    def get_buy_orders(self) -> [Order]:
        return self.__buy_orders

    def get_sell_orders(self) -> [Order]:
        return self.__sell_orders

    def set_buy_orders(self, buy_orders: [Order]) -> None:
        self.remove_buy_orders()
        for order in buy_orders:
            self.insert_buy_order(order)

    def set_sell_orders(self, sell_orders: [Order]) -> None:
        self.remove_sell_orders()
        for order in sell_orders:
            self.insert_sell_order(order)

    def remove_buy_orders(self) -> None:
        self.__buy_orders = []

    def remove_sell_orders(self) -> None:
        self.__sell_orders = []

    def check_empty(self) -> bool:
        return self.check_empty_buy() and self.check_empty_sell()

    def check_empty_buy(self):
        return len(self.__buy_orders) == 0

    def check_empty_sell(self):
        return len(self.__sell_orders) == 0

    def get_empty_amount_orders(self) -> [Order]:
        """returns True, if there is an order with 0 amount and removes them"""
        return self.get_empty_amount_buy() + self.get_empty_amount_sell()

    def get_empty_amount_buy(self) -> [Order]:
        return [order for order in self.__buy_orders if order.amount == Decimal("0")]

    def get_empty_amount_sell(self) -> [Order]:
        return [order for order in self.__sell_orders if order.amount == Decimal("0")]

    def remove_empty_amount_orders(self):
        self.__buy_orders = [
            order for order in self.__buy_orders if order.amount != Decimal("0")
        ]
        self.__sell_orders = [
            order for order in self.__sell_orders if order.amount != Decimal("0")
        ]

    def __eq__(self, other):
        return (
            self.__bottom == other.__bottom
            and self.__top == other.__top
            and self.__buy_orders == other.get_buy_orders()
            and self.__sell_orders == other.get_sell_orders()
        )

    def __str__(self):
        str_interval = f"\nInterval({self.__bottom}, {self.__top})"
        str_interval += (
            f" Count buy orders: {len(self.__buy_orders)}"
            f" buy_orders_amount: {self.get_buy_orders_amount()}"
            if self.__buy_orders
            else ""
        )
        str_interval += (
            f" Count sell orders: {len(self.__sell_orders)}"
            f" sell_orders_amount: {self.get_sell_orders_amount()}"
            if self.__sell_orders
            else ""
        )
        return str_interval

    def __repr__(self):
        return str(self)
