from decimal import Decimal

from main.order import Order


class Interval:
    def __init__(self, bottom: Decimal, top: Decimal, buy_orders: [Order], sell_orders: [Order]):
        self.bottom = bottom
        self.top = top
        self.buy_orders = buy_orders
        self.sell_orders = sell_orders
