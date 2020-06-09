import os, sys
import logging
import logging.handlers
from datetime import datetime
from utils.slack import Slack
import utils.helpers as helper

def set_slack(slack_webhook_url):
    slack = Slack(webhook_url=slack_webhook_url)
    slack.webhook_check(webhook_url=slack_webhook_url)
    return slack

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
    def __init__(self, name,
                 log_file=None,
                 log_formatter='%(message)s',
                 console_level=logging.DEBUG,
                 file_level=logging.DEBUG,
                 logging_level=logging.DEBUG,
                 slack_webhook_url='https://hooks.slack.com/services/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'):
        self.name = name
        self.log_file = self.set_log_file(log_file)
        self.log_formatter = log_formatter
        self.console_level = console_level
        self.file_level = file_level
        self.logging_level = logging_level
        self.slack = set_slack(slack_webhook_url)
        self.root_path = helper.set_root_path()
        self.logger = self.create_logger(separate_file=(True if log_file else False))

    def set_log_file(self, log_file):
        if log_file is not None:
            return log_file
        else:
            return f"{self.name}.log"

    def create_logger(self, separate_file=False):
        dir_name = f'{self.root_path}logs'
        self._create_dir_when_none(dir_name)
        logger = logging.getLogger(self.log_file)
        
        if not logger.handlers:
            logger = self.set_logger_handler(dir_name, logger)
        
        return logger

    def set_logger_handler(self, dir_name, logger):
        log_file = f'{dir_name}/{self.log_file}'
        logger.setLevel(self.logging_level)
        formatter = logging.Formatter(self.log_formatter)
        # Console handler stream
        # ch = logging.StreamHandler()
        # ch.setLevel(self.console_level)
        # ch.setFormatter(formatter)
        # File Handler stream
        fh = logging.FileHandler(log_file)
        fh.setLevel(self.file_level)
        fh.setFormatter(formatter)
        # Apply parameters
        # logger.addHandler(ch)
        logger.addHandler(fh)
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=2000000, backupCount=20)
        logger.addHandler(handler)

        return logger

    def _create_dir_when_none(self, dir_name):
        """Check if a directory exist or create one.
        return: bool."""
        try:
            if dir_name[0] == '/':
                dir_name = dir_name[1:]
            if not os.path.isdir(dir_name):
                os.makedirs(dir_name)
                return False
            else:
                return True
        except OSError:
            pass

    def log(self, msg, level='info', from_=None, slack=False, print_=False, **log):
        log['from'] = f'{self.name}__{from_}' if from_ else self.name
        log['timestamp'] = datetime.now().timestamp()
        log['msg'] = str(msg)
        log['level'] = level

        if level == 'warning':
            self.logger.warning(log)
        elif level == 'error':
            self.logger.error(log)
        elif level == 'debug' or level == 'dev':
            self.logger.debug(log)
        elif level == 'critical':
            self.logger.critical(log)
        # add your custom log type here..
        else:
            self.logger.info(log)
        
        if print_:
            print(msg)
        
        if slack:
            if not self.slack:
                raise Exception("Slack hasn't connected")
            try:
                self.slack.send_slack_message(msg)
            except:
                pass