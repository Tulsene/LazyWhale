from decimal import Decimal
from abc import ABC, abstractmethod

from utils.converters import divider, quantizator


def calculate_exponential_coefficient(y1, x2, y2):
    """For simplicity: x1 = 0"""
    return quantizator((y2 / y1) ** (1 / x2))


def exponent(linear_coefficient, exponential_coefficient, power):
    """y = a*(x ** b)"""
    return quantizator(linear_coefficient * (exponential_coefficient ** power))


class AbstractAllocation(ABC):
    @abstractmethod
    def get_amount(self, interval_index: int = 0, side: str = 'none', additional_amount: Decimal = Decimal('0'))\
            -> Decimal:
        """Will be implemented in subclasses:
        function to calculate correct amount of MANA for each interval"""
        pass


class NoSpecificAllocation(AbstractAllocation):
    def __init__(self, constant_amount):
        self.amount = constant_amount

    def get_amount(self, interval_index: int = 0, side: str = 'none', additional_amount: Decimal = Decimal('0')):
        """Just simply returns the same amount for each interval"""
        return self.amount


class LinearAllocation(AbstractAllocation):
    def __init__(self, min_amount: Decimal, max_amount: Decimal, intervals_count: int, start_index: int = 0):
        self.min_amount = min_amount
        self.linear_coefficient = divider(max_amount - min_amount, intervals_count - start_index)
        self.start_index = start_index

    def get_amount(self, interval_index: int = 0, side: str = 'none', additional_amount: Decimal = Decimal('0')):
        """Linear coefficient makes such computations, that:
        if interval_index = 0 - return min_amount,
        if interval_index = len(intervals) - return max_amount"""
        if side == 'buy' or interval_index < self.start_index:
            return self.min_amount

        return self.min_amount + self.linear_coefficient * interval_index


class CurvedAllocation(AbstractAllocation):
    def __init__(self, min_amount: Decimal, max_amount: Decimal, intervals_count: int, start_index: int = 0):
        self.min_amount = min_amount
        self.exponent_coefficient = calculate_exponential_coefficient(min_amount, intervals_count - start_index,
                                                                      max_amount)
        self.start_index = start_index

    def get_amount(self, interval_index: int = 0, side: str = 'none', additional_amount: Decimal = Decimal('0')):
        if side == 'buy' or interval_index < self.start_index:
            return self.min_amount

        return exponent(self.min_amount, self.exponent_coefficient, interval_index)


class CurvedLinearAllocation(AbstractAllocation):
    def __init__(self, lowest_interval_amount: Decimal, middle_interval_amount: Decimal,
                 highest_interval_amount: Decimal, intervals_count: int):
        self.middle_amount = middle_interval_amount
        self.middle_point = intervals_count // 2
        self.buy_exponent_coefficient\
            = calculate_exponential_coefficient(middle_interval_amount, self.middle_point, lowest_interval_amount)
        self.sell_exponent_coefficient\
            = calculate_exponential_coefficient(middle_interval_amount, self.middle_point, highest_interval_amount)

    def get_amount(self, interval_index: int = 0, side: str = 'none', additional_amount: Decimal = Decimal('0')):
        if side == 'buy':
            if interval_index >= self.middle_point:
                return self.middle_amount

            return exponent(self.middle_amount, self.buy_exponent_coefficient, self.middle_point - interval_index)

        elif side == 'sell':
            if interval_index <= self.middle_point:
                return self.middle_amount

            return exponent(self.middle_amount, self.sell_exponent_coefficient, interval_index - self.middle_point)

        else:
            return self.middle_amount


# TODO: implement this
class ProfitAllocation(AbstractAllocation):
    def __init__(self, amount: Decimal):
        pass

    def get_amount(self, interval_index: int = 0, side: str = 'none',
                   additional_amount: Decimal = Decimal('0')):
        pass


