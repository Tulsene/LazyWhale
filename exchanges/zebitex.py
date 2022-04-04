#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import requests
import json
import hmac
import hashlib


class ZebitexError(Exception):
    """
    Exception for catch invalid commands and other repsonses
    that don't match with 2xx code responses.
    """

    def __init__(self, err):
        pass


class Zebitex:
    """Zebitex's API wrapper"""

    def __init__(self, access_key=None, secret_key=None, is_staging=False):
        self.access_key = str(access_key) if access_key else None
        self.secret_key = str(secret_key) if secret_key else None
        self.url = (
            "https://api-staging.zebitex.com"
            if is_staging
            else "https://api.zebitex.com"
        )

    #
    # Private methods
    #

    def _signature_payload(self, method, path, tonce, params=None):
        """Sign a payload with HMAC SHA256 and the secret key.
        The signature_payload consist of uppercased HTTP verb,
        the API path without the host part,
        the tonce and all the params in JSON form.
        All separated with a vertical slash."""
        json_params = json.dumps(params) if params else "{}"
        payload = f"{method.upper()}|{path}|{str(tonce)}|{json_params.replace(' ', '')}"
        signature = hmac.new(
            self.secret_key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return signature

    def _authorization_header(self, method, path, params):
        """The Authorization header:
        - access_key - your token access_key
        - signature - a signature_payload HMAC SHA256 signed with your token secret_key
        - tonce - 13 digits timestamp
        - signed_params - a semicolon separated list of the param names submitted and signed in the request
        """
        tonce = int(time.time() * 1000)
        signature = self._signature_payload(method, path, tonce, params)
        signed_params = ";".join(params.keys()) if params else ""
        authorization_header = f"ZEBITEX-HMAC-SHA256 access_key={self.access_key}, signature={signature}, tonce={tonce}, signed_params={signed_params}"
        return {"Authorization": authorization_header}

    def __call__(self, level, method, path, params=None):
        """"""
        status_code_list = [200, 201, 204]
        user_agent = {"User-Agent": "zebitex-python3 0.0.1 alpha version"}
        authorization_header = {}
        params = {k: str(v) for k, v in params.items()} if params else None
        if level == "PRIVATE":
            authorization_header = self._authorization_header(method, path, params)
        url = f"{self.url}{path}"
        headers = {**user_agent, **authorization_header}
        r = requests.request(method, url, params=params, headers=headers, json=True)
        with open("zebitex-api-calls.txt", "a") as f:
            f.write(f"{method} {url} params={params}\n")
            try:
                f.write(f"response: {r.json()}\n")
            except json.JSONDecodeError:
                pass

        status = {"status_code": r.status_code}
        if r.status_code not in status_code_list:
            raise ZebitexError({**status, **r.json()})
        if r.status_code == 200 or r.status_code == 201:
            return r.json()
        else:
            return True

    #
    # Public methods
    #

    def funds(self):
        return self.__call__("PRIVATE", "GET", "/api/v1/funds")

    def tickers(self):
        return self.__call__("PUBLIC", "GET", "/api/v1/orders/tickers")

    def ticker(self, market):
        return self.__call__("PUBLIC", "GET", f"/api/v1/orders/ticker_summary/{market}")

    def orderbook(self, market):
        return self.__call__(
            "PUBLIC", "GET", "/api/v1/orders/orderbook", {"market": market}
        )

    def public_trade_history(self, market):
        return self.__call__(
            "PUBLIC", "GET", "/api/v1/orders/trade_history", {"market": market}
        )

    def open_orders(self, page=1, per=10):
        query = {"page": page, "per": per}
        return self.__call__("PRIVATE", "GET", "/api/v1/orders/opened", query)

    def trade_history(self, side, start_date, end_date, page, per):
        query = {
            "side": side,
            "start_date": start_date,
            "end_date": end_date,
            "page": page,
            "per": per,
        }
        return self.__call__("PRIVATE", "GET", "/api/v1/history/trades", query)

    def order_history(self, side, start_date, end_date, page, per):
        query = {
            "side": side,
            "start_date": start_date,
            "end_date": end_date,
            "page": page,
            "per": per,
        }
        return self.__call__("PRIVATE", "GET", "/api/v1/history/orders", query)

    def cancel_all_orders(self):
        return self.__call__("PRIVATE", "DELETE", "/api/v1/orders/cancel_all")

    def cancel_order(self, id_order):
        return self.__call__(
            "PRIVATE",
            "DELETE",
            f"/api/v1/orders/{str(id_order)}/cancel",
            {"id": str(id_order)},
        )

    def new_order(self, bid, ask, side, price, amount, market, ord_type):
        query = {
            "bid": bid,
            "ask": ask,
            "side": side,
            "price": price,
            "amount": amount,
            "market": market,
            "ord_type": ord_type,
        }
        return self.__call__("PRIVATE", "POST", "/api/v1/orders", query)
