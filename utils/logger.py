import os, sys
import logging
import logging.handlers
import inspect
from datetime import datetime

from utils.slack import Slack
import utils.helpers as helper
import utils.converters as convert


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
                 slack_webhook=''):
        self.name = name
        self.log_file = self.set_log_file(log_file)
        self.log_formatter = log_formatter
        self.console_level = console_level
        self.file_level = file_level
        self.logging_level = logging_level
        self.slack = self.set_slack(slack_webhook)
        self.root_path = helper.set_root_path()
        self.logger = self.create_logger(separate_file=(True if log_file else False))

    def set_log_file(self, log_file):
        if log_file is not None:
            return log_file
        else:
            return f"{self.name}.log"

    def create_logger(self, separate_file=False):
        dir_name = f'{self.root_path}logs'
        helper.create_dir_when_none(dir_name)
        logger = logging.getLogger(self.log_file)
        
        if not logger.handlers:
            logger = self.set_logger_handler(dir_name, logger)
        
        return logger

    def set_logger_handler(self, dir_name, logger):
        log_file = f'{dir_name}/{self.log_file}'
        logger.setLevel(self.logging_level)
        formatter = logging.Formatter(self.log_formatter)
        fh = logging.FileHandler(log_file)
        fh.setLevel(self.file_level)
        fh.setFormatter(formatter)
        # Apply parameters
        logger.addHandler(fh)
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=2000000, backupCount=20)
        logger.addHandler(handler)

        return logger

    def set_slack(self, slack_webhook_url):
        if not slack_webhook_url:
            return None

        slack = Slack(webhook_url=slack_webhook_url)
        slack.webhook_check(webhook_url=slack_webhook_url)
        
        if inspect.stack()[1].function != '__init__':
            self.slack = slack

        return slack

    def log(self, msg, level='debug', from_=None, slack=False, print_=False, **log):
        log['from'] = f'{self.name}__{from_}' if from_ else self.name
        log['timestamp'] = convert.datetime_to_string(datetime.now())
        log['msg'] = str(msg)
        log['level'] = level

        if level == 'debug' or level == 'dev':
            self.logger.debug(log)
        elif level == 'info':
            self.logger.info(log)
        else:
            slack = True
            print_ = True
            if level == 'warning':
                self.logger.warning(log)
            elif level == 'error':
                self.logger.error(log)
            elif level == 'critical':
                self.logger.critical(log)
            # add your custom log type here..
            else:
                self.logger.critical(f'Wrong logger level: {level}, from: '
                f'{inspect.stack()[1].function}, log message: {log}')
            
        
        if print_:
            print(msg)
        
        if slack:
            if self.slack:
                try:
                    self.slack.post_message(msg)
                except Exception as e:
                    msg = f'slack.post_message error: {e}'
                    self.logger.warning(msg)
                    print(msg)
            else:
                msg = "Slack isn't connected"
                self.logger.warning(msg)
                print(msg)
            