from decimal import Decimal


class Order:
    def __init__(self, idx: int, price: Decimal, amount: Decimal, value: Decimal, timestamp: int, date: str):
        self.idx = idx
        self.price = price
        self.amount = amount
        self.value = value
        self.timestamp = timestamp
        self.date = date

    def __eq__(self, other):
        return self.price == other.price
