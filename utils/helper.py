import os, sys
from pathlib import Path
from decimal import *
from copy import deepcopy
from datetime import datetime
from time import time
import logging



class UtilsMixin:
    def create_file_when_none(self, file_name):  # Need to be refactored
        """Check if a file exist or create one.
        return: bool.
        """
        if not os.path.isfile(file_name):
            Path(file_name).touch()
            return False
        else:
            return True

    def read_one_line(self, file_name, line_nb):
        """Read and return a specific line in a file.
        return: string."""
        with open(file_name) as f:
            return f.readlines()[line_nb].replace('\n', '').replace("'", '"')

    def create_dir_when_none(self, dir_name):
        """Check if a directory exist or create one.
        return: bool."""
        if not os.path.isdir(dir_name):
            os.makedirs(dir_name)
            return False
        else:
            return True

    def logfile_not_empty(self, file_name):  # Need to be refactored
        """Check if there is data in the logfile.
        return : bool.
        """
        if os.path.getsize(file_name):
            return True
        else:
            self.log('Logfile is empty!',level='info')
            return False

    def file_line_counter(self, file_name):
        """Line counter for any file.
        return: int, number of line. Start at 0."""
        try:
            with open(file_name, mode='r', encoding='utf-8') as log_file:
                for i, l in enumerate(log_file):
                    pass
            return i
        except NameError:
            self.log(f'{file_name} is empty', level='info')
            return

    def simple_file_writer(self, file_name, text):
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
            self.log(f'File writer error: {e}')
            self.exit()

    def str_to_decimal(self, s, error_message=None):
        """Convert a string to Decimal or raise an error.
        s: string, element to convert
        error_message: string, error message detail to display if fail.
        return: Decimal."""
        try:
            return Decimal(str(s))
        except Exception as e:
            raise ValueError(f'{error_message} {e}')

    def is_date(self, str_date):
        """Check if a date have a valid formating.
        str_date: string
        """
        try:
            return datetime.strptime(str_date, '%Y-%m-%d %H:%M:%S.%f')
        except Exception as e:
            raise ValueError(f'{str_date} is not a valid date: {e}')

    def str_to_bool(self, s, error_message=None):  # Fancy things can be added
        """Convert a string to boolean or rise an error
        s: string.
        error_message: string, error message detail to display if fail.
        return: bool.
        """
        if s == 'True' or s == 'y':
            return True
        elif s == 'False' or s == 'n':
            return False
        else:
            raise ValueError(f'{error_message} {e}')

    def str_to_int(self, s, error_message=None):
        """Convert a string to an int or rise an error
        s: string.
        error_message: string, error message detail to display if fail.
        return: int.
        """
        try:
            return int(s)
        except Exception as e:
            raise ValueError(f'{error_message} {e}')

    def dict_to_str(self, a_dict):
        """Format dict into a string.
        return: string, formated string for logfile."""
        b_dict = deepcopy(a_dict)
        for key, value in b_dict.items():
            b_dict[key] = str(value)
        b_dict = str(b_dict)
        return b_dict.replace("'", '"')

    def timestamp_formater(self):
        """Format time.time() into the same format as timestamp.
        used in ccxt: 13 numbers.
        return: string, formated timestamp"""
        timestamp = str(time()).split('.')
        return f'{timestamp[0]}{timestamp[1][:3]}'

    def limitation_to_btc_market(self, market):
        """Special limitation to BTC market : only ALT/BTC for now.
        market: string, market name.
        return: bool True or bool False + error message
        """
        if market[-3:] != 'BTC':
            return f'LW is limited to ALT/BTC markets : {market}'
        return True

    def param_checker_range_bot(self, range_bot):
        """Verifies the value of the bottom of the channel
        range_bot: decimal"""
        if range_bot < Decimal('0.00000001'):
            raise ValueError('The bottom of the range is too low')
        return True

    def param_checker_range_top(self, range_top):
        """Verifies the value of the top of the channel
        range_top: decimal"""
        if range_top > Decimal('0.99'):
            raise ValueError('The top of the range is too high')
        return True

    def param_checker_interval(self, interval):
        """Verifies the value of interval between orders
        interval: decimal"""
        if Decimal('1.01') > interval or interval > Decimal('1.50'):
            raise ValueError('Increment is too low (<=1%) or high (>=50%)')
        return True

    def param_checker_amount(self, amount, minimum_amount):
        """Verifies the value of each orders
        amount: decimal"""
        if amount < minimum_amount or amount > Decimal('10000000'):
            raise ValueError(f'Amount is too low (< {minimum_amount} \
                ) or high (>10000000)')

    def param_checker_profits_alloc(self, nb):
        """Verifie the nb for benefice allocation
        nb: int"""
        if Decimal('0') <= nb >= Decimal('100'):
            msg = (
                f'The benefice allocation too low (<0) or high '
                f'(>100) {nb}'
            )
            raise ValueError(msg)
        return True

    def exit(self):
        """Clean program exit"""
        self.log("End the program")
        sys.exit(0)

    def log(self, msg, level='critical'):
        if hasattr(self, 'applog'):
            self.applog.critical(msg)
        else:
            from main import BotConfiguration
            # applog = BotConfiguration().bot.applog
            from logger.logger import Logger
            applog = Logger(name='stratlogs',
                                   log_file='strat.log',
                                   log_formatter='%(message)s',
                                   console_level=logging.DEBUG,
                                   file_level=logging.INFO,
                                   root_path=BotConfiguration().root_path + "logger/").create()
            try:
                eval('applog.'+level)(msg)
            except:
                applog.critical(f'Wrong log level: {level}')
                applog.critical(msg)

    def multiplier(self, nb1, nb2, nb3=Decimal('1')):
        """Do a simple multiplication between Decimal.
        nb1: Decimal.
        nb2: Decimal.
        nb3: Decimal, optional.
        return: Decimal.
        """
        return self.quantizator(nb1 * nb2 * nb3)

    def quantizator(self, nb):
        """Format a Decimal object to 8 decimals
        return: Decimal"""
        try:
            if nb < Decimal('1'):
                return nb.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_EVEN)
            else:
                whole_part, fractional_part = str(nb).split('.')
                return Decimal(whole_part)+Decimal('0.'+fractional_part).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_EVEN)
        except Exception as e:
            return

    def increment_coef_buider(self, nb):
        """Formating increment_coef.
        nb: int, the value to increment in percentage.
        return: Decimal, formated value.
        """
        try:
            nb = Decimal(str(nb))
            nb = Decimal('1') + nb / Decimal('100')
            self.param_checker_interval(nb)
            return nb
        except Exception as e:
            raise ValueError(e)

    def flip_side(self, side):
        if side == 'buy':
            return 'sell'
        elif side == 'sell':
            return 'buy'