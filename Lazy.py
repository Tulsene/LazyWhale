#!/usr/bin/env python
# -*- coding: utf-8 -*-
# market making script for lazy whale  market maker
# if you don't get it, don't use it

import logging
import time
import apiInterface
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
        self.buy_price_min = Decimal('0.00124')
        self.buy_price_max = Decimal('0.00125')
        self.sell_price_min = Decimal('0.00136')
        self.sell_price_max = Decimal('0.00139')
        self.nb_orders_to_display = Decimal('2') # Have to be a int entry

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
        
        log = 'sell orders :', self.sell_orders, '\n', 'new_sell_orders :', new_sell_orders
        logging.info(log)

        if new_sell_orders[0][0] != self.sell_orders[0][0]:
            logging.warning('a sell has occured')

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
            
            log = 'compare_orders() sell i :', i , 'price_start :', price_start
            logging.warning(log)

            while i > 0:
                order = api.set_buy_order(self.currency_pair, price_start, self.amount)
                
                log = 'buy order added : ', order
                logging.warning(order)
                
                buy_orders_executed.append(order)

                i -= 1
                price_start += self.increment

        log = 'buy orders :', self.buy_orders, '\n', 'new_buy_orders :', new_buy_orders
        logging.info(log)

        # check if a buy occured
        if new_buy_orders[-1][0] != self.buy_orders[-1][0]:
            logging.warning('a buy has occured')

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
            
            log = 'compare_orders() buy i :', i, 'price_start :', price_start
            logging.warning(log)

            while i > 0:
                order = api.set_sell_order(self.currency_pair, price_start, self.amount)
                
                log = 'sell order added : ', order
                logging.warning(log)

                sell_orders_executed.insert(0, order)
                
                i -= 1
                price_start -= self.increment

        if sell_orders_executed != []:
            self.update_sell_orders(buy_orders_missing, sell_orders_executed)
        
        if buy_orders_executed != []:
            self.update_buy_orders(sell_orders_missing, buy_orders_executed)
        
        self.limit_nb_orders_displayed()

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
        logging.info('check_if_no_orders(self):')

        new_buy_orders, new_sell_orders = api.get_orders(self.currency_pair)
        sell_orders_executed, buy_orders_executed = [], []

        if new_sell_orders == []:
            price_start = self.sell_orders[-1][2] + self.increment
            
            log = 'new_sell_orders == [], price_start = ', price_start
            logging.warning(log)

            if self.sell_orders[0][0] == 0:
                new_sell_orders = self.sell_orders[:]
                logging.info('self.sell_orders[0][0] == 0:')

            elif price_start > self.sell_price_max:
                new_sell_orders.append([0, Decimal('0'), price_start])
                logging.info('new_sell_orders.append([0, Decimal(\'0\'), price_start])')

            else:
                if price_start + self.increment * self.nb_orders_to_display \
                    <= self.sell_price_max:
                    
                    i = int(self.nb_orders_to_display - ((price_start - \
                        self.sell_orders[0][2]) / semf.increment))
                
                if price_start + self.increment * self.nb_orders_to_display \
                    > self.sell_price_max:
                    
                    i = int((self.sell_price_max - price_start) / self.increment) + 1
               
                log = 'There is ', i, 'sell orders to add from ', price_start
                logging.warning(log)

                sell_orders_executed += api.set_several_sell_orders(self.currency_pair, \
                    price_start, self.amount, i, self.increment)

                for item in sell_orders_executed:
                    self.sell_orders.append(item)
                    new_sell_orders.append(item)

        if new_buy_orders == []:
            price_start = self.buy_orders[0][2] - self.increment
            
            log = 'new_buy_orders == [], price_start', price_start
            logging.warning(log)
            
            if self.buy_orders[-1][0] == 0:
                new_buy_orders = self.buy_orders[:]
                logging.info('self.buy_orders[-1][0] == 0:')
            
            elif price_start < self.buy_price_min:
                new_buy_orders.append([0, Decimal('0'), price_start])
                logging.info('new_buy_orders.append([0, Decimal(\'0\'), price_start])')
            
            else:
                if price_start - self.increment * self.nb_orders_to_display \
                    >= self.buy_price_min:
                
                    i = int(self.nb_orders_to_display - ((self.buy_orders[0][2] - \
                        price_start) / self.increment))
               
                elif price_start - self.increment * self.nb_orders_to_display \
                    < self.buy_price_min:
                
                    i = int((price_start - self.buy_price_min) / self.increment) + 1
                
                log = 'There is ', i, 'buy orders to add from', price_start
                logging.warning(log)

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
        logging.info('update_sell_orders(self):')

        for item in buy_orders_missing:
            if item in self.buy_orders:
                self.buy_orders.remove(item)

        i = 0
        for item in sell_orders_executed:
            self.sell_orders.insert(i, item)
            i += 1

    def update_buy_orders(self, sell_orders_missing, buy_orders_executed):
        """Update user orders after a buy occured.

        Remove missing orders from sell_orders.
        Add executed orders to buy_orders.
        """
        logging.info('update_buy_orders(self):')

        for item in sell_orders_missing:
            if item in self.sell_orders:
                self.sell_orders.remove(item)

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
        logging.info('limit_nb_orders_displayed(self):')
        new_buy_orders, new_sell_orders = api.get_orders(self.currency_pair)

        # check sell orders
        if self.sell_orders == []:
            self.sell_orders.append([0, Decimal('0'), self.sell_price_max \
                + self.increment])
            new_sell_orders = self.sell_orders[:]
            
            log = 'Buy limit reached limit_nb_orders_displayed, sell_orders : ', \
                self.sell_orders, 'new_sell_orders : ', new_sell_orders
            logging.warning(log)
        
        elif self.sell_orders[0][0] == 0:
            logging.info('self.sell_orders[0][0] == 0:')
            pass
        
        else:
            if new_sell_orders == []:
                logging.warning('sell orders not ok, waiting for the next round')
                pass

            else :
                price_start = self.sell_orders[-1][2] + self.increment
                
                log = 'self.sell_orders[-1][2]', self.sell_orders[-1], \
                    'new_sell_orders[0][2]', new_sell_orders[0][2]
                logging.info(log)
                
                if self.sell_orders[-1][2] - new_sell_orders[0][2] \
                    > self.increment * self.nb_orders_to_display:

                    log = (self.sell_orders[-1][2] - new_sell_orders[0][2] \
                        > self.increment * self.nb_orders_to_display)
                    logging.info(log)
                    
                    i = int((self.sell_orders[-1][2] - (new_sell_orders[0][2] \
                        + self.increment * self.nb_orders_to_display)) / self.increment)
                    
                    log = 'Nb of sell to remove :', i, 'from : ', price_start
                    logging.warning(log)
                    
                    while i > 0:
                        log = 'SELL to cancel :', self.sell_orders[-1]
                        logging.info(log)

                        if self.sell_orders[-1][0] == 0:
                            del self.sell_orders[-1]

                        else:
                            resp = api.cancel_order(self.currency_pair, self.sell_orders[-1][0])
                            
                            log = 'Order canceled : ', resp
                            logging.info(log)

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
                        logging.warning('Sell price max almost reached')
                    
                    log = 'Nb of sell orders to put : i =', i, 'from :', price_start
                    logging.warning(log)
                    
                    sell_order_executed = api.set_several_sell_orders(self.currency_pair, \
                        price_start, self.amount, i, self.increment)

                    for item in sell_order_executed:
                        self.sell_orders.append(item)
                
                else:
                    logging.warning('sell orders ok')
        
        # check buy orders
        if self.buy_orders ==[]:
            self.buy_orders.append([0, Decimal('0'), self.buy_price_min - self.increment])
            new_buy_orders = self.buy_orders[:]
            
            log = 'Buy limit reached , buy_orders : ', self.buy_orders, \
                ' new_sell_orders : ', new_sell_orders
            logging.warning(log)
        
        elif self.buy_orders[-1][0] == 0:
            logging.warning('self.buy_orders[-1][0] == 0 :')
            pass
        
        else:
            if new_buy_orders == []:
                logging.warning('Buy orders not ok, waiting for the next round')

            else:
                price_start = self.buy_orders[0][2] - self.increment
                
                log = 'new_buy_orders[-1][2]', new_buy_orders[-1][2], \
                    'self.buy_orders[0][2]', self.buy_orders[0][2]
                logging.info(log)
                
                if new_buy_orders[-1][2] - self.buy_orders[0][2] \
                    > self.increment * self.nb_orders_to_display:

                    log = (new_buy_orders[-1][2] - self.buy_orders[0][2] \
                        > self.increment * self.nb_orders_to_display)
                    logging.info(log)
                    
                    i = int((new_buy_orders[-1][2] - (self.buy_orders[0][2] \
                        + self.increment * self.nb_orders_to_display)) / self.increment)
                    
                    log = 'Nb of buy order to remove : ', i, 'from : ', price_start
                    logging.warning(log)
                    
                    while i > 0:
                        log = 'BUY to cancel :', self.buy_orders[0]
                        logging.info(log)

                        if self.buy_orders[0][0] == 0:
                            del self.buy_orders[0]

                        else:
                            resp = api.cancel_order(self.currency_pair, self.buy_orders[0][0])
                            
                            log = 'Order canceled : ', resp
                            logging.info(log)

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
                        logging.warning('buy_price_min almost reached')
                    
                    log = 'nb of buy orders to put : i =', i, 'from :', price_start
                    logging.warning(log)
                    
                    buy_order_executed = api.set_several_buy_orders(self.currency_pair, \
                        price_start, self.amount, i, self.increment)

                    i = 0
                    for item in buy_order_executed:
                        self.buy_orders.insert(i, item)
                
                else:
                    logging.warning('buy orders ok')

    def set_orders(self):
        """Sort orders at the apps init.

        Assign new_..._orders by calling get_orders(self.currency_pair), i = 0.
        Check if user sell book on the marketplace is not empty.
        Remove orders < sell_price_min & if there is too much of them.
        If the user sell book is not empty and if the 1st order == sell_price_min, 
            add one otherwise
        Loop to check if there is no more or less than increment between orders, 
            add or remove otherwise
        If there is no orders in new_sell_orders, add sell orders < nb_orders_to_display 
            & sell_price_max
        Do almost the same for buy orders.
        """
        new_buy_orders, new_sell_orders = api.get_orders(self.currency_pair)

        if new_sell_orders != []:
            log = 'new_sell_orders : ', new_sell_orders
            logging.info(log)

            if new_sell_orders[0][2] < self.sell_price_min:
                for order in new_sell_orders:
                    if order[2] < self.sell_price_min:
                        resp = api.cancel_order(self.currency_pair, order[0])
                        
                        log = 'Sell order removed : ', order
                        logging.warning(log)

                        new_sell_orders.remove(order)

            if new_sell_orders[-1][2] > self.sell_price_min + self.increment \
                * self.nb_orders_to_display:
                
                price_target = self.sell_price_min + self.increment \
                    * self.nb_orders_to_display

                for order in new_sell_orders:
                    if order[2] > price_target:
                        resp = api.cancel_order(self.currency_pair, order[0])
                        
                        log = 'Sell order removed : ', order
                        logging.warning(log)

                        new_sell_orders.remove(order) 

            if new_sell_orders != []:
                i = 0
                target = len(new_sell_orders)
                nb_orders_to_display_tmp = int(self.nb_orders_to_display)

                log = 'new_sell_orders : ', new_sell_orders
                logging.info(log)

                if new_sell_orders[0][2] != self.sell_price_min:
                    order = api.set_several_sell_orders(self.currency_pair, price_start, \
                        self.amount)

                    new_sell_orders.insert(0, order)

                    log = 'Sell order added : ', order
                    logging.warning(log)

                    if target < nb_orders_to_display_tmp:
                        target += 1

                while i < target:
                    if new_sell_orders[i][2] + self.increment > self.sell_price_max:
                        i = target
                        logging('sell_price_max reached')

                    else:
                        if i + 1 <= len(new_sell_orders):
                            order = api.set_sell_order(self.currency_pair, \
                                (new_sell_orders[i][2] + self.increment), self.amount)

                            new_sell_orders.insert((i + 1), order)

                            log = 'Added sell order : ', order
                            logging.warning(log)

                            if target < nb_orders_to_display_tmp:
                                target += 1
                        
                            i += 1

                        elif new_sell_orders[i + 1][2] - new_sell_orders[i][2] \
                            < self.increment:

                            resp = api.cancel_order(self.currency_pair, new_sell_orders[i + 1][0])
                            
                            log = 'Sell order removed : ', order
                            logging.warning(log)

                            new_sell_orders.remove(order)

                            target -= 1

                        elif new_sell_orders[i + 1][2] - new_sell_orders[i][2] \
                            > self.increment:

                            order = api.set_sell_order(self.currency_pair, \
                                (new_sell_orders[i][2] + self.increment), self.amount)

                            new_sell_orders.insert((i + 1), order)

                            log = 'Added sell order : ', order
                            logging.warning(log)

                            if target < nb_orders_to_display_tmp:
                                target += 1
                        
                            i += 1

                        else:
                            i += 1

                self.sell_orders = new_sell_orders[:]

        if new_sell_orders == []:
            price_start = self.sell_price_min

            logging.warning('no active sell orders')
            
            if (self.sell_price_max - self.sell_price_min) / self.increment \
                > self.nb_orders_to_display:
            
                i = int(self.nb_orders_to_display)
            
            else:
                i = int((self.sell_price_max - self.sell_price_min) / self.increment)

            log = i, 'sell order to add from : ', price_start, 'to', (price_start + i \
                * self.increment)
            logging.warning(log)
            
            sell_orders_executed = api.set_several_sell_orders(self.currency_pair, price_start, \
                self.amount, i, self.increment)
            
            for item in sell_orders_executed:
                log = 'Sell order added : ', item
                logging.info(log)

                self.sell_orders.append(item)
        
        # Set nb of buy order to put
        if new_buy_orders != []:
            log = 'new_buy_orders : ', new_buy_orders
            logging.info(log)

            if new_buy_orders[-1][2] > self.buy_price_max:
                for order in new_buy_orders:
                    if order[2] > self.buy_price_max:
                        resp = api.cancel_order(self.currency_pair, order[0])
                        
                        log = 'Buy order removed : ', order
                        logging.warning(log)

                        new_buy_orders.remove(order)

            if new_buy_orders[0][2] < self.buy_price_max - self.increment \
                * self.nb_orders_to_display:

                price_target = self.buy_price_max - self.increment \
                    * self.nb_orders_to_display

                for order in new_buy_orders:
                    if order[2] < price_target:
                        resp = api.cancel_order(self.currency_pair, order[0])
                        
                        log = 'Buy order removed : ', order
                        logging.warning(log)

                        new_buy_orders.remove(order)

            if new_buy_orders != []:
                i = 0
                target = len(new_buy_orders)

                if new_buy_orders[0][2] != self.buy_price_max - self.increment \
                    * self.nb_orders_to_display:
                    
                    if self.buy_price_max - self.increment * self.nb_orders_to_display \
                        < self.buy_price_min:
                        
                        buy_price = self.buy_price_min
                        target = int((self.buy_price_max - self.buy_price_min) / self.increment)

                    else:
                        buy_price = self.buy_price_max - self.increment * self.nb_orders_to_display
                    
                    order = api.set_buy_order(self.currency_pair, buy_price, self.amount)

                    new_buy_orders.insert(0, order)

                    log = 'Added buy order : ', order
                    logging.warning(log)

                    nb_orders_to_display_tmp = int(self.nb_orders_to_display)
                        
                    if target < nb_orders_to_display_tmp:
                        target += 1

                while i < target:
                    if i + 1 < len(new_buy_orders):
                        order = api.set_buy_order(self.currency_pair, (new_buy_orders[i][2] \
                            + self.increment), self.amount)

                        new_buy_orders.insert((i + 1), order)

                        log = 'Added buy order : ', order
                        logging.warning(log)

                        nb_orders_to_display_tmp = int(self.nb_orders_to_display)
                        
                        if target < nb_orders_to_display_tmp:
                            target += 1

                        i += 1

                    elif new_buy_orders[i + 1][2] - new_buy_orders[i][2] < self.increment:
                        resp = api.cancel_order(self.currency_pair, item[0])
                        
                        log = 'Buy order removed : ', order
                        logging.warning(log)

                        new_buy_orders.remove(order)

                        target -= 1

                    elif new_buy_orders[i + 1][2] - new_buy_orders[i][2] > self.increment:
                        order = api.set_buy_order(self.currency_pair, (new_buy_orders[i][2] \
                            + self.increment), self.amount)

                        new_buy_orders.insert((i + 1), order)

                        log = 'Added buy order : ', order
                        logging.warning(log)

                        nb_orders_to_display_tmp = int(self.nb_orders_to_display)
                        
                        if target < nb_orders_to_display_tmp:
                            target += 1

                        i += 1

                    else:
                        i += 1

            self.buy_orders = new_buy_orders[:]

        if new_buy_orders == []:
            price_start = self.buy_price_max
            logging.warning('No active buy orders')
            
            if (self.buy_price_max - self.buy_price_min) / self.increment \
                > self.nb_orders_to_display:
            
                i = int(self.nb_orders_to_display)
            
            else:
                i = int((self.buy_price_max - self.buy_price_min) / self.increment)

            log = 'Add buy orders from', price_start, 'to', (price_start \
                    + Decimal(str(i)) * self.increment)
            logging.warning(log)
            
            buy_orders_executed = api.set_several_buy_orders(self.currency_pair, price_start, \
                self.amount, i, self.increment)
            
            for item in buy_orders_executed:
                log = 'Sell order added : ', item
                logging.info(log)

                self.buy_orders.append(item)

    def strat(self):
        """Do the lazy whale strategy.

        Simple execution loop.
        """
        while True:
            logging.warning('CYCLE START')
            self.compare_orders()
            logging.warning('CYCLE STOP')
            api.api_sleep()

    def main(self):
        logging.basicConfig(filename='Lazy.log', format='%(asctime)s %(levelname)s:\
            %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
        
        logging.warning('HERE WE GO!')

        self.set_orders()
        self.strat()



api = apiInterface.ApiInterface()
lazy = Lazy()

if __name__ == '__main__':
    lazy.main()
