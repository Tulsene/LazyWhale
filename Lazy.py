#!/usr/bin/env python
# -*- coding: utf-8 -*-
# market making script for lazy whale  market maker
# if you don't get it, don't use it

import poloniex
import time
import urllib2
from decimal import *
api_key = ''
api_secret = ''
poloniex = poloniex.Poloniex(api_key, api_secret)

class Lazy:

    getcontext().prec = 8

    def __init__(self):
        self.currency_pair = ''
        self.buy_pair = ''
        self.sell_pair = ''
        self.amount = Decimal('1.00000000')
        self.increment = Decimal('0.00001000')
        self.orders = []
        self.buy_orders = []
        self.buy_orders_temp = []
        self.new_buy_orders = []
        self.temp_buy_orders = []
        self.buy_price_min = Decimal('0.00100')
        self.buy_price_max = Decimal('0.00196')
        self.sell_orders = []
        self.sell_orders_temp = []
        self.new_sell_orders = []
        self.temp_sell_orders = []
        self.sell_price_min = Decimal('0.00207')
        self.sell_price_max = Decimal('0.00225')
        self.nb_orders_to_display = Decimal('1')

    def api_sleep(self):
        """Sleeping function, call it to make a break in the code execution.
        """
        time.sleep(7)

    def get_balance(self):
        """Get the user account balance.

        Get the buy pair balance.
        Get the sell pair balance.
        Return the balance of the buy and sell pair.
        """
        try:
            self.buy_balance = poloniex.returnBalances()[self.buy_pair]
            self.sell_balance = poloniex.returnBalances()[self.sell_pair]
        except urllib2.HTTPError as e:
            print e.code
            self.api.sleep()
            self.get_balance()
        except urllib2.URLError as e:
            print e.args
            self.api.sleep()
            self.get_balance()

    def get_orders(self):
        """Get the user actives orders.

        Get the balance from the marketplace.
        Call the function fetch_orders to organize the user buy and sell order book.
        Return new_buy_orders and new_sell_orders.
        """
        try:
            self.orders = poloniex.returnOpenOrders(self.currency_pair)
            self.orders = self.fetch_orders(self.orders)
        except urllib2.HTTPError as e:
            print e.code
            self.api.sleep()
            self.get_orders()
        except urllib2.URLError as e:
            print e.args
            self.api.sleep()
            self.get_orders()

    def fetch_orders(self, orders):
        """Fetch buy and sell orders from self.orders.
        
        Fetch self.new_buy_orders, self.new_sell_orders.
        """
        self.new_buy_orders = []
        self.new_sell_orders = []
        for item in orders:
            order_number = int(item['orderNumber'])
            order_type = str(item['type'])
            order_rate = Decimal(item['rate'])
            order_amount = Decimal(item['amount'])
            if order_type == 'buy':
                self.new_buy_orders.append([order_number, order_amount, order_rate])
            if order_type == 'sell':
                self.new_sell_orders.append([order_number, order_amount, order_rate])

    def set_sell_order(self, currency_pair, rate, amount):
        """Set sell order.

        Catch response, display result.
        Return result.
        """
        try:
            result = poloniex.sell(currency_pair, rate, amount)
            result = int(result['orderNumber'])
            result = [result, amount, rate]
            print time.strftime('%X'), 'Sell : ',  amount , ' ' , self.sell_pair , \
                ' at ' , rate
            return result
        except urllib2.HTTPError as e:
            print e.code
            self.retry_set_sell_order(currency_pair, rate, amount)
        except urllib2.URLError as e:
            print e.args
            self.retry_set_sell_order(currency_pair, rate, amount)

    def retry_set_sell_order(self, currency_pair, rate, amount):
        self.api_sleep()
        self.get_orders()
        for item in self.new_sell_orders:
            if rate in item:
                sell_order = True
        if sell_orders == False:
            self.set_sell_order(currency_pair, rate, amount)

    def set_several_sell_orders(self, currency_pair, price_start, amount, nb_orders):
        """Call i times set_sell_order()."""
        while nb_orders > 0:
             order = self.set_sell_order(currency_pair, price_start, amount)
             self.sell_orders.append(order)
             price_start += self.increment
             nb_orders -= 1

    def set_buy_order(self, currency_pair,rate, amount):
        """Set buy order.

        Catch response, display result.
        Return result.
        """
        try:
            result = poloniex.buy(self.currency_pair, rate, amount)
            result = int(result['orderNumber'])
            result = [result, amount, rate]
            print time.strftime('%X'), 'Buy : ' ,  amount , ' ' , self.sell_pair , \
                ' at ' , rate
            return result
        except urllib2.HTTPError as e:
            print e.code
            self.retry_set_buy_order(currency_pair, rate, amount)
        except urllib2.URLError as e:
            print e.args
            self.retry_set_buy_order(currency_pair, rate, amount)

    def retry_set_buy_order(self, currency_pair, rate, amount):
        self.api_sleep()
        self.get_orders()
        for item in self.new_buy_orders:
            if rate in item:
                buy_order = True
        if buy_orders == False:
            self.set_buy_order(currency_pair, rate, amount)

    def set_several_buy_orders(self, currency_pair, price_start, amount, nb_orders):
        """Call i times set_buy_order()."""
        while nb_orders > 0:
            order = self.set_buy_order(currency_pair, price_start, amount)
            self.buy_orders.insert(0, order)
            price_start -= self.increment
            nb_orders -= 1

    def cancel_order(self, currency_pair, order_number):
        """Cancell order_number order."""
        try:
            result_cancel = poloniex.cancel(self.currency_pair, order_number)
            return result_cancel
        except urllib2.HTTPError as e:
            print e.code
            self.api.sleep()
            self.get_balance()
            for item in self.orders:
                if order_number in item:
                    order = True
            if order == True:
                cancel_order(currency_pair, order_number)
        except urllib2.URLError as e:
            print e.args
            self.api.sleep()
            self.get_balance()
            for item in self.orders:
                if order_number in item:
                    order = True
            if order == True:
                cancel_order(currency_pair, order_number)

    def cancel_all(self):
        """Cancel all actives orders."""
        self.get_orders()
        for item in self.new_buy_orders:
            self.cancel_order(self.currency_pair, item[0])
            print time.strftime('%X'), 'BUY canceled :', item
        for item in self.new_sell_orders:
            self.cancel_order(self.currency_pair, item[0])
            print time.strftime('%X'), 'SELL canceled :', item

    def update_sell_orders(self):
        """Update user orders after a buy occured.

        remove item from buy_orders.
        add item to sell_orders.
        """
        #print time.strftime('%X'), 'self.temp_sell_orders', self.temp_sell_orders, \
        #    'buy_orders_temp', self.buy_orders_temp
        # remove from buy_orders item in buy_orers_temps
        for item in self.buy_orders_temp:
            if item in self.buy_orders:
                self.buy_orders.remove(item)
        #add self.temp_sell_orders to sell_orders
        i = 0
        for item in self.temp_sell_orders:
            self.sell_orders.insert(i, item)
            i += 1

    def update_buy_orders(self):
        """Update user orders after a buy occured.

        remove item from sell_orders.
        add item to buy_orders.
        """
        #print time.strftime('%X'), 'temp_buy_orders', self.temp_buy_orders, \
        #    'sell_orders_temp', self.sell_orders_temp
        # remove from sell_orders item in sell_orders_temp
        for item in self.sell_orders_temp:
            if item in self.sell_orders:
                self.sell_orders.remove(item)
        # add temp_buy_orders to buy_orders
        for item in self.temp_buy_orders:
            self.buy_orders.append(item)

    def limit_nb_orders_displayed(self):
        """Limit the number of orders displayed in the order book.

        Check if there is not too much sell order, and remove some if necessary.
        Check if there is enough sell order, and add some if necessary.
        Do the same for buy orders.
        """
        self.get_orders()
        sell_orders2 = self.new_sell_orders[:]
        buy_orders2 = self.new_buy_orders[:]
        # check sell orders
        print 'self.sell_orders[-1][2]', self.sell_orders[-1][2], \
            'sell_orders2[0][2]', sell_orders2[0][2]
        if self.sell_orders[-1][2] - sell_orders2[0][2] \
            > self.increment * self.nb_orders_to_display:
            i = int((self.sell_orders[-1][2] - (sell_orders2[0][2] \
                + self.increment * self.nb_orders_to_display)) / self.increment)
            print 'i :', i
            while i > 0:
                order = []
                self.cancel_order(self.currency_pair, self.sell_orders[-1][0])
                print time.strftime('%X'), 'SELL canceled :', self.sell_orders[-1]
                for item in self.sell_orders[-1]:
                    order.append(item)
                sell_orders2.remove(order)
                self.sell_orders.remove(order)
                i -= 1
        elif self.sell_orders[-1][2] - sell_orders2[0][2] \
            < self.increment * self.nb_orders_to_display:
            if self.sell_orders[-1][2] + self.nb_orders_to_display \
                * self.increment < self.sell_price_max:
                i = int( self.nb_orders_to_display - (self.sell_orders[-1][2] \
                    - sell_orders2[0][2]) / self.increment)
            elif self.sell_orders[-1][2] + self.nb_orders_to_display \
                * self.increment >= self.sell_price_max:
                i = int((self.sell_price_max - self.sell_orders[-1][2]) \
                    / self.increment)
                print 'sel price max almost reached'
            price_start = self.sell_orders[-1][2] + self.increment
            print 'nb of sell orders to put : i =', i, 'from :', price_start
            self.set_several_sell_orders(self.currency_pair, price_start, self.amount, i)
        else:
            print 'orders ok'
        # check buy orders
        print 'buy_orders2[-1][2]', buy_orders2[-1][2], \
            'self.buy_orders[0][2]', self.buy_orders[0][2]
        if buy_orders2[-1][2] - self.buy_orders[0][2] \
            > self.increment * self.nb_orders_to_display:
            i = int((buy_orders2[-1][2] - (self.buy_orders[0][2] \
                + self.increment * self.nb_orders_to_display)) / self.increment)
            print 'i', i
            while i > 0:
                order = []
                self.cancel_order(self.currency_pair, self.buy_orders[0][0])
                print time.strftime('%X'), 'BUY canceled :', self.buy_orders[0]
                for item in self.buy_orders[0]:
                    order.append(item)
                buy_orders2.remove(order)
                self.buy_orders.remove(order)
                i -= 1
        elif buy_orders2[-1][2] - self.buy_orders[0][0] \
            < self.increment * self.nb_orders_to_display:
            if self.buy_orders[0][0] - self.nb_orders_to_display \
                * self.increment > self.buy_price_min:
                i = int(self.nb_orders_to_display - (buy_orders2[-1][2] \
                    - self.buy_orders[0][2]) / self.increment)
            elif self.buy_orders[0][0] - self.nb_orders_to_display \
                * self.increment <= self.buy_price_min:
                i = int((self.buy_orders[0][0] - self.buy_price_min) \
                    / self.increment)
                print 'buy_price_min almost reached'
            price_start = self.buy_orders[0][2] - self.increment
            print 'nb of buy orders to put : i =', i, 'from :', price_start
            self.set_several_buy_orders(self.currency_pair, price_start, self.amount, i)
        else:
            print 'buy orders ok'

    def compare_orders(self):
        """Compare between user actives orders and actives orders from the marketplace.

        Check if there is more than 0 actives sell then buy orders on the marketplace. 
        Put some if needed and update orders, orders2, orders_temp.
        Compare between user actives sell orders and actives sell orders from the marketplace.
        Set the number of buy order to do.
        Set the price from where buy will sart.
        Regroup sell order to remove from user active sell orders in sell_orders_temp.
        But buy orders, update user buy orders book
        Do the same for buy orders.
        If buy or sell occured update user order book
        Call limit_nb_orders_displayed() to limit the number of order displayed \
        in the marketplace order book"""
        i = 0
        sell_orders2, buy_orders2 = [], []
        self.temp_buy_orders, self.temp_sell_orders = [], []
        self.buy_orders_temp, self.sell_orders_temp = [], []
        self.buy_orders_temp = self.buy_orders[:]
        self.sell_orders_temp = self.sell_orders[:]
        # get active orders : update sell_orders2 & buy_orders2
        self.get_orders()
        sell_orders2 = self.new_sell_orders[:]
        buy_orders2 = self.new_buy_orders[:]
        #print time.strftime('%X'), 'sell orders :', self.sell_orders, '\n', \
        #    'sell_orders2 :', sell_orders2
        if sell_orders2 == []:
            price_start = self.sell_orders[-1][2] + self.increment
            i = int(self.nb_orders_to_display)
            self.set_several_sell_orders(self.currency_pair, price_start, self.amount, i)
            self.get_orders()
            sell_orders2 = self.new_sell_orders[:]
            self.sell_orders_temp = self.sell_orders[:]
        if buy_orders2 == []:
            price_start = self.buy_orders[0][2] - self.increment
            i = int(self.nb_orders_to_display)
            self.set_several_buy_orders(self.currency_pair, price_start, self.amount, i)
            self.get_orders()
            buy_orders2 = self.new_buy_orders[:]
            self.buy_orders_temp = self.buy_orders[:]
        # check if a sell occured 
        if sell_orders2[0][0] != self.sell_orders[0][0]:
            print 'a sell has occured'
            # set the new buy price_start to target
            i = len(self.sell_orders) - len(sell_orders2)
            price_start = buy_orders2[-1][2] + self.increment
            # check wich item in sell_orders need to be removed and store it 
            # in sell_orders_temp
            for item in self.sell_orders:
                if item in sell_orders2:
                    self.sell_orders_temp.remove(item)
            # put buy orders
            #print 'i :', i , 'price_start :', price_start
            while i > 0:
                order = self.set_buy_order(self.currency_pair, price_start, self.amount)
                self.temp_buy_orders.append(order)
                #print 'temp_buy_orders :', self.temp_buy_orders
                i -= 1
                price_start += self.increment
        # check if a buy occured
        #print time.strftime('%X'), 'buy orders :', self.buy_orders, '\n', \
        #    'buy_orders2 :', buy_orders2
        if buy_orders2[-1][0] != self.buy_orders[-1][0]:
            print 'a buy has occured'
            # set the new sell price_start to target
            i = len(self.buy_orders) - len(buy_orders2)
            price_start = sell_orders2[0][2] - self.increment
            # check wich item in buy_orders need to be removed and store it in buy_orders_temp
            for item in self.buy_orders:
                if item in buy_orders2:
                    self.buy_orders_temp.remove(item)
            # put sell orders
            #print 'i :', i, 'price_start :', price_start
            while i > 0:
                order = self.set_sell_order(self.currency_pair, price_start, self.amount)
                self.temp_sell_orders.insert(0, order)
                #print 'temp_sell_orders :', self.temp_sell_orders
                i -= 1
                price_start -= self.increment
        # if a sell order occured
        if self.temp_sell_orders != []:
            self.update_sell_orders()
        # if a buy order occured
        if self.temp_buy_orders != []:
            self.update_buy_orders()
        self.limit_nb_orders_displayed()
        #print time.strftime('%X'), 'end sell_orders', self.sell_orders, '\n', \
        #    'end sell_orders2', sell_orders2
        #print time.strftime('%X'), 'end buy_orders', self.buy_orders, '\n', \
        #    'end buy_orders2', buy_orders2

    def set_orders(self):
        """Sort orders at the apps init.

        Check if user sell book on the marketplace is empty.
        Set the number of sell order to do.
        If it's not empty set the number of sell to do and set sell_orders.
        If no need of new sell orders, set sell_orders.
        Put sell orders if needed.
        Do the same for buy orders."""
        # Get actives orders from marketplace
        self.get_orders()
        sell_orders2 = self.new_sell_orders[:]
        buy_orders2 = self.new_buy_orders[:]
        # Set nb of sell order to put
        i = 0
        if sell_orders2 == []:
            print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                'no active sell orders'
            if (self.sell_price_max - self.sell_price_min) / self.increment \
                > self.nb_orders_to_display:
                i = int(self.nb_orders_to_display)
            else:
                i = int((self.sell_price_max - self.sell_price_min) / self.increment)
        elif sell_orders2[0][2] != self.sell_price_min:
            print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                'Add sell orders from', sell_orders2[0][2], 'to', self.sell_price_min
            i = int((sell_orders2[0][2] - self.sell_price_min) / self.increment)
            self.sell_orders = sell_orders2[:]
        else:
            print 'Sell orders already set'
            self.sell_orders = sell_orders2[:]
        if i != 0:
            price_start = self.sell_price_min
            self.set_several_sell_orders(self.currency_pair, price_start, \
                self.amount, i)
        # Set nb of buy order to put
        i = 0
        if buy_orders2 == []:
            print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                'No active buy orders'
            if (self.buy_price_max - self.buy_price_min) / self.increment \
                > self.nb_orders_to_display:
                i = int(self.nb_orders_to_display)
            else:
                i = int((self.buy_price_max - self.buy_price_min) / self.increment)
        elif buy_orders2[-1][2] != self.buy_price_max:
            print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                'Add sell orders from', buy_orders2[-1][2], 'to', self.buy_price_max
            i = int((buy_orders2[-1][2] - self.buy_price_max) / self.increment)
            self.buy_orders = buy_orders2[:]
        else:
            print 'Sell orders already set'
            self.buy_orders = buy_orders2[:]
        if i != 0:
            price_start = self.buy_price_max
            self.set_several_buy_orders(self.currency_pair, price_start, \
                self.amount, i)

    def strat(self):
        """Simple execution loop."""
        while True:
            print time.strftime('%x'), time.strftime('%X'), 'CYCLE START'
            self.compare_orders()
            print time.strftime('%x'), time.strftime('%X'), 'CYCLE STOP'
            self.api_sleep()

lazy = Lazy()

lazy.cancel_all()

lazy.set_orders()
lazy.strat()
