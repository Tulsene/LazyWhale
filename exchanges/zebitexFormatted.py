from exchanges.zebitex import Zebitex, ZebitexError
from decimal import Decimal, ROUND_HALF_EVEN
from datetime import datetime, date, timedelta
import time
from utils.converters import multiplier

class ZebitexFormatted:
    """"Zebittex api formatter to get almost same outputs as ccxt."""

    def __init__(self, access_key=None, secret_key=None, is_staging=False):
        self.ze = Zebitex(access_key, secret_key, is_staging)
        self.fees = Decimal('0.0015')
        self.symbols = self.load_markets()
    
    def fetch_balance(self):
        """balance = {'COIN': {'isFiat': bool,
            'depositFee': int,
            'code': 'COIN',
            'title': 'commercialName',
            'paymentAddress': '',
            'balance': '0.000',
            'lockedBalance': '0.00',
            'paymentAddressQrCode': '/uploads/payment_address/qr_code_file/630/',
            'bankAccounts': [],
            'isDisabled': bool}, ...}"""
        balance = self.ze.funds()
        fetched_balance = {}
        for key, value in balance.items():
            balance = Decimal(value['balance'])
            locked = Decimal(value['lockedBalance'])
            if balance == Decimal('0') or balance == Decimal('1E-8'):
                value['balance'] = '0.0'
            
            if locked == Decimal('0') or locked == Decimal('1E-8'):
                value['lockedBalance'] = '0.0'
            
            fetched_balance.update(
                {key: {'free': value['balance'],
                       'used': value ['lockedBalance'],
                       'total': str(balance + locked)}})
        
        return fetched_balance

    def fetch_open_orders(self, market=None):
        open_orders = self.ze.open_orders('1', '1000')
        fetched_open_order = []
        for order in open_orders:
            market_name = self.from_zebitex_market_name(order['base'], order['quote'])
            if market:
                if market_name == market:
                    fetched_open_order.append(self.order_formatted(order, market_name))
            else:
                fetched_open_order.append(self.order_formatted(order, market_name))
        return fetched_open_order

    def order_formatted(self, order, market):
        """fetch_open_orders == [{'id': '',
            'side': str,
            'price': '0.xxxxxxxxx',
            'total': '0.x',
            'base': 'xxx',
            'quote': 'zzz',
            'amount': 'yy.yyyyyyyy',
            'filled': 'y.yyyyyyyy',
            'type': 'limit',
            'timestamp': '1590471283'}, ...]"""
        date = self.epoch_to_str(int(order['timestamp']))
        side = 'buy' if order['side'] == 'bid' else 'sell'
        return {'id': str(order['id']),
                'timestamp': order['timestamp'],
                'datetime': date,
                'lastTradeTimestamp': None,
                'status': 'open',
                'symbol': market,
                'type': order['type'],
                'side': side,
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
        """Dumb version"""
        symbols = []
        tickers = self.ze.tickers()
        for ticker in tickers.keys():
            symbols.append(self.from_zebitex_market_name(tickers[ticker]['base'], tickers[ticker]['quote']))
        return symbols

    def fetch_ticker(self, market):
        ticker = self.ze.ticker(self.from_ccxt_market_name(market))
        return self.format_ticker(ticker, market)

    def format_ticker(self, ticker, market):
        """{'base': 'xxx',
            'quote': 'zzz',
            'at': 1590563313,
            'low': '0.10000000',
            'high': '0.10000000',
            'last': '0.10000000',
            'open': '0.00000000',
            'volume': '0.00066670',
            'isUpTrend': '1',
            'percent': '0.00000000',
            'change': '0.10000000'}"""
        return {'symbol': market, 
                'timestamp': ticker['at'], 
                'datetime': self.epoch_to_str(ticker['at']), 
                'high': float(ticker['high']), 
                'low': float(ticker['low']), 
                'bid': None, 
                'bidVolume': None, 
                'ask': None, 
                'askVolume': None, 
                'vwap': None, 
                'open': float(ticker['open']), 
                'close': None,
                'last': float(ticker['last']), 
                'previousClose': None, 
                'change': float(ticker['change']), 
                'percentage': float(ticker['percent']), 
                'average': None, 
                'baseVolume': float(ticker['volume']), 
                'quoteVolume': None}

    def fetch_trades(self, market=None):
        """{'items': [...], 'per': 20, 'nextCursor': XXXXXX}"""
        history = self.ze.trade_history('', '', '', '', 20)
        my_trades = []
        for trade in history['items']:
            market_name = self.from_zebitex_market_name(trade['baseCurrency'], trade['quoteCurrency'])
            if market and market_name != market:
                continue
        
            my_trades.append(self.trade_formatted(trade, market_name))
        
        return my_trades

    def trade_formatted(self, trade, market_name):
        """{'id': int,
        'createdAt': '',
        'baseCurrency': 'BTC',
        'quoteCurrency': 'EUR',
        'side': 'buy',
        'price': '6365.00',
        'baseAmount': '0.13956352',
        'quoteAmount': '888.32'}"""
        return {'timestamp': self.str_to_epoch(trade['createdAt']),
                'datetime': trade['createdAt'] + '.000Z',
                'symbol': market_name,
                'id': str(trade['id']),
                'order': trade['id'],
                'type': 'limit',
                'side': trade['side'],
                'price': float(trade['price']),
                'amount': float(trade['baseAmount']),
                'cost':  float(trade['quoteAmount']),
                'fee': {'type': None,
                        'rate': 0.0015,
                        'cost': float(self.calcultate_paid_fees(
                            trade['quoteAmount'])),
                        'currency': trade['quoteCurrency']}}

    def from_ccxt_market_name(self, market):
        market = market.split('/')
        return (f'{market[0]}{market[1]}').lower()

    def from_zebitex_market_name(self, base_name, quote_name):
        return f"{base_name}/{quote_name}".upper()

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

    def cancel_all_orders(self):
        return self.ze.cancel_all_orders()

    def str_to_epoch(self, date_string):
        return int(str(time.mktime(datetime.strptime(date_string,
            '%Y-%m-%d %H:%M:%S').timetuple())).split('.')[0] + '000')

    def epoch_to_str(self, epoch):
        return datetime.fromtimestamp(epoch).isoformat() + '.000Z'

    def calculate_filled_cost(self, amt_filled, price):
        return multiplier(Decimal(amt_filled), Decimal(price), 
                         ((Decimal('1') - self.fees)))
    
    def calcultate_paid_fees(self, amt_filled):
        return multiplier(Decimal(amt_filled), self.fees)

