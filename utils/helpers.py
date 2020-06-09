import os, sys
from pathlib import Path
from decimal import Decimal, ROUND_HALF_EVEN
from copy import deepcopy
from datetime import datetime
from time import time

# from utils.logger import Logger

#log = Logger('test', slack_webhook_url='https://hooks.slack.com/services/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').log

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

def generate_empty_list(size):
    """List generator.
    size: int.
    return: list."""
    return [None for _ in range(size)]