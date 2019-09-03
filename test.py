import zebitexFormatted
import main
import threading
import sys, os
from time import sleep
from decimal import *
from copy import deepcopy
import logging
import logging.handlers
import json
import static_config
from exchange_manager.api_manager import APIManager
from logger.logger import Logger
from logger.slack import Slack
from static_config import SLEEP_FOR_TEST
from utils.helper import UtilsMixin
from test_case_config import *






class LazyTest():
    """docstring for lazyTest"""
    getcontext().prec = 15

    def __init__(self):
        self.script_position = os.path.dirname(sys.argv[0])
        self.root_path = f'{self.script_position}/' if self.script_position else ''
        self.keys_file2 = f'{self.root_path}keys2.txt'
        self.fees_coef = Decimal(static_config.FEES_COEF)  # TODO: could be different for other exchanges?
        self.lazy_keys = None
        self.lazy_account = "lazy_account"
        self.a_user_account = "a_user_account"
        self.selected_market = 'DASH/BTC'
        self.safety_buy_value = Decimal('0.00000001')
        self.safety_sell_value = Decimal('1')
        self.slack = Slack(static_config.SLACK_HOOK_URL)
        self.testlog = Logger(name='test_logs',
                               log_file='strat.log',
                               log_formatter='%(asctime)s - %(levelname)s - %(message)s',
                               console_level=logging.DEBUG,
                               file_level=logging.DEBUG,
                               root_path=self.root_path + "logger/"
                                ).create()
        self.applog, self.stratlog = [self.testlog]*2   #   script classes expected expected self.applog, self.stratlog as looger
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
                    self.testlog.critical(f'Something went wrong : {e}')
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
            self.testlog.critical(f'Something went wrong : {e}')
            self.exit()
        self.lazy_keys = (keys[self.lazy_account]['apiKey'],
                          keys[self.lazy_account]['secret'])
        lazy_account = APIManager(config=self)
        lazy_account.set_exchange('zebitex_testnet', keys={
            'apiKey':keys[self.lazy_account]['apiKey'],
            'secret':keys[self.lazy_account]['secret']
        })
        lazy_account.load_markets()
        self.lazy_account = lazy_account
        a_user_account = APIManager(config=self)
        a_user_account.set_exchange('zebitex_testnet', keys=keys[self.a_user_account])
        a_user_account.load_markets()
        a_user_account.cancel_all()
        self.a_user_account = a_user_account
        return

    def exit(self):
        """Clean program exit"""
        self.testlog.critical("End the program")
        sys.exit(0)

    def main(self):
        self.keys_launcher()
        self.lazy_account.cancel_all()
        self.a_user_account.cancel_all()
        l = main.Bot(params=self.lazy_params, keys=self.lazy_keys, test_mode=True)
        t = threading.Thread(target=l.launch, name='lazyWhaleBot')
        t.start()
        #TODO: test cases, check strategy behaviour
        while not l.is_init_order_plased:
            sleep(1)
        open_orders = deepcopy(l.config.open_orders)
        open_orders['buy'] = reversed(open_orders['buy'])
        TestCases(
            test_obj=self,
            bot=l,
        ).execute()
        sleep(15)





