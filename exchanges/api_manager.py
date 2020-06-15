import sys
from time import sleep
from datetime import datetime
from decimal import Decimal
from operator import itemgetter

import utils.converters as convert
from exchanges.zebitexFormatted import ZebitexFormatted
from utils.logger import Logger


class APIManager():
    def __init__(self, url):
        self.log = Logger(name='api_manager', slack_webhook=url).log
        self.exchange = None
        self.err_counter = 0
        self.is_kraken = False
        self.now = 0
        self.fees_coef = 0
        self.intervals = []
        self.market = ''
        self.profits_alloc = 0

    def set_zebitex(self, keys, network):
        if network == 'zebitex_testnet':
            self.exchange = ZebitexFormatted(
                keys['apiKey'], keys['secret'], True)
        elif network == 'zebitex':
            self.exchange = ZebitexFormatted(
                keys['apiKey'], keys['secret'], False)
        else:
            raise ValueError(f'{keys} unsupported')

    def set_params(self, params):
        self.intervals = params['intervals']
        self.market = params['market']
        self.profits_alloc = params['profits_alloc']

    def load_markets(self):
        """Load the market list from a marketplace to self.exchange.
        Retry 1000 times when error and send message on slack each 10 tries.
        """
        try:
            self.exchange.load_markets()
        except Exception as e:
            self.log(f'WARNING: {sys._getframe().f_code.co_name}: {e}', level='warning')
            sleep(0.5)
            self.api_fail_message_handler()
            self.load_markets()

    def fetch_balance(self):
        """Get account balance from the marketplace.
        Retry 1000 times when error and send message on slack each 10 tries.
        return: dict, formated balance by ccxt."""
        try:
            return self.exchange.fetch_balance()
        except Exception as e:
            self.log(f'WARNING: {sys._getframe().f_code.co_name}: {e}', level='warning')
            sleep(0.5)
            self.api_fail_message_handler()
            return self.fetch_balance()

    def fetch_open_orders(self, market=None):
        """Get open orders of a market from a marketplace.
        Retry 1000 times when error and send message on slack each 10 tries.
        market: string, market name.
        return: list, formatted open orders by ccxt."""
        try:
            return self.exchange.fetch_open_orders(market)
        except Exception as e:
            self.log(f'WARNING: {sys._getframe().f_code.co_name}: {e}', level='warning')
            sleep(0.5)
            self.api_fail_message_handler()
            return self.fetch_open_orders(market)

    def fetch_trades(self, market):
        """Get trading history of a market from a marketplace.
        Retry 1000 times when error and send message on slack each 10 tries.
        market: string, market name.
        return: list, formatted trade history by ccxt."""
        try:
            return self.exchange.fetch_trades(market)
        except Exception as e:
            self.log(f'WARNING: {sys._getframe().f_code.co_name}: {e}', level='warning')
            sleep(0.5)
            self.api_fail_message_handler()
            return self.fetch_trades(market)

    def fetch_ticker(self, market=None):
        """Get ticker info of a market from a marketplace.
        Retry 1000 times when error and send message on slack each 10 tries.
        market: string, market name.
        return: list, formatted trade history by ccxt."""
        try:
            if not market:
                market = self.market
            return self.exchange.fetch_ticker(market)
        except Exception as e:
            self.log(f'WARNING: {sys._getframe().f_code.co_name}: {e}', level='warning')
            sleep(0.5)
            self.api_fail_message_handler()
            return self.fetch_ticker(market)

    def init_limit_buy_order(self, market, amount, price):
        """Generate a timestamp before creating a buy order."""
        self.now = convert.timestamp_formater()
        return self.create_limit_buy_order(market, amount, price)

    def create_limit_buy_order(self, market, amount, price):
        """Create a limit buy order on a market of a marketplace.
        Retry 1000 times when error and send message on slack each 10 tries.
        market: string, market name.
        amount: string, amount of ALT to buy.
        price: string, price of the order.
        return: list, formatted trade history by ccxt."""
        try:
            order = self.exchange.create_limit_buy_order(market, amount, price)
            date = self.order_logger_formatter('buy', order['id'], price,
                                               amount)
            return self.format_order(order['id'], price, amount,
                                     date[0], date[1])
        except Exception as e:
            self.log(f'WARNING: {sys._getframe().f_code.co_name}: {e}', level='warning')
            sleep(0.5)
            self.api_fail_message_handler()
            rsp = self.check_limit_order(market, price, 'buy')
            if not rsp:
                return self.create_limit_buy_order(market, amount, price)
            else:
                return rsp

    def set_several_buy(self, start_index, target, amounts):
        """Loop for opening buy orders. It generate amount to split benef
        following benef alloc.
        start_index: int, from where the loop start in self.intervals.
        target: int, from where the loop start in self.intervals.
        amounts: list, orders amount per intervals.
        return: list, of executed orders.
        """
        buy_orders = []
        while start_index <= target:
            order = self.init_limit_buy_order(self.market, amounts[start_index],
                                              self.intervals[start_index])
            buy_orders.append(order)
            start_index += 1
        return buy_orders

    def init_limit_sell_order(self, market, amount, price):
        """Generate a global timestamp before calling """
        self.now = convert.timestamp_formater()
        return self.create_limit_sell_order(market, amount, price)

    def create_limit_sell_order(self, market, amount, price):
        """Create a limit sell order on a market of a marketplace.
        Retry 1000 times when error and send message on slack each 10 tries.
        market: string, market name.
        amount: string, amount of ALT to sell.
        price: string, price of the order.
        return: list, formatted trade history by ccxt
                or boolean True when the order is already filled"""
        try:
            order = self.exchange.create_limit_sell_order(market,
                                                          amount,
                                                          price)
            date = self.order_logger_formatter('sell', order['id'], price,
                                               amount)
            return self.format_order(order['id'], price, amount,
                                     date[0], date[1])
        except Exception as e:
            self.log(f'WARNING: {sys._getframe().f_code.co_name}: {e}', level='warning')
            sleep(0.5)
            self.api_fail_message_handler()
            rsp = self.check_limit_order(market, price, 'sell')
            if not rsp:
                return self.create_limit_sell_order(market, amount, price)
            else:
                return rsp

    def set_several_sell(self, start_index, target, amounts):
        """Loop for opening sell orders.
        start_index: int, from where the loop start in self.intervals.
        target: int, from where the loop start in self.intervals.
        amounts: list, orders amount per intervals.
        return: list, of executed orders.
        """
        sell_orders = []
        while start_index <= target:
            order = self.init_limit_sell_order(self.market,
                                               amounts[start_index],
                                               self.intervals[start_index])
            sell_orders.append(order)
            start_index += 1
        return sell_orders

    def check_limit_order(self, market, price, side):
        """Verify if an order have been correctly created despite API error
        market: string, market name.
        price: string, price of the order.
        side: string, buy or sell
        return: list, in a formatted order"""
        sleep(0.5)
        orders = self.get_orders(market)[side]
        is_open = self.does_an_order_is_open(price, orders)
        if is_open:
            return is_open
        else:
            trades = self.get_user_history(market)[side]
            is_traded = self.order_in_history(market, price, trades, side, self.now)
            if is_traded:
                return is_traded
        return False

    def does_an_order_is_open(self, target, a_list):
        """Verify if an order is contained in a list
        target: decimal, price of an order.
        a_list: list, user trade history.
        return: boolean."""
        for item in a_list:
            if item[1] == target:
                return item
        return False

    def order_in_history(self, market, target, a_list, side, timestamp):
        """Verify that an order is in user history.
        target: decimal, price of an order.
        a_list: list, user trade history.
        side: string, buy or sell.
        timestamp: int, timestamp of the order.
        return: boolean."""
        price = self.get_market_last_price(market)
        if side == 'buy':
            for item in a_list:
                if item[4] >= timestamp:
                    if price * Decimal('1.005') <= item[1] <= target:
                        return True
        
        if side == 'sell':
            for item in a_list:
                if item[4] >= timestamp:
                    if price * Decimal('1.005') >= item[1] >= target:
                        return True
        
        return False

    def trade_history(self):
        try:
            history = self.exchange.fetch_trades(self.market)
            if isinstance(history, list):
                return history
            else:
                self.log(f'WARNING: Unexpected order history: {history}', level='warning')
        except Exception as e:
            self.log(f'WARNING: {sys._getframe().f_code.co_name}: {e}', level='warning')

    def cancel_order(self, market, order_id, price, timestamp, side):
        """Cancel an order with it's id.
        Retry 1000 times, send message on slack each 10 tries.
        Warning : Not connard proofed!
        order_id: string, marketplace order id.
        price: string, price of the order.
        timestamp: int, timestamp of the order.
        side: string, buy or sell.
        return: boolean, True if the order is canceled correctly, False when the
        order have been filled before it's cancellation"""
        cancel_side = 'cancel_buy' if side == 'buy' else 'cancel_sell'
        try:
            self.log(f'Init cancel {side} order {order_id} {price}', level='info', print_=True, slack=True)
            rsp = self.exchange.cancel_order(order_id)
            if rsp:
                self.order_logger_formatter(cancel_side, order_id, price, 0)
                return True
           
            else:
                msg = (f'The {side} {order_id} have been filled '
                       f'before being canceled')
                self.log(msg, level='warning')

                return rsp
        except Exception as e:
            self.log(f'WARNING: {sys._getframe().f_code.co_name}: {e}', level='warning')
            sleep(0.5)
            self.api_fail_message_handler()
            orders = self.get_orders(self.market)[side]
            is_open = self.does_an_order_is_open(price, orders)

            if is_open:
                rsp = self.exchange.cancel_order(order_id)
                if rsp:
                    self.err_counter = 0
                    return rsp

            trades = self.get_user_history(self.market)[side]
            is_traded = self.order_in_history(market, price, trades, side, timestamp)

            if is_traded:
                msg = (f'The {side} {order_id} have been filled '
                       f'before being canceled')
                self.log(msg, level='warning')
                return False

            else:
                self.order_logger_formatter(cancel_side, order_id, price, 0)
                return True

    def cancel_all(self, market, open_orders=None):
        if open_orders:
            if open_orders['buy']:
                for item in open_orders['buy']:
                    self.cancel_order(market, item[0], item[1], item[4], 'buy')
            if open_orders['sell']:
                for item in open_orders['sell']:
                    self.cancel_order(market, item[0], item[1], item[4], 'sell')
        else:
            open_orders = self.fetch_open_orders(market)
            for item in open_orders:
                self.cancel_order(market, item['id'], item['price'], item['timestamp'], item['side'])

    def api_fail_message_handler(self):
        """Send an alert where ther eis too much fail with the exchange API"""
        self.err_counter += 1
        if self.err_counter >= 10:
            self.log('api error >= 10', level='warning', slack=True, print_=True)
            self.err_counter = 0


    """
    ###################### API REQUESTS FORMATTERS ############################
    """

    def get_market_last_price(self, market):
        """Get the last price of a specific market
        market: str, need to have XXX/YYY ticker format
        return: decimal"""
        return Decimal(f"{self.fetch_ticker(market)['last']:.8f}")

    def get_balances(self):  # Need to be refactored
        """Get the non empty balance of a user on a marketplace."""
        balance = self.fetch_balance()
        user_balance = {}
        for key, value in balance.items():
            if 'total' in value:
                if float(value['total']) != 0.0:
                    for item in value:
                        value[item] = Decimal(str(value[item]))
                    user_balance.update({key: value})
        
        if self.is_kraken:
            user_balance = self.generate_kraken_balance(user_balance)

        return user_balance

    def generate_kraken_balance(self, user_balance):
        orders = self.fetch_open_orders()
        
        for coin in user_balance.keys():
            for item in user_balance[coin]:
                if item == 'None':
                    user_balance[coin][item] = Decimal('0')
        
        for order in orders:
            if order['side'] == 'buy':
                coin = order['symbol'].split('/')[1]
                user_balance[coin]['used'] += Decimal(order['price']) \
                                              * Decimal(order['amount'])
            
            else:
                coin = order['symbol'].split('/')[0]
                user_balance[coin]['used'] += Decimal(order['amount'])

        for coin in user_balance:
            user_balance[coin]['free'] = user_balance[coin]['total'] \
                                         - user_balance[coin]['used']

        return user_balance

    def format_order(self, order_id, price, amount, timestamp, date):
        """Sort the information of an order in a list of 6 items.
        id: string, order unique identifier.
        price: Decimal or string.
        amount: Decimal.
        timestamp: string.
        date: string.
        return: list, containing: id, price, amount, value, timestamp and date.
        """
        return [str(order_id), Decimal(price), amount, convert.multiplier(
            Decimal(price), amount, self.fees_coef), timestamp, date]

    def get_orders(self, market):
        """Get actives orders from a marketplace and organize them.
        return: dict, containing list of buys & sells.
        """
        orders = {'sell': [], 'buy': []}
        raw_orders = self.fetch_open_orders(market)
        for order in raw_orders:
            formated_order = self.format_order(
                order['id'],
                Decimal(str(order['price'])),
                Decimal(str(order['amount'])),
                str(order['timestamp']),
                order['datetime'])
            if order['side'] == 'buy':
                orders['buy'].append(formated_order)
            if order['side'] == 'sell':
                orders['sell'].append(formated_order)
        return orders

    def orders_price_ordering(self, orders):
        """Ordering open orders in their respective lists.
        list[0][1] is the lowest value.
        orders: dict, containing list of buys & sells.
        return: dict, ordered lists of buys & sells."""
        if orders['buy']:
            orders['buy'] = sorted(orders['buy'], key=itemgetter(1))
        if orders['sell']:
            orders['sell'] = sorted(orders['sell'], key=itemgetter(1))
        return orders

    def get_user_history(self, market):
        """Get orders history from a marketplace and organize them.
        return: dict, containing list of buy & list of sell.
        """
        orders = {'sell': [], 'buy': []}
        raw_orders = self.fetch_trades(market)
        for order in raw_orders:
            formated_order = self.format_order(
                order['id'],
                Decimal(str(order['price'])),
                Decimal(str(order['amount'])),
                str(order['timestamp']),
                order['datetime'])
            if order['side'] == 'buy':
                orders['buy'].append(formated_order)
            if order['side'] == 'sell':
                orders['sell'].append(formated_order)
        return orders

    def order_logger_formatter(self, side, order_id, price, amount):
        """Format into a string an order for the logger
        side : string. buy, cancel_buy, sell or cancel_sell
        order_id: string, order id on the marketplace.
        price: Decimal.
        amount: Decimal.
        return: tuple with strings."""
        timestamp = convert.timestamp_formater()
        date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        msg = (
            f'side: {str(side)}, order_id: {str(order_id)}, '
            f'price: {str(price)}, amount: {str(amount)}, '
            f'timestamp: {timestamp}, datetime: {date_time}')
        self.log(msg, level='info', slack=True, print_=True)

        return timestamp, date_time