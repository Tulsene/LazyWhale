from decimal import Decimal

from utils.checkers import is_equal_decimal_amount
from utils.converters import multiplier
import config.config as config


class Order:
    def __init__(
        self,
        idx,
        price,
        amount,
        side: str,
        timestamp,
        date: str,
        fee=config.FEES_COEFFICIENT,
        filled=Decimal("0"),
    ):
        self.id = str(idx)
        self.price = Decimal(price)
        self.amount = Decimal(amount)
        self.value = multiplier(self.price, self.amount, Decimal(fee))
        self.timestamp = int(timestamp)
        self.date = date
        self.filled = Decimal(filled)
        self.side = side

    def __eq__(self, other):
        return (
            self.price == other.price
            and ((is_equal_decimal_amount(self.amount, other.amount))
                 or (is_equal_decimal_amount(self.amount, other.amount, Decimal('5')) and self.filled == other.filled))
            and self.id == other.id
            and self.side == other.side
        )

    def __str__(self):
        return (
            f"id: {self.id} "
            f"side: {self.side} "
            f"price: {self.price} "
            f"amount: {self.amount} "
            f"filled: {self.filled} "
            f"value: {self.value} "
            f"timestamp: {self.timestamp} "
            f"date: {self.date}\n"
        )

    def __repr__(self):
        return str(self)
