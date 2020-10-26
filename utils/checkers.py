from decimal import Decimal
from datetime import datetime

import utils.converters as convert
from config import config


def is_date(str_date):
    """Check if a date have a valid formating.
    str_date: string
    """
    try:
        return datetime.strptime(str_date, '%Y-%m-%d %H:%M:%S.%f')
    except Exception as e:
        raise ValueError(f'{str_date} is not a valid date: {e}')


def range_bot(range_bot):
    """Verifies the value of the bottom of the channel
    range_bot: decimal"""
    if range_bot < Decimal('0.00000001'):
        raise ValueError('The bottom of the range is too low')
    if range_bot > Decimal('0.99'):
        raise ValueError('The bottom of the range is too high')
    return True


def range_top(range_top, range_bot):
    """Verifies the value of the top of the channel
    range_top: decimal"""
    if range_bot < Decimal('0.00000001'):
        raise ValueError('The top of the range is too low')
    if range_bot > Decimal('0.99'):
        raise ValueError('The top of the range is too high')
    if range_bot >= range_top:
        raise ValueError(f'range_top ({range_top}) must be superior to range_bot ({range_bot})')
    return True


def interval(interval):
    """Verifies the value of interval between orders
    interval: decimal"""
    if Decimal('1.01') > interval or interval > Decimal('1.50'):
        raise ValueError('Increment is too low (<=1%) or high (>=50%)')
    return interval


def amount(amount, range_bot):
    """Verifies the value of each orders
    amount: Decimal.
    range_bot: Decimal.
    return: True"""
    minimum_amount = Decimal('0.001') / range_bot
    if amount < minimum_amount or amount > Decimal('10000000'):
        raise ValueError(f'Amount is too low (< {minimum_amount} \
            ) or high (>10000000)')
    return True


def profits_alloc(nb):
    """Verify the nb for benefice allocation
    nb: int"""
    if nb <= Decimal('0') or nb >= Decimal('100'):
        raise ValueError(f'The benefice allocation too low (<0) or high '
                         f'(>100) {nb}')
    return nb


def increment_coef_buider(nb):
    """Formating increment_coef.
    nb: int, the value to increment in percentage.
    return: Decimal, formated value."""
    try:
        a = interval(Decimal('1') + convert.str_to_decimal(nb) / Decimal('100'))
        return a
    except Exception as e:
        raise ValueError(e)


def limitation_to_btc_market(market):
    """Special limitation to BTC market : only ALT/BTC for now.
    market: string, market name.
    return: bool True or bool False + error message
    """
    if market[-3:] != 'BTC':
        return f'LW is limited to ALT/BTC markets : {market}'
    return True


def nb_to_display(nb, max_size):
    """Verify the nb of intervals to display
    nb: int"""
    if nb > max_size or nb < 0:
        raise ValueError('The number of intervals to display is too low (<0) '
                         f'or high {max_size}')
    return True


def nb_orders_per_interval(nb, max_size):
    """Verify the nb of orders per interval
        nb: int"""
    if nb > max_size or nb < 0:
        raise ValueError('The number of orders per interval is too low (<0) '
                         f'or high {max_size}')


def is_equal_decimal(first: Decimal, second: Decimal):
    eps = Decimal(Decimal('10') ** (-config.DECIMAL_PRECISION + 2))
    return (first - second).copy_abs() <= eps
