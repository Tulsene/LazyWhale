import os
import logging, logging.handlers
from decimal import Decimal



class Logger:
    """Generate logging systems which display any level on the console
    and starting from INFO into logging file
    self.name: string, name of the logger,
    self.log_file: string, name of the file where to place the log datas.
    self.log_formatter: string, how the log is formated. See Formatter logging
        rules.
    self.console_level: logging object, the logging level to display in the
        console. Need to be superior to logging_level.
    self.file_level: logging object, the logging level to put in the
        logging file. Need to be superior to logging_level.
    self.logging_level: logging object, optional, the level of logging to catch.
    return: logging object, contain rules for logging.
    """
    def __init__(self, name, log_file, log_formatter, console_level,
                     file_level, logging_level=logging.DEBUG, root_path='/'):
        self.name = name
        self.log_file = log_file
        self.log_formatter = log_formatter
        self.console_level = console_level
        self.file_level = file_level
        self.logging_level = logging_level
        self.root_path = root_path

    def create(self):
        dir_name = f'{self.root_path}logfiles'
        self._create_dir_when_none('logger/logfiles')    #TODO; in logger
        log_file = f'{dir_name}/{self.log_file}'
        logger = logging.getLogger(self.name)
        logger.setLevel(self.logging_level)
        formatter = logging.Formatter(self.log_formatter)
        # Console handler stream
        ch = logging.StreamHandler()
        ch.setLevel(self.console_level)
        ch.setFormatter(formatter)
        # File Handler stream
        fh = logging.FileHandler(log_file)
        fh.setLevel(self.file_level)
        fh.setFormatter(formatter)
        logger.addHandler(ch)
        logger.addHandler(fh)
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=2000000, backupCount=20)
        logger.addHandler(handler)
        return logger

    def _create_dir_when_none(self, dir_name):
        """Check if a directory exist or create one.
        return: bool."""
        if not os.path.isdir(dir_name):
            os.makedirs(dir_name)
            return False
        else:
            return True


