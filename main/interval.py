from decimal import Decimal

from main.order import Order


class Interval:
    def __init__(self, bottom: Decimal, top: Decimal, buy_orders: [Order],
                 sell_orders: [Order], buy_sum_amount: Decimal, sell_sum_amount: Decimal):
        self.bottom = bottom
        self.top = top
        self.buy_orders = buy_orders
        self.sell_orders = sell_orders
        self.buy_sum_amount = buy_sum_amount
        self.sell_sum_amount = sell_sum_amount

    def sort_buy_orders(self):
        self.buy_orders.sort(lambda order: order.price)

    def sort_sell_orders(self):
        self.sell_orders.sort(lambda order: order.price)
