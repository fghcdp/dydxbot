import time
import json
import datetime
import decimal
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
)


class System:

    def __init__(
        self,
        market,
        resolution='1HOUR',
        limit=100,
        records_fname='records',
        ):
        self.client = Client(
            host=HOST,
            default_ethereum_address=ETHEREUM_ADDRESS,
            api_key_credentials=API_KEY_CREDENTIALS
        )
        self.client.stark_private_key = STARK_PRIVATE_KEY
        self.market = market
        self.resolution = resolution
        self.limit = limit
        self.records_fname = records_fname
        self.candles = []
        self.mean_price = None
        self.mean_std = None
        self.market_info = {}
        self.orderbook = {}
        self.account = {}
        self.positions = {}
        self.buy_orders = []
        self.sell_orders = []
        self.max_positions = 5
        self.max_positions_per_side = 3
        self.max_risk = .02
        self.stoploss_delta = .2
        self.max_equity_ratio = self.max_risk / self.stoploss_delta
        self.max_position_size = 10000

        self.get_account()
        self.get_market_info()
        self.get_candles()
        self.calculate_price_stats()
        self.get_orderbook()
        self.get_buy_orders()
        self.get_sell_orders()
        self.get_positions()

        self.step_size = self.market_info['stepSize']
        self.step_exp = abs(decimal.Decimal(self.step_size).as_tuple().exponent)
        self.ticker = self.calculate_mid_market_price()            

    def load_all_histories(self):
        with open(self.histories_fname + '.json', 'r') as f:
            histories = json.load(f)
        return histories

    def load_market_history(self):
        histories = self.load_all_histories()
        return histories[self.market] if histories.get(self.market) else []

    def save_market_history(self, data):
        histories = self.load_all_histories()
        histories[self.market] = data
        with open(self.histories_fname + '.json', 'w') as f:
            json.dump(histories, f)

    def get_candles(self):
        to_iso = (
            datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        ).isoformat()
        r = self.client.public.get_candles(
            self.market,
            resolution=self.resolution,
            limit=self.limit,
            to_iso=to_iso,
        )['candles']
        self.candles = r[::-1]

    def calculate_price_stats(self):
        candle_closes = [float(x['close']) for x in self.candles]
        self.mean_price = statistics.mean(candle_closes)
        self.mean_std = statistics.stdev(candle_closes)

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
            limit=10,
        )
        self.buy_orders = orders['orders']

    def get_sell_orders(self):
        orders = self.client.private.get_orders(
            market=self.market,
            status=ORDER_STATUS_OPEN,
            side=ORDER_SIDE_SELL,
            limit=10,
        )
        self.sell_orders = orders['orders']

    def get_positions(self):
        positions = self.client.private.get_positions(
            market=self.market,
            status=POSITION_STATUS_OPEN,
        )['positions']
        self.positions = {
            'long': [x for x in positions if x['side'] == 'LONG'],
            'short': [x for x in positions if x['side'] == 'SHORT'],
        }

    def calculate_mid_market_price(self):
        bid_price = float(self.orderbook['bids'][0]['price'])
        ask_price = float(self.orderbook['asks'][0]['price'])
        return bid_price + (ask_price - bid_price) * .5

    def cancel_buy_orders(self):
        for order in self.buy_orders:
            self.client.private.cancel_order(order_id=order['id'])

    def cancel_sell_orders(self):
        for order in self.sell_orders:
            self.client.private.cancel_order(order_id=order['id'])

    def execute_long_entry(self):
        if self.positions['long'] or self.buy_orders:
            return
        if len(self.account['openPositions']) > self.max_positions:
            return
        long_positions = [
            x for x in self.account['openPositions'] if x.get('side') == 'LONG'
        ]
        if len(long_positions) > self.max_positions_per_side:
            return
        equity = float(self.account['equity'])
        size = min(equity * self.max_equity_ratio, self.max_position_size)
        size = size / float(self.market_info['indexPrice'])
        size = round(size - size % float(self.step_size), self.step_exp)
        size = str(
            max(size, float(self.market_info['minOrderSize']))
        )
        price = self.orderbook['bids'][0]['price']
        order_params = {
            'position_id': self.account['positionId'],
            'market': self.market,
            'side': ORDER_SIDE_BUY,
            'order_type': ORDER_TYPE_LIMIT,
            'post_only': True,
            'size': size,
            'price': price,
            'limit_fee': '0.0005',
            'expiration_epoch_seconds': time.time() + 3600,
        }
        self.cancel_buy_orders()
        self.client.private.create_order(**order_params)

    def execute_long_exit(self):
        if not self.positions['long'] or self.sell_orders:
            return
        price = self.orderbook['asks'][0]['price']
        size = self.positions['long'][0]['sumOpen']
        order_params = {
            'position_id': self.account['positionId'],
            'market': self.market,
            'side': ORDER_SIDE_SELL,
            'order_type': ORDER_TYPE_LIMIT,
            'post_only': True,
            'size': size,
            'price': price,
            'limit_fee': '0.0005',
            'expiration_epoch_seconds': time.time() + 3600,
        }
        if float(size) < float(self.market_info['minOrderSize']):
            order_params.update(
                {
                    'side': ORDER_SIDE_BUY,
                    'size': self.market_info['minOrderSize'],
                    'price': self.orderbook['bids'][0]['price'],
                }
            )
        self.cancel_buy_orders()
        self.client.private.create_order(**order_params)

    def execute_short_entry(self):
        if self.positions['short'] or self.sell_orders:
            return
        if len(self.account['openPositions']) > self.max_positions:
            return
        print(self.account['openPositions'])
        short_positions = [
            x for x in self.account['openPositions']
            if x.get('side') == 'SHORT'
        ]
        if len(short_positions) > self.max_positions_per_side:
            return
        equity = float(self.account['equity'])
        size = min(equity * self.max_equity_ratio, self.max_position_size)
        size = size / float(self.market_info['indexPrice'])
        size = round(size - size % float(self.step_size), self.step_exp)
        size = str(
            max(size, float(self.market_info['minOrderSize']))
        )
        price = self.orderbook['asks'][0]['price']
        order_params = {
            'position_id': self.account['positionId'],
            'market': self.market,
            'side': ORDER_SIDE_SELL,
            'order_type': ORDER_TYPE_LIMIT,
            'post_only': True,
            'size': size,
            'price': price,
            'limit_fee': '0.0005',
            'expiration_epoch_seconds': time.time() + 3600,
        }
        self.cancel_sell_orders()
        self.client.private.create_order(**order_params)

    def execute_short_exit(self):
        if not self.positions['short'] or self.buy_orders:
            return
        price = self.orderbook['bids'][0]['price']
        size = self.positions['short'][0]['sumOpen']
        order_params = {
            'position_id': self.account['positionId'],
            'market': self.market,
            'side': ORDER_SIDE_BUY,
            'order_type': ORDER_TYPE_LIMIT,
            'post_only': True,
            'size': size,
            'price': price,
            'limit_fee': '0.0005',
            'expiration_epoch_seconds': time.time() + 3600,
        }
        if float(size) < float(self.market_info['minOrderSize']):
            order_params.update(
                {
                    'side': ORDER_SIDE_SELL,
                    'size': self.market_info['minOrderSize'],
                    'price': self.orderbook['asks'][0]['price'],
                }
            )
        self.cancel_buy_orders()
        self.client.private.create_order(**order_params)

    def execute_long_stoploss(self):
        if self.buy_orders:
            for order in self.buy_orders:
                self.client.private.cancel_order(order_id=order['id'])
        if self.sell_orders:
            for order in self.sell_orders:
                self.client.private.cancel_order(order_id=order['id'])
        for position in self.positions['long']:
            size = position['sumOpen']
            order_params = {
                'position_id': self.account['positionId'],
                'market': self.market,
                'side': ORDER_SIDE_SELL,
                'order_type': 'MARKET',
                'post_only': False,
                'size': size,
                'price': self.orderbook['bids'][10]['price'],
                'limit_fee': '0.002',
                'time_in_force': 'FOK',
                'expiration_epoch_seconds': time.time() + 3600,
            }
            self.client.private.create_order(**order_params)

    def execute_short_stoploss(self):
        if self.buy_orders:
            for order in self.buy_orders:
                self.client.private.cancel_order(order_id=order['id'])
        if self.sell_orders:
            for order in self.sell_orders:
                self.client.private.cancel_order(order_id=order['id'])
        for position in self.positions['short']:
            size = position['sumOpen']
            order_params = {
                'position_id': self.account['positionId'],
                'market': self.market,
                'side': ORDER_SIDE_BUY,
                'order_type': 'MARKET',
                'post_only': False,
                'size': size,
                'price': self.orderbook['asks'][10]['price'],
                'limit_fee': '0.002',
                'time_in_force': 'FOK',
                'expiration_epoch_seconds': time.time() + 3600,
            }
            self.client.private.create_order(**order_params)

    def update_limit_orders(self):
        if self.buy_orders:
            price = self.orderbook['bids'][0]['price']
            for order in self.buy_orders:
                if float(order['price']) != float(price):
                    order_params = {
                        'position_id': self.account['positionId'],
                        'market': self.market,
                        'side': ORDER_SIDE_BUY,
                        'order_type': ORDER_TYPE_LIMIT,
                        'post_only': True,
                        'size': order['size'],
                        'price': price,
                        'limit_fee': '0.0005',
                        'expiration_epoch_seconds': time.time() + 3600,
                        'cancel_id': order['id'],
                    }
                    self.client.private.create_order(**order_params)
        if self.sell_orders:
            price = self.orderbook['asks'][0]['price']
            for order in self.sell_orders:
                if float(order['price']) != float(price):
                    order_params = {
                        'position_id': self.account['positionId'],
                        'market': self.market,
                        'side': ORDER_SIDE_SELL,
                        'order_type': ORDER_TYPE_LIMIT,
                        'post_only': True,
                        'size': order['size'],
                        'price': price,
                        'limit_fee': '0.0005',
                        'expiration_epoch_seconds': time.time() + 3600,
                        'cancel_id': order['id'],
                    }
                    self.client.private.create_order(**order_params)
