from decimal import Decimal
from datetime import datetime

import utils.converters as convert
from main.interval import Interval


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
    """Verifie the nb for benefice allocation
    nb: int"""
    if Decimal('0') <= nb >= Decimal('100'):
        raise ValueError(f'The benefice allocation too low (<0) or high ' \
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


def interval_generator(range_bottom, range_top, increment):
    """Generate a list of interval inside a range by incrementing values
    range_bottom: Decimal, bottom of the range
    range_top: Decimal, top of the range
    increment: Decimal, value used to increment from the bottom
    return: list, value from [range_bottom, range_top[
    """
    intervals_int = [range_bottom, convert.multiplier(range_bottom, increment)]
    if range_top <= intervals_int[1]:
        raise ValueError('Range top value is too low')

    while intervals_int[-1] <= range_top:
        intervals_int.append(convert.multiplier(intervals_int[-1], increment))

    # Remove value > to range_top
    del intervals_int[-1]

    if len(intervals_int) < 6:
        raise ValueError('Range top value is too low, or increment too '
            'high: need to generate at lease 6 intervals. Try again!')

    # Creating [Interval] without top interval:
    intervals = []
    for idx in range(len(intervals_int) - 1):
        if idx < len(intervals_int):
            intervals.append(Interval(intervals_int[idx], intervals_int[idx + 1]))

    # Inserting top Interval
    intervals.append(Interval(intervals_int[-1], range_top))

    return intervals


def nb_to_display(nb, max_size):
    """Verifie the nb of order to display
    nb: int"""
    if nb > max_size and nb < 0:
        raise ValueError('The number of order to display is too low (<0) '
                         f'or high {max_size}')
    return True
