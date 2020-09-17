from decimal import Decimal

from utils.checkers import is_equal_decimal
from utils.converters import multiplier, quantizator
import config.config as config


class Order:
    def __init__(self, idx, price, amount, side: str, timestamp, date: str,
                 fee=config.FEES_COEFFICIENT, filled=Decimal('0')):
        self.id = str(idx)
        self.price = quantizator(Decimal(price))
        self.amount = quantizator(Decimal(amount))
        self.value = multiplier(self.price, self.amount, Decimal(fee))
        # TODO: redo this assert
        assert self.value >= config.MIN_VALUE_ORDER
        self.timestamp = int(timestamp)
        self.date = date
        self.filled = filled
        self.side = side

    # TODO: apply not fulfilled orders (cannot compare by index)
    def __eq__(self, other):
        return is_equal_decimal(self.price, other.price) and self.id == other.id and self.side == other.side

    def __str__(self):
        return f"id: {self.id}\n" \
               f"price: {self.price}\n" \
               f"amount: {self.amount}\n" \
               f"value: {self.value}\n" \
               f"timestamp: {self.timestamp}\n" \
               f"date: {self.date}\n"

    def __repr__(self):
        return str(self)
