import zebitexFormatted
import lazyStarter
import threading
import sys, os
from time import sleep
from decimal import *
from copy import deepcopy
import logging
import logging.handlers
import json

class LazyTest():
    """docstring for lazyTest"""
    getcontext().prec = 15

    def __init__(self):
        self.script_position = os.path.dirname(sys.argv[0])
        self.root_path = f'{self.script_position}/' if self.script_position else ''
        self.keys_file2 = f'{self.root_path}keys2.txt'
        self.lazy_account = "lazy_account"
        self.a_user_account = "a_user_account"
        self.selected_market = 'DASH/BTC'
        self.safety_buy_value = Decimal('0.00000001')
        self.safety_sell_value = Decimal('1')
        self.test_logs = self.logger_setup('test_logs', 'test.log',
                                           '%(asctime)s - %(levelname)s - %(message)s',
                                           logging.DEBUG,
                                           logging.DEBUG)
        self.lazy_params = {"datetime": "2019-07-27 23:58:47.834790",
                            "marketplace": "zebitex_testnet",
                            "market": "DASH/BTC",
                            "range_bot": "0.01",
                            "range_top": "0.015",
                            "increment_coef": "1.02",
                            "amount": "0.2",
                            "spread_bot": "0.01082432",
                            "spread_top": "0.01104081",
                            "stop_at_bot": "False",
                            "stop_at_top": "True",
                            "nb_buy_to_display": "3",
                            "nb_sell_to_display": "3",
                            "profits_alloc": "50"}

    def logger_setup(self, name, log_file, log_formatter, console_level,
                     file_level, logging_level=logging.DEBUG):
        """Generate logging systems which display any level on the console
        and starting from INFO into logging file
        name: string, name of the logger,
        log_file: string, name of the file where to place the log datas.
        log_formatter: string, how the log is formated. See Formatter logging
            rules.
        console_level: logging object, the logging level to display in the
            console. Need to be superior to logging_level.
        file_level: logging object, the logging level to put in the
            logging file. Need to be superior to logging_level.
        logging_level: logging object, optional, the level of logging to catch.
        return: logging object, contain rules for logging.
        """
        dir_name = f'{self.root_path}logfiles'
        #self.create_dir_when_none('logfiles')
        log_file = f'{dir_name}/{log_file}'
        logger = logging.getLogger(name)
        logger.setLevel(logging_level)
        formatter = logging.Formatter(log_formatter)
        # Console handler stream
        ch = logging.StreamHandler()
        ch.setLevel(console_level)
        ch.setFormatter(formatter)
        # File Handler stream
        fh = logging.FileHandler(log_file)
        fh.setLevel(file_level)
        fh.setFormatter(formatter)
        logger.addHandler(ch)
        logger.addHandler(fh)
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=2000000, backupCount=20)
        logger.addHandler(handler)
        return logger

    def keys_file_reader(self):  # Need to be refactored
        """Check the consistence of datas in key.txt.
        return: dict, api keys
        """
        keys = {}
        with open(self.keys_file2, mode='r', encoding='utf-8') as keys_file:
            for line in keys_file:
                line = line.replace('\n', '')
                line = line.replace("'", '"')
                try:
                    key = json.loads(line)
                    for k in key.keys():
                        if k not in ["lazy_account", "a_user_account"]:
                            raise NameError('The account name is invalid!')
                except Exception as e:
                    self.test_logs.critical(f'Something went wrong : {e}')
                    self.exit()
                keys.update(key)
        return keys

    def keys_launcher(self):
        keys = self.keys_file_reader()
        try:
            if keys[self.lazy_account]['apiKey'] == keys[self.a_user_account]['apiKey']\
                or keys[self.lazy_account]['secret'] == keys[self.a_user_account]['secret']:
                raise ValueError('Twice the same apiKey or secret value')
        except Exception as e:
            self.test_logs.critical(f'Something went wrong : {e}')
            self.exit()
        self.lazy_account = zebitexFormatted.ZebitexFormatted(
                keys[self.lazy_account]['apiKey'],
                keys[self.lazy_account]['secret'],
                True)
        self.a_user_account = zebitexFormatted.ZebitexFormatted(
                keys[self.a_user_account]['apiKey'],
                keys[self.a_user_account]['secret'],
                True)
        return

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
        return nb.quantize(Decimal('.00000001'), rounding=ROUND_HALF_EVEN)

    def interval_generator(self):
        """Generate a list of interval inside a range by incrementing values
        range_bottom: Decimal, bottom of the range
        range_top: Decimal, top of the range
        increment: Decimal, value used to increment from the bottom
        return: list, value from [range_bottom, range_top[
        """
        range_bottom = self.lazy_params['range_bottom']
        range_top = self.lazy_params['range_top']
        increment = self.lazy_params['increment']
        intervals = [range_bottom]
        intervals.append(self.multiplier(intervals[-1], increment))
        if range_top <= intervals[1]:
            raise ValueError('Range top value is too low')
        while intervals[-1] <= range_top:
            intervals.append(self.multiplier(intervals[-1], increment))
        del intervals[-1]
        if len(intervals) < 6:
            raise ValueError(
                f'Range top value is too low, or increment too '
                f'high: need to generate at lease 6 intervals. Try again!'
            )
        return intervals

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
            self.test_logs.critical(f'File writer error: {e}')
            self.exit()

    def dict_to_str(self, a_dict):
        """Format dict into a string.
        return: string, formated string for logfile."""
        b_dict = deepcopy(a_dict)
        for key, value in b_dict.items():
            b_dict[key] = str(value)
        b_dict = str(b_dict)
        return b_dict.replace("'", '"')

    def exit(self):
        """Clean program exit"""
        self.test_logs.critical("End the program")
        sys.exit(0)

    def main(self):
        file_path = f'{self.root_path}params.txt'
        self.simple_file_writer(file_path, self.dict_to_str(self.lazy_params))
        self.keys_launcher()
        self.lazy_account.cancel_all()
        self.a_user_account.cancel_all()
        l = lazyStarter.LazyStarter(True)
        t = threading.Thread(target=l.main(),name=lazyMain)
        t.daemon = True
        t.start()
        sleep(15)

if __name__ == "__main__":
    l = LazyTest()
    l.main()
