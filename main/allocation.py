from decimal import Decimal
from abc import ABC, abstractmethod

from main.interval import Interval
from utils.converters import divider, quantizator, multiplier
import config.config as config
import utils.converters as convert


def calculate_exponential_coefficient(y1, x2, y2):
    """For simplicity: x1 = 0"""
    return quantizator((y2 / y1) ** (Decimal("1") / x2))


def exponent(linear_coefficient, exponential_coefficient, power):
    """y = a*(x ** b)"""
    return quantizator(linear_coefficient * (exponential_coefficient ** power))


def generate_empty_benefits(intervals_count: int):
    return [Benefit(Decimal("0"), Decimal("0")) for _ in range(intervals_count)]


def generate_benefits_by_intervals(
    intervals: [Interval], profit_allocation: Decimal, fees: Decimal, amount: Decimal
):
    benefits = generate_empty_benefits(len(intervals))
    for i in range(3, len(intervals)):
        benefits[i - 3].set_max_benefit(
            quantizator(
                (intervals[i].get_bottom() - intervals[i - 3].get_top())
                * amount
                * profit_allocation
                * fees
                * fees
            )
        )

    return benefits


class Benefit:
    def __init__(self, actual_benefit, max_benefit):
        self.__actual_benefit = actual_benefit
        self.__max_benefit = max_benefit

    def get_max_benefit(self):
        return self.__max_benefit

    def set_max_benefit(self, max_benefit: Decimal):
        self.__max_benefit = max_benefit

    def get_actual_benefit(self):
        return self.__actual_benefit

    def set_actual_benefit(self, actual_benefit: Decimal):
        actual_benefit = max(Decimal("0"), actual_benefit)
        self.__actual_benefit = min(actual_benefit, self.__max_benefit)

    def add_actual_benefit(self, additional_benefit: Decimal):
        self.set_actual_benefit(self.__actual_benefit + additional_benefit)

    def subtract_actual_benefit(self, benefit: Decimal):
        self.set_actual_benefit(self.__actual_benefit - benefit)

    def __str__(self):
        return f"Benefit(actual_benefit = {self.__actual_benefit}, max_benefit = {self.__max_benefit})"

    def __repr__(self):
        return str(self)


class AbstractAllocation(ABC):
    @abstractmethod
    def get_amount(self, interval_index: int = 0, side: str = "none") -> Decimal:
        """Will be implemented in subclasses:
        function to calculate correct amount of MANA for each interval"""
        pass

    @abstractmethod
    def get_buy_to_open(
        self, interval_index: int, amount_consumed_sell: Decimal
    ) -> Decimal:
        """Calculate amount buy to open in interval when amount_consumed_sell is known"""
        pass

    @abstractmethod
    def get_sell_to_open(
        self, interval_index: int, amount_consumed_buy: Decimal
    ) -> Decimal:
        """Calculate amount buy to open in interval when amount_consumed_sell is known"""
        pass


class NoSpecificAllocation(AbstractAllocation):
    def __init__(self, constant_amount: Decimal):
        self.amount = constant_amount

    def get_amount(self, interval_index: int = 0, side: str = "none") -> Decimal:
        """Just simply returns the same amount for each interval"""
        return self.amount

    def get_buy_to_open(
        self, interval_index: int, amount_consumed_sell: Decimal
    ) -> Decimal:
        return amount_consumed_sell

    def get_sell_to_open(
        self, interval_index: int, amount_consumed_buy: Decimal
    ) -> Decimal:
        return amount_consumed_buy


class LinearAllocation(AbstractAllocation):
    def __init__(
        self,
        min_amount: Decimal,
        max_amount: Decimal,
        intervals_count: int,
        start_index: int = 0,
    ):
        self.min_amount = min_amount
        self.linear_coefficient = divider(
            max_amount - min_amount, intervals_count - start_index - 1
        )
        self.start_index = start_index
        self.sell_amounts = self._get_sell_amounts(intervals_count)

    def _get_sell_amounts(self, intervals_count: int) -> [Decimal]:
        sell_amounts = []
        for index in range(intervals_count):
            sell_amounts.append(
                self.min_amount
                + multiplier(self.linear_coefficient, (index - self.start_index))
            )

        return sell_amounts

    def get_amount(self, interval_index: int = 0, side: str = "none") -> Decimal:
        """Linear coefficient makes such computations, that:
        if interval_index = 0 - return min_amount,
        if interval_index = len(intervals) - return max_amount"""
        if side == "buy" or interval_index < self.start_index:
            return self.min_amount

        return self.sell_amounts[interval_index]

    def get_buy_to_open(
        self, interval_index: int, amount_consumed_sell: Decimal
    ) -> Decimal:
        buy_to_open = multiplier(
            self.get_amount(interval_index, "buy"),
            divider(amount_consumed_sell, self.get_amount(interval_index, "sell")),
        )

        # update amounts to not sell second time this additional amount
        self.sell_amounts[interval_index] = max(
            self.min_amount,
            self.get_amount(interval_index, "sell") - amount_consumed_sell,
        )

        return buy_to_open

    def get_sell_to_open(
        self, interval_index: int, amount_consumed_buy: Decimal
    ) -> Decimal:
        return amount_consumed_buy


