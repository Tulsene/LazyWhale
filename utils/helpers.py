import os, sys
from pathlib import Path
from decimal import Decimal, ROUND_HALF_EVEN
from copy import deepcopy
from datetime import datetime
from random import uniform
from time import time
import config.config as config

import utils.converters as convert
from main.interval import Interval
from main.order import Order


def set_root_path():
    root_path = os.path.dirname(sys.argv[0])
    return f'{root_path}/' if root_path else ''


def create_empty_file(file_path):
    """Warning : no erase safety.
    file_path: string.
    return: bool."""
    open(file_path, 'w').close()
    return True


def create_file_when_none(file_path):
    if os.path.isfile(file_path):
        return False

    return create_empty_file(file_path)


def read_one_line(file_name, line_nb=0):
    """Read and return a specific line in a file.
    return: string."""
    with open(file_name) as f:
        return f.readlines()[line_nb].replace('\n', '').replace("'", '"')


def create_dir_when_none(dir_name):
    """Check if a directory exist or create one.
    return: bool."""
    if not os.path.isdir(dir_name):
        os.makedirs(dir_name)
        return False
    else:
        return True


def file_line_counter(file_name):
    """Line counter for any file.
    return: int, number of line. Start at 0."""
    try:
        with open(file_name, mode='r', encoding='utf-8') as log_file:
            for i, l in enumerate(log_file):
                pass
        return i
    except NameError:
        return f'{file_name} is empty'


def simple_file_writer(file_name, text):
    """Write a text in a file.
    file_name: string, full path of the file.
    text: string.
    return: boolean.
    """
    try:
        with open(file_name, mode='w', encoding='utf-8') as file:
            file.write(text)
        return True
    except Exception as e:
        return f'File writer error: {e}'


def params_writer(file_path, params):
    updated = deepcopy(params)
    if 'intervals' in updated.keys():
        del updated['intervals']
    if 'api_connector' in updated.keys():
        del updated['api_connector']
    simple_file_writer(file_path, convert.dict_to_str(updated))


def append_to_file(file_name, line):
    with open(file_name, mode='a', encoding='utf-8') as a_file:
        a_file.write(line)
    return True


def read_file(file_name):
    if os.path.getsize(file_name) > 0:
        with open(file_name, mode='r', encoding='utf-8') as a_file:
            lines = a_file.read().splitlines()
        return lines
    return False


def generate_list(size, value=None):
    """List generator.
    size: int.
    return: list."""
    return [value for _ in range(size)]


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


def populate_intervals(intervals: [Interval], orders: [Order]):
    """Populating intervals with incoming orders (store them in correct Interval way in self.intervals)"""
    # sort orders by price
    orders = sorted(orders, key=lambda x: x.price)

    interval_idx = 0
    for order in orders:
        if order.price < intervals[0].get_bottom() or order.price >= intervals[-1].get_top():
            continue

        while not (intervals[interval_idx].get_bottom() <=
                   order.price < intervals[interval_idx].get_top()):
            interval_idx += 1

        if order.side == 'buy':
            intervals[interval_idx].insert_buy_order(order)
        else:
            intervals[interval_idx].insert_sell_order(order)

    return intervals


def get_amount_to_open(prev_orders: [Order], new_orders: [Order]) -> Decimal:
    """Get amount of orders, that have been consumed or not fully consumed"""
    amount_to_open = Decimal('0')

    new_orders_id_list = [order.id for order in new_orders]
    consumed_orders = [order for order in prev_orders if order.id not in new_orders_id_list]
    amount_to_open += sum([order.amount for order in consumed_orders])

    for new_order in new_orders:
        prev_order = [pr_order for pr_order in prev_orders if pr_order.id == new_order.id][0]
        if prev_order.filled != new_order.filled and prev_order.amount != new_order.amount:
            amount_to_open += prev_order.amount - new_order.amount

    return amount_to_open
