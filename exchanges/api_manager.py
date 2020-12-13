from copy import deepcopy
from time import sleep
from datetime import datetime
from decimal import Decimal

import utils.helpers as helpers
import utils.converters as convert
from exchanges.zebitexFormatted import ZebitexFormatted
from main.order import Order
import utils.logger_factory as lf
import config.config as config


class APIManager:
    def __init__(self, url, safety_buy_value, safety_sell_value):
        self.log = lf.get_simple_logger("api_manager")
        self.log.set_slack(url)
        self.safety_buy_value = safety_buy_value
        self.safety_sell_value = safety_sell_value
        self.root_path = helpers.set_root_path()
        self.exchange = None
        self.err_counter = 0
        self.is_kraken = False
        self.now = 0
        self.fees_coef = config.FEES_COEFFICIENT
        self.intervals = []
        self.empty_intervals = []
        self.market = ""
        self.profits_alloc = 0

    def set_zebitex(self, keys, network):
        if network == "zebitex_testnet":
            self.exchange = ZebitexFormatted(keys["apiKey"], keys["secret"], True)
        elif network == "zebitex":
            self.exchange = ZebitexFormatted(keys["apiKey"], keys["secret"], False)
        else:
            raise ValueError(f"{keys} unsupported")

    def set_params(self, params):
        self.intervals = params["intervals"]
        self.empty_intervals = deepcopy(self.intervals)
        self.market = params["market"]
        self.profits_alloc = params["profits_alloc"]

    def load_markets(self):
        """Load the market list from a marketplace to self.exchange.
        Retry 1000 times when error and send message on slack each 10 tries.
        """
        try:
            self.exchange.load_markets()
        except Exception as e:
            self.log.warning(f"WARNING: {e}")
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
            self.log.warning(f"WARNING: {e}")
            sleep(0.5)
            self.api_fail_message_handler()
            return self.fetch_balance()

    def fetch_open_orders(self, market=None):
        """Get open orders of a market from a marketplace.
        Retry 1000 times when error and send message on slack each 10 tries.
        market: string, market name.
        return: list, formatted open orders by ccxt."""
        try:
            if market is None:
                market = self.market
            return self.exchange.fetch_open_orders(market)
        except Exception as e:
            self.log.warning(f"WARNING: {e}")
            sleep(0.5)
            self.api_fail_message_handler()
            return self.fetch_open_orders(market)

    def format_open_orders(self, raw_orders):
        """Format orders from fetch_open_orders in the correct way: [Order]"""
        orders = [
            Order(
                order["id"],
                convert.quantizator(Decimal(order["price"])),
                convert.quantizator(Decimal(order["amount"])),
                order["side"],
                int(order["timestamp"]),
                date=order["datetime"],
                fee=self.fees_coef,
                filled=convert.quantizator(Decimal(order["filled"]) / Decimal("100")),
            )
            for order in raw_orders
        ]
        return sorted(orders, key=lambda x: x.price)

    def get_open_orders(self, market=None):
        if market is None:
            market = self.market
        """Format orders from fetch_open_orders in the correct way and sort by price: [Order]"""
        raw_orders = self.exchange.fetch_open_orders(market)
        return self.format_open_orders(raw_orders)

    def fetch_trades(self, market=None):
        """Get trading history of a market from a marketplace.
        Retry 1000 times when error and send message on slack each 10 tries.
        market: string, market name.
        return: list, formatted trade history by ccxt."""
        try:
            if market is None:
                market = self.market
            return self.exchange.fetch_trades(market)
        except Exception as e:
            self.log.warning(f"WARNING: {e}")
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
            self.log.warning(f"WARNING: {e}")
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
            date = self.order_logger_formatter("buy", order["id"], price, amount)
            return Order(
                order["id"], price, amount, "buy", date[0], date[1], self.fees_coef
            )
        except Exception as e:
            self.log.warning(f"WARNING: {e}")
            sleep(0.5)
            self.api_fail_message_handler()
            rsp = self.check_limit_order(market, price, "buy")
            if not rsp:
                return self.create_limit_buy_order(market, amount, price)
            else:
                return rsp

    def set_several_buy(self, orders_to_open: [dict]) -> [Order]:
        buy_orders = []
        for order in orders_to_open:
            buy_orders.append(
                self.init_limit_buy_order(self.market, order["amount"], order["price"])
            )
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
            order = self.exchange.create_limit_sell_order(market, amount, price)
            date = self.order_logger_formatter("sell", order["id"], price, amount)
            return Order(
                order["id"], price, amount, "sell", date[0], date[1], self.fees_coef
            )
        except Exception as e:
            self.log.warning(f"WARNING: {e}")
            sleep(0.5)
            self.api_fail_message_handler()
            rsp = self.check_limit_order(market, price, "sell")
            if not rsp:
                return self.create_limit_sell_order(market, amount, price)
            else:
                return rsp

    def set_several_sell(self, orders_to_open: [dict]) -> [Order]:
        sell_orders = []
        for order in orders_to_open:
            sell_orders.append(
                self.init_limit_sell_order(self.market, order["amount"], order["price"])
            )
        return sell_orders

    def check_limit_order(self, market, price, side):
        """Verify if an order have been correctly created despite API error
        market: string, market name.
        price: string, price of the order.
        side: string, buy or sell
        return: list, in a formatted order"""
        sleep(0.5)
        is_open = self.check_an_order_is_open(price, side)
        if is_open:
            return is_open
        else:
            trades = self.get_user_history(market)[side]
            is_traded = self.order_in_history(market, price, trades, side, self.now)
            if is_traded:
                return is_traded
        return False

    def find_interval_for_price(self, price):
        """return idx of correct interval for price"""
        if (
            price < self.intervals[0].get_bottom()
            or price >= self.intervals[-1].get_top()
        ):
            return None

        interval_idx = 0
        while not (
            self.intervals[interval_idx].get_bottom()
            <= price
            < self.intervals[interval_idx].get_top()
        ):
            interval_idx += 1

        return interval_idx

    def check_an_order_is_open(self, price, side):
        """Verify if an order is contained in a list
        target: decimal, price of an order.
        a_list: list, user trade history.
        return: boolean."""
        intervals = self.get_intervals(self.market)
        idx = self.find_interval_for_price(price)
        if idx is None:
            return False

        if side == "buy":
            return intervals[idx].find_buy_order_by_price(price)
        else:
            return intervals[idx].find_buy_order_by_price(price)

    def order_in_history(self, market, target, a_list, side, timestamp):
        """Verify that an order is in user history.
        target: decimal, price of an order.
        a_list: list, user trade history.
        side: string, buy or sell.
        timestamp: int, timestamp of the order.
        return: boolean."""
        price = self.get_market_last_price(market)
        if side == "buy":
            for item in a_list:
                if item.timestamp >= timestamp:
                    if price * Decimal("1.005") <= item.price <= target:
                        return True

        if side == "sell":
            for item in a_list:
                if item.timestamp >= timestamp:
                    if price * Decimal("1.005") >= item.price >= target:
                        return True

        return False

    def trade_history(self):
        try:
            history = self.exchange.fetch_trades(self.market)
            if isinstance(history, list):
                return history
            else:
                self.log.warning(f"WARNING: Unexpected order history: {history}")
        except Exception as e:
            self.log.warning(f"WARNING: {e}")

    def cancel_orders(self, orders):
        """Cancel multiple orders"""
        for order in orders:
            self.cancel_order(order)

    def cancel_order(self, order):
        """Cancel an order with it's id.
        Retry 1000 times, send message on slack each 10 tries.
        Warning : Not connard proofed!
        order_id: string, marketplace order id.
        price: string, price of the order.
        timestamp: int, timestamp of the order.
        side: string, buy or sell.
        return: boolean, True if the order is canceled correctly, False when the
        order have been filled before it's cancellation"""
        cancel_side = "cancel_buy" if order.side == "buy" else "cancel_sell"
        try:
            self.log.debug(f"Init cancel {order.side} order {order.id} {order.price}")
            rsp = self.exchange.cancel_order(order.id, self.market)
            if rsp:
                self.order_logger_formatter(
                    cancel_side, order.id, order.price, order.amount
                )
                return True

            else:
                msg = (
                    f"The {order.side} {order.id} have been filled "
                    f"before being canceled"
                )
                self.log.warning(msg)

                return rsp
        except Exception as e:
            self.log.warning(f"WARNING: {e}")
            sleep(0.5)
            self.api_fail_message_handler()
            is_open = self.check_an_order_is_open(order.price, order.side)

            if is_open:
                rsp = self.exchange.cancel_order(order.id)
                if rsp:
                    self.err_counter = 0
                    return rsp

            trades = self.get_user_history(self.market)[order.side]
            is_traded = self.order_in_history(
                self.market, order.price, trades, order.side, order.timestamp
            )

            if is_traded:
                msg = (
                    f"The {order.side} {order.id} have been filled "
                    f"before being canceled"
                )
                self.log.warning(msg)
                return False

            else:
                self.order_logger_formatter(
                    cancel_side, order.id, order.price, order.amount
                )
                return True

    def cancel_all(self, market, open_orders=None):
        if not open_orders:
            open_orders = self.get_open_orders(market)
        for order in open_orders:
            self.cancel_order(order)

    def api_fail_message_handler(self):
        """Send an alert where ther eis too much fail with the exchange API"""
        self.err_counter += 1
        if self.err_counter >= 10:
            self.log.ext_warning("api error >= 10")
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
            if "total" in value:
                if float(value["total"]) != 0.0:
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
                if item == "None":
                    user_balance[coin][item] = Decimal("0")

        for order in orders:
            if order["side"] == "buy":
                coin = order["symbol"].split("/")[1]
                user_balance[coin]["used"] += Decimal(order["price"]) * Decimal(
                    order["amount"]
                )

            else:
                coin = order["symbol"].split("/")[0]
                user_balance[coin]["used"] += Decimal(order["amount"])

        for coin in user_balance:
            user_balance[coin]["free"] = (
                user_balance[coin]["total"] - user_balance[coin]["used"]
            )

        return user_balance

    def get_intervals(self, market=None):
        """Get actives orders from a marketplace and organize them.
        return: dict, containing list of buys & sells.
        """
        if market is None:
            market = self.market
        self.intervals = deepcopy(self.empty_intervals)

        open_orders = self.get_open_orders(market)
        helpers.populate_intervals(self.intervals, open_orders)
        return self.intervals

    def get_safety_buy(self, market=None):
        if market is None:
            market = self.market

        orders = self.get_open_orders(market)
        safety_buys = [
            order for order in orders if order.price == self.safety_buy_value
        ]
        if len(safety_buys) > 0:
            return safety_buys[0]
        return None

    def get_safety_sell(self, market=None):
        if market is None:
            market = self.market

        orders = self.get_open_orders(market)
        safety_sells = [
            order for order in orders if order.price == self.safety_sell_value
        ]
        if len(safety_sells) > 0:
            return safety_sells[0]
        return None

    def get_user_history(self, market=None):
        """Get orders history from a marketplace and organize them.
        return: dict, containing list of buy & list of sell.
        """
        if market is None:
            market = self.market

        orders = {"sell": [], "buy": []}
        raw_orders = self.fetch_trades(market)
        for order in raw_orders:
            formatted_order = Order(
                order["id"],
                Decimal(str(order["price"])),
                Decimal(str(order["amount"])),
                order["side"],
                str(order["timestamp"]),
                order["datetime"],
                self.fees_coef,
            )
            if order["side"] == "buy":
                orders["buy"].append(formatted_order)
            if order["side"] == "sell":
                orders["sell"].append(formatted_order)
        return orders

    def order_logger_formatter(self, side, order_id, price, amount):
        """Format into a string an order for the logger
        side : string. buy, cancel_buy, sell or cancel_sell
        order_id: string, order id on the marketplace.
        price: Decimal.
        amount: Decimal.
        return: tuple with strings."""
        timestamp = convert.timestamp_formater()
        date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        msg = (
            f"side: {str(side)}, order_id: {str(order_id)}, "
            f"price: {str(price)}, amount: {str(amount)}, "
            f"timestamp: {timestamp}, datetime: {date_time}"
        )

        if price in [self.safety_buy_value, self.safety_sell_value, "0.00000001"]:
            slack = False
        else:
            slack = True
            helpers.append_to_file(f"{self.root_path}logs/history.txt", f"{msg}\n")

        if slack:
            self.log.ext_info(msg)
        else:
            self.log.info(msg)

        return timestamp, date_time

    def get_order_book(self, market=None):
        if market is None:
            market = self.market

        return self.exchange.get_order_book(market)