class CurvedAllocation(AbstractAllocation):
    def __init__(
        self,
        lowest_interval_amount: Decimal,
        middle_interval_amount: Decimal,
        highest_interval_amount: Decimal,
        intervals_count: int,
    ):
        self.middle_amount = middle_interval_amount
        self.middle_point = intervals_count // 2
        self.buy_exponent_coefficient = calculate_exponential_coefficient(
            middle_interval_amount, self.middle_point, lowest_interval_amount
        )
        self.sell_exponent_coefficient = calculate_exponential_coefficient(
            middle_interval_amount, self.middle_point, highest_interval_amount
        )
        # buy and sells amount, that will change during runtime: under self.middle_point - buy, over - sell
        self.amounts = self._get_amounts(intervals_count)

    def _get_amounts(self, intervals_count) -> [Decimal]:
        amounts = []
        for index in range(self.middle_point):
            amounts.append(
                exponent(
                    self.middle_amount,
                    self.buy_exponent_coefficient,
                    self.middle_point - index,
                )
            )

        additional = 0
        if intervals_count % 2 == 1:
            amounts.append(self.middle_amount)
            additional = 1

        for index in range(self.middle_point + additional, intervals_count):
            amounts.append(
                exponent(
                    self.middle_amount,
                    self.sell_exponent_coefficient,
                    index + 1 - additional - self.middle_point,
                )
            )

        return amounts

    def get_amount(self, interval_index: int = 0, side: str = "none") -> Decimal:
        if side == "buy":
            if interval_index >= self.middle_point:
                return self.middle_amount

            return self.amounts[interval_index]

        elif side == "sell":
            if interval_index <= self.middle_point:
                return self.middle_amount

            return self.amounts[interval_index]

        else:
            return self.middle_amount

    def get_buy_to_open(
        self, interval_index: int, amount_consumed_sell: Decimal
    ) -> Decimal:
        if interval_index <= self.middle_point:
            return amount_consumed_sell

        buy_to_open = multiplier(
            self.get_amount(interval_index, "buy"),
            divider(amount_consumed_sell, self.get_amount(interval_index, "sell")),
        )

        # update amounts to not sell second time this additional amount
        self.amounts[interval_index] = max(
            self.middle_amount,
            self.get_amount(interval_index, "sell") - amount_consumed_sell,
        )

        return buy_to_open

    def get_sell_to_open(
        self, interval_index: int, amount_consumed_buy: Decimal
    ) -> Decimal:
        if interval_index >= self.middle_point:
            return amount_consumed_buy

        sell_to_open = multiplier(
            self.get_amount(interval_index, "sell"),
            divider(amount_consumed_buy, self.get_amount(interval_index, "buy")),
        )

        # update amounts to not buy second time this additional amount
        self.amounts[interval_index] = max(
            self.middle_amount,
            self.get_amount(interval_index, "buy") - amount_consumed_buy,
        )

        return sell_to_open


class ProfitAllocation(AbstractAllocation):
    def __init__(
        self,
        intervals: [Interval],
        profit_allocation_percent: int,
        fees: Decimal,
        amount: Decimal,
    ):
        self.profit_allocation = profit_allocation_percent / Decimal("100")
        self.amount = amount
        self.benefits = generate_benefits_by_intervals(
            intervals, self.profit_allocation, fees, amount
        )
        print("benefits:", self.benefits)

    def set_benefit(self, interval_index: int, amount_buy: Decimal):
        benefit = self.benefits[interval_index]
        additional_benefit = multiplier(
            benefit.get_max_benefit(), divider(amount_buy, self.amount)
        )
        benefit.add_actual_benefit(additional_benefit)

    def get_amount(self, interval_index: int = 0, side: str = "none") -> Decimal:
        if side == "buy":
            return min(
                self.amount + self.benefits[interval_index].get_actual_benefit(),
                self.amount + self.benefits[interval_index].get_max_benefit(),
            )
        else:
            return self.amount

    def get_buy_to_open(
        self, interval_index: int, amount_consumed_sell: Decimal
    ) -> Decimal:
        return amount_consumed_sell

    def get_sell_to_open(
        self, interval_index: int, amount_consumed_buy: Decimal
    ) -> Decimal:
        if amount_consumed_buy > self.amount:
            self.benefits[interval_index].subtract_actual_benefit(
                amount_consumed_buy - self.amount
            )

        return amount_consumed_buy


class AllocationFactory:
    def __init__(
        self,
        allocation_type: str,
        amount: Decimal,
        intervals: [Interval],
        fees_coefficient: Decimal = None,
        profits_alloc: int = None,
    ):
        self.allocation_type = allocation_type
        self.amount = amount
        self.intervals = intervals
        self.fees_coefficient = fees_coefficient
        self.profits_alloc = profits_alloc

    def get_allocation(self):
        if self.allocation_type == "profit_allocation":
            return ProfitAllocation(
                self.intervals, self.profits_alloc, self.fees_coefficient, self.amount
            )

        elif self.allocation_type == "linear_allocation":
            return LinearAllocation(
                self.amount,
                convert.multiplier(self.amount, config.MAX_AMOUNT_COEFFICIENT),
                len(self.intervals),
                start_index=0,
            )

        elif self.allocation_type == "curved_allocation":
            return CurvedAllocation(
                convert.multiplier(self.amount, config.LOWEST_AMOUNT_COEFFICIENT),
                convert.multiplier(self.amount, config.MIDDLE_AMOUNT_COEFFICIENT),
                convert.multiplier(self.amount, config.HIGHEST_AMOUNT_COEFFICIENT),
                len(self.intervals),
            )
        else:
            return NoSpecificAllocation(self.amount)
