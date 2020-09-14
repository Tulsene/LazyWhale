from decimal import Decimal
from utils.converters import multiplier


class Order:
    def __init__(self, idx, price, amount, timestamp, date: str, fee=Decimal('0.9975')):
        self.idx = str(idx)
        self.price = Decimal(price)
        self.amount = Decimal(amount)
        self.value = multiplier(self.price, self.amount, Decimal(fee))
        self.timestamp = int(timestamp)
        self.date = date

    def __eq__(self, other):
        return self.price == other.price or self.idx == other.idx

    def __str__(self):
        return f"id: {self.idx}\n" \
               f"price: {self.price}\n" \
               f"amount: {self.amount}\n" \
               f"value: {self.value}\n" \
               f"timestamp: {self.timestamp}\n" \
               f"date: {self.date}\n"

    def __repr__(self):
        return str(self)
