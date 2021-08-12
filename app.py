import time
import json
import decimal
import requests
import statistics
from dydx3 import Client
from dydx3.constants import ORDER_SIDE_BUY
from dydx3.constants import ORDER_SIDE_SELL
from dydx3.constants import ORDER_TYPE_LIMIT
from dydx3.constants import ORDER_STATUS_OPEN
from dydx3.constants import POSITION_STATUS_OPEN
from config import (
    HOST,
    ETHEREUM_ADDRESS,
    API_KEY_CREDENTIALS,
    STARK_PRIVATE_KEY,
    QUOTATION_ASSET,
    BASE_ASSETS,
)


class Bot:

    def __init__(self, num_samples=20, num_std=2, records_fname='records'):
        self.client = Client(
            host=HOST,
            default_ethereum_address=ETHEREUM_ADDRESS,
            api_key_credentials=API_KEY_CREDENTIALS
        )
        self.client.stark_private_key = STARK_PRIVATE_KEY
        self.coinbase_api = 'https://api.pro.coinbase.com'
        self.market = None
        self.num_samples = num_samples
        self.num_std = num_std
        self.records_fname = records_fname
        self.candles = {}
        self.price_history = []
        self.latest_low = None
        self.mean_price = None
        self.mean_std = None
        self.market_info = {}
        self.orderbook = {}
        self.account = {}
        self.positions = {}
        self.buy_orders = []
        self.sell_orders = []
        self.get_account()

    def load_all_records(self):
        with open(self.records_fname + '.json', 'r') as f:
            records = json.load(f)
        return records

    def load_market_record(self):
        records = self.load_all_records()
        return records[self.market]

    def save_market_record(self, data):
        records = self.load_all_records()
        records[self.market] = data
        with open(self.records_fname + '.json', 'w') as f:
            json.dump(records, f)

    def get_latest_candle(self):
        for asset in BASE_ASSETS:
            market_pair = f'{asset}-{QUOTATION_ASSET}'
            self.candles[market_pair] = self.client.public.get_candles(
                market_pair,
                resolution='1HOUR',
                limit=1
            )

    def get_price_history(self):
        endpoint = f'/products/{self.market}/candles'
        r = requests.get(self.coinbase_api + endpoint)
        data = r.json()[:self.num_samples][::-1]
        self.price_history = [float(x[4]) for x in data]

    def calculate_price_stats(self):
        self.mean_price = statistics.mean(self.price_history)
        self.mean_std = statistics.stdev(self.price_history)

    def get_entry_signal(self, price):
        return price < self.mean_price - self.num_std * self.mean_std

    def get_take_profit_signal(self, entry_price, price):
        return entry_price * 1.001 < self.mean_price - self.mean_std < price

    def get_stop_signal(self, entry_price, price):
        return price < entry_price * .98

    def get_market_info(self):
        r = self.client.public.get_markets(self.market)
        self.market_info = r['markets'][self.market]

    def get_orderbook(self):
        self.orderbook = self.client.public.get_orderbook(market=self.market)

    def get_account(self):
        account = self.client.private.get_account()
        self.account = account['account']
        self.positions = self.account['openPositions']

    def get_buy_orders(self):
        orders = self.client.private.get_orders(
            market=self.market,
            status=ORDER_STATUS_OPEN,
            side=ORDER_SIDE_BUY,
            limit=1,
        )
        self.buy_orders = orders['orders']

    def get_sell_orders(self):
        orders = self.client.private.get_orders(
            market=self.market,
            status=ORDER_STATUS_OPEN,
            side=ORDER_SIDE_SELL,
            limit=1,
        )
        self.sell_orders = orders['orders']

    def get_positions(self):
        positions = self.client.private.get_positions(
            market=self.market,
            status=POSITION_STATUS_OPEN,
        )
        self.positions = positions['positions']

    def calculate_mid_market_price(self):
        bid_price = float(self.orderbook['bids'][0]['price'])
        ask_price = float(self.orderbook['asks'][0]['price'])
        return bid_price + (ask_price - bid_price) * .5

    """
    STRATEGIES
    """

    def run_meanreversion_strategy(self):
        for market in [b + '-' + QUOTATION_ASSET for b in BASE_ASSETS]:
            self.market = market
            self.get_market_info()
            self.get_price_history()
            self.calculate_price_stats()
            self.get_orderbook()
            self.get_buy_orders()
            self.get_sell_orders()
            self.get_positions()

            step_size = self.market_info['stepSize']
            step_exp = abs(decimal.Decimal(step_size).as_tuple().exponent)

            if not self.positions:
                price = float(self.orderbook['bids'][0]['price'])
                if self.get_entry_signal(price):
                    buy_orders = self.client.private.get_orders(
                        market=market,
                        status=ORDER_STATUS_OPEN,
                        side=ORDER_SIDE_BUY,
                        order_type=ORDER_TYPE_LIMIT,
                        limit=1,
                    )
                    buy_order = buy_orders['orders'][0]\
                        if buy_orders['orders']\
                        else None
                    if not buy_order:
                        equity = float(self.account['equity'])
                        size = min(equity, 10000)
                        size = size / float(self.market_info['indexPrice'])
                        size = round(size - size % float(step_size), step_exp)
                        size = str(
                            max(size, float(self.market_info['minOrderSize']))
                        )
                        price = str(price)
                        order_params = {
                            'position_id': self.account['positionId'],
                            'market': market,
                            'side': ORDER_SIDE_BUY,
                            'order_type': ORDER_TYPE_LIMIT,
                            'post_only': True,
                            'size': size,
                            'price': price,
                            'limit_fee': '0.0005',
                            'expiration_epoch_seconds': time.time() + 3600,
                        }
                        self.client.private.create_order(**order_params)

            else:
                entry_price = float(self.positions[0]['entryPrice'])
                price = float(self.orderbook['asks'][0]['price'])
                sell_orders = self.client.private.get_orders(
                    market=market,
                    status=ORDER_STATUS_OPEN,
                    side=ORDER_SIDE_SELL,
                    order_type=ORDER_TYPE_LIMIT,
                    limit=1,
                )
                sell_order = sell_orders['orders'][0]\
                    if sell_orders['orders']\
                    else None
                size = self.positions[0]['sumOpen']
                if self.get_take_profit_signal(entry_price, price):
                    if not sell_order:
                        order_params = {
                            'position_id': self.account['positionId'],
                            'market': market,
                            'side': ORDER_SIDE_SELL,
                            'order_type': ORDER_TYPE_LIMIT,
                            'post_only': True,
                            'size': size,
                            'price': str(price),
                            'limit_fee': '0.0005',
                            'expiration_epoch_seconds': time.time() + 3600,
                        }
                        self.client.private.create_order(**order_params)
                if self.get_stop_signal(entry_price, price):
                    order_params = {
                        'position_id': self.account['positionId'],
                        'market': market,
                        'side': ORDER_SIDE_SELL,
                        'order_type': 'MARKET',
                        'post_only': False,
                        'size': size,
                        'price': str(self.orderbook['bids'][10]['price']),
                        'limit_fee': '0.002',
                        'time_in_force': 'FOK',
                        'expiration_epoch_seconds': time.time() + 3600,
                    }
                    self.client.private.create_order(**order_params)
                    if sell_order:
                        self.client.private.cancel_order(
                            order_id=sell_order['id']
                        )
