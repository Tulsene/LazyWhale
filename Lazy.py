#!/usr/bin/env python
# -*- coding: utf-8 -*-
# market making script for lazy whale  market maker
# if you don't get it, don't use it

import apiInterface
import time
from decimal import *

class Lazy:

    getcontext().prec = 8

    def __init__(self):
        self.buy_orders = []
        self.sell_orders = []
        self.currency_pair = 'BTC_SDC'
        self.buy_pair = 'BTC'
        self.sell_pair = 'SDC'
        self.amount = Decimal('1.00000000')
        self.increment = Decimal('0.00001000')
        self.buy_price_min = Decimal('0.00148')
        self.buy_price_max = Decimal('0.00150')
        self.sell_price_min = Decimal('0.00161')
        self.sell_price_max = Decimal('0.00163')
        self.nb_orders_to_display = Decimal('2')

    def compare_orders(self):
        """Compare between LW actives orders and actives orders from the marketplace.

        Call check_if_no_orders().
        Clear ..._orders_executed, assign new_..._orders and ..._orders_missing.
        Compare between 1st LW actives sell orders and actives sell orders from the marketplace.
        Select sell_orders_missing.
        Set the price from where buy will sart.
        Set the numbre of buy if if self.buy_orders[-1][0] == 0:
        Set the number of buy order to do (i) but not exceed buy_price_min.
        For i orders, put order, update user buy orders book, decrement i, increment price.
        Do the oposite compare for buy orders.
        If buy or sell occured update user order book.
        Call limit_nb_orders_displayed().
        """
        new_buy_orders, new_sell_orders = self.check_if_no_orders()
        buy_orders_executed, sell_orders_executed = [], []
        buy_orders_missing = self.buy_orders[:]
        sell_orders_missing = self.sell_orders[:]
        
        print time.strftime('%X'), 'sell orders :', self.sell_orders, '\n', \
            'new_sell_orders :', new_sell_orders

        if new_sell_orders[0][0] != self.sell_orders[0][0]:
            print 'a sell has occured'

            for item in self.sell_orders:
                if item in new_sell_orders:
                    sell_orders_missing.remove(item)

            price_start = new_buy_orders[-1][2] + self.increment
            if price_start - self.increment * self.nb_orders_to_display \
                <= self.buy_price_min:
                
                if self.buy_orders[-1][0] == 0:
                    i = int((self.sell_orders[0][2] - new_sell_orders[0][2]) \
                        / self.increment)
                
                else:
                    i = int((price_start - self.buy_price_min) / self.increment)

            else:
                if new_sell_orders[0][0] == 0:
                    i = len(self.sell_orders) - len(new_sell_orders) +1

                else:
                    i = len(self.sell_orders) - len(new_sell_orders)
            
            print 'compare_orders() sell i :', i , 'price_start :', price_start

            while i > 0:
                order = api.set_buy_order(self.currency_pair, price_start, self.amount)
                print 'buy order added : ', order
                buy_orders_executed.append(order)
                #print 'buy_orders_executed :', self.buy_orders_executed
                i -= 1
                price_start += self.increment

        print time.strftime('%X'), 'buy orders :', self.buy_orders, '\n', \
            'new_buy_orders :', new_buy_orders

        # check if a buy occured
        if new_buy_orders[-1][0] != self.buy_orders[-1][0]:
            print 'a buy has occured'

            for item in self.buy_orders:
                if item in new_buy_orders:
                    buy_orders_missing.remove(item)

            price_start = new_sell_orders[0][2] - self.increment
            if price_start + self.increment * self.nb_orders_to_display \
                >= self.sell_price_max:
                
                if self.sell_orders[0][0] == 0:
                    i = int((self.buy_orders[-1][2] - new_buy_orders[-1][2]) / self.increment)
                
                else:
                    i = int((self.sell_price_max - price_start) / self.increment)
            
            else:
                if new_buy_orders[0][0] == 0:
                    i = len(self.buy_orders) - len(new_buy_orders) + 1

                else:
                    i = len(self.buy_orders) - len(new_buy_orders)
            
            print 'compare_orders() buy i :', i, 'price_start :', price_start

            while i > 0:
                order = api.set_sell_order(self.currency_pair, price_start, self.amount)
                print 'sell order added : ', order
                sell_orders_executed.insert(0, order)
                i -= 1
                price_start -= self.increment

        if sell_orders_executed != []:
            self.update_sell_orders(buy_orders_missing, sell_orders_executed)
        
        if buy_orders_executed != []:
            self.update_buy_orders(sell_orders_missing, buy_orders_executed)
        
        self.limit_nb_orders_displayed()
        
        #print time.strftime('%X'), 'end sell_orders', self.sell_orders, '\n', \
        #    'end new_sell_orders', new_sell_orders
        #print time.strftime('%X'), 'end buy_orders', self.buy_orders, '\n', \
        #    'end new_buy_orders', new_buy_orders

    def check_if_no_orders(self):
        """Put orders if there is no user orders active on the marketplace.

        Set new_buy_orders, new_sell_orders by calling get_orders(self.currency_pair).
        Assign [] to ..._orders_executed
        Check if new_sell_orders is empty
        If the sell max limit is already reached fill new_sell_orders to avoid errors
        If the sell max limit became reached fill new_sell_orders
        Set the number of sell order to do but less than sell_price_max & nb_orders_to_display.
        Call set_several_sell_orders().
        Fetch sell_orders.
        Do the same for new_buy_orders.
        """
        print 'check_if_no_orders(self):'
        new_buy_orders, new_sell_orders = api.get_orders(self.currency_pair)
        sell_orders_executed, buy_orders_executed = [], []

        if new_sell_orders == []:
            price_start = self.sell_orders[-1][2] + self.increment
            print 'new_sell_orders == [], price_start = ', price_start

            if self.sell_orders[0][0] == 0:
                new_sell_orders = self.sell_orders[:]

            elif price_start > self.sell_price_max:
                new_sell_orders.append([0, Decimal('0'), price_start])

            else:
                if price_start + self.increment * self.nb_orders_to_display \
                    <= self.sell_price_max:
                    
                    i = int(self.nb_orders_to_display - ((price_start - \
                        self.sell_orders[0][2]) / semf.increment))
                
                if price_start + self.increment * self.nb_orders_to_display \
                    > self.sell_price_max:
                    
                    i = int((self.sell_price_max - price_start) / self.increment) + 1
               
                print 'There is ', i, 'sell orders to add from ', price_start
                sell_orders_executed += api.set_several_sell_orders(self.currency_pair, \
                    price_start, self.amount, i, self.increment)

                for item in sell_orders_executed:
                    self.sell_orders.append(item)
                    new_sell_orders.append(item)

        if new_buy_orders == []:
            price_start = self.buy_orders[0][2] - self.increment
            print 'new_buy_orders == [], price_start', price_start
            
            if self.buy_orders[-1][0] == 0:
                new_buy_orders = self.buy_orders[:]
            
            elif price_start < self.buy_price_min:
                new_buy_orders.append([0, Decimal('0'), price_start])
            
            else:
                if price_start - self.increment * self.nb_orders_to_display \
                    >= self.buy_price_min:
                
                    i = int(self.nb_orders_to_display - ((self.buy_orders[0][2] - \
                        price_start) / self.increment))
               
                elif price_start - self.increment * self.nb_orders_to_display \
                    < self.buy_price_min:
                
                    i = int((price_start - self.buy_price_min) / self.increment) + 1
                
                print 'There is ', i, 'buy orders to add from', price_start
                buy_orders_executed += api.set_several_buy_orders(self.currency_pair, \
                    price_start, self.amount, i, self.increment)

                for item in buy_orders_executed:
                    self.buy_orders.append(item)
                    new_buy_orders.append(item)

        return new_buy_orders, new_sell_orders
    
    def update_sell_orders(self, buy_orders_missing, sell_orders_executed):
        """Update user orders after a buy occured.

        Remove missing orders from buy_orders.
        Add executed orders to sell_orders.
        """
        print 'update_sell_orders(self):'
        #print time.strftime('%X'), 'self.sell_orders_executed', self.sell_orders_executed, \
        #    'buy_orders_missing', self.buy_orders_missing

        # remove from buy_orders item in buy_orers_temps
        for item in buy_orders_missing:
            if item in self.buy_orders:
                self.buy_orders.remove(item)

        #add self.sell_orders_executed to sell_orders
        i = 0
        for item in sell_orders_executed:
            self.sell_orders.insert(i, item)
            i += 1

    def update_buy_orders(self, sell_orders_missing, buy_orders_executed):
        """Update user orders after a buy occured.

        Remove missing orders from sell_orders.
        Add executed orders to buy_orders.
        """
        print 'update_buy_orders(self):'
        #print time.strftime('%X'), 'buy_orders_executed', self.buy_orders_executed, \
        #    'sell_orders_missing', self.sell_orders_missing
        
        # remove from sell_orders item in sell_orders_missing
        for item in sell_orders_missing:
            if item in self.sell_orders:
                self.sell_orders.remove(item)
        
        # add buy_orders_executed to buy_orders
        for item in buy_orders_executed:
            self.buy_orders.append(item)

    def limit_nb_orders_displayed(self):
        """Limit the number of orders displayed in the order book.

        Assign new_..._orders by calling get_orders(self.currency_pair).
        Check if sell_orders is empty and put arbitrary data format : 
            [0, Decimal('0'), self.sell_price_max + self.increment]).
        Or pass if sell_orders [0][0] == 0.
        Otherwise check if no sell order happend during the cycle, if so pass
        Assign price_start
        Remove sell orders (check if it's not arbitrary data) if there is too much of them.
        Set the number of sell order to do but less than sell_price_max & nb_orders_to_display.
        Fetch data returned by set_several_sell_orders
        Do the same for buy orders.
        """
        print 'limit_nb_orders_displayed(self):'
        new_buy_orders, new_sell_orders = api.get_orders(self.currency_pair)

        # check sell orders
        if self.sell_orders == []:
            self.sell_orders.append([0, Decimal('0'), self.sell_price_max \
                + self.increment])
            new_sell_orders = self.sell_orders[:]
            print 'Buy limit reached limit_nb_orders_displayed, sell_orders : ', \
                self.sell_orders, 'new_sell_orders : ', new_sell_orders
        
        elif self.sell_orders[0][0] == 0:
            print 'self.sell_orders[0][0] == 0:'
            pass
        
        else:
            if new_sell_orders == []:
                print 'sell orders not ok, waiting for the next round'
                pass

            else :
                price_start = self.sell_orders[-1][2] + self.increment
                print 'self.sell_orders[-1][2]', self.sell_orders[-1], \
                    'new_sell_orders[0][2]', new_sell_orders[0][2]
                
                if self.sell_orders[-1][2] - new_sell_orders[0][2] \
                    > self.increment * self.nb_orders_to_display:

                    print (self.sell_orders[-1][2] - new_sell_orders[0][2] \
                    > self.increment * self.nb_orders_to_display)
                    
                    i = int((self.sell_orders[-1][2] - (new_sell_orders[0][2] \
                        + self.increment * self.nb_orders_to_display)) / self.increment)
                    
                    print 'Nb of sell to remove :', i, 'from : ', price_start
                    
                    while i > 0:
                        print time.strftime('%X'), 'SELL to cancel :', self.sell_orders[-1]

                        if self.sell_orders[-1][0] == 0:
                            del self.sell_orders[-1]

                        else:
                            resp = api.cancel_order(self.currency_pair, self.sell_orders[-1][0])
                            print 'Order canceled : ', resp
                            del self.sell_orders[-1]
                        
                        i -= 1
                
                elif self.sell_orders[-1][2] - new_sell_orders[0][2] \
                    <= self.increment * self.nb_orders_to_display:
                    
                    if self.sell_orders[-1][2] + self.nb_orders_to_display \
                        * self.increment < self.sell_price_max:
                        
                        i = int((self.sell_orders[0][2] + self.nb_orders_to_display \
                            * self.increment - self.sell_orders[-1][2]) / self.increment)
                    
                    elif self.sell_orders[-1][2] + self.nb_orders_to_display \
                        * self.increment >= self.sell_price_max:
                        
                        i = int((self.sell_price_max - self.sell_orders[-1][2]) \
                            / self.increment)
                        print 'Sell price max almost reached'
                    
                    print 'Nb of sell orders to put : i =', i, 'from :', price_start
                    
                    sell_order_executed = api.set_several_sell_orders(self.currency_pair, \
                        price_start, self.amount, i, self.increment)

                    for item in sell_order_executed:
                        self.sell_orders.append(item)
                
                else:
                    print 'sell orders ok'
        
        # check buy orders
        if self.buy_orders ==[]:
            self.buy_orders.append([0, Decimal('0'), self.buy_price_min - self.increment])
            new_buy_orders = self.buy_orders[:]
            
            print 'Buy limit reached , buy_orders : ', self.buy_orders, \
                ' new_sell_orders : ', new_sell_orders
        
        elif self.buy_orders[-1][0] == 0:
            print 'self.buy_orders[-1][0] == 0 :'
            pass
        
        else:
            if new_buy_orders == []:
                print 'Buy orders not ok, waiting for the next round'

            else:
                price_start = self.buy_orders[0][2] - self.increment
                print 'new_buy_orders[-1][2]', new_buy_orders[-1][2], \
                    'self.buy_orders[0][2]', self.buy_orders[0][2]
                
                if new_buy_orders[-1][2] - self.buy_orders[0][2] \
                    > self.increment * self.nb_orders_to_display:

                    print (new_buy_orders[-1][2] - self.buy_orders[0][2] \
                    > self.increment * self.nb_orders_to_display)
                    
                    i = int((new_buy_orders[-1][2] - (self.buy_orders[0][2] \
                        + self.increment * self.nb_orders_to_display)) / self.increment)
                    
                    print 'Nb of buy order to remove : ', i, 'from : ', price_start
                    
                    while i > 0:
                        print time.strftime('%X'), 'BUY to cancel :', self.buy_orders[0]

                        if self.buy_orders[0][0] == 0:
                            del self.buy_orders[0]

                        else:
                            resp = api.cancel_order(self.currency_pair, self.buy_orders[0][0])
                            print 'Order canceled : ', resp
                            del self.buy_orders[0]
                        
                        i -= 1
                
                elif new_buy_orders[-1][2] - self.buy_orders[0][0] \
                    <= self.increment * self.nb_orders_to_display:
                    
                    if self.buy_orders[0][0] - self.nb_orders_to_display \
                        * self.increment > self.buy_price_min:
                        
                        i = int((self.buy_orders[0][2] + self.nb_orders_to_display \
                            * self.increment - self.buy_orders[-1][2]) / self.increment)
                    
                    elif self.buy_orders[0][0] - self.nb_orders_to_display \
                        * self.increment <= self.buy_price_min:
                        
                        i = int((self.buy_orders[0][0] - self.buy_price_min) \
                            / self.increment)
                        print 'buy_price_min almost reached'
                    
                    print 'nb of buy orders to put : i =', i, 'from :', price_start
                    
                    buy_order_executed = api.set_several_buy_orders(self.currency_pair, \
                        price_start, self.amount, i, self.increment)

                    i = 0
                    for item in buy_order_executed:
                        self.buy_orders.insert(i, item)
                
                else:
                    print 'buy orders ok'

    def set_orders(self):
        """Sort orders at the apps init.

        Assign new_..._orders by calling get_orders(self.currency_pair), i = 0.
        Check if user sell book on the marketplace is empty and set the number of 
            sell order to do but less than sell_price_max & nb_orders_to_display.
        If new_sell_orders != [] remove all sell_orders < sell_price_min if any
        Then complete by adding sell orders from sell_price_min to sell_orders[0] if needed
        Set the number of sell order to do (less than sell_price_max & 
            nb_orders_to_display), self.sell_orders and price_start.
        If new_sell_orders == [] the number of sell order to do (less than sell_price_max & 
            nb_orders_to_display), and price_start.
        set_several_sell_orders() if needed, fetch the returned response into self.sell_orders
        Do almost the same for buy orders.
        """
        new_buy_orders, new_sell_orders = api.get_orders(self.currency_pair)

        i = 0
        
        if new_sell_orders == []:
            print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                'no active sell orders'
            
            if (self.sell_price_max - self.sell_price_min) / self.increment \
                > self.nb_orders_to_display:
            
                i = int(self.nb_orders_to_display)
            
            else:
                i = int((self.sell_price_max - self.sell_price_min) / self.increment)

            price_start = self.sell_price_min
        
        else:
            if new_sell_orders[0][2] < self.sell_price_min:
                for item in new_sell_orders:
                    if item[2] < self.sell_price_min:
                        resp = api.cancel_order(self.currency_pair, item[0])
                        print 'Sell order removed : ', item

                        new_sell_orders.remove(item)

            if new_sell_orders != []:
                if new_sell_orders[0][2] > self.sell_price_min:
                    price_start = self.sell_price_min
                    i = int((new_sell_orders[0][2] - self.sell_price_min) / self.increment)

                    print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                        i, ' sell to add from', price_start,
                    
                    sell_orders_executed = api.set_several_sell_orders(self.currency_pair, price_start, \
                        self.amount, i, self.increment)

                    i2 = 0
                    for item in sell_orders_executed:
                        print 'Sell order added : ', item
                        new_sell_orders.insert(i2, item)
                        i -= 1

                
                if new_sell_orders[0][2] == self.sell_price_min:
                    nb_of_orders = len(new_sell_orders)

                    if new_sell_orders[0][2] + self.increment * self.nb_orders_to_display \
                        <= self.sell_price_max:
                        i = int(self.nb_orders_to_display) - nb_of_orders

                    elif new_sell_orders[0][2] + self.increment * self.nb_orders_to_display \
                        > self.sell_price_max:
                        i = int((self.sell_price_max - self.sell_price_min) / \
                            self.increment) - nb_of_orders

                    else:
                        print 'Sell orders already set'

                self.sell_orders = new_sell_orders[:]
                price_start = new_sell_orders[-1][2] + self.increment
                print i, 'sell order to add from : ', price_start

            else:
                print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                    'no active sell orders'
                
                if (self.sell_price_max - self.sell_price_min) / self.increment \
                    > self.nb_orders_to_display:
                
                    i = int(self.nb_orders_to_display)
                
                else:
                    i = int((self.sell_price_max - self.sell_price_min) / self.increment)

                price_start = self.sell_price_min

        if i != 0:
            print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                'Add sell orders from', price_start, 'to', (price_start + i * self.increment)
            
            sell_orders_executed = api.set_several_sell_orders(self.currency_pair, price_start, \
                self.amount, i, self.increment)
            for item in sell_orders_executed:
                print 'Sell order added : ', item
                self.sell_orders.append(item)
        
        # Set nb of buy order to put
        i = 0
        if new_buy_orders == []:
            print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                'No active buy orders'
            
            if (self.buy_price_max - self.buy_price_min) / self.increment \
                > self.nb_orders_to_display:
            
                i = int(self.nb_orders_to_display)
            
            else:
                i = int((self.buy_price_max - self.buy_price_min) / self.increment)

            price_start = self.buy_price_max
        
        else:
            if new_buy_orders[-1][2] > self.buy_price_max:
                for item in new_buy_orders:
                    if item[2] > self.buy_price_max:
                        resp = api.cancel_order(self.currency_pair, item[0])
                        print 'Buy order removed : ', item

                        new_buy_orders.remove(item)

            if new_buy_orders != []:
                nb_of_orders = len(new_buy_orders)

                if new_buy_orders[-1][2] < self.buy_price_max:
                    price_start = self.buy_price_max
                    i = int((self.buy_price_max - new_buy_orders[-1][2]) / self.increment)

                    print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                        'Add buy orders from', price_start, 'to', (price_start + Decimal(str(i)) * self.increment)

                    buy_orders_executed = api.set_several_buy_orders(self.currency_pair, \
                        price_start, self.amount, i, self.increment)

                    for item in buy_orders_executed:
                        print 'Buy orders already set'
                        new_buy_orders.insert((nb_of_orders - 1), item)
                        nb_of_orders += 1
                        i -= 1

                if new_buy_orders[-1][2] == self.buy_price_max:
                    if new_buy_orders[-1][2] - self.increment * self.nb_orders_to_display \
                        >= self.buy_price_min:
                        i = int(self.nb_orders_to_display) - nb_of_orders

                    if new_buy_orders[-1][2] - self.increment * self.nb_orders_to_display \
                        < self.buy_price_min:
                        i = int((self.sell_price_max - self.sell_price_min) / \
                            self.increment) - nb_of_orders

                    else:
                        print 'Buy orders already set'
                    
                self.buy_orders = new_buy_orders[:]
                price_start = new_buy_orders[0][2] + self.increment

                buy_orders_executed = api.set_several_buy_orders(self.currency_pair, \
                    price_start, self.amount, i, self.increment)

                i2 = 0
                for item in buy_orders_executed:
                    self.buy_orders.insert(i2, item)
                    i2 += 1
                    i -= 1

            else:
                print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                    'No active buy orders'
                    
                if (self.buy_price_max - self.buy_price_min) / self.increment \
                    > self.nb_orders_to_display:
                    
                    i = int(self.nb_orders_to_display)
                    
                else:
                    i = int((self.buy_price_max - self.buy_price_min) / self.increment)

                price_start = self.buy_price_max

        if i != 0:
            print 'Current date & time ', time.strftime('%x'), time.strftime('%X'), \
                'Add buy orders from', price_start, 'to', (price_start + i * self.increment)
            
            buy_orders_executed = api.set_several_buy_orders(self.currency_pair, price_start, \
                self.amount, i, self.increment)
            
            for item in buy_orders_executed:
                print 'Sell order added : ', item
                self.buy_orders.append(item)

    def strat(self):
        """Simple execution loop."""
        while True:
            print time.strftime('%x'), time.strftime('%X'), 'CYCLE START'
            self.compare_orders()
            print time.strftime('%x'), time.strftime('%X'), 'CYCLE STOP'
            api.api_sleep()


api = apiInterface.ApiInterface()
lazy = Lazy()

#lazy.cancel_all()

lazy.set_orders()
lazy.strat()

