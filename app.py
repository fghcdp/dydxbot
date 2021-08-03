import time
import json
import requests
import statistics
from dydx3 import Client
from dydx3.constants import ORDER_SIDE_BUY
from dydx3.constants import ORDER_SIDE_SELL
from dydx3.constants import ORDER_TYPE_LIMIT
from dydx3.constants import ORDER_STATUS_OPEN
from config import (
    HOST,
    ETHEREUM_ADDRESS,
    API_KEY_CREDENTIALS,
    STARK_PRIVATE_KEY,
    QUOTATION_ASSET,
    BASE_ASSETS,
)


class Bot:

    def __init__(self, num_samples=20, num_std=2):
        self.client = Client(
            host=HOST,
            default_ethereum_address=ETHEREUM_ADDRESS,
            api_key_credentials=API_KEY_CREDENTIALS
        )
        self.client.stark_private_key = STARK_PRIVATE_KEY
        self.coinbase_api = 'https://api.pro.coinbase.com'
        self.product_id = None
        self.num_samples = num_samples
        self.num_std = num_std
        self.records = {}
        self.candles = {}
        self.orderbook = {}
        self.account = {}
        self.positions = {}
        self.buy_orders = []
        self.sell_orders = []
        self.get_account()

    def open_records(self):
        with open('records.json', 'r') as f:
            self.records = json.load(f)
            f.close()

    def save_records(self):
        with open('records.json', 'w') as f:
            self.records = json.dump(self.records, f)
            f.close()

    def get_latest_candles(self):
        for asset in BASE_ASSETS:
            market_pair = f'{asset}-{QUOTATION_ASSET}'
            self.candles[market_pair] = self.client.public.get_candles(
                market_pair,
                resolution='1HOUR',
                limit=1
            )

    def get_price_history(self):
        endpoint = f'/products/{self.product_id}/candles'
        r = requests.get(self.coinbase_api + endpoint)
        data = r.json()[:self.num_samples][::-1]
        return [float(x[4]) for x in data]

    def check_price_anomaly(self):
        price_history = self.get_price_history()
        mean_price = statistics.mean(price_history)
        mean_std = statistics.stdev(price_history)
        return price_history[-1] < mean_price - self.num_std * mean_std

    def get_orderbook(self, market: str):
        self.orderbook = self.client.public.get_orderbook(market=market)

    def get_account(self):
        account = self.client.private.get_account()
        self.account = account['account']
        self.positions = self.account['openPositions']

    def get_buy_orders(self, market: str):
        orders = self.client.private.get_orders(
            market=market,
            status=ORDER_STATUS_OPEN,
            side=ORDER_SIDE_BUY,
            limit=1,
        )
        self.buy_orders = orders['orders']

    def get_sell_orders(self, market: str):
        orders = self.client.private.get_orders(
            market=market,
            status=ORDER_STATUS_OPEN,
            side=ORDER_SIDE_SELL,
            limit=1,
        )
        self.sell_orders = orders['orders']

    def calculate_mid_market_price(self):
        bid_price = float(self.orderbook['bids'][0]['price'])
        ask_price = float(self.orderbook['asks'][0]['price'])
        return bid_price + (ask_price - bid_price) * .5

    """
    STRATEGIES
    """

    def run_market_maker_strategy(self):
        for market in self.candles:
            self.get_orderbook(market)
            self.get_buy_orders(market)
            self.get_sell_orders(market)

            if not self.buy_orders and not self.sell_orders:
                mm_price = self.calculate_mid_market_price()
                size = min(float(self.account['quoteBalance']) / 10, 10000)
                size = round(size / mm_price, 3)
                price = round(mm_price * (1 - .00055), 1)
                order_params = {
                    'position_id': self.account['positionId'],
                    'market': market,
                    'side': ORDER_SIDE_BUY,
                    'order_type': ORDER_TYPE_LIMIT,
                    'post_only': True,
                    'size': str(size),
                    'price': str(price),
                    'limit_fee': '0.0005',
                    'expiration_epoch_seconds': time.time() + 2592000,
                }
                self.client.private.create_order(**order_params)

                price = round(mm_price * (1 + .00055), 1)
                order_params = {
                    'position_id': self.account['positionId'],
                    'market': market,
                    'side': ORDER_SIDE_SELL,
                    'order_type': ORDER_TYPE_LIMIT,
                    'post_only': True,
                    'size': str(size),
                    'price': str(price),
                    'limit_fee': '0.0005',
                    'expiration_epoch_seconds': time.time() + 2592000,
                }
                self.client.private.create_order(**order_params)

    def run_mean_reversion_strategy(self,):
        for market in self.candles:
            self.get_orderbook(market)
            self.get_buy_orders(market)
            self.get_sell_orders(market)

            if not self.buy_orders and not self.sell_orders:
                mm_price = self.calculate_mid_market_price()
                size = min(float(self.account['quoteBalance']) / 10, 10000)
                size = round(size / mm_price, 3)
                price = round(mm_price * (1 - .00055), 1)
                order_params = {
                    'position_id': self.account['positionId'],
                    'market': market,
                    'side': ORDER_SIDE_BUY,
                    'order_type': ORDER_TYPE_LIMIT,
                    'post_only': True,
                    'size': str(size),
                    'price': str(price),
                    'limit_fee': '0.0005',
                    'expiration_epoch_seconds': time.time() + 2592000,
                }
                self.client.private.create_order(**order_params)

                price = round(mm_price * (1 + .00055), 1)
                order_params = {
                    'position_id': self.account['positionId'],
                    'market': market,
                    'side': ORDER_SIDE_SELL,
                    'order_type': ORDER_TYPE_LIMIT,
                    'post_only': True,
                    'size': str(size),
                    'price': str(price),
                    'limit_fee': '0.0005',
                    'expiration_epoch_seconds': time.time() + 2592000,
                }
                self.client.private.create_order(**order_params)