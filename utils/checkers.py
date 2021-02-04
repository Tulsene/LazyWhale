from random import uniform

from decimal import Decimal
from datetime import datetime

import utils.converters as convert
from config import config


def is_date(str_date):
    """Check if a date have a valid formating.
    str_date: string
    """
    try:
        return datetime.strptime(str_date, "%Y-%m-%d %H:%M:%S.%f")
    except Exception as e:
        raise ValueError(f"{str_date} is not a valid date: {e}")


def range_bot(r_bot):
    """Verifies the value of the bottom of the channel
    range_bot: decimal"""
    if r_bot < Decimal("0.00000001"):
        raise ValueError("The bottom of the range is too low")
    if r_bot > Decimal("0.99"):
        raise ValueError("The bottom of the range is too high")
    return True


def range_top(r_top, r_bot):
    """Verifies the value of the top of the channel
    range_top: decimal"""
    if r_bot < Decimal("0.00000001"):
        raise ValueError("The top of the range is too low")
    if r_bot > Decimal("0.99"):
        raise ValueError("The top of the range is too high")
    if r_bot >= r_top:
        raise ValueError(f"range_top ({r_top}) must be superior to range_bot ({r_bot})")
    return True


def interval(increment):
    """Verifies the value of interval between orders
    interval: decimal"""
    if Decimal("1.01") > increment or increment > Decimal("1.50"):
        raise ValueError("Increment is too low (<=1%) or high (>=50%)")
    return increment


def amount(interval_amount, r_bot):
    """Verifies the value of each orders
    amount: Decimal.
    range_bot: Decimal.
    return: True"""
    minimum_amount = Decimal("0.001") / r_bot
    if interval_amount < minimum_amount or interval_amount > Decimal("10000000"):
        raise ValueError(
            f"Amount is too low (< {minimum_amount} \
            ) or high (>10000000)"
        )
    return True


def profits_alloc(nb):
    """Verify the nb for benefice allocation
    nb: int"""
    if nb < Decimal("0") or nb > Decimal("100"):
        raise ValueError(
            f"The benefice allocation too low (<0) or high " f"(>100) {nb}"
        )
    return nb


def increment_coef_buider(nb):
    """Formating increment_coef.
    nb: int, the value to increment in percentage.
    return: Decimal, formated value."""
    try:
        a = interval(Decimal("1") + convert.str_to_decimal(nb) / Decimal("100"))
        return a
    except Exception as e:
        raise ValueError(e)


def limitation_to_btc_market(market):
    """Special limitation to BTC market : only ALT/BTC for now.
    market: string, market name.
    return: bool True or bool False + error message
    """
    if market[-3:] != "BTC":
        return f"LW is limited to ALT/BTC markets : {market}"
    return True


def nb_to_display(nb, max_size):
    """Verify the nb of intervals to display
    nb: int"""
    if nb > max_size or nb < 0:
        raise ValueError(
            "The number of intervals to display is too low (<0) " f"or high {max_size}"
        )
    return True


def nb_orders_per_interval(nb, max_size):
    """Verify the nb of orders per interval
    nb: int"""
    if nb > max_size or nb < 0:
        raise ValueError(
            "The number of orders per interval is too low (<0) " f"or high {max_size}"
        )


def random_precision(precision: Decimal, max_precision: Decimal):
    if precision < Decimal("1e-8") or precision > max_precision:
        raise ValueError(
            "The precision is too low (<1e-8) " f"or high (>{max_precision})"
        )


def is_equal_decimal_amount(
    first: Decimal, second: Decimal, allow_percent_difference: Decimal = Decimal("0.1")
):
    """Compare amounts by checking if they have less than 0.01% difference"""
    coefficient = (Decimal("1") / allow_percent_difference) * Decimal("100")
    eps = max(convert.divider(first, coefficient), config.DECIMAL_PRECISION)
    return (first - second).copy_abs() <= eps


def get_random_decimal(bot, top, precision: Decimal = config.DECIMAL_PRECISION):
    result = Decimal(
        str(
            round(
                uniform(float(bot + precision), float(top - precision)),  # failsafe
                8,  # round to satoshi
            )
        )
    )
    return convert.floor_decimal(result, precision)
