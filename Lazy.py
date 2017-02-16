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
        self.currency_pair = 'BTC_SDC'
        self.buy_pair = 'BTC'
        self.sell_pair = 'SDC'
        self.amount = Decimal('1.00000000')
        self.increment = Decimal('0.00001000')
        self.buy_orders = []
        self.buy_orders_temp = []
        self.new_buy_orders = []
        self.temp_buy_orders = []
        self.buy_price_min = Decimal('0.00153')
        self.buy_price_max = Decimal('0.00155')
        self.sell_orders = []
        self.sell_orders_temp = []
        self.new_sell_orders = []
        self.temp_sell_orders = []
        self.sell_price_min = Decimal('0.00166')
        self.sell_price_max = Decimal('0.00168')
        self.nb_orders_to_display = Decimal('2')