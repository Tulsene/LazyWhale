import json
from copy import deepcopy
from decimal import Decimal
from time import sleep
import jsonpickle

import ccxt

import utils.helpers as helper
import utils.converters as convert
from main.allocation import ProfitAllocation
from main.interval import Interval
from main.order import Order
from ui.user_interface import UserInterface
from utils.checkers import is_equal_decimal
import config.config as config
import utils.logger_factory as lf
from utils.logger_factory import Logger


class LazyWhale:
    """Core strategy for LW.
    open order = [id, price, amount, value, timestamp, date]"""

    def __init__(self, preset_params=False):
        self.root_path = helper.set_root_path()
        self.log = self.set_app_log()
        self.preset_params = preset_params
        self.keys = self.keys_initialisation()
        self.fees_coef = config.FEES_COEFFICIENT

        self.ui = UserInterface(
            self.keys, self.fees_coef, config.SAFETY_BUY_VALUE, config.SAFETY_SELL_VALUE
        )

        self.safety_buy_value = self.ui.safety_buy_value
        self.safety_sell_value = self.ui.safety_sell_value

        self.open_orders = {"sell": [], "buy": []}
        self.params = {}
        self.connector = None
        self.intervals: [Interval] = []
        self.amounts = []
        self.id_list = []
        self.max_sell_index = 0
        self.sides = ("buy", "sell")
        # calculated properly in set_min_amount
        self.min_amount = Decimal("0")
        self.remaining_amount_to_open_buy = Decimal("0")
        self.remaining_amount_to_open_sell = Decimal("0")
        self.allocation = None

    def set_app_log(self) -> Logger:
        lf.set_simple_logger(self.root_path)

        return lf.get_simple_logger("lazy_whale")

    def keys_initialisation(self):
        """Check if a key.json file exist and create one if none.
        return: dict, with all api keys found.
        """
        keys_path = f"{self.root_path}config/keys.json"
        if helper.create_file_when_none(keys_path):
            self.log.critical(
                (
                    "No file keys.json was found, an empty one has been created, "
                    "please fill it as indicated in the documentation"
                )
            )
            raise SystemExit

        else:
            api_keys = self.keys_file_reader(keys_path)
            if not api_keys:
                self.log.critical(
                    (
                        "Your keys.json file is empty, please "
                        "fill it as indicated to the documentation"
                    )
                )
                raise SystemExit

        return api_keys

    def keys_file_reader(self, keys_path):
        """Check the consistence of datas in keys.json.
        return: dict, api keys
        """
        name_list = ccxt.exchanges + ["zebitex", "zebitex_testnet", "slack_webhook"]
        api_keys = {}
        with open(keys_path, mode="r", encoding="utf-8") as keys_file:
            try:
                keys_json = json.load(keys_file)

            except Exception as e:
                self.log.exception(f"keys.json file is not correct : {e}")
                raise SystemExit

            try:
                if "marketPlaces" not in keys_json:
                    raise IndexError(
                        "json is not formatted correctly: marketPlaces key not exists"
                    )

                for market_place_name, market_place_info in keys_json[
                    "marketPlaces"
                ].items():
                    if market_place_name not in name_list:
                        raise NameError("The marketplace name is invalid!")

                    api_keys[market_place_name] = market_place_info

                if "slack_webhook" not in keys_json:
                    raise IndexError(
                        "json is not formatted correctly: slack_webhook key not exists"
                    )

                self.log.set_slack(keys_json["slack_webhook"])
                api_keys["slack_webhook"] = keys_json["slack_webhook"]

            except Exception as e:
                self.log.exception(f"Something went wrong : {e}")
                raise SystemExit

        return api_keys

    def strat_init(self):
        """Prepare open orders on the market by asking to the user if he want
        to remove some outside the strategy or remove those that don't have
        the right amount of alts.
        return: dict, of open orders used for the strategy.
        """
        self.log.debug("strat_init()")
        self.set_min_amount()
        self.connector.intervals = self.intervals

        lowest_buy, highest_sell = self.get_lowest_highest_interval_index()

        self.log.info(
            f"self.intervals: {self.intervals}, "
            f'lowest_buy: {lowest_buy}, self.params["spread_bot"]: '
            f"{self.params['spread_bot']}, self.params['spread_top']: "
            f"{self.params['spread_top']}, highest_sell: {highest_sell}"
        )

        self.set_first_intervals()

    def get_lowest_highest_interval_index(self):
        lowest_interval = max(
            0, self.params["spread_bot"] - self.params["nb_buy_to_display"] + 1
        )
        highest_interval = min(
            len(self.intervals),
            self.params["spread_top"] + self.params["nb_sell_to_display"] - 1,
        )
        return lowest_interval, highest_interval

    def set_first_intervals(self) -> None:
        """Open intervals due to parameters and store in the self.intervals:
        spread_bot - index of bottom interval
        spread_top - index of top interval
        nb_buy_to_display - number intervals to buy
        nb_sell_to_display - number intervals to sell
        amount - total amount of MANA in each interval (except not fulfilled)
        orders_per_interval - amount of orders in each intervals (except not fully)
        """
        lowest_interval, highest_interval = self.get_lowest_highest_interval_index()
        existing_intervals = self.connector.get_intervals()

        intervals_buy = []
        intervals_sell = []

        for interval_idx in reversed(
            range(lowest_interval, self.params["spread_bot"] + 1)
        ):
            if existing_intervals[interval_idx].get_buy_orders():
                self.connector.cancel_orders(
                    existing_intervals[interval_idx].get_buy_orders()
                )

            intervals_buy.append(
                {
                    "interval_index": interval_idx,
                    "amount": self.allocation.get_amount(
                        interval_index=interval_idx, side="buy"
                    ),
                }
            )

        for interval_idx in range(self.params["spread_top"], highest_interval + 1):
            if existing_intervals[interval_idx].get_sell_orders():
                self.connector.cancel_orders(
                    existing_intervals[interval_idx].get_sell_orders()
                )

            intervals_sell.append(
                {
                    "interval_index": interval_idx,
                    "amount": self.allocation.get_amount(
                        interval_index=interval_idx, side="sell"
                    ),
                }
            )

        self.execute_orders(
            self.intervals,
            self.prepare_orders(intervals_buy),
            self.prepare_orders(intervals_sell),
        )

    def set_safety_orders(self):
        """Add safety orders to lock funds for the strategy.
        lowest_buy_index: int.
        highest_sell_index: int."""
        lowest_interval, highest_interval = self.get_lowest_highest_interval_index()
        self.log.debug(
            f"set_safety_orders(), lowest_buy_index: {lowest_interval}, "
            f"highest_sell_index: {highest_interval}"
        )

        if lowest_interval > 0:
            self.create_safety_buy(lowest_interval)

        if highest_interval < len(self.intervals) - 1:
            self.create_safety_sell(highest_interval)

        self.log.info(
            f"safety buy: {self.connector.get_safety_buy()} , "
            f"safety sell: {self.connector.get_safety_sell()}"
        )

    def create_safety_buy(self, lowest_buy_index):
        buy_sum = Decimal("0")
        index = lowest_buy_index - 1
        while index >= 0:
            buy_sum += convert.divider(
                convert.multiplier(
                    self.allocation.get_amount(interval_index=index, side="buy"),
                    self.intervals[index].get_top(),
                ),
                self.safety_buy_value,
            )
            index -= 1

        self.log.debug(f"buy_sum: {buy_sum}, lowest_buy_index: {lowest_buy_index}")

        self.connector.init_limit_buy_order(
            self.params["market"], buy_sum, self.safety_buy_value
        )

    def create_safety_sell(self, highest_sell_index):
        sell_sum = Decimal("0")
        index = highest_sell_index + 1

        while index < len(self.intervals):
            sell_sum += self.allocation.get_amount(interval_index=index, side="sell")
            index += 1

        self.log.debug(
            f"sell_sum: {sell_sum}, highest_sell_index: "
            f"{highest_sell_index}, max_index: "
            f"{index}"
        )

        self.connector.init_limit_sell_order(
            self.params["market"], sell_sum, self.safety_sell_value
        )

    def cancel_safety_orders(self):
        self.cancel_safety_buy()
        self.cancel_safety_sell()

    def cancel_safety_buy(self):
        safety_buy = self.connector.get_safety_buy()
        if safety_buy:
            self.connector.cancel_order(safety_buy)

    def cancel_safety_sell(self):
        safety_sell = self.connector.get_safety_sell()
        if safety_sell:
            self.connector.cancel_order(safety_sell)

    def get_orders_id_list(self) -> [str]:
        """Get the list of all opened orders id"""
        orders_id_list: [str] = []
        for index in helper.get_indexes_buy_intervals(self.intervals):
            orders_id_list.extend(
                [order.id for order in self.intervals[index].get_buy_orders()]
            )

        for index in helper.get_indexes_sell_intervals(self.intervals):
            orders_id_list.extend(
                [order.id for order in self.intervals[index].get_sell_orders()]
            )

        return orders_id_list

    def omit_orders_off_strat(self, new_intervals):
        """Omit all orders, that are not included to the strategy"""
        self.log.debug(f"omit_orders_off_strat(), new_intervals: {new_intervals}")

        lw_orders_id_list = self.get_orders_id_list()
        for index in helper.get_indexes_buy_intervals(new_intervals):
            new_intervals[index].set_buy_orders(
                [
                    order
                    for order in new_intervals[index].get_buy_orders()
                    if order.id in lw_orders_id_list
                ]
            )

        for index in helper.get_indexes_sell_intervals(new_intervals):
            new_intervals[index].set_sell_orders(
                [
                    order
                    for order in new_intervals[index].get_sell_orders()
                    if order.id in lw_orders_id_list
                ]
            )

        return new_intervals

    def cancel_all_intervals(self):
        """Cancel all orders inside all intervals and make self.intervals empty"""
        for interval in self.intervals:
            self.connector.cancel_orders(interval.get_buy_orders())
            self.connector.cancel_orders(interval.get_sell_orders())

        self.intervals = deepcopy(self.connector.empty_intervals)
        self.cancel_safety_orders()

    def cancel_buy_interval_by_index(self, intervals, index):
        """Cancel all buys inside interval from market and from intervals"""
        self.connector.cancel_orders(intervals[index].get_buy_orders())
        intervals[index].remove_buy_orders()

    def cancel_sell_interval_by_index(self, intervals, index):
        """Cancel all sells inside interval from market and from intervals"""
        self.connector.cancel_orders(intervals[index].get_sell_orders())
        intervals[index].remove_sell_orders()

    def when_bottom_is_reached(self):
        """Stop if stop_at_bot"""
        if self.params["stop_at_bot"]:
            self.cancel_safety_orders()
            self.cancel_all_intervals()
            self.log.ext_critical(f"Bottom target reached!")
            raise SystemExit()

    def when_top_is_reached(self):
        """Stop if stop_at_top"""
        if self.params["stop_at_bot"]:
            self.cancel_safety_orders()
            self.cancel_all_intervals()
            self.log.ext_critical(f"Top target reached!")
            raise SystemExit()

    def amount_compare_intervals(self, new_intervals: [Interval]) -> (Decimal, Decimal):
        """Compare intervals and return amount of MANA to open with correct side"""
        interval_index = 0
        amount_to_open_sell = Decimal("0")
        amount_to_open_buy = Decimal("0")

        while interval_index < len(new_intervals):
            if self.intervals[interval_index] != new_intervals[interval_index]:
                amount_consumed_buy = helper.get_amount_to_open(
                    self.intervals[interval_index].get_buy_orders(),
                    new_intervals[interval_index].get_buy_orders(),
                )

                amount_consumed_sell = helper.get_amount_to_open(
                    self.intervals[interval_index].get_sell_orders(),
                    new_intervals[interval_index].get_sell_orders(),
                )

                amount_to_open_buy += self.allocation.get_buy_to_open(
                    interval_index, amount_consumed_sell
                )
                amount_to_open_sell += self.allocation.get_sell_to_open(
                    interval_index, amount_consumed_buy
                )

            interval_index += 1

        return amount_to_open_buy, amount_to_open_sell

    def get_spread_bot(self, intervals: [Interval]) -> int:
        """Returns highest buy interval with amount >= params['amount']"""
        buy_indexes = helper.get_indexes_buy_intervals(intervals)

        for index in reversed(buy_indexes):
            if intervals[index].get_buy_orders_amount() > self.allocation.get_amount(
                index, "buy"
            ) or is_equal_decimal(
                intervals[index].get_buy_orders_amount(),
                self.allocation.get_amount(index, "buy"),
            ):
                return index

        # fail safe
        if buy_indexes:
            return buy_indexes[-1]
        else:
            raise ValueError(
                "Could not get spread_bot because there is no buy intervals!"
            )

    def get_spread_top(self, intervals: [Interval]) -> int:
        """Returns lowest sell interval with amount >= params['amount']"""
        sell_indexes = helper.get_indexes_sell_intervals(intervals)
        for index in sell_indexes:
            if intervals[index].get_sell_orders_amount() > self.allocation.get_amount(
                index, "sell"
            ) or is_equal_decimal(
                intervals[index].get_sell_orders_amount(),
                self.allocation.get_amount(index, "sell"),
            ):
                return index

        # fail safe
        if sell_indexes:
            return sell_indexes[-1]
        else:
            raise ValueError(
                "Could not get spread_top because there is no sell intervals!"
            )

    def where_to_open_buys(
        self, new_intervals: [Interval], amount_to_open_buy: Decimal
    ):
        """Decide, depending on amount_to_open and new_intervals, where to open intervals"""
        buy_intervals_to_open = []
        buy_indexes = helper.get_indexes_buy_intervals(new_intervals)
        buy_step = 1
        if buy_indexes:
            highest_buy_index = buy_indexes[-1]
        else:
            buy_step *= -1
            sell_indexes = helper.get_indexes_sell_intervals(new_intervals)
            if sell_indexes:
                highest_buy_index = self.get_spread_top(new_intervals) - 3
            else:
                highest_buy_index = self.params["spread_bot"]

        intervals_opened_counter = 0
        while amount_to_open_buy > convert.multiplier(
            self.min_amount, self.params["orders_per_interval"]
        ):
            # fail safe, if interval will go so high
            if highest_buy_index >= len(new_intervals):
                self.when_top_is_reached()

            # fail safe, if interval will go so low
            elif highest_buy_index < 0 and not buy_indexes:
                highest_buy_index = self.params["spread_bot"]
                buy_step *= -1

            # if opened more that enough, when there were no more buy_indexes
            elif (
                intervals_opened_counter >= self.params["nb_buy_to_display"]
                and not buy_indexes
            ):
                index_to_open = max(self.params["spread_bot"], highest_buy_index) + 1
                amount_to_open = min(
                    self.allocation.get_amount(index_to_open, "buy"), amount_to_open_buy
                )
                buy_intervals_to_open.append(
                    {
                        "interval_index": index_to_open,
                        "amount": amount_to_open,
                    }
                )
                amount_to_open_buy -= amount_to_open

            # main purpose - when each order just at correct position
            else:
                highest_buy_amount = new_intervals[
                    highest_buy_index
                ].get_buy_orders_amount()
                missing_amount = (
                    self.allocation.get_amount(highest_buy_index, "buy")
                    - highest_buy_amount
                )
                if missing_amount > Decimal("0"):
                    self.cancel_buy_interval_by_index(new_intervals, highest_buy_index)
                    amount_to_open = min(
                        self.allocation.get_amount(highest_buy_index, "buy"),
                        highest_buy_amount + amount_to_open_buy,
                    )
                    buy_intervals_to_open.append(
                        {
                            "interval_index": highest_buy_index,
                            "amount": amount_to_open,
                        }
                    )

                    amount_to_open_buy -= missing_amount

            highest_buy_index += buy_step
            intervals_opened_counter += 1

        # end while
        if amount_to_open_buy > Decimal("0"):
            self.remaining_amount_to_open_buy += amount_to_open_buy

        return buy_intervals_to_open

    def where_to_open_sells(
        self, new_intervals: [Interval], amount_to_open_sell: Decimal
    ):
        """Decide, depending on amount_to_open and new_intervals, where to open intervals"""
        sell_intervals_to_open = []
        sell_indexes = helper.get_indexes_sell_intervals(new_intervals)
        sell_step = -1
        if sell_indexes:
            lowest_sell_index = sell_indexes[0]
        else:
            sell_step *= -1
            buy_indexes = helper.get_indexes_buy_intervals(new_intervals)
            if buy_indexes:
                lowest_sell_index = self.get_spread_bot(new_intervals) + 3
            else:
                lowest_sell_index = self.params["spread_top"]

        intervals_opened_counter = 0
        while amount_to_open_sell > convert.multiplier(
            self.min_amount, self.params["orders_per_interval"]
        ):
            # fail safe, if interval will go so low
            if lowest_sell_index < 0:
                self.when_bottom_is_reached()

            # fail safe, if interval will go so high
            elif lowest_sell_index >= len(self.intervals) and not sell_indexes:
                lowest_sell_index = self.params["spread_top"]
                sell_step *= -1

            # if opened more that enough, when there were no more sell_indexes
            elif (
                intervals_opened_counter >= self.params["nb_buy_to_display"]
                and not sell_indexes
            ):
                index_to_open = min(self.params["spread_top"], lowest_sell_index) - 1
                amount_to_open = min(
                    self.allocation.get_amount(index_to_open, "sell"),
                    amount_to_open_sell,
                )
                sell_intervals_to_open.append(
                    {
                        "interval_index": index_to_open,
                        "amount": amount_to_open,
                    }
                )
                amount_to_open_sell -= amount_to_open

            # main purpose - when each order just at correct position
            else:
                lowest_sell_amount = new_intervals[
                    lowest_sell_index
                ].get_sell_orders_amount()
                missing_amount = (
                    self.allocation.get_amount(lowest_sell_index, "sell")
                    - lowest_sell_amount
                )
                if missing_amount > Decimal("0"):
                    # cancel existing orders
                    self.cancel_sell_interval_by_index(new_intervals, lowest_sell_index)
                    amount_to_open = min(
                        self.allocation.get_amount(lowest_sell_index, "sell"),
                        lowest_sell_amount + amount_to_open_sell,
                    )
                    sell_intervals_to_open.append(
                        {
                            "interval_index": lowest_sell_index,
                            "amount": amount_to_open,
                        }
                    )
                    amount_to_open_sell -= missing_amount

            lowest_sell_index += sell_step
            intervals_opened_counter += 1

        # end while
        if amount_to_open_sell > Decimal("0"):
            self.remaining_amount_to_open_sell += amount_to_open_sell

        return sell_intervals_to_open

    def update_benefits(self, buy_intervals_to_open: [dict]) -> None:
        """Set benefits for profit allocation for intervals to open, changes amount due to profit rules
        buy_intervals_to_open: {
            'interval_index': index,
            'amount': amount,
        }
        """
        assert isinstance(self.allocation, ProfitAllocation)
        for interval in buy_intervals_to_open:
            prev_actual_benefit = self.allocation.benefits[
                interval["interval_index"]
            ].get_actual_benefit()
            self.allocation.set_benefit(interval["interval_index"], interval["amount"])
            additional_benefit = (
                self.allocation.benefits[
                    interval["interval_index"]
                ].get_actual_benefit()
                - prev_actual_benefit
            )
            interval["amount"] += additional_benefit

    def prepare_orders(self, intervals: [dict]) -> [Order]:
        """Prepare orders for opening
        intervals: {
            'interval_index': index,
            'amount': amount,
        }
        """
        orders = []
        for interval in intervals:
            orders.extend(
                self.intervals[interval["interval_index"]].generate_orders_by_amount(
                    interval["amount"],
                    self.min_amount,
                    self.params["orders_per_interval"],
                )
            )

        return orders

    def execute_orders(self, new_intervals, buy_orders_to_open, sell_orders_to_open):
        """Open orders saved them in new_intervals and return new_intervals"""
        if buy_orders_to_open:
            buy_orders = self.connector.set_several_buy(buy_orders_to_open)

            if buy_orders:
                new_intervals = helper.populate_intervals(new_intervals, buy_orders)

        if sell_orders_to_open:
            sell_orders = self.connector.set_several_sell(sell_orders_to_open)

            if sell_orders:
                new_intervals = helper.populate_intervals(new_intervals, sell_orders)

        return new_intervals

    def compare_intervals(self, new_intervals: [Interval]) -> None:
        """Compares intervals and opens new orders and saves them in self.intervals"""
        assert len(self.intervals) == len(new_intervals)
        amount_to_open_buy, amount_to_open_sell = self.amount_compare_intervals(
            new_intervals
        )
        if amount_to_open_buy == amount_to_open_sell == Decimal("0"):
            return

        self.log.info(
            f"Amount to open buy: {amount_to_open_buy} \n"
            f"Amount to open sell: {amount_to_open_sell}"
        )

        if self.remaining_amount_to_open_buy > Decimal("0"):
            amount_to_open_buy += self.remaining_amount_to_open_buy
            self.remaining_amount_to_open_buy = Decimal("0")

        if self.remaining_amount_to_open_sell > Decimal("0"):
            amount_to_open_sell += self.remaining_amount_to_open_sell
            self.remaining_amount_to_open_sell = Decimal("0")

        amount_buys = len(helper.get_indexes_buy_intervals(new_intervals))
        amount_sells = len(helper.get_indexes_sell_intervals(new_intervals))

        # some cheats to use things, that spread_bot - spread_top = 3
        if amount_buys > 0 and amount_sells > 0:
            self.log.ext_warning(
                f"A buy of {amount_buys} and a sell of"
                f"{amount_sells} has occured"
            )
            buy_intervals_to_open = self.where_to_open_buys(
                new_intervals, amount_to_open_buy
            )
            sell_intervals_to_open = self.where_to_open_sells(
                new_intervals, amount_to_open_sell
            )

        elif amount_buys > 0:
            self.log.ext_info(f"A buy of {amount_buys} has occured")
            buy_intervals_to_open = self.where_to_open_buys(
                new_intervals, amount_to_open_buy
            )
            if isinstance(self.allocation, ProfitAllocation):
                self.update_benefits(buy_intervals_to_open)

            buy_orders_to_open = self.prepare_orders(buy_intervals_to_open)
            self.execute_orders(new_intervals, buy_orders_to_open, [])
            buy_intervals_to_open = []
            sell_intervals_to_open = self.where_to_open_sells(
                new_intervals, amount_to_open_sell
            )

        elif amount_sells > 0:
            self.log.ext_info("A sell of {amount_sells} has occured")
            sell_intervals_to_open = self.where_to_open_sells(
                new_intervals, amount_to_open_sell
            )
            sell_orders_to_open = self.prepare_orders(sell_intervals_to_open)
            self.execute_orders(new_intervals, [], sell_orders_to_open)
            sell_intervals_to_open = []
            buy_intervals_to_open = self.where_to_open_buys(
                new_intervals, amount_to_open_buy
            )

        else:
            sell_intervals_to_open = self.where_to_open_sells(
                new_intervals, amount_to_open_sell
            )
            buy_intervals_to_open = self.where_to_open_buys(
                new_intervals, amount_to_open_buy
            )

        if isinstance(self.allocation, ProfitAllocation):
            self.update_benefits(buy_intervals_to_open)

        buy_orders_to_open = self.prepare_orders(buy_intervals_to_open)
        sell_orders_to_open = self.prepare_orders(sell_intervals_to_open)
        self.intervals = self.execute_orders(
            new_intervals, buy_orders_to_open, sell_orders_to_open
        )

    def backup_spread_value(self):
        """Set correct spread bot and spread top depending on currently opened intervals"""
        buy_indexes = helper.get_indexes_buy_intervals(self.intervals)
        sell_indexes = helper.get_indexes_sell_intervals(self.intervals)

        if not buy_indexes:
            self.when_bottom_is_reached()
            self.params["spread_bot"] = 0
            self.params["spread_top"] = 3
        elif not sell_indexes:
            self.when_top_is_reached()
            self.params["spread_bot"] = len(self.intervals) - 4
            self.params["spread_top"] = len(self.intervals) - 1
        else:
            self.params["spread_bot"] = self.get_spread_bot(self.intervals)
            self.params["spread_top"] = self.params["spread_bot"] + 3

        helper.params_writer(f"{self.root_path}config/params.json", self.params)

    def cancel_extra_buy_interval(self):
        """When there is more than needed buy intervals are active - close it"""
        buy_indexes = helper.get_indexes_buy_intervals(self.intervals)
        self.cancel_buy_interval_by_index(self.intervals, buy_indexes[0])

    def cancel_extra_sell_interval(self):
        """When there is more than needed sell intervals are active - close it"""
        sell_indexes = helper.get_indexes_sell_intervals(self.intervals)
        self.cancel_sell_interval_by_index(self.intervals, sell_indexes[-1])

    def open_deficit_buy_interval(self) -> dict:
        """When there is less than needed buy intervals are active - open it"""
        sell_indexes = helper.get_indexes_sell_intervals(self.intervals)
        buy_indexes = helper.get_indexes_buy_intervals(self.intervals)
        if len(buy_indexes) > 0:
            if buy_indexes[0] - 1 >= 0:
                return {
                    "interval_index": buy_indexes[0] - 1,
                    "amount": self.allocation.get_amount(buy_indexes[0] - 1, "buy"),
                }

        elif len(sell_indexes) >= 0 and sell_indexes[0] - 3 >= 0:
            return {
                "interval_index": sell_indexes[0] - 3,
                "amount": self.allocation.get_amount(sell_indexes[0] - 3, "buy"),
            }

    def open_deficit_sell_interval(self):
        """When there is less than needed sell intervals are active - open it"""
        sell_indexes = helper.get_indexes_sell_intervals(self.intervals)
        buy_indexes = helper.get_indexes_buy_intervals(self.intervals)
        if len(sell_indexes) > 0:
            if sell_indexes[-1] + 1 < len(self.intervals):
                return {
                    "interval_index": sell_indexes[-1] + 1,
                    "amount": self.allocation.get_amount(sell_indexes[-1] + 1, "sell"),
                }

        elif len(buy_indexes) >= 0 and buy_indexes[-1] + 3 < len(self.intervals):
            return {
                "interval_index": buy_indexes[-1] + 3,
                "amount": self.allocation.get_amount(buy_indexes[-1] + 3, "sell"),
            }

    def limit_nb_intervals(self):
        buy_indexes = helper.get_indexes_buy_intervals(self.intervals)
        sell_indexes = helper.get_indexes_sell_intervals(self.intervals)
        nb_buy_intervals = len(buy_indexes)
        nb_sell_intervals = len(sell_indexes)
        iterations = abs(nb_buy_intervals - nb_sell_intervals)

        for _ in range(iterations):
            if nb_buy_intervals > self.params["nb_buy_to_display"] + 1 or (
                nb_buy_intervals == self.params["nb_buy_to_display"] + 1
                and buy_indexes[-1] == self.get_spread_bot(self.intervals)
            ):
                self.cancel_extra_buy_interval()

            if nb_sell_intervals > self.params["nb_sell_to_display"] + 1 or (
                nb_sell_intervals == self.params["nb_sell_to_display"] + 1
                and sell_indexes[0] == self.get_spread_top(self.intervals)
            ):
                self.cancel_extra_sell_interval()

            if (
                self.params["spread_bot"] - self.params["nb_buy_to_display"] + 1 >= 0
                and nb_buy_intervals < self.params["nb_buy_to_display"]
            ):
                buy_interval = self.open_deficit_buy_interval()
                if buy_interval:
                    self.execute_orders(
                        self.intervals, self.prepare_orders([buy_interval]), []
                    )

            if (
                self.params["spread_top"] + self.params["nb_sell_to_display"] - 1
                < len(self.intervals)
                and nb_sell_intervals < self.params["nb_sell_to_display"]
            ):
                sell_interval = self.open_deficit_sell_interval()
                if sell_interval:
                    self.execute_orders(
                        self.intervals, [], self.prepare_orders([sell_interval])
                    )

            nb_buy_intervals = len(helper.get_indexes_buy_intervals(self.intervals))
            nb_sell_intervals = len(helper.get_indexes_sell_intervals(self.intervals))

    # TD: think if we need not only check but return side and step for move_intervals
    def check_intervals_position(self) -> bool:
        """Checks if intervals spread has correct difference between buys and sells"""
        buy_indexes = helper.get_indexes_buy_intervals(self.intervals)
        sell_indexes = helper.get_indexes_sell_intervals(self.intervals)
        if not buy_indexes or not sell_indexes:
            return True
        highest_buy = max(buy_indexes)
        lowest_sell = min(sell_indexes)
        if lowest_sell - highest_buy > 3:
            return False

        return True

    # TD: implement for buy side (if needed) - don't know exactly, do we need for buy
    def move_intervals(self, side: str, step: int):
        """Moves intervals 1 step up or 1 step down if check_interval_position returns False
        side: sell or buy
        step: -1 or +1"""
        intervals_to_open = []
        if side == "sell":
            sell_indexes = helper.get_indexes_sell_intervals(self.intervals)
            for index in sell_indexes:
                current_amount = self.intervals[index].get_sell_orders_amount()
                percentage_amount = convert.divider(
                    current_amount, self.allocation.get_amount(index, "sell")
                )
                amount_to_open = convert.multiplier(
                    percentage_amount, self.allocation.get_amount(index + step, "sell")
                )
                intervals_to_open.append(
                    {"interval_index": index + step, "amount": amount_to_open}
                )
                self.cancel_sell_interval_by_index(self.intervals, index)
            self.execute_orders(
                self.intervals, [], self.prepare_orders(intervals_to_open)
            )

    def check_intervals_equal(self, new_intervals):
        return self.amount_compare_intervals(new_intervals) == (Decimal('0'), Decimal('0'))

    def set_min_amount(self):
        """In crypto there is a minimal value for each order to open
        Due to this - lets calculate minimal amount for order to open"""
        lowest_price = self.intervals[0].get_bottom()
        self.min_amount = convert.divider(config.MIN_VALUE_ORDER, lowest_price)

    def lw_initialisation(self):
        """Initializing parameters, check parameters then initialize LW."""
        self.safety_buy_value = self.ui.safety_buy_value
        self.safety_sell_value = self.ui.safety_sell_value
        self.connector = self.params["api_connector"]
        self.intervals = self.params["intervals"]
        self.allocation = self.params["allocation"]
        self.connector.set_params(self.params)

        self.connector.cancel_all(self.params["market"])

        self.log.ext_info("LW is starting")

        self.strat_init()
        #self.set_safety_orders()

    def backup_lw(self):
        with open(f"{self.root_path}config/backup_lw.json", "w") as f:
            f.write(jsonpickle.encode(self))

    def main_cycle(self):
        """One cycle of LW activity"""
        new_intervals = self.connector.get_intervals()
        if not self.check_intervals_equal(new_intervals):
            new_intervals = self.omit_orders_off_strat(new_intervals)

        is_equal = self.check_intervals_equal(new_intervals)
        if not is_equal:
            #self.cancel_safety_orders()
            self.compare_intervals(new_intervals)
            # TD: here only sell moves to buy (spread_top closer to spread_bot) - redo if needed
            if not self.check_intervals_position():
                self.move_intervals("sell", -1)

            self.limit_nb_intervals()
            self.backup_spread_value()
            self.backup_lw()

            #self.set_safety_orders()

    def main(self):
        self.backup_lw()
        while True:
            self.log.info(f"CYCLE START")

            # core functionality is here
            self.main_cycle()

            self.log.info(f"CYCLE STOP")
            sleep(config.LW_CYCLE_SLEEP_TIME)
