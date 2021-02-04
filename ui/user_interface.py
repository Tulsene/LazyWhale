import json
from datetime import datetime
from decimal import Decimal

import ccxt

from config import config
import utils.helpers as helper
import utils.converters as convert
import utils.checkers as check
import exchanges.api_manager as api_manager
from main.allocation import AllocationFactory, AbstractAllocation
from main.interval import Interval
import utils.logger_factory as lf


def get_free_balance(params, side):
    if side == "sell":
        crypto = params["market"].split("/")[0]
    else:
        crypto = params["market"].split("/")[1]
    return convert.str_to_decimal(
        params["api_connector"].get_balances()[crypto]["free"]
    )


class UserInterface:
    def __init__(self, api_keys, fees_coef, safety_buy_value, safety_sell_value):
        self.log = lf.get_simple_logger("user_interface")
        self.slack_webhook = None
        self.allowed_exchanges = self.set_keys(api_keys)
        self.root_path = helper.set_root_path()
        self.fees_coef = fees_coef
        self.safety_buy_value = safety_buy_value
        self.safety_sell_value = safety_sell_value

    def set_keys(self, api_keys):
        """Little hack because I'm lazy and I don't want to add another argument to init.
        api_keys: dict.
        return: dict."""
        if "slack_webhook" in api_keys.keys():
            self.slack_webhook = api_keys["slack_webhook"]
            del api_keys["slack_webhook"]

        return api_keys

    def simple_question(self, q):
        """Simple question prompted and response handling.
        q: string, the question to ask.
        return: boolean True or None, yes of no
        """
        while True:
            self.log.info(q)
            choice = input(" >> ")
            choice = choice.lower()
            self.log.debug(choice)
            if choice in ["yes", "y", "o", "oui", "j", "ja", "d", "da"]:
                return True
            if choice in ["no", "nein", "non", "n", "niet"]:
                return False

    def ask_question(self, q, formater_func, control_func=None, control_value=None):
        """Ask any question to the user, control the value returned or ask again.
        q: string, question to ask to the user.
        formater_funct: function, format from string to the right datatype.
        control_funct: optional function, allow to check that the user's choice is
                       within the requested parameters
        return: formated (int, decimal, ...) choice of the user
        """
        self.log.info(q)
        while True:
            try:
                choice = input(" >> ")
                self.log.debug(choice)
                choice = formater_func(choice)

                if control_func:
                    if control_value:
                        control_func(choice, control_value)
                    else:
                        control_func(choice)
                return choice

            except Exception as e:
                self.log.info(f"{q} invalid choice: {choice} -> {e}")

    def ask_to_select_in_a_list(self, q, a_list):
        """Ask to the user to choose between items in a list
        a_list: list.
        q: string.
        return: int, the position of this item"""
        self.log.info(q)
        q = ""
        for i, item in enumerate(a_list, start=1):
            q += f"{i}: {item}, "
        self.log.info(q)

        while True:
            try:
                choice = input(" >> ")
                self.log.debug(choice)
                choice = convert.str_to_int(choice)

                if 0 < choice <= i:
                    return choice - 1
                else:
                    self.log.info(f"You need to enter a number between 1 and {i}")

            except Exception as e:
                self.log.info(f"{q} invalid choice: {choice} -> {e}")

        return choice

    def get_lw_backup(self):
        import jsonpickle
        import os

        lw = None
        backup_path = f"{self.root_path}config/backup_lw.json"
        if os.path.exists(backup_path):
            try:
                with open(backup_path, "r") as f:
                    lw = jsonpickle.decode(f.read())
            except json.JSONDecodeError as e:
                self.log.exception(
                    f"There was an error while restoring lw from backup_lw.json: {e}"
                )

        return lw

    def ask_for_params(self):
        """Allow user to use previous parameter if they exist and backup it.
        At the end of this section, parameters are set and LW can be initialized.
        """
        backup_lw = self.get_lw_backup()
        if backup_lw is not None:
            q = "You have complete previous version of LW, do want to continue it?"
            # backup is fully ready for work
            if self.simple_question(q):
                return backup_lw

        file_path = f"{self.root_path}config/params.json"
        params = self.params_reader(file_path)
        self.log.info(f"Your previous parameters are: {params}")

        if params:
            q = "Do you want to display history from logs?"
            if self.simple_question(q):
                self.history_reader()

            q = "Do you want to use those params?"
            if self.simple_question(q):
                self.check_safety_buy_sell_values(params)
                params = self.check_for_enough_funds(params)
            else:
                params = None
        else:
            self.log.info(
                f"Your parameters are not set correctly: {params}, please enter new one!"
            )

        if not params:
            params = self.enter_params()

        helper.params_writer(file_path, params)

        return params

    def get_allocation_from_params(self, params):
        allocation_factory = AllocationFactory(
            params["allocation_type"],
            params["amount"],
            params["intervals"],
            self.fees_coef,
            params["profits_alloc"],
        )
        return allocation_factory.get_allocation()

    def check_safety_buy_sell_values(self, params: dict):
        max_tries = 100
        count_tries = 0
        while (
            params["api_connector"].get_safety_buy(params["market"]) is not None
            or params["api_connector"].get_safety_sell(params["market"]) is not None
        ) and count_tries < max_tries:
            self.safety_buy_value = check.get_random_decimal(
                convert.multiplier(self.safety_buy_value, Decimal("2")),
                convert.multiplier(self.safety_buy_value, Decimal("10")),
            )
            self.safety_sell_value = check.get_random_decimal(
                convert.multiplier(self.safety_sell_value, Decimal("0.99")),
                convert.multiplier(self.safety_sell_value, Decimal("1.01")),
            )

            params["api_connector"].safety_buy_value = self.safety_buy_value
            params["api_connector"].safety_sell_value = self.safety_sell_value
            count_tries += 1

    def enter_params(self):
        """Series of questions to setup LW parameters.
        return: dict, valid parameters"""
        params = {"datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}
        params.update(self.set_marketplace())
        params.update(self.select_market(params["api_connector"]))

        # check and correct if safety_buy/sell_value set before is correct:
        self.check_safety_buy_sell_values(params)

        params.update(self.ask_range_setup())
        params.update(
            self.ask_params_spread(
                params["api_connector"], params["market"], params["intervals"]
            )
        )
        allocation_type = self.ask_allocation_type()
        params.update(allocation_type)
        if allocation_type["allocation_type"] == "profit_allocation":
            params.update(self.ask_profits_alloc())
        else:
            params.update({"profits_alloc": 0})
        params.update(self.ask_param_amount(params))

        params.update({"allocation": self.get_allocation_from_params(params)})

        # No need to continue further without enough funds
        params = self.check_for_enough_funds(params)

        params.update(self.ask_if_stop())
        params.update(self.ask_nb_to_display(params["intervals"]))
        params.update(self.ask_nb_orders_per_interval())
        params.update(self.ask_price_random_precision(params))
        params.update(self.ask_amount_random_precision(params["amount"]))

        return params

    def set_marketplace(self, marketplace=None, test_mode=None):
        """Select a marketplace among the loaded keys.
        Connect to the selected marketplace.
        return: String, name of the selected marketplace.
        """
        api_connector = api_manager.APIManager(
            self.slack_webhook, self.safety_buy_value, self.safety_sell_value
        )

        if test_mode:
            api_connector.set_zebitex(self.allowed_exchanges["zebitex_testnet"])

        else:
            exchanges_list = list(self.allowed_exchanges.keys())
            if not marketplace:
                q = "Please select a market:"
                choice = self.ask_to_select_in_a_list(q, self.allowed_exchanges)
            else:
                choice = exchanges_list.index(marketplace)
            # Because kraken balance do not return free and used balance
            api_connector.is_kraken = (
                True
                if self.allowed_exchanges[exchanges_list[choice]] == "kraken"
                else False
            )

            if exchanges_list[choice] in ["zebitex", "zebitex_testnet"]:
                api_connector.set_zebitex(
                    self.allowed_exchanges[exchanges_list[choice]],
                    exchanges_list[choice],
                )

            else:
                api_connector.exchange = eval(
                    f"ccxt.{exchanges_list[choice]}"
                    f"({self.allowed_exchanges[exchanges_list[choice]]})"
                )

        # for binance_testnet or other testnet purpose only
        # api_connector.exchange.set_sandbox_mode(True)
        api_connector.load_markets()

        return {
            "marketplace": marketplace if marketplace else exchanges_list[choice],
            "api_connector": api_connector,
        }

    def select_market(self, api_connector, market=None):
        """Market selection menu.
        return: string, selected market.
        """
        if market:
            if market not in api_connector.exchange.symbols:
                raise ValueError(
                    f"{market} not in api_connector.exchange.symbols: "
                    f"{api_connector.exchange.symbols}"
                )

            limitation = check.limitation_to_btc_market(market)
            if limitation != True:
                raise ValueError(limitation)
        else:
            while True:
                self.log.info(
                    f"Please enter the name of a market: {api_connector.exchange.symbols}"
                )
                market = input(" >> ").upper()
                allowed = check.limitation_to_btc_market(market)
                if allowed == True:
                    if market in api_connector.exchange.symbols:
                        return {"market": market}
                else:
                    self.log.info(allowed)

    def ask_range_setup(self):
        """Ask to the user to enter the range and increment parameters.
        return: dict, asked parameters."""
        while True:
            try:
                range_bot = self.ask_param_range_bot()
                range_top = self.ask_param_range_top(range_bot)
                increment = self.ask_param_increment()
                intervals = helper.interval_generator(range_bot, range_top, increment)
                return {
                    "range_bot": range_bot,
                    "range_top": range_top,
                    "increment_coef": increment,
                    "intervals": intervals,
                }

            except Exception as e:
                self.log.exception(f"{e}")

    def ask_param_increment(self):
        """Ask the user to enter a value for the spread between each order.
        return: decimal."""
        q = "How much % of spread between two orders? It must be " "between 1% and 50%"
        return self.ask_question(q, check.increment_coef_buider)

    def ask_param_range_bot(self):
        """Ask the user to enter a value for the bottom of the range.
        return: decimal."""
        q = (
            "Enter a value for the bottom of the range. It must be "
            "superior to 1 satoshi (10^-8 btc):"
        )
        return self.ask_question(q, convert.str_to_decimal, check.range_bot)

    def ask_param_range_top(self, range_bot):
        """Ask the user to enter a value for the top of the range.
        return: decimal."""
        q = (
            "Enter a value for the top of the range. It must be "
            "inferior to 0.99 BTC:"
        )
        return self.ask_question(q, convert.str_to_decimal, check.range_top, range_bot)

    def ask_params_spread(self, api_connector, selected_market, intervals):
        """Ask to the user to choose between value for spread bot and setup
        spread top automatically
        return: dict, of decimal values
        """
        price = api_connector.get_market_last_price(selected_market)
        msg = f"The actual price of {selected_market} is {price}"
        self.log.info(msg)

        q = (
            "Please select the price of your highest buy interval "
            f"(spread_bot) in the list. {intervals[-2]} can't be selected"
        )
        position = self.ask_to_select_in_a_list(q, intervals[:-2])

        self.log.info(
            f"The price of your lowest sell interval is {intervals[position + 2]}"
        )

        return {"spread_bot": position, "spread_top": position + 3}

    def calculate_amount_suggestion(self, params: dict, funds: Decimal):
        """Calculate amount suggestion for user to simplify user calculation (depends on allocation strategy)"""
        # cheat to use allocation_factory
        params.update({"amount": Decimal("1")})
        allocation = self.get_allocation_from_params(params)
        total_interval_amount_coefficient = Decimal("0")
        for i in range(params["spread_top"], len(params["intervals"])):
            total_interval_amount_coefficient += allocation.get_amount(i, "sell")

        return convert.divider(funds, total_interval_amount_coefficient)

    def ask_param_amount(self, params):
        """Ask the user to enter a value of ALT to sell at each order.
        selected_market: string.
        range_bot: Decimal.
        return: Decimal."""
        sell_balance = get_free_balance(params, "sell")

        suggestion = self.calculate_amount_suggestion(params, sell_balance)

        q = (
            f"How much {params['market'][:4]} do you want to sell "
            f"per interval? It must be between "
            f"{Decimal('0.001') / params['range_bot']} and 10000000."
            f"Suggestion:  {suggestion}"
        )

        while True:
            try:
                amount = self.ask_question(q, convert.str_to_decimal)
                check.amount(amount, params["range_bot"])
                return {"amount": amount}

            except Exception as e:
                self.log.info(f"{e}")

    def ask_nb_to_display(self, intervals):
        """Ask how much buy and sell intervals are going to be in the book.
        return: dict, nb_buy_to_display + nb_sell."""
        max_size = len(intervals) - 3
        result = []
        for side in ["buy", "sell"]:
            q = (
                f"How many {side} intervals do you want to display? It must be "
                f"less than {max_size}. 0 value = {max_size} :"
            )
            result.append(
                self.ask_question(q, convert.str_to_int, check.nb_to_display, max_size)
            )

        return {"nb_buy_to_display": result[0], "nb_sell_to_display": result[1]}

    def ask_nb_orders_per_interval(self):
        """Ask user to enter number of orders to be opened in each interval"""
        q = "How many orders should be opened in each price interval?" "Suggestion: 2"
        max_size = 10
        return {
            "orders_per_interval": self.ask_question(
                q, convert.str_to_int, check.nb_orders_per_interval, max_size
            )
        }

    @staticmethod
    def _found_suggested_precision(max_suggested: Decimal):
        result = Decimal("1e-8")
        while result * 10 <= max_suggested:
            result *= 10

        return result

    def ask_price_random_precision(self, params):
        """Ask user, about possible price precision for performing random"""
        max_precision = max(
            self._found_suggested_precision(
                convert.divider(
                    params["intervals"][0].get_top()
                    - params["intervals"][0].get_bottom(),
                    Decimal(params["orders_per_interval"]),
                )
            ),
            config.DECIMAL_PRECISION,
        )
        suggested = max(convert.divider(max_precision, Decimal('10')), config.DECIMAL_PRECISION)
        q = (
            f"What should be the precision in random price? (Must be >= 1e-8, <= {max_precision})"
            f"\nDefault: 1e-8, Suggested: {suggested}"
        )
        return {
            "price_random_precision": self.ask_question(
                q, convert.str_to_decimal, check.random_precision, suggested
            )
        }

    def ask_amount_random_precision(self, amount_per_interval):
        """Ask user, about possible amount precision for performing random"""
        max_precision = max(
            self._found_suggested_precision(
                convert.divider(amount_per_interval, Decimal("100"))
            ),
            config.DECIMAL_PRECISION,
        )
        suggested = max(convert.divider(max_precision, Decimal('10')), config.DECIMAL_PRECISION)
        q = (
            f"What should be the precision in random amount? (Must be >= 1e-8, <= {max_precision})"
            f"\nDefault: 1e-8, Suggested: {suggested}"
        )
        return {
            "amount_random_precision": self.ask_question(
                q, convert.str_to_decimal, check.random_precision, suggested
            )
        }

    def ask_allocation_type(self):
        types = (
            "no_specific_allocation",
            "linear_allocation",
            "curved_allocation",
            "profit_allocation",
        )
        q = "Please select the amount allocation you want to use"
        position = self.ask_to_select_in_a_list(q, types)
        return {"allocation_type": types[position]}

    def ask_if_stop(self):
        q1 = "Do you want to stop LW if range_bot is reach? (y) or (n) only."
        q2 = "Do you want to stop LW if range_top is reach? (y) or (n) only."

        return {
            "stop_at_bot": self.ask_question(q1, convert.str_to_bool),
            "stop_at_top": self.ask_question(q2, convert.str_to_bool),
        }

    def ask_profits_alloc(self):
        """Ask for profits allocation.
        return: int."""
        q = (
            "How do you want to allocate your profits in %. It must "
            "be between 1 and 100, both included:"
        )
        return {
            "profits_alloc": self.ask_question(
                q, convert.str_to_int, check.profits_alloc
            )
        }

    def change_params(self, params):
        """Allow the user to change one LW parameter.
        params: dict, all the parameter for LW.
        return: dict."""
        editable_params = (
            ("range_bot", self.ask_param_range_bot),
            ("range_top", self.ask_param_range_top),
            ("increment_coef", self.ask_param_increment),
            ("amount", self.ask_param_amount),
        )
        question = "What parameter do you want to change?"
        question_list = [
            f"The bottom of the range: {params['range_bot']}?\n",
            f"The top of the range: {params['range_top']}?\n",
            f"The spread between orders? {params['spread_bot']}\n",
            f"The amount of {params['market'].split('/')[0]} per orders?\n",
            f"Select the highest buy order?: {params['spread_bot']}\n",
            "Add funds to your account\n",
        ]

        while True:
            try:
                choice = self.ask_to_select_in_a_list(question, question_list)
                if choice < 3:
                    params[editable_params[choice][0]] = editable_params[choice][1]()
                    params["intervals"] = helper.interval_generator(
                        params["range_bot"],
                        params["range_top"],
                        params["increment_coef"],
                    )
                    params = self.change_spread(params)

                elif choice == 3:
                    params[editable_params[choice][0]] = editable_params[choice][1](
                        params
                    )["amount"]

                elif choice == 4:
                    params = self.change_spread(params)

                else:
                    self.wait_for_funds()

                break

            except Exception as e:
                self.log.exception(f"{e}")

        return params

    def change_spread(self, params):
        spread = self.ask_params_spread(
            params["api_connector"], params["market"], params["intervals"]
        )
        for key, value in spread.items():
            params[key] = value
        return params

    def wait_for_funds(self):
        """The answer is in the question!"""
        q = "Waiting for funds to arrive, (y) when you're ready, (n) to leave."
        if not self.simple_question(q):
            raise SystemExit("Ok, see you later then!")

    def history_reader(self):
        """Import the last 20 order from strat.log and organize it.
        return: None or dict containing : list of executed buy,
                                          list of executed sell,
                                          dict of parameters
        """
        file_path = f"{self.root_path}logs/history.txt"
        last_line = self.check_history_file(file_path)

        if not last_line:
            return None

        line_nb = last_line - 20 if last_line > 20 else 0
        # Get the last 20 orders saved in log file
        while line_nb < last_line:
            print(helper.read_one_line(file_path, line_nb))
            line_nb += 1

    def check_history_file(self, file_path):
        """Better to read when there is something to do so.
        file_path: string.
        return: int."""
        if helper.create_file_when_none(file_path):
            self.log.info("history.txt file have been created")
            return None

        self.log.debug("Reading the strat.log file")
        nb_of_lines = helper.file_line_counter(file_path)

        if not isinstance(nb_of_lines, int):
            self.log.info("Your strat.log file was empty")
            return None

        return nb_of_lines

    def params_reader(self, file_path):
        """Load parameters from params.json.
        file_path: string, params.json relative path.
        return: dict with valid parameters, or False.
        """
        if helper.create_file_when_none(file_path):
            self.log.info(f"There was no {file_path}. One have been created")
            return None

        try:
            return self.check_params(json.loads(helper.read_one_line(file_path, 0)))

        except Exception as e:
            self.log.exception(f"Something went wrong when loading params: {e}")
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
            if params["marketplace"] not in self.allowed_exchanges:
                raise ValueError(
                    f"You can't choose {params['marketplace']}" f" as marketplace"
                )

            params.update(self.set_marketplace(params["marketplace"]))
            self.select_market(params["api_connector"], params["market"])

            check.is_date(params["datetime"])
            check.range_bot(params["range_bot"])
            check.range_top(params["range_top"], params["range_bot"])
            check.interval(params["increment_coef"])
            check.amount(params["amount"], params["range_bot"])
            check.profits_alloc(params["profits_alloc"])

            params.update(
                {
                    "intervals": helper.interval_generator(
                        params["range_bot"],
                        params["range_top"],
                        params["increment_coef"],
                    )
                }
            )

            params.update({"allocation": self.get_allocation_from_params(params)})

            if params["spread_top"] - params["spread_bot"] != 3:
                raise ValueError("Spread_bot isn't properly configured")

        except Exception as e:
            self.log.exception(f"The LW parameters are not well configured: {e}")
            return False

        return params

    def check_value_presences(self, params):
        params_names = [
            "datetime",
            "marketplace",
            "market",
            "range_bot",
            "range_top",
            "spread_bot",
            "spread_top",
            "increment_coef",
            "amount",
            "stop_at_bot",
            "stop_at_top",
            "nb_buy_to_display",
            "orders_per_interval",
            "allocation_type",
            "nb_sell_to_display",
            "profits_alloc",
            "price_random_precision",
            "amount_random_precision",
        ]

        for name in params_names:
            if not params[name]:
                raise ValueError(f"{name} is not set in parameters")

        return params

    def convert_params(self, params):
        decimal_to_test = [
            "range_bot",
            "range_top",
            "increment_coef",
            "amount",
            "profits_alloc",
            "price_random_precision",
            "amount_random_precision",
        ]

        for name in decimal_to_test:
            error_message = f"params['{name}'] is not a string:"
            params[name] = convert.str_to_decimal(params[name], error_message)

        for name in ["stop_at_bot", "stop_at_top"]:
            error_message = f"params['{name}'] is not a boolean:"
            params[name] = convert.str_to_bool(params[name], error_message)

        for name in [
            "nb_buy_to_display",
            "nb_sell_to_display",
            "spread_bot",
            "spread_top",
            "orders_per_interval",
        ]:
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
            price = params["api_connector"].get_market_last_price(params["market"])
            balances = params["api_connector"].get_balances()
            pair = params["market"].split("/")
            sell_balance = convert.str_to_decimal(balances[pair[0]]["free"])
            buy_balance = convert.str_to_decimal(balances[pair[1]]["free"])
            spread_bot_index = params["spread_bot"]
            spread_top_index = spread_bot_index + 3
            try:
                total_buy_funds_needed = self.calculate_buy_funds(
                    spread_bot_index, params["allocation"], params["intervals"]
                )
                total_sell_funds_needed = self.calculate_sell_funds(
                    spread_top_index, params["allocation"], params["intervals"]
                )
                msg = (
                    f"check_for_enough_funds total_buy_funds_needed: "
                    f"{total_buy_funds_needed}, buy_balance: {buy_balance}, "
                    f"total_sell_funds_needed: {total_sell_funds_needed}, "
                    f"sell_balance: {sell_balance}, price: {price}"
                )
                self.log.info(msg)

                # When the strategy start with spread bot inferior or
                # equal to the actual market price
                if params["intervals"][params["spread_bot"]].get_top() <= price:
                    total_buy_funds_needed = self.sum_buy_needs(
                        params, spread_top_index, total_buy_funds_needed, price
                    )
                # When the strategy start with spread bot superior to the
                # actual price on the market
                else:
                    total_sell_funds_needed = self.sum_sell_needs(
                        params, spread_bot_index, total_sell_funds_needed, price
                    )

                msg = (
                    f"Your actual strategy require: {pair[1]} needed: "
                    f"{total_buy_funds_needed} and you have {buy_balance} "
                    f"{pair[1]}; {pair[0]} needed: {total_sell_funds_needed}"
                    f" and you have {sell_balance} {pair[0]}."
                )
                self.log.info(msg)

                buy_balance, sell_balance = self.search_more_funds(
                    total_buy_funds_needed,
                    total_sell_funds_needed,
                    buy_balance,
                    sell_balance,
                    params,
                )

                return params
            except ValueError as e:
                self.log.exception(f"You need to change some parameters: {e}")
                params = self.change_params(params)

    def calculate_buy_funds(
        self, index: int, allocation: AbstractAllocation, intervals: [Interval]
    ):
        """Calculate the buy funds required to execute the strategy
        amount: Decimal, allocated ALT per order
        return: Decimal, funds needed
        """
        buy_funds_needed = Decimal("0")
        i = 0
        while i <= index:
            buy_funds_needed += intervals[i].get_top() * allocation.get_amount(i, "buy")
            i += 1
        return buy_funds_needed

    def calculate_sell_funds(
        self, index: int, allocation: AbstractAllocation, intervals: [Interval]
    ):
        """Calculate the sell funds required to execute the strategy
        amount: Decimal, allocated ALT per order
        return: Decimal, funds needed
        """
        sell_funds_needed = Decimal("0")
        i = len(intervals) - 1
        while i >= index:
            sell_funds_needed += allocation.get_amount(i, "sell")
            i -= 1
        return sell_funds_needed

    def sum_buy_needs(self, params, spread_top_index, total_buy_funds_needed, price):
        incoming_buy_funds = Decimal("0")
        i = spread_top_index
        # When the whole strategy is lower than actual price
        if params["range_top"] < price:
            while i < len(params["intervals"]):
                incoming_buy_funds += convert.multiplier(
                    params["intervals"][i].get_top(),
                    params["allocation"].get_amount(i, "buy"),
                    self.fees_coef,
                )
                i += 1
        # When only few sell orders are planned to be under the
        # actual price
        else:
            while params["intervals"][i].get_top() <= price:
                incoming_buy_funds += convert.multiplier(
                    params["intervals"][i].get_top(),
                    params["allocation"].get_amount(i, "buy"),
                )
                i += 1
                # It crash when price >= range_top
                if i == len(params["intervals"]):
                    break

        return total_buy_funds_needed - incoming_buy_funds

    def sum_sell_needs(self, params, spread_bot_index, total_sell_funds_needed, price):
        incoming_sell_funds = Decimal("0")
        i = spread_bot_index
        # When the whole strategy is upper than actual price
        if params["spread_bot"] > price:
            while i >= 0:
                incoming_sell_funds += params["allocation"].get_amount(i, "sell")
                i -= 1
        # When only few buy orders are planned to be upper the
        # actual price
        else:
            while params["intervals"][i].get_bottom() >= price:
                incoming_sell_funds += params["allocation"].get_amount(i, "sell")
                i -= 1
                if i < 0:
                    break

        return total_sell_funds_needed - incoming_sell_funds

    def look_for_more_funds(self, params, funds_needed, funds, side):
        """Look into open orders how much funds there is, offer to cancel orders not
        in the strategy.
        funds_needed: Decimal, how much funds are needed for the strategy.
        funds: Decimal, sum of available funds for the strategy.
        side: string, buy or sell.
        return: Decimal, sum of available funds for the strategy."""
        orders = params["api_connector"].get_open_orders()

        funds, orders_outside_strat = self.sum_open_orders(params, side, orders, funds)

        # If there is still not enough funds but there is open orders outside the
        # strategy
        if funds > Decimal("0"):
            if orders_outside_strat:
                funds = self.ask_cancel_orders(
                    params, orders_outside_strat, funds, funds_needed, side
                )

        return funds

    def sum_open_orders(self, params, side, orders, funds):
        """simple addition of funds stuck in open order and will be used for the
        strategy"""
        orders_outside_strat = []
        for order in orders:
            if side == "buy":
                if order.side == "buy":
                    if (
                        order.price < params["range_bot"]
                        or order.price == self.safety_buy_value
                    ):
                        funds += order.price * order.amount
                    else:
                        orders_outside_strat.append(order)

            else:
                if order.side == "sell":
                    if (
                        order.price > params["range_top"]
                        or order.price == self.safety_sell_value
                    ):
                        funds += order.amount
                    else:
                        orders_outside_strat.append(order)

        return funds, orders_outside_strat

    def ask_cancel_orders(
        self, params, orders_outside_strat, funds, funds_needed, side
    ):
        while True:
            if not orders_outside_strat:
                break
            q = (
                f"Do you want to remove some orders outside of the "
                f"strategy to get enough funds to run it? (y or n)"
            )
            if self.simple_question(q):
                q = "Which order do you want to remove:"
                rsp = self.ask_to_select_in_a_list(q, orders_outside_strat)
                order = orders_outside_strat[rsp]
                del orders_outside_strat[rsp]
                rsp = params["api_connector"].cancel_order(order)
                if rsp:
                    if side == "buy":
                        funds += order.price * order.amount
                    else:
                        funds += order.amount
                    self.log.info(
                        (
                            f"You have now {get_free_balance(params, side)} {side} "
                            f"funds and you need {funds_needed}."
                        )
                    )
            else:
                break

        return funds

    def search_more_funds(
        self,
        total_buy_funds_needed,
        total_sell_funds_needed,
        buy_balance,
        sell_balance,
        params,
    ):
        """In case there is not enough funds, check if there is none stuck
        before asking to change params"""
        if total_buy_funds_needed > buy_balance:
            buy_balance = self.look_for_more_funds(
                params, total_buy_funds_needed, buy_balance, "buy"
            )

        if total_sell_funds_needed > sell_balance:
            sell_balance = self.look_for_more_funds(
                params, total_sell_funds_needed, buy_balance, "sell"
            )

        if (
            total_buy_funds_needed > buy_balance
            or total_sell_funds_needed > sell_balance
        ):
            raise ValueError("You don't own enough funds!")

        return buy_balance, sell_balance
