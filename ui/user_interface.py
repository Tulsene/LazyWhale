import json
from datetime import datetime
from decimal import Decimal
from copy import deepcopy

import ccxt

import utils.helpers as helper
import utils.converters as convert
import utils.checkers as check
import exchanges.api_manager as api_manager
from utils.logger import Logger


class UserInterface():
    def __init__(self, api_keys, fees_coef, safety_buy_value, safety_sell_value):
        self.log = Logger('user_interface').log
        self.slack_webhook = None
        self.allowed_exchanges = self.set_keys(api_keys)
        self.root_path = helper.set_root_path()
        self.fees_coef = fees_coef
        # TODO need to be improved, like with an automatic selection if there is already a bot running on the same market
        self.safety_buy_value = safety_buy_value
        self.safety_sell_value = safety_sell_value

    def set_keys(self, api_keys):
        """Little hack because I'm lazy and I don't want to add another argument to init.
        api_keys: dict.
        return: dict."""
        if 'slack_webhook' in api_keys.keys():
            self.slack_webhook = api_keys['slack_webhook']
            del api_keys['slack_webhook']

        return api_keys

    def simple_question(self, q):
        """Simple question prompted and response handling.
        q: string, the question to ask.
        return: boolean True or None, yes of no
        """
        while True:
            self.log(q, level='info', print_=True)
            choice = input(' >> ')
            choice = choice.lower()
            self.log(choice, level='debug', print_=False)
            if choice in ['yes', 'y', 'o', 'oui', 'j', 'ja','d', 'da']:
                return True
            if choice in ['no', 'nein', 'non', 'n', 'niet']:
                return False

    def ask_question(self, q, formater_func, control_func=None, control_value=None):
        """Ask any question to the user, control the value returned or ask again.
        q: string, question to ask to the user.
        formater_funct: function, format from string to the right datatype.
        control_funct: optional function, allow to check that the user's choice is
                       within the requested parameters
        return: formated (int, decimal, ...) choice of the user
        """
        self.log(q, level='info', print_=True)
        while True:
            try:
                choice = input(' >> ')
                self.log(choice, level='debug', print_=False)
                choice = formater_func(choice)

                if control_func:
                    if control_value:
                        control_func(choice, control_value)
                    else:
                        control_func(choice)
                return choice

            except Exception as e:
                self.log(f'{q} invalid choice: {choice} -> {e}', level='info', print_=True)

    def ask_to_select_in_a_list(self, q, a_list):
        """Ask to the user to choose between items in a list
        a_list: list.
        q: string.
        return: int, the position of this item """
        self.log(q, level='info', print_=True)
        q = ''
        for i, item in enumerate(a_list, start=1):
            q += f'{i}: {item}, '
        self.log(q, level='info', print_=True)

        while True:
            try:
                choice = input(' >> ')
                self.log(choice, level='debug')
                choice = convert.str_to_int(choice)
                
                if 0 < choice <= i:
                    return choice - 1
                else:
                    self.log(f'You need to enter a number between 1 and {i}',
                        level='info', print_=True)
            
            except Exception as e:
                self.log(f'{q} invalid choice: {choice} -> {e}',
                    level='info', print_=True)
        
        return choice

    def ask_for_params(self, test_file_path=None):
        """Allow user to use previous parameter if they exist and backup it.
        At the end of this section, parameters are set and LW can be initialized.
        """
        if test_file_path:
            # TODO
            return self.check_for_enough_funds(self.params_reader(test_file_path))

        file_path = f'{self.root_path}config/params.txt'
        params = self.params_reader(file_path)
        self.log(f'Your previous parameters are: {params}', level='info', print_=True)

        if params:
            # q = 'Do you want to display history from logs?'
            # if self.simple_question(q):
            #     self.history_reader()
            
            q = 'Do you want to use those params?'
            if self.simple_question(q):
                params = self.check_for_enough_funds(params)
            else:
                params = None
        else:
            self.log(f'Your parameters are not set correctly: {params}, please enter new one!',
                        level='warning', print_=True)

        if not params:
            params = self.enter_params()
        
        self.params_writer(file_path, params)
        
        return params

    def enter_params(self):
        """Series of questions to setup LW parameters.
        return: dict, valid parameters """
        params = {'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}
        params.update(self.set_marketplace())
        params.update({'market': self.select_market(params['api_connector'])})
        params.update(self.ask_range_setup())
        params.update(self.ask_params_spread(params['api_connector'], params['market'], params['intervals']))
        params.update({'amount': self.ask_param_amount(params)})
        params = self.check_for_enough_funds(params)
        q = 'Do you want to stop LW if range_bot is reach? (y) or (n) only.'
        params.update({'stop_at_bot': self.ask_question(q, convert.str_to_bool)})
        q = 'Do you want to stop LW if range_top is reach? (y) or (n) only.'
        params.update({'stop_at_top': self.ask_question(q, convert.str_to_bool)})
        params.update(self.ask_nb_to_display(params['intervals']))
        params.update({'profits_alloc': self.ask_profits_alloc()})
        return params

    def set_marketplace(self, marketplace=None, test_mode=None):
        """Select a marketplace among the loaded keys.
        Connect to the selected marketplace.
        return: String, name of the selected marketplace.
        """
        api_connector = api_manager.APIManager(self.slack_webhook)

        if test_mode:
            api_connector.set_zebitex(self.allowed_exchanges['zebitex_testnet'])
            
        else:
            exchanges_list = list(self.allowed_exchanges.keys())
            if not marketplace:
                q = 'Please select a market:'
                choice = self.ask_to_select_in_a_list(q, self.allowed_exchanges)
            else:
                choice = exchanges_list.index(marketplace)
            # Because kraken balance do not return free and used balance
            api_connector.is_kraken = True if self.allowed_exchanges[exchanges_list[choice]] == 'kraken' \
                else False
            if exchanges_list[choice] in ['zebitex', 'zebitex_testnet']:
                api_connector.set_zebitex(self.allowed_exchanges[exchanges_list[choice]], exchanges_list[choice])
                
            else:
                api_connector.exchange = eval(
                    f'ccxt.{exchanges_list[choice]}'
                    f'({self.allowed_exchanges[exchanges_list[choice]]})')
                
        api_connector.load_markets()

        return {'marketplace': marketplace if marketplace else exchanges_list[choice],
                'api_connector': api_connector}

    def select_market(self, api_connector, market=None):
        """Market selection menu.
        return: string, selected market.
        """
        if market:
            if market not in api_connector.exchange.symbols:
                raise ValueError(f"{market} not in api_connector.exchange.symbols : {api_connector.exchange.symbols}")
            
            limitation = check.limitation_to_btc_market(market)
            if limitation != True:
                raise ValueError(limitation)
        else:
            while True:
                self.log(f"Please enter the name of a market: {api_connector.exchange.symbols}", level='info', print_=True)
                market = input(' >> ').upper()
                allowed = check.limitation_to_btc_market(market)
                if allowed == True:
                    if market in api_connector.exchange.symbols:
                        return market
                else:
                    self.log(allowed, level='info', print_=True)

    def ask_range_setup(self):
        """Ask to the user to enter the range and increment parameters.
        return: dict, asked parameters."""
        while True:
            try:
                range_bot = self.ask_param_range_bot()
                range_top = self.ask_param_range_top(range_bot)
                increment = self.ask_param_increment()
                intervals = check.interval_generator(range_bot,
                                               range_top,
                                               increment)
                return {'range_bot': range_bot, 'range_top': range_top,
                        'increment_coef': increment, 'intervals': intervals}
            
            except Exception as e:
                self.log(e, level='warning', print_=True)

    def ask_param_increment(self):
        """Ask the user to enter a value for the spread between each order.
        return: decimal."""
        q = ('How much % of spread between two orders? It must be '
            'between 1% and 50%')
        return self.ask_question(q, check.increment_coef_buider)

    def ask_param_range_bot(self):
        """Ask the user to enter a value for the bottom of the range.
        return: decimal."""
        q = ('Enter a value for the bottom of the range. It must be '
            'superior to 1 satoshi (10^-8 btc):')
        return self.ask_question(q, convert.str_to_decimal, check.range_bot)

    def ask_param_range_top(self, range_bot):
        """Ask the user to enter a value for the top of the range.
        return: decimal."""
        q = ('Enter a value for the top of the range. It must be '
            'inferior to 0.99 BTC:')
        return self.ask_question(q, convert.str_to_decimal, check.range_top, range_bot)

    def ask_params_spread(self, api_connector, selected_market, intervals):
        """Ask to the user to choose between value for spread bot and setup
        spread top automatically
        return: dict, of decimal values
        """
        price = api_connector.get_market_last_price(selected_market)
        msg = f'The actual price of {selected_market} is {price}'
        self.log(msg, level='info', print_=True)
        
        q = ('Please select the price of your highest buy order '
             f"(spread_bot) in the list. {intervals[-2]} can't be selected")
        position = self.ask_to_select_in_a_list(q, intervals[:-2])

        self.log(f'The price of your lowest sell order is {intervals[position + 2]}',
                 level='info', print_=True)
        
        return {'spread_bot': intervals[position],
                'spread_top': intervals[position + 2]}

    def ask_param_amount(self, params):
        """Ask the user to enter a value of ALT to sell at each order.
        selected_market: string.
        range_bot: Decimal.
        return: Decimal."""
        pair = params['market'].split('/')[0]
        funds = params['api_connector'].get_balances()[pair]['total']
        suggestion = convert.divider(funds, 
                                     (len(params['intervals'])
                                      - params['intervals'].index(params['spread_top'])
                                      - 1))

        q = (f"How much {params['market'][:4]} do you want to sell "
             f'per order? It must be between'
             f"{Decimal('0.001') / params['range_bot']} and 10000000."
             f"Suggestion:  {suggestion}")
        
        while True:
            try:
                amount = self.ask_question(q, convert.str_to_decimal)
                check.amount(amount, params['range_bot'])
                return amount

            except Exception as e:
                self.log(e, level='info', print_=True)

    def ask_nb_to_display(self, intervals):
        """Ask how much buy and sell orders are going to be in the book.
        return: dict, nb_buy_to_display + nb_sell."""
        max_size = len(intervals)
        result = []
        for side in ['buy', 'sell']:
            q = (f'How many {side} orders do you want to display? It must be '
                f'less than {max_size}. 0 value = {max_size} :')
            result.append(self.ask_question(q, convert.str_to_int,
                                                check.nb_to_display,
                                                max_size))
        
        return {'nb_buy_to_display': result[0],
                'nb_sell_to_display': result[1]}

    def ask_profits_alloc(self):
        """Ask for profits allocation.
        return: int."""
        q = ('How do you want to allocate your profits in %. It must '
            'be between 0 and 100, both included:')
        return self.ask_question(q, convert.str_to_int, check.profits_alloc)

    def params_writer(self, file_path, params):
        updated = deepcopy(params)
        if 'intervals' in updated.keys():
            del updated['intervals']
        if 'api_connector' in updated.keys():
            del updated['api_connector']
        helper.simple_file_writer(file_path, convert.dict_to_str(updated))

    def change_params(self, params):
        """Allow the user to change one LW parameter.
        params: dict, all the parameter for LW.
        return: dict."""
        editable_params = (('range_bot', self.ask_param_range_bot),
                           ('range_top', self.ask_param_range_top),
                           ('increment_coef', self.ask_param_increment),
                           ('amount', self.ask_param_amount))
        question = 'What parameter do you want to change?'
        question_list = [f"The bottom of the range: {params['range_bot']}?\n",
                         f"The top of the range: {params['range_top']}?\n",
                         f"The spread between orders? {params['spread_bot']}\n",
                         f"The amount of {params['market'].split('/')[0]} per orders?\n",
                         f"Select the highest buy order?: {params['spread_bot']}\n",
                         'Add funds to your account\n']
        
        while True:
            try:
                choice = self.ask_to_select_in_a_list(question, question_list)
                if choice < 3:
                    params[editable_params[choice][0]] = \
                        editable_params[choice][1]()
                    params['intervals'] = check.interval_generator(
                        params['range_bot'], params['range_top'],
                        params['increment_coef'])
                    params = self.change_spread(params)

                elif choice == 3:
                    params[editable_params[choice][0]] = \
                        editable_params[choice][1](params['range_bot'])

                elif choice == 4:
                    params = self.change_spread(params)

                else:
                    self.wait_for_funds()

                break

            except Exception as e:
                self.log(e, level='warning', print_=True)

        return params

    def change_spread(self, params):
        spread = self.ask_params_spread(params['api_connector'], params['market'], params['intervals'])
        for key, value in spread.items():
            params[key] = value
        return params

    def wait_for_funds(self):
        """The answer is in the question!"""
        q = "Waiting for funds to arrive, (y) when you're ready, (n) to leave."
        if not self.simple_question(q):
            raise SystemExit('Ok, see you later then!')

    def history_reader(self):
        """Import the last 20 order from strat.log and organize it.
        return: None or dict containing : list of exectuted buy,
                                          list of executed sell,
                                          dict of parameters
        """
        file_path = f'{self.root_path}logs/history.log'
        raw_data = []
        logs_data = {'buy': [], 'sell': []}
        nb_of_lines = self.check_history_file(file_path)
        print('Function TODO')
        breakpoint()

        if not nb_of_lines:
            return None

        target = nb_of_lines - 20 if nb_of_lines > 20 else 0
        # Get the last 20 orders saved in log file
        while target < nb_of_lines:
            line = helper.read_one_line(file_path, nb_of_lines)
            try:
                line = json.loads(line)
                raw_data.append(line)
            # Don't care about malformed data, just skip it.
            except Exception:
                target = target - 1 if target - 1 >= 0 else target
            nb_of_lines -= 1

        self.display_user_trades(logs_data)

    def check_history_file(self, file_path):
        """Better to read when there is something to do so.
        file_path: string.
        return: int."""
        if helper.create_file_when_none(file_path):
            self.log("history.txt file have been created", level='warning', print_=True)
            return None

        self.log("Reading the strat.log file", level='debug', print_=True)
        nb_of_lines = helper.file_line_counter(file_path)
        print('function TODO')
        breakpoint()
        if not isinstance(nb_of_lines, int):
            self.log('Your strat.log file was empty', level='warning', print_=True)
            return None

        return nb_of_lines

    def format_bunch_of_trades(self, trades, logs_data):
        for order in trades:
            formated_order = self.format_log_order(
                order['side'],
                order['order_id'],
                order['price'],
                order['amount'],
                order['timestamp'],
                order['datetime'])
            if order['side'] == 'buy' or \
                    order['side'] == 'canceled_buy':
                logs_data['buy'].append(formated_order)
            if order['side'] == 'sell' or \
                    order['side'] == 'canceled_sell':
                logs_data['sell'].append(formated_order)

        return logs_data

    def format_log_order(self, side, order_id, price, amount, timestamp, date):
        """Sort the information of an order in a list of 6 items.
        id: string, order unique identifier.
        price: Decimal or string.
        amount: Decimal.
        timestamp: string.
        date: string.
        return: list, containing: id, price, amount, value, timestamp and date.
        """
        return [side, order_id, price, amount, str(convert.multiplier(
            Decimal(price), Decimal(amount), self.fees_coef)), \
                timestamp, date]

    def display_user_trades(self, orders):
        """Pretify and display orders list.
        orders: dict, contain all orders.
        """
        if orders['buy']:
            for order in orders['buy']:
                self.log(self.format_order_to_display(order), level='debug', print_=True)
        if orders['sell']:
            for order in orders['sell']:
                self.log(self.format_order_to_display(order), level='debug', print_=True)
        return

    def format_order_to_display(self, order):
        """To format an order as a string.
        order: dict.
        return: string."""
        return (
            f'{order[0]} on: {order[6]}, id: {order[1]}, price: {order[2]}, '
            f'amount: {order[3]}, value: {order[4]}, timestamp: {order[5]}'
        )

    def params_reader(self, file_path):
        """Load parameters from params.txt.
        file_path: string, params.txt relative path.
        return: dict with valid parameters, or False.
        """
        if helper.create_file_when_none(file_path):
            self.log(f'There was no {file_path}. One have been created', level='warning', print_=True)        
            return None
        
        try:
            return self.check_params(
                json.loads(
                    helper.read_one_line(file_path, 0)))
        
        except Exception as e:
            msg = f'Something went wrong when loading params: {e}'
            self.log(msg, level='warning', print_=True)
            return None

    def check_params(self, params):
        """Check the integrity of all parameters and return False if it's not.
        params: dict, params in string format.
        return: dict with formatted parameters, or False.
        """
        try:
            # Check there is values for all parameters
            params = self.check_value_presences(params)
            # Convert values
            params = self.convert_params(params)
            # Test if values are correct
            if params['marketplace'] not in self.allowed_exchanges:
                raise ValueError(f"You can't choose {params['marketplace']}"
                                 f" as marketplace")
            
            params.update(self.set_marketplace(params['marketplace']))
            self.select_market(params['api_connector'], params['market'])
            
            check.is_date(params['datetime'])
            check.range_bot(params['range_bot'])
            check.range_top(params['range_top'], params['range_bot'])
            check.interval(params['increment_coef'])
            check.amount(params['amount'], params['range_bot'])
            check.profits_alloc(params['profits_alloc'])

            params.update({'intervals': check.interval_generator(
                                            params['range_bot'],
                                            params['range_top'],
                                            params['increment_coef'])})
            
            if params['spread_bot'] not in params['intervals']:
                raise ValueError('Spread_bot isn\'t properly configured')
            
            spread_bot_index = params['intervals'].index(params['spread_bot'])
            if params['spread_top'] != params['intervals'][spread_bot_index + 2]:
                raise ValueError('Spread_top isn\'t properly configured')

        except Exception as e:
            self.log(f'The LW parameters are not well configured: {e}', level='warning', print_=True)
            return False
        
        return params

    def check_value_presences(self, params):
        params_names = ['datetime', 'marketplace', 'market', 'range_bot',
                        'range_top', 'spread_bot', 'spread_top',
                        'increment_coef', 'amount', 'stop_at_bot',
                        'stop_at_top', 'nb_buy_to_display',
                        'nb_sell_to_display', 'profits_alloc']
        
        for name in params_names:
            if not params[name]:
                raise ValueError(f'{name} is not set in parameters')
        
        return params

    def convert_params(self, params):
        decimal_to_test = ['range_bot', 'range_top', 'spread_bot', 'spread_top',
                            'increment_coef', 'amount', 'profits_alloc']
        
        for name in decimal_to_test:
            error_message = f"params['{name}'] is not a string:"
            params[name] = convert.str_to_decimal(params[name], error_message)
        
        for name in ['stop_at_bot', 'stop_at_top']:
            error_message = f"params['{name}'] is not a boolean:"
            params[name] = convert.str_to_bool(params[name], error_message)
        
        for name in ['nb_buy_to_display', 'nb_sell_to_display']:
            error_message = f"params['{name}'] is not a boolean:"
            params[name] = convert.str_to_int(params[name], error_message)

        return params

    def check_for_enough_funds(self, params):
        """Check if the user have enough funds to run LW with he's actual
        parameters.
        Printed value can be negative!
        Ask for params change if there's not.
        params: dict, parameters for LW.
        return: dict, params"""
        # Force user to set strategy parameters in order to have enough funds
        # to run the whole strategy
        while True:
            price = params['api_connector'].get_market_last_price(params['market'])
            balances = params['api_connector'].get_balances()
            pair = params['market'].split('/')
            sell_balance = convert.str_to_decimal(balances[pair[0]]['free'])
            buy_balance = convert.str_to_decimal(balances[pair[1]]['free'])
            spread_bot_index = params['intervals'].index(params['spread_bot'])
            spread_top_index = spread_bot_index + 1
            try:
                total_buy_funds_needed = self.calculate_buy_funds(
                    spread_bot_index, params['amount'], params['intervals'])
                total_sell_funds_needed = self.calculate_sell_funds(
                    spread_top_index, params['amount'], params['intervals'])

                msg = (
                    f'check_for_enough_funds total_buy_funds_needed: '
                    f'{total_buy_funds_needed}, buy_balance: {buy_balance}, '
                    f'total_sell_funds_needed: {total_sell_funds_needed}, '
                    f'sell_balance: {sell_balance}, price: {price}'
                )
                self.log(msg, level='debug', print_=True)

                # When the strategy start with spread bot inferior or
                # equal to the actual market price
                if params['spread_bot'] <= price:
                    total_buy_funds_needed = self.sum_buy_needs(params,
                                                                spread_top_index,
                                                                total_buy_funds_needed,
                                                                price)                
                # When the strategy start with spread bot superior to the
                # actual price on the market
                else:
                    total_sell_funds_needed = self.sum_sell_needs(params,
                                                                  spread_bot_index,
                                                                  total_sell_funds_needed,
                                                                  price)
                    
                msg = (
                    f'Your actual strategy require: {pair[1]} needed: '
                    f'{total_buy_funds_needed} and you have {buy_balance} '
                    f'{pair[1]}; {pair[0]} needed: {total_sell_funds_needed}'
                    f' and you have {sell_balance} {pair[0]}.'
                )
                self.log(msg, level='debug', print_=True)
                

                buy_balance, sell_balance = self.search_moar_funds(
                    total_buy_funds_needed,
                    total_sell_funds_needed,
                    buy_balance,
                    sell_balance,
                    params
                )
                
                return params
            except ValueError as e:
                self.log(f'You need to change some parameters: {e}', level='warning', print_=True)
                params = self.change_params(params)

    def calculate_buy_funds(self, index, amount, intervals):
        """Calculate the buy funds required to execute the strategy
        amount: Decimal, allocated ALT per order
        return: Decimal, funds needed
        """
        buy_funds_needed = Decimal('0')
        i = 0
        while i <= index:
            buy_funds_needed += intervals[i] * amount
            i += 1
        return buy_funds_needed

    def calculate_sell_funds(self, index, amount, intervals):
        """Calculate the sell funds required to execute the strategy
        amount: Decimal, allocated ALT per order
        return: Decimal, funds needed
        """
        sell_funds_needed = Decimal('0')
        i = len(intervals) - 1
        while i >= index:
            sell_funds_needed += amount
            i -= 1
        return sell_funds_needed

    def sum_buy_needs(self, params, spread_top_index, total_buy_funds_needed, price):
        incoming_buy_funds = Decimal('0')
        i = spread_top_index
        # When the whole strategy is lower than actual price
        if params['range_top'] < price:
            while i < len(params['intervals']):
                incoming_buy_funds += convert.multiplier(
                    params['intervals'][i], params['amount'],
                    self.fees_coef)
                i += 1
        # When only few sell orders are planned to be under the
        # actual price
        else:
            while params['intervals'][i] <= price:
                incoming_buy_funds += convert.multiplier(
                    params['intervals'][i], params['amount'])
                i += 1
                # It crash when price >= range_top
                if i == len(params['intervals']):
                    break

        return total_buy_funds_needed - incoming_buy_funds

    def sum_sell_needs(self, params, spread_bot_index, total_sell_funds_needed, price):
        incoming_sell_funds = Decimal('0')
        i = spread_bot_index
        # When the whole strategy is upper than actual price
        if params['spread_bot'] > price:
            while i >= 0:
                incoming_sell_funds += params['amount']
                i -= 1
        # When only few buy orders are planned to be upper the
        # actual price
        else:
            while params['intervals'][i] >= price:
                incoming_sell_funds += params['amount']
                i -= 1
                if i < 0:
                    break
        
        return total_sell_funds_needed - incoming_sell_funds

    def look_for_moar_funds(self, params, funds_needed, funds, side):
        """Look into open orders how much funds there is, offer to cancel orders not
        in the strategy.
        funds_needed: Decimal, how much funds are needed for the strategy.
        funds: Decimal, sum of available funds for the strategy.
        side: string, buy or sell.
        return: Decimal, sum of available funds for the strategy."""
        orders = params['api_connector'].orders_price_ordering(
            params['api_connector'].get_orders(params['market']))

        funds, orders_outside_strat = self.sum_open_orders(params, side, orders, funds)
        
        # If there is still not enough funds but there is open orders outside the
        # strategy
        if funds > Decimal('0'):
            if orders_outside_strat:
                funds = self.ask_cancel_orders(params, orders_outside_strat, funds, funds_needed, side)
                
        return funds

    def sum_open_orders(self, params, side, orders, funds):
        """simple addition of funds stuck in open order and will be used for the
        strategy"""
        orders_outside_strat = []
        if side == 'buy':
            for order in orders['buy']:
                if order[1] in params['intervals'] \
                        or order[1] == self.safety_buy_value:
                    funds += order[1] * order[2]
                else:
                    orders_outside_strat.append(order)
        else:
            for order in orders['sell']:
                if order[1] in params['intervals'] \
                        or order[1] == self.safety_sell_value:
                    funds += order[2]
                else:
                    orders_outside_strat.append(order)

        return funds, orders_outside_strat

    def ask_cancel_orders(self, params, orders_outside_strat, funds, funds_needed, side):
        while True:
            if not orders_outside_strat:
                break
            q = (
                f'Do you want to remove some orders outside of the '
                f'strategy to get enough funds to run it? (y or n)'
            )
            if self.simple_question(q):
                q = 'Which order do you want to remove:'
                rsp = self.ask_to_select_in_a_list(q,
                                                    orders_outside_strat)
                order = orders_outside_strat[rsp]
                del orders_outside_strat[rsp]
                rsp = params['api_connector'].cancel_order(params['market'],
                                                           order[0],
                                                           order[1],
                                                           order[4],
                                                           side)
                if rsp:
                    if side == 'buy':
                        funds += order[1] * order[2]
                    else:
                        funds += order[2]
                    self.log((f'You have now {funds} {side} '
                        f'funds and you need {funds_needed}.'),
                        level='debug', print_=True)
            else:
                break
        
        return funds

    def search_moar_funds(self, total_buy_funds_needed, total_sell_funds_needed, buy_balance, sell_balance, params):
        """In case there is not enough funds, check if there is none stuck
        before asking to change params"""
        if total_buy_funds_needed > buy_balance:
            buy_balance = self.look_for_moar_funds(
                params, total_buy_funds_needed, buy_balance, 'buy')
        
        if total_sell_funds_needed > sell_balance:
            sell_balance = self.look_for_moar_funds(
                params, total_buy_funds_needed, buy_balance, 'sell')
        
        if total_buy_funds_needed > buy_balance or \
                total_sell_funds_needed > sell_balance:
            raise ValueError('You don\'t own enough funds!')

        return buy_balance, sell_balance