class TestCases(UtilsMixin):
    def __init__(self, test_obj, bot, logger=None):
        self.test_obj = test_obj
        self.bot = bot
        if not logger:
            script_position = os.path.dirname(sys.argv[0])
            root_path = f'{script_position}/' if script_position else ''
            self.logger = Logger(name='test_logs',
                                   log_file='strat.log',
                                   log_formatter='%(asctime)s - %(levelname)s - %(message)s',
                                   console_level=logging.DEBUG,
                                   file_level=logging.DEBUG,
                                   root_path=root_path + "logger/"
                                    ).create()
        else:
            self.logger = logger
        self.test_case_data = {
            # 'testing_by_open_orders_number':test_case_by_open_orders_number,
            'testing_by_open_orders_ids':test_case_by_open_orders_ids,
            #add new test case here as new dict element. Test case must have a key that equal to the name of the method..
        }

    def execute(self):
        while True:
            for test_case, test_case_data in self.test_case_data.items():
                if self.is_valid_test(test_case, test_case_data):
                    #TODO: sync and async ways
                    eval('self.'+test_case)(test_case_data=test_case_data)
                    sleep(2)

    def is_valid_test(self, test_case, test_case_data):
        if hasattr(self, test_case):
            return True
        #TODO: add others validation methods


    def testing_by_open_orders_number(self, test_case_data):
        if not test_case_data:
            self.logger.error(f"ERROR: test_case_data required")
            self.exit()
        open_orders = deepcopy(self.bot.config.open_orders)
        open_orders['buy'] = list(reversed(open_orders['buy']))
        input_nb = self.get_input_nb()
        for test_case in test_case_data:
            for side in ['buy','sell']:
                if not input_nb[side] == len(open_orders[side]):
                    self.logger.error(f"Unexpected strategy behaviour: expected {str(test_case['output_nb'][side+'_nb'])} open orders, but got {str(len(open_orders[side]))}")
                    self.exit()
                for index, order in enumerate(open_orders[side]):
                    if index in test_case['input'][side]:
                        amount_coef = test_case['input'][side][index]['amount_percent']
                        amount = order[3] * Decimal(amount_coef)
                        result = eval(f'self.test_obj.a_user_account.init_limit_{self.flip_side(side)}_order')(self.test_obj.selected_market, amount, order[1])
                    else:
                        #TODO handle this case
                        pass
            sleep(SLEEP_FOR_TEST)
            updated_open_orders = self.test_obj.lazy_account.get_orders(self.test_obj.selected_market)
            for side in ['buy','sell']:
                if not test_case['output_nb'][side+'_nb'] == len(updated_open_orders[side]):
                    #check again if in this moment safety orders will be cancelled
                    msg = f"Unexpected strategy behaviour: expected {str(test_case['output_nb'][side+'_nb'])} open orders, but got {str(len(updated_open_orders[side]))}"
                    self.logger.error(msg)
                    self.test_obj.slack.send_slack_message(msg)
                    self.exit()





    def testing_by_open_orders_ids(self, test_case_data):

        if not test_case_data:
            self.logger.error(f"ERROR: test_case_data required")
            self.exit()
        raw_open_orders = self.test_obj.lazy_account.fetch_open_orders(self.test_obj.selected_market)
        real_id_list = sorted([order['id'] for order in raw_open_orders])
        try:
            bot_config_id_list = sorted(self.get_input_ids())
        except:
            bot_config_id_list=2
            pass
        filled_order_ids = []
        if not real_id_list == bot_config_id_list:
            msg = f"Unexpected strategy behaviour: expected {str(real_id_list)} open orders, but got {str(bot_config_id_list)}"
            self.logger.error(msg)
            self.test_obj.slack.send_slack_message(msg)
            self.exit()



        for test_case in test_case_data:
            open_orders = deepcopy(self.bot.config.open_orders)
            open_orders['buy'] = list(reversed(open_orders['buy']))
            for side in ['buy','sell']:
                for index, order in enumerate(open_orders[side]):
                    if order[0] in ['FB','FS']:
                        continue
                    if index in test_case['input'][side]:
                        amount_coef = test_case['input'][side][index]['amount_percent']
                        try:
                            amount = order[2] * Decimal(amount_coef)
                        except Exception as e:
                            a=e
                        orderbook1 = self.test_obj.lazy_account.order_book(self.test_obj.selected_market)
                        self.test_obj.slack.send_slack_message(f"fixing order data: {str(orderbook1)}")
                        result = eval(f'self.test_obj.a_user_account.init_limit_{self.flip_side(side)}_order')(self.test_obj.selected_market, amount, order[1])
                        self.test_obj.slack.send_slack_message(f'Expected that order {order[0]} has been filled')
                        updated_raw_open_orders = self.test_obj.lazy_account.fetch_open_orders(
                            self.test_obj.selected_market)
                        updated_real_id_list = sorted([order['id'] for order in updated_raw_open_orders])
                        if order[0] in updated_real_id_list:
                            orderbook2 = self.test_obj.lazy_account.order_book(self.test_obj.selected_market)
                            self.test_obj.slack.send_slack_message(f"fixing order data: {str(orderbook2)}")
                            a=1
                        filled_order_ids.append(order[0])
                    else:
                        #TODO handle this case
                        pass
            sleep(SLEEP_FOR_TEST)
            updated_raw_open_orders = self.test_obj.lazy_account.fetch_open_orders(self.test_obj.selected_market)
            updated_real_id_list = sorted([order['id'] for order in updated_raw_open_orders])
            for filled_order_id in filled_order_ids:
                if filled_order_id in updated_real_id_list:
                    msg = f"Unexpected strategy behaviour: expected that order {filled_order_id} already filled, but order is still included in the order book now"
                    self.logger.error(msg)
                    self.test_obj.slack.send_slack_message(msg)
                    orderbook = self.test_obj.lazy_account.exchange.ze.orderbook(self.test_obj.selected_market.replace('/',''))
                    self.exit()
            a=1
        sleep(SLEEP_FOR_TEST*2)
        return

    def get_input_nb(self):
        return {
            'buy': self.bot.config.params['nb_buy_to_display'] + 1,   # +1 to nb_{side}_to_display because of safety orders
            'sell':self.bot.config.params['nb_sell_to_display'] + 1
        }

    def get_input_ids(self):
        return [id for id in self.bot.config.id_list if id and not id in ['FS','FB']]

    def check_if_missed_order_is_safety(self):

        return

if __name__ == "__main__":
    l = LazyTest()
    l.main()