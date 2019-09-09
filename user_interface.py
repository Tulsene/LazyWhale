import json
from datetime import datetime
from decimal import Decimal
from copy import deepcopy
from utils.helper import UtilsMixin
from exchange_manager import zebitexFormatted




class UserInterface(UtilsMixin):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    def simple_question(self, q):  # Fancy things can be added
        """Simple question prompted and response handling.
        q: string, the question to ask.
        return: boolean True or None, yes of no
        """
        while True:
            self.bot.applog.info(q)
            choice = input(' >> ')
            self.bot.applog.debug(choice)
            if choice == 'y':
                return True
            if choice == 'n':
                return False

    def ask_question(self, q, formater_func, control_func=None):
        """Ask any question to the user, control the value returned or ask again.
        q: string, question to ask to the user.
        formater_funct: function, format from string to the right datatype.
        control_funct: optional function, allow to check that the user's choice is
                       within the requested parameters
        return: formated (int, decimal, ...) choice of the user
        """
        self.bot.applog.info(q)
        while True:
            try:
                choice = input(' >> ')
                self.bot.applog.debug(choice)
                choice = formater_func(choice)
                if control_func:
                    control_func(choice)
                return choice
            except Exception as e:
                self.bot.applog.info(f'{q} invalid choice: {choice} -> {e}')

    def ask_to_select_in_a_list(self, q, a_list):
        """Ask to the user to choose between items in a list
        a_list: list.
        q: string.
        return: int, the position of this item """
        self.bot.applog.info(q)
        q = ''
        for i, item in enumerate(a_list, start=1):
            q += f'{i}: {item}, '
        self.bot.applog.info(q)
        while True:
            try:
                choice = input(' >> ')
                self.bot.applog.debug(choice)
                choice = self.str_to_int(choice)
                if 0 < choice <= i:
                    return choice - 1
                else:
                    msg = f'You need to enter a number between 1 and {i}'
                    self.bot.applog.info(msg)
            except Exception as e:
                self.bot.applog.info(f'{q} invalid choice: {choice} -> {e}')
        return choice

    def ask_param_range_bot(self):
        """Ask the user to enter a value for the bottom of the range.
        return: decimal."""
        q = (
            f'Enter a value for the bottom of the range. It must be '
            f'superior to 1 stats:')
        return self.ask_question(q, self.str_to_decimal,
                                 self.param_checker_range_bot)

    def ask_param_range_top(self):
        """Ask the user to enter a value for the top of the range.
        return: decimal."""
        q = (
            f'Enter a value for the top of the range. It must be '
            f'inferior to 0.99 BTC:')
        return self.ask_question(q, self.str_to_decimal,
                                 self.param_checker_range_top)

    def ask_param_amount(self, range_bot):
        """Ask the user to enter a value of ALT to sell at each order.
        return: decimal."""
        minimum_amount = Decimal('0.001') / range_bot
        q = (
            f'How much {self.config.selected_market[:4]} do you want to sell '
            f'per order? It must be between {minimum_amount} and 10000000:')
        while True:
            try:
                amount = self.ask_question(q, self.str_to_decimal)
                self.param_checker_amount(amount, minimum_amount)
                return amount
            except Exception as e:
                self.bot.applog.warning(e)

    def ask_param_increment(self):
        """Ask the user to enter a value for the spread between each order.
        return: decimal."""
        q = (
            f'How much % of spread between two orders? It must be '
            f'between 1% and 50%')
        return self.ask_question(q, self.increment_coef_buider)

    def ask_range_setup(self):
        """Ask to the user to enter the range and increment parameters.
        return: dict, asked parameters."""
        is_valid = False
        while is_valid is False:
            try:
                range_bot = self.ask_param_range_bot()
                range_top = self.ask_param_range_top()
                increment = self.ask_param_increment()
                intervals = self.bot.interval_generator(range_bot, range_top,
                                                    increment)
                is_valid = True
            except Exception as e:
                self.bot.applog.warning(e)
        self.config.intervals = intervals
        return {'range_bot': range_bot, 'range_top': range_top,
                'increment_coef': increment}

    def ask_params_spread(self):
        """Ask to the user to choose between value for spread bot and setup
        spread top automatically
        return: dict, of decimal values
        """
        price = self.bot.api.get_market_last_price(self.config.selected_market)
        msg = f'The actual price of {self.config.selected_market} is {price}'
        self.bot.applog.info(msg)
        q = (
            f'Please select the price of your highest buy order '
            f'(spread_bot) in the list')
        position = self.ask_to_select_in_a_list(q, self.config.intervals)
        return {'spread_bot': self.config.intervals[position],
                'spread_top': self.config.intervals[position + 1]}  # Can be improved by suggesting a value

    def ask_nb_to_display(self):
        """Ask how much buy and sell orders are going to be in the book.
        return: dict, nb_buy_to_display + nb_sell."""
        q = (
            f'How many buy orders do you want to display? It must be '
            f'less than {len(self.config.intervals)}. 0 value = '
            f'{len(self.config.intervals)} :')
        nb_buy_to_display = self.ask_question(q, self.str_to_int,
                                              self.param_checker_nb_to_display)
        q = (
            f'How many sell orders do you want to display? It must be '
            f'less than {len(self.config.intervals)}. 0 value = '
            f'{len(self.config.intervals)} :')
        nb_sell_to_display = self.ask_question(q, self.str_to_int,
                                               self.param_checker_nb_to_display)
        return {'nb_buy_to_display': nb_buy_to_display,
                'nb_sell_to_display': nb_sell_to_display}

    def ask_profits_alloc(self):
        """Ask for profits allocation.
        return: int."""
        q = (
            f'How do you want to allocate your profits in %. It must '
            f'be between 0 and 100, both included:')
        profits_alloc = self.ask_question(q, self.str_to_int,
                                          self.param_checker_profits_alloc)
        return profits_alloc

    def ask_for_params(self):
        """Allow user to use previous parameter if they exist and backup it.
        At the end of this section, parameters are set and LW can be initialized.
        """
        q = 'Do you want to check if a previous parameter is in params.txt?'
        file_path = f'{self.config.root_path}params.txt'
        if self.simple_question(q):
            params = self.params_reader(file_path)
            if params:
                self.bot.applog.info(f'Your previous parameters are: {params}')
                q = 'Do you want to display history from logs?'
                if self.simple_question(q):
                    self.log_file_reader()
                q = 'Do you want to use those params?'
                if self.simple_question(q):
                    self.config.params = self.bot.check_for_enough_funds(params)
            else:
                msg = 'Your parameters are corrupted, please enter new one!'
                self.bot.applog.warning(msg)
        if not self.config.params:
            self.config.params = self.enter_params()
        self.simple_file_writer(file_path, self.dict_to_str(self.config.params))
        return True

    def param_checker_nb_to_display(self, nb):
        """Verifie the nb of order to display
        nb: int"""
        if nb > len(self.config.intervals) and nb < 0:
            msg = (
                f'The number of order to display is too low (<0) '
                f'or high {len(self.config.intervals)}'
            )
            raise ValueError(msg)
        return True

    def enter_params(self):
        """Series of questions to setup LW parameters.
        return: dict, valid parameters """
        params = {'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}
        params.update({'marketplace': self.select_marketplace()})
        params.update({'market': self.select_market()})
        params.update(self.ask_range_setup())
        params.update({'amount': self.ask_param_amount(params['range_bot'])})
        params.update(self.ask_params_spread())
        params = self.bot.check_for_enough_funds(params)
        q = 'Do you want to stop LW if range_bot is reach? (y) or (n) only.'
        params.update({'stop_at_bot': self.ask_question(q, self.str_to_bool)})
        q = 'Do you want to stop LW if range_top is reach? (y) or (n) only.'
        params.update({'stop_at_top': self.ask_question(q, self.str_to_bool)})
        params.update(self.ask_nb_to_display())
        params.update({'profits_alloc': self.ask_profits_alloc()})
        return params

    def change_params(self, params):
        """Allow the user to change one LW parameter.
        params: dict, all the parameter for LW.
        return: dict."""
        editable_params = (('range_bot', self.ask_param_range_bot),
                           ('range_top', self.ask_param_range_top),
                           ('increment_coef', self.ask_param_increment),
                           ('amount', self.ask_param_amount))
        question = 'What parameter do you want to change?'
        question_list = ['The bottom of the range?', 'The top of the range?',
                         'The value between order?',
                         'The amount of alt per orders?',
                         'The value of your initial spread?',
                         'Add funds to your account']
        is_valid = False
        while is_valid is False:
            try:
                choice = self.ask_to_select_in_a_list(question, question_list)
                if choice < 3:
                    params[editable_params[choice][0]] = \
                        editable_params[choice][1]()
                    self.config.intervals = self.bot.interval_generator(
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
                is_valid = True
            except Exception as e:
                self.bot.applog.warning(e)
        return params

    def select_marketplace(self, marketplace=None):
        """Select a marketplace among the loaded keys.
        Connect to the selected marketplace.
        return: String, name of the selected marketplace.
        """
        if self.config.test_mode:
            self.config.exchange = self.bot.api.set_exchange('zebitex_testnet')
            # zebitexFormatted.ZebitexFormatted(
            #     self.config.testing_keys[0], self.config.testing_keys[1], True)
            self.bot.api.load_markets()
            return
        else:
            if not marketplace:
                q = 'Please select a market:'
                choice = self.ask_to_select_in_a_list(q, self.config.user_market_name_list)
            else:
                choice = self.config.user_market_name_list.index(marketplace)
            # Because kraken balance has no free and used balance
            self.is_kraken = True if self.config.user_market_name_list[choice] == 'kraken' \
                else False

            if self.config.user_market_name_list[choice] == 'zebitex':
                self.config.exchange = self.bot.api.set_exchange('zebitex')
                    # zebitexFormatted.ZebitexFormatted(
                    # self.config.keys[self.config.user_market_name_list[choice]]['apiKey'],
                    # self.config.keys[self.config.user_market_name_list[choice]]['secret'],
                    # False)
            elif self.config.user_market_name_list[choice] == 'zebitex_testnet':
                self.config.exchange = self.bot.api.set_exchange('zebitex')
                    # zebitexFormatted.ZebitexFormatted(
                    # self.config.keys[self.config.user_market_name_list[choice]]['apiKey'],
                    # self.config.keys[self.config.user_market_name_list[choice]]['secret'],
                    # True)
            else:
                self.config.exchange = eval(
                    f'ccxt.{self.config.user_market_name_list[choice]}'
                    f'({str(self.config.keys[self.config.user_market_name_list[choice]])})')
        self.bot.api.load_markets()
        return self.config.user_market_name_list[choice]

    def select_market(self, market=None):
        """Market selection menu.
        return: string, selected market.
        """
        if market:
            if market not in self.bot.api.exchange.symbols:
                raise ValueError(f'{market} not in self.config.exchange.symbols')
            limitation = self.limitation_to_btc_market(market)
            if limitation != True:
                raise ValueError(limitation)
        else:
            valid_choice = False
            while valid_choice is False:
                self.bot.applog.info(
                    f'Please enter the name of a market: {self.bot.api.exchange.symbols}')
                market = input(' >> ').upper()
                limitation = self.limitation_to_btc_market(market)
                if limitation is True:
                    if market in self.bot.api.exchange.symbols:
                        valid_choice = True
                else:
                    self.bot.applog.info(limitation)
        self.config.selected_market = market
        return market

    def change_spread(self, params):
        spread = self.ask_params_spread()
        for key, value in spread.items():
            params[key] = spread[key]
        return params

    def wait_for_funds(self):
        """The answer is in the question!"""
        q = 'Waiting for funds to arrive, (y) when you\'re ready, (n) to leave.'
        if not self.simple_question(q):
            self.config.exit()

    def send_slack_message(self, message):
        """Send a message to slack channel.
        message: string.
        return: slack object"""
        try:
            message = str(message)
            self.bot.stratlog.warning(message)
            if self.bot.slack:
                rsp = self.bot.slack.send_slack_message(
                text=message)
            if rsp['ok'] is False:
                for item in rsp:
                    raise ValueError(item)
            return rsp
        except Exception as e:
            self.bot.applog.critical(f'Something went wrong with slack: {e}')
            return

    def log_file_reader(self):
        """Import the last 20 order from strat.log and organize it.
        return: None or dict containing : list of exectuted buy,
                                          list of executed sell,
                                          dict of parameters
        """
        strat_log_file = f'{self.config.root_path}logger/logfiles/strat.log'
        raw_data = []
        logs_data = {'buy': [], 'sell': []}
        # In case there is no log file
        if not self.create_file_when_none(strat_log_file):
            self.bot.applog.warning("strat.log file have been created")
            return
        self.bot.applog.debug("Reading the strat.log file")
        nb_of_lines = self.file_line_counter(strat_log_file)
        print(nb_of_lines)
        # In case the log file is empty
        if not nb_of_lines:
            self.bot.applog.warning('Your strat.log file was empty')
            return
        target = nb_of_lines - 20 if nb_of_lines > 20 else 0
        # Get the last 20 orders saved in log file
        while target < nb_of_lines:
            line = self.read_one_line(strat_log_file, nb_of_lines)
            try:
                line = json.loads(line)
                raw_data.append(line)
            except Exception as e:
                target = target - 1 if target - 1 >= 0 else target
            nb_of_lines -= 1
        # It's better when it's pretty to display
        for order in raw_data:
            formated_order = self.bot.api.format_log_order(
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
        self.bot.api.display_user_trades(logs_data)
        return logs_data

    def params_reader(self, file_path):
        """Load parameters from params.txt.
        file_path: string, params.txt relative path.
        return: dict with valid parameters, or False.
        """
        if not self.create_file_when_none(file_path):
            self.bot.applog.warning('There was no params.txt. One have been created')
            return
        try:
            params = json.loads(self.read_one_line(file_path, 0))
        except Exception as e:
            msg = f'Something went wrong when loading params: {e}'
            self.bot.applog.warning(msg)
            return
        params = self.check_params(params)
        return params

    def check_params(self, params):
        """Check the integrity of all parameters and return False if it's not.
        params: dict, params in string format.
        return: dict with formatted parameters, or False.
        """
        try:
            # Check if values exist
            if not params['datetime']:
                raise ValueError('Datetime isn\'t set')
            if not params['marketplace']:
                raise ValueError('Market isn\'t set')
            if not params['market']:
                raise ValueError('Market isn\'t set')
            if not params['range_bot']:
                raise ValueError('The bottom of the range isn\'t set')
            if not params['range_top']:
                raise ValueError('The top of the range isn\'t set')
            if not params['spread_bot']:
                raise ValueError('The bottom of the spread isn\'t set')
            if not params['spread_top']:
                raise ValueError('The bottom of the spread isn\'t set')
            if not params['increment_coef']:
                raise ValueError('Increment coeficient isn\'t set')
            if not params['amount']:
                raise ValueError('Amount isn\'t set')
            if not params['stop_at_bot']:
                raise ValueError('Stop at bottom isn\'t set')
            if not params['stop_at_top']:
                raise ValueError('Stop at top isn\'t set')
            if not params['nb_buy_to_display']:
                raise ValueError('Number of buy displayed isn\'t set')
            if not params['nb_sell_to_display']:
                raise ValueError('Number of sell displayed isn\'t set')
            if not params['profits_alloc']:
                raise ValueError('Benefices allocation isn\'t set')
            # Convert values
            error_message = f"params['range_bot'] is not a string:"
            params['range_bot'] = self.str_to_decimal(
                params['range_bot'], error_message)
            error_message = f"params['range_top'] is not a string:"
            params['range_top'] = self.str_to_decimal(
                params['range_top'], error_message)
            error_message = f"params['spread_bot'] is not a string:"
            params['spread_bot'] = self.str_to_decimal(params['spread_bot'],
                                                       error_message)
            error_message = f"params['spread_top'] is not a string:"
            params['spread_top'] = self.str_to_decimal(params['spread_top'],
                                                       error_message)
            error_message = f"params['increment_coef'] is not a string:"
            params['increment_coef'] = self.str_to_decimal(
                params['increment_coef'], error_message)
            error_message = f"params['amount'] is not a string:"
            params['amount'] = self.str_to_decimal(
                params['amount'], error_message)
            error_message = f"params['stop_at_bot'] is not a boolean:"
            params['stop_at_bot'] = self.str_to_bool(params['stop_at_bot'],
                                                     error_message)
            error_message = f"params['stop_at_top'] is not a boolean:"
            params['stop_at_top'] = self.str_to_bool(params['stop_at_top'],
                                                     error_message)
            error_message = f"params['nb_buy_to_display'] is not an int:"
            params['nb_buy_to_display'] = self.str_to_int(
                params['nb_buy_to_display'], error_message)
            error_message = f"params['nb_sell_to_display'] is not an int:"
            params['nb_sell_to_display'] = self.str_to_int(
                params['nb_sell_to_display'], error_message)
            error_message = f"params['profits_alloc'] is not an int:"
            params['profits_alloc'] = self.str_to_decimal(params['profits_alloc'],
                                                          error_message)
            self.bot.applog.debug(f'param_checker, params: {params}')
            # Test if values are correct
            self.is_date(params['datetime'])
            if params['marketplace'] not in self.config.exchanges_list:
                raise ValueError(f"You can't choose {params['marketplace']}"
                                 f" as marketplace")
            if params['marketplace'] not in self.config.keys:
                raise ValueError(f"You don't own api key for"
                                 f" {params['marketplace']}")
            self.select_marketplace(params['marketplace'])
            self.select_market(params['market'])
            self.param_checker_range_bot(params['range_bot'])
            self.param_checker_range_top(params['range_top'])
            self.param_checker_interval(params['increment_coef'])
            self.config.intervals = self.bot.interval_generator(params['range_bot'],
                                                     params['range_top'],
                                                     params['increment_coef'])
            if self.config.intervals is False:
                raise ValueError(
                    f'Range top value is too low, or increment too '
                    f'high: need to generate at lease 6 intervals.')
            if params['spread_bot'] not in self.config.intervals:
                raise ValueError('Spread_bot isn\'t properly configured')
            spread_bot_index = self.config.intervals.index(params['spread_bot'])
            if params['spread_top'] != self.config.intervals[spread_bot_index + 1]:
                raise ValueError('Spread_top isn\'t properly configured')
            self.param_checker_amount(params['amount'], params['spread_bot'])
            self.param_checker_profits_alloc(params['profits_alloc'])
        except Exception as e:
            self.bot.applog.warning(f'The LW parameters are not well configured: {e}')
            return False
        return params




    def str_to_decimal(self, s, error_message=None):
        """Convert a string to Decimal or raise an error.
        s: string, element to convert
        error_message: string, error message detail to display if fail.
        return: Decimal."""
        try:
            return Decimal(str(s))
        except Exception as e:
            raise ValueError(f'{error_message} {e}')

    def is_date(self, str_date):
        """Check if a date have a valid formating.
        str_date: string
        """
        try:
            return datetime.strptime(str_date, '%Y-%m-%d %H:%M:%S.%f')
        except Exception as e:
            raise ValueError(f'{str_date} is not a valid date: {e}')

    def str_to_bool(self, s, error_message=None):  # Fancy things can be added
        """Convert a string to boolean or rise an error
        s: string.
        error_message: string, error message detail to display if fail.
        return: bool.
        """
        if s == 'True' or s == 'y':
            return True
        elif s == 'False' or s == 'n':
            return False
        else:
            raise ValueError(f'{error_message} {e}')

    def str_to_int(self, s, error_message=None):
        """Convert a string to an int or rise an error
        s: string.
        error_message: string, error message detail to display if fail.
        return: int.
        """
        try:
            return int(s)
        except Exception as e:
            raise ValueError(f'{error_message} {e}')

    def dict_to_str(self, a_dict):
        """Format dict into a string.
        return: string, formated string for logfile."""
        b_dict = deepcopy(a_dict)
        for key, value in b_dict.items():
            b_dict[key] = str(value)
        b_dict = str(b_dict)
        return b_dict.replace("'", '"')