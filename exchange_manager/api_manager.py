import logging
from time import sleep
from datetime import datetime
from decimal import Decimal
from operator import itemgetter
from utils.singleton import singleton
from utils.helper import UtilsMixin
import zebitexFormatted



class APIManager(UtilsMixin):
    def __init__(self, config, bot=None):
        if bot:
            self.bot = bot
            self.config = config
        else:
            self.bot, self.config = config, config
        self.exchange = None
        self.err_counter = 0
        self.is_kraken = False

    def set_exchange(self, exchange, keys=None):
        if keys:
            if exchange == 'zebitex_testnet':
                self.exchange = zebitexFormatted.ZebitexFormatted(
                    keys['apiKey'], keys['secret'], True)
            elif exchange == 'zebitex':
                self.exchange = zebitexFormatted.ZebitexFormatted(
                    # keys['apiKey'], keys['secret'], True) #TODO: replace for real accounts
                    keys['apiKey'], keys['secret'], True)
        else:
            if exchange == 'zebitex_testnet':
                self.exchange = zebitexFormatted.ZebitexFormatted(
                    self.config.keys[exchange]['apiKey'], self.config.keys[exchange]['secret'], True)
            elif exchange == 'zebitex':
                self.exchange = zebitexFormatted.ZebitexFormatted(
                    # self.config.keys[exchange]['apiKey'], self.config.keys[exchange]['secret'], True) #TODO: replace for real accounts
                    self.config.keys['zebitex_testnet']['apiKey'], self.config.keys['zebitex_testnet']['secret'], True)
            else:
                raise Exception(f'{exchange} unsupported')

    def fetch_balance(self):
        """Get account balance from the marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        return: dict, formated balance by ccxt."""
        try:
            return self.exchange.fetch_balance()
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            sleep(0.5)
            self.api_fail_message_handler()
            return self.fetch_balance()

    def load_markets(self):
        """Load the market list from a marketplace to self.exchange.
        Retry 1000 times when error and send a mail each 10 tries.
        """
        try:
            self.exchange.load_markets()
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            sleep(0.5)
            self.api_fail_message_handler()
            self.load_markets()

    def fetch_open_orders(self, market=None):
        """Get open orders of a market from a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        market: string, market name.
        return: list, formatted open orders by ccxt."""
        try:
            return self.exchange.fetch_open_orders(market)
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            sleep(0.5)
            self.api_fail_message_handler()
            return self.fetch_open_orders(market)

    def fetch_trades(self, market):
        """Get trading history of a market from a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        market: string, market name.
        return: list, formatted trade history by ccxt."""
        try:
            return self.exchange.fetch_trades(market)
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            sleep(0.5)
            self.api_fail_message_handler()
            return self.fetch_trades(market)

    def fetch_ticker(self, market):
        """Get ticker info of a market from a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
        market: string, market name.
        return: list, formatted trade history by ccxt."""
        try:
            return self.exchange.fetch_ticker(market)
        except Exception as e:
            logging.warning(f'WARNING: {e}')
            sleep(0.5)
            self.api_fail_message_handler()
            return self.fetch_ticker(market)

    def init_limit_buy_order(self, market, amount, price):
        """Generate a timestamp before creating a buy order."""
        self.now = self.timestamp_formater()
        return self.create_limit_buy_order(market, amount, price)

    def create_limit_buy_order(self, market, amount, price):
        """Create a limit buy order on a market of a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
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
            logging.warning(f'WARNING: {e}')
            sleep(0.5)
            self.api_fail_message_handler()
            rsp = self.check_limit_order(market, price, 'buy')
            if not rsp:
                return self.create_limit_buy_order(market, amount, price)
            else:
                return rsp


    def init_limit_sell_order(self, market, amount, price):
        """Generate a global timestamp before calling """
        self.now = self.timestamp_formater()
        return self.create_limit_sell_order(market, amount, price)

    def create_limit_sell_order(self, market, amount, price):
        """Create a limit sell order on a market of a marketplace.
        Retry 1000 times when error and send a mail each 10 tries.
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
            logging.warning(f'WARNING: {e}')
            sleep(0.5)
            self.api_fail_message_handler()
            rsp = self.check_limit_order(market, price, 'sell')
            if not rsp:
                return self.create_limit_sell_order(market, amount, price)
            else:
                return rsp

    def set_several_sell(self, start_index, target):
        """Loop for opening sell orders.
        start_index: int, from where the loop start in self.intervals.
        target: int, from where the loop start in self.intervals.
        return: list, of executed orders.
        """
        sell_orders = []
        while start_index <= target:
            order = self.init_limit_sell_order(self.config.selected_market,
                                               self.config.params['amount'],
                                               self.config.intervals[start_index])
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
            is_traded = self.order_in_history(price, trades, side, self.now)
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

    def order_in_history(self, target, a_list, side, timestamp):
        """Verify that an order is in user history.
        target: decimal, price of an order.
        a_list: list, user trade history.
        side: string, buy or sell.
        timestamp: int, timestamp of the order.
        return: boolean."""
        if side == 'buy':
            coef = Decimal('2') - Decimal(self.config.params['increment_coef']) + \
                   Decimal('0.001')
            for item in a_list:
                if item[4] >= timestamp:
                    if target * coef <= item[1] <= target:
                        return True
        if side == 'sell':
            coef = Decimal(self.config.params['increment_coef']) - Decimal('0.001')
            for item in a_list:
                if item[4] >= timestamp:
                    if target * coef >= item[1] >= target:
                        return True
        return False

    def trade_history(self):
        try:
            history = self.exchange.fetch_trades(self.config.selected_market)
            if type(history) == list:
                return history
            else:
                self.bot.applog.warning(f'WARNING: Unexpected order history: {history}')
        except Exception as e:
            self.bot.applog.warning(f'WARNING: {e}')

    def is_order_open(self, order_id):
        raw_open_orders = self.fetch_open_orders(self.config.selected_market)
        id_list = [order['id'] for order in raw_open_orders]
        if order_id in id_list:
            return True


    def cancel_order(self, order_id, price, timestamp, side):
        """Cancel an order with it's id.
        Retry 1000 times, send an email each 10 tries.
        Warning : Not connard proofed!
        order_id: string, marketplace order id.
        price: string, price of the order.
        timestamp: int, timestamp of the order.
        side: string, buy or sell.
        return: boolean, True if the order is canceled correctly, False when the
        order have been filled before it's cancellation"""
        cancel_side = 'cancel_buy' if side == 'buy' else 'cancel_sell'
        try:
            self.bot.applog.debug(f'Init cancel {side} order {order_id} {price}')
            rsp = self.exchange.cancel_order(order_id)
            self.bot.slack.send_slack_message(f'canceled order {str(order_id)} responce: {str(rsp)}')
            if rsp:
                self.order_logger_formatter(cancel_side, order_id, price, 0)
                if self.is_order_open(order_id):
                    raise Exception('Cancelled order still open')
                return True
            else:
                msg = (
                    f'The {side} {order_id} have been filled '
                    f'before being canceled'
                )
                self.bot.stratlog.warning(msg)
                return rsp
        except Exception as e:
            self.bot.applog.warning(f'WARNING: {e}')
            sleep(0.5)
            self.api_fail_message_handler()
            if self.is_order_open(order_id):
                rsp = self.exchange.cancel_order(order_id)
                if rsp:
                    self.err_counter = 0
                    return rsp
            trades = self.get_user_history(self.config.selected_market)[side]
            is_traded = self.order_in_history(price, trades, side, timestamp)
            if is_traded:
                msg = (
                    f'The {side} {order_id} have been filled '
                    f'before being canceled'
                )
                self.bot.stratlog.warning(msg)
                return False
            else:
                self.order_logger_formatter(cancel_side, order_id, price, 0)
                return True

    def cancel_all(self, open_orders=None):
        if not open_orders:
            open_orders = self.get_orders(market=self.config.selected_market)
        if open_orders['buy']:
            for item in open_orders['buy']:
                self.cancel_order(item[0], item[1], item[4], 'buy')
        if open_orders['sell']:
            for item in open_orders['sell']:
                self.cancel_order(item[0], item[1], item[4], 'sell')



    def api_fail_message_handler(self):
        """Send an alert where ther eis too much fail with the exchange API"""
        self.err_counter += 1
        if self.err_counter >= 10:
            msg = 'api error >= 10'
            if self.bot.slack:
                self.bot.slack.send_slack_message(msg)
            else:
                self.config.strat.warning(msg)
            self.err_counter = 0

    def order_book(self, market):
        if type(self.exchange) is zebitexFormatted.ZebitexFormatted:
            market = market.replace('/','').lower()
            return self.exchange.ze.orderbook(market)
        else:
            #TODO
            raise Exception('Unsupported yet')


    """
    ###################### API REQUESTS FORMATTERS ############################
    """

    def get_market_last_price(self, market):
        """Get the last price of a specific market
        market: str, need to have XXX/YYY ticker format
        return: decimal"""
        return Decimal(f"{self.fetch_ticker(market)['last']:.8f}")

    def get_balances(self):  # Need to be refactored
        """Get the non empty balance of a user on a marketplace and make
        it global."""
        balance = self.fetch_balance()
        user_balance = {}
        for key, value in balance.items():
            if 'total' in value:
                if float(value['total']) != 0.0:
                    for item in value:
                        value[item] = str(value[item])
                    user_balance.update({key: value})
        if self.is_kraken:
            orders = self.fetch_open_orders()
            for order in orders:
                if order['side'] == 'buy':
                    coin = order['symbol'].split('/')[1]
                    if user_balance[coin]['used'] == 'None':
                        user_balance[coin]['used'] = Decimal(order['price']) \
                                                     * Decimal(order['amount'])
                    else:
                        user_balance[coin]['used'] = user_balance[coin]['used'] \
                                                     + Decimal(order['price']) * Decimal(order['amount'])
                else:
                    coin = order['symbol'].split('/')[0]
                    if user_balance[coin]['used'] == 'None':
                        user_balance[coin]['used'] = Decimal(order['amount'])
                    else:
                        user_balance[coin]['used'] = user_balance[coin]['used'] \
                                                     + Decimal(order['amount'])
            for coin in user_balance:
                if user_balance[coin]['used'] != 'None':
                    user_balance[coin]['free'] = str(
                        Decimal(user_balance[coin]['total']) \
                        - user_balance[coin]['used'])
                    user_balance[coin]['used'] = str(user_balance[coin]['used'])
                else:
                    user_balance[coin]['used'] = '0.0'
                    user_balance[coin]['free'] = user_balance[coin]['total']
                if user_balance[coin]['free'] == 'None':
                    user_balance[coin]['free'] = '0.0'
        self.config.user_balance = user_balance
        return user_balance

    def display_user_balance(self):
        """Display the user balance"""
        for key, value in self.config.user_balance.items():
            self.bot.stratlog.info(f'{key}: {value}')
        return

    def format_order(self, order_id, price, amount, timestamp, date):
        """Sort the information of an order in a list of 6 items.
        id: string, order unique identifier.
        price: Decimal or string.
        amount: Decimal.
        timestamp: string.
        date: string.
        return: list, containing: id, price, amount, value, timestamp and date.
        """
        return [order_id, Decimal(price), amount, self.multiplier(
            Decimal(price), amount, self.config.fees_coef), timestamp, date]

    def format_log_order(self, side, order_id, price, amount, timestamp, date):
        """Sort the information of an order in a list of 6 items.
        id: string, order unique identifier.
        price: Decimal or string.
        amount: Decimal.
        timestamp: string.
        date: string.
        return: list, containing: id, price, amount, value, timestamp and date.
        """
        return [side, order_id, price, amount, str(self.multiplier(
            Decimal(price), Decimal(amount), self.config.fees_coef)), \
                timestamp, date]

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

    def display_user_trades(self, orders):
        """Pretify and display orders list.
        orders: dict, contain all orders.
        """
        if orders['buy']:
            for order in orders['buy']:
                self.bot.stratlog.info(self.format_order_to_display(order))
        if orders['sell']:
            for order in orders['sell']:
                self.bot.stratlog.info(self.format_order_to_display(order))
        return

    def format_order_to_display(self, order):
        """To format an order as a string.
        order: dict.
        return: string."""
        return (
            f'{order[0]} on: {order[6]}, id: {order[1]}, price: {order[2]}, '
            f'amount: {order[3]}, value: {order[4]}, timestamp: {order[5]}'
        )

    def order_logger_formatter(self, side, order_id, price, amount):
        """Format into a string an order for the logger
        side : string. buy, cancel_buy, sell or cancel_sell
        order_id: string, order id on the marketplace.
        price: Decimal.
        amount: Decimal.
        return: tuple with strings."""
        timestamp = self.timestamp_formater()
        date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        msg = (
            f'{{"side": "{str(side)}", "order_id": "{str(order_id)}", '
            f'"price": "{str(price)}", "amount": "{str(amount)}", '
            f'"timestamp": "{timestamp}", "datetime": "{date_time}" н}}')
        if self.bot.slack:
            self.bot.slack.send_slack_message(msg)
        else:
            self.bot.stratlog.warning(msg)
        return timestamp, date_time

