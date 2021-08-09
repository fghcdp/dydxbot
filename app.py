import time
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

    def __init__(self, num_samples=20, num_std=2):
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
        self.candles = {}
        self.latest_low = None
        self.market_info = {}
        self.orderbook = {}
        self.account = {}
        self.positions = {}
        self.buy_orders = []
        self.sell_orders = []
        self.get_account()

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
        self.latest_low = float(data[-1][1])
        return [float(x[4]) for x in data]

    def check_price_anomaly(self):
        price_history = self.get_price_history()
        mean_price = statistics.mean(price_history)
        mean_std = statistics.stdev(price_history)
        return self.latest_low < mean_price - self.num_std * mean_std

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

    def run_marketmaker_strategy(self):
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

    def run_meanreversion_strategy(self):
        for market in [b + '-' + QUOTATION_ASSET for b in BASE_ASSETS]:
            self.market = market
            self.get_market_info()
            self.get_orderbook()
            self.get_buy_orders()
            self.get_sell_orders()
            self.get_positions()

            step_size = self.market_info['stepSize']
            step_exp = abs(decimal.Decimal(step_size).as_tuple().exponent)
            tick_size = self.market_info['tickSize']
            tick_exp = abs(decimal.Decimal(tick_size).as_tuple().exponent)
            if not self.positions:
                if self.check_price_anomaly():
                    all_buy_orders = self.client.private.get_orders(
                        market=market,
                        status=ORDER_STATUS_OPEN,
                        side=ORDER_SIDE_BUY,
                        order_type=ORDER_TYPE_LIMIT,
                        limit=1,
                    )
                    buy_order = all_buy_orders['orders'][0]\
                        if all_buy_orders['orders']\
                        else None
                    bid_price = float(self.orderbook['bids'][0]['price'])
                    price = min(self.latest_low, bid_price)
                    equity = float(self.account['equity'])
                    size = min(equity / len(BASE_ASSETS), 10000)
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
                        'expiration_epoch_seconds': time.time() + 2592000,
                    }
                    if buy_order:
                        order_params.update({'cancel_id': buy_order['id']})
                    self.client.private.create_order(**order_params)
            else:
                if self.positions[0]['status'] == POSITION_STATUS_OPEN:
                    all_sell_orders = self.client.private.get_orders(
                        market=market,
                        status=ORDER_STATUS_OPEN,
                        side=ORDER_SIDE_SELL,
                        order_type=ORDER_TYPE_LIMIT,
                        limit=1,
                    )
                    sell_order = all_sell_orders['orders'][0]\
                        if all_sell_orders['orders']\
                        else None
                    entry_price = float(self.positions[0]['entryPrice'])
                    ask_price = float(self.orderbook['asks'][0]['price'])
                    if ask_price < entry_price * .995:
                        # Stop loss price
                        price = self.orderbook['asks'][0]['price']
                    else:
                        # Take profit price
                        price = str(round(entry_price * 1.005, tick_exp))
                    size = self.positions[0]['sumOpen']
                    order_params = {
                        'position_id': self.account['positionId'],
                        'market': market,
                        'side': ORDER_SIDE_SELL,
                        'order_type': ORDER_TYPE_LIMIT,
                        'post_only': True,
                        'size': size,
                        'price': price,
                        'limit_fee': '0.0005',
                        'expiration_epoch_seconds': time.time() + 2592000,
                    }
                    if sell_order:
                        order_params.update({'cancel_id': sell_order['id']})
                    if (
                        not sell_order
                        or float(price) != float(sell_order['price'])
                        ):
                        self.client.private.create_order(**order_params)
