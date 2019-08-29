from zebitex import Zebitex, ZebitexError
from decimal import *
from datetime import datetime, date, timedelta
import time
from utils.helper import UtilsMixin

class ZebitexFormatted(UtilsMixin):
    """"Zebittex api formatter to get almost same output as ccxt"""
    getcontext().prec = 8

    def __init__(self, access_key=None, secret_key=None, is_staging=False):
        self.ze = Zebitex(access_key, secret_key, is_staging)
        self.fees = Decimal('0.0015')
        self.symbols = None
    
    def fetch_balance(self):
        balance = self.ze.funds()
        fetched_balance = {}
        for key, value in balance.items():
            if value['balance'] == '0.00000000' or value['balance'] == '1E-8':
                value['balance'] = '0.0'
            if value['lockedBalance'] == '0.00000000' or\
                value['lockedBalance'] == '1E-8':
                value['lockedBalance'] = '0.0'
            fetched_balance.update(
                {key: {'free': value['balance'],
                       'used': value ['lockedBalance'],
                       'total': str(Decimal(value['balance']) +\
                                   Decimal(value ['lockedBalance']))}})
        return fetched_balance

    def fetch_open_orders(self, market=None):
        open_orders = self.ze.open_orders('1', '1000')
        fetched_open_order = []
        for item in open_orders['items']:            
            if market:
                if item['pair'] == market:
                    fetched_open_order.append(self.order_formatted(item))
            else:
                fetched_open_order.append(self.order_formatted(item))
        return fetched_open_order

    def order_formatted(self, order):
        return {'info': 
                    {'orderNumber': order['id'],
                     'type': order['ordType'],
                     'rate': order['price'],
                     'startingAmount': order['amount'],
                     'amount': str(Decimal(order['amount']) - Decimal(
                          order['filled'])),
                     'total': order['total'],
                     'date': order['updatedAt'],
                     'margin': 0,
                     'status': order['state'],
                     'side': order['side'],
                     'price': order['price']},
                'id': order['id'],
                'timestamp': self.str_to_epoch(order['updatedAt']), #carefull, it will construct epoch following your personnal timezone
                'datetime': order['updatedAt'],
                'lastTradeTimestamp': None, #Not enough info fro the api to construct it
                'status': order['state'],
                'symbol': order['pair'],
                'type': order['ordType'],
                'side': order['side'],
                'price': float(order['price']),
                'cost': float(self.calculate_filled_cost(order['filled'],
                    order['price'])),
                'amount': float(order['amount']),
                'filled': float(order['filled']),
                'remaining': float(Decimal(order['amount']) - Decimal(
                    order['filled'])),
                'trades': None if float(order['filled']) != 0 else True,
                'fee': float(self.calcultate_paid_fees(order['filled']))
                }

    def load_markets(self):
        tickers = self.ze.tickers()
        fetched_tickers = {}
        for key, ticker in tickers.items():
            fetched_tickers.update({ticker['name']: {
                'fee_loaded': False,
                'percentage': True,
                'maker': ticker['ask_fee'],
                'taker': ticker['bid_fee'],
                'precision': {'amount': 8, 'price': 8},#need to check for eur 
                'limits': {'amount': {'min': 1e-07, ' max': 1000000000},
                           'price': {'min': 1e-08, 'max': 1000000000},
                           'cost': {'min': 0.000001}},
                'id': f"{ticker['base_unit']}_{ticker['quote_unit']}".upper(),
                'symbol': ticker['name'],
                'baseId': ticker['base_unit'].upper(),
                'quoteId': ticker['quote_unit'].upper(),
                'active': ticker['isUpTend'],
                'info': {'id': None,
                         'last': ticker['last'],
                         'lowestAsk': ticker['sell'],
                         'highestBid': ticker['buy'],
                         'percentChange': ticker['percent'],
                         'baseVolume': None,
                         'quoteVolume': ticker['volume'],
                         'isFrozen': '0',
                         'high24hr': ticker['high'],
                         'low24hr': ticker['low']
                         }}})
        self.symbols = self.format_symbols_list(tickers)
        return

    def format_symbols_list(self, tickers):
        symbols = []
        for item in tickers:
            if item[-4:] == 'usdt':
                item = f'{item[:-4]}/{item[-4:]}'
            else:
                item = f'{item[:-3]}/{item[-3:]}'
            symbols.append(item.upper())
        return symbols

    def fetch_ticker(self, ticker_name):
        formatted_ticker_name = ticker_name.split('/')
        formatted_ticker_name = (f'{formatted_ticker_name[0]}'
            f'{formatted_ticker_name[1]}').lower()
        ticker = self.ze.ticker(formatted_ticker_name)
        return {'symbol': ticker_name, 
                'timestamp': ticker['at'], 
                'datetime': self.epoch_to_str(ticker['at']), 
                'high': float(ticker['high']), 
                'low': float(ticker['low']), 
                'bid': float(ticker['sell']), 
                'bidVolume': None, 
                'ask': float(ticker['buy']), 
                'askVolume': None, 
                'vwap': None, 
                'open': float(ticker['visualOpen']), 
                'close': None,
                'last': float(ticker['last']), 
                'previousClose': None, 
                'change': float(ticker['change']), 
                'percentage': float(ticker['percent']), 
                'average': None, 
                'baseVolume': float(ticker['volume']), 
                'quoteVolume': None, 
                'info': {'id': 229, 
                         'last': ticker['last'], 
                         'lowestAsk': ticker['sell'], 
                         'highestBid': ticker['buy'], 
                         'percentChange': ticker['percent'], 
                         'baseVolume': ticker['volume'], 
                         'quoteVolume': None, 
                         'isFrozen': '0', 
                         'high24hr': None, 
                         'low24hr': None}}

    def fetch_trades(self, market):
        history = self.ze.trade_history('', '2018-04-01',
            (date.today() + timedelta(days=1)).isoformat(), 1, 1000)
        my_trades = []
        for item in history['items']:
            market_name = f"{item['baseCurrency']}/{item['quoteCurrency']}"
            if market:
                if market_name == market:
                    my_trades.append(self.trade_formatted(item, market_name))
        return my_trades

    def trade_formatted(self, trade, market_name):
        return {'info': {'globalTradeID': None,
                         'tradeID': None,
                         'date': trade['createdAt'],
                         'rate': trade['price'],
                         'amount': trade['baseAmount'],
                         'total': trade['quoteAmount'],
                         'fee': '0.00150000',
                         'orderNumber': None,
                         'type': trade['side'],
                         'category': 'exchange'},
                'timestamp': self.str_to_epoch(trade['createdAt']),
                'datetime': trade['createdAt'] + '.000Z',
                'symbol': market_name,
                'id': None,
                'order': None,
                'type': None,
                'side': trade['side'],
                'price': float(trade['price']),
                'amount': float(trade['baseAmount']),
                'cost':  float(trade['quoteAmount']),
                'fee': {'type': None,
                        'rate': 0.0015,
                        'cost': float(self.calcultate_paid_fees(
                            trade['quoteAmount'])),
                        'currency': trade['quoteCurrency']}}

    def create_limit_buy_order(self, symbol, amount, price):
        symbol = symbol.lower().split('/')
        return self.ze.new_order(symbol[0], symbol[1], 'bid', price, amount,
            f'{symbol[0]}{symbol[1]}', 'limit')

    def create_limit_sell_order(self, symbol, amount, price):
        symbol = symbol.lower().split('/')
        return self.ze.new_order(symbol[0], symbol[1], 'ask', price, amount,
            f'{symbol[0]}{symbol[1]}', 'limit')

    def cancel_order(self, order_id):
        return self.ze.cancel_order(int(order_id))

    def str_to_epoch(self, date_string):
        return int(str(time.mktime(datetime.strptime(date_string,
            '%Y-%m-%d %H:%M:%S').timetuple())).split('.')[0] + '000')

    def epoch_to_str(self, epoch):
        return datetime.fromtimestamp(epoch).isoformat() + '.000Z'

    def calculate_filled_cost(self, amt_filled, price):
        return (Decimal(amt_filled) * Decimal(price) * (Decimal('1') -\
            self.fees).quantize(Decimal('.00000001'), rounding=ROUND_HALF_EVEN))
    
    def calcultate_paid_fees(self, amt_filled):
        return (Decimal(amt_filled) * self.fees).quantize(Decimal('.00000001'),
                                                      rounding=ROUND_HALF_EVEN)


    # """ START - IT'S SHITTY BUT IT REQUIRED ONLY FOR CURRENT TEST FROM test.py - START """
    #
    # def cancel_order_smart(self, order_id, price, timestamp, side):
    #     """Cancel an order with it's id.
    #     Retry 1000 times, send an email each 10 tries.
    #     Warning : Not connard proofed!
    #     order_id: string, marketplace order id.
    #     price: string, price of the order.
    #     timestamp: int, timestamp of the order.
    #     side: string, buy or sell.
    #     return: boolean, True if the order is canceled correctly, False when the
    #     order have been filled before it's cancellation"""
    #     cancel_side = 'cancel_buy' if side == 'buy' else 'cancel_sell'
    #     try:
    #         rsp = self.cancel_order(order_id)
    #         if rsp:
    #             self.order_logger_formatter(cancel_side, order_id, price, 0)
    #             return True
    #         else:
    #             return rsp
    #     except Exception as e:
    #         time.sleep(0.5)
    #         orders = self.get_orders(self.config.selected_market)[side]
    #         is_open = self.does_an_order_is_open(price, orders)
    #         if is_open:
    #             rsp = self.exchange.cancel_order(order_id)
    #             if rsp:
    #                 self.err_counter = 0
    #                 return rsp
    #         trades = self.get_user_history(self.config.selected_market)[side]
    #         is_traded = self.order_in_history(price, trades, side, timestamp)
    #         if is_traded:
    #             msg = (
    #                 f'The {side} {order_id} have been filled '
    #                 f'before being canceled'
    #             )
    #             self.config.stratlog.warning(msg)
    #             return False
    #         else:
    #             self.order_logger_formatter(cancel_side, order_id, price, 0)
    #             return True
    #
    # def cancel_all(self, open_orders):
    #     if open_orders['buy']:
    #         for item in open_orders['buy']:
    #             self.cancel_order_smart(item[0], item[1], item[4], 'buy')
    #     if open_orders['sell']:
    #         for item in open_orders['sell']:
    #             self.cancel_order_smart(item[0], item[1], item[4], 'sell')
    #
    # def order_logger_formatter(self, side, order_id, price, amount):
    #     """Format into a string an order for the logger
    #     side : string. buy, cancel_buy, sell or cancel_sell
    #     order_id: string, order id on the marketplace.
    #     price: Decimal.
    #     amount: Decimal.
    #     return: tuple with strings."""
    #     timestamp = self.timestamp_formater()
    #     date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    #     return timestamp, date_time
    #
    # """END IT'S SHITTY BUT IT REQUIRED FOR CURRENT TEST FROM test.py END"""
