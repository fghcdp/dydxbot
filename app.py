import time
import json
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


class MarketMaker:

    def __init__(self):
        self.client = Client(
            host=HOST,
            default_ethereum_address=ETHEREUM_ADDRESS,
            api_key_credentials=API_KEY_CREDENTIALS
        )
        self.client.stark_private_key = STARK_PRIVATE_KEY
        self.records = {}
        self.candles = {}
        self.orderbook = {}
        self.account = {}
        self.positions = {}
        self.buy_orders = []
        self.sell_orders = []
        self.fills = []
        self.open_records()
        self.get_latest_candles()
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

    def get_fills(self, market: str):
        fills = self.client.private.get_fills(market=market)
        self.fills = fills['fills']

    def trade(self):
        for market in self.candles:
            record = self.records[market]
            candle = self.candles[market]['candles'][0]
            self.get_orderbook(market)
            self.get_buy_orders(market)
            self.get_sell_orders(market)
            self.get_fills(market)

            if not self.positions.get(market):
                orderbook_price = float(self.orderbook['asks'][0]['price'])
                size = min(float(self.account['quoteBalance']), 10000)
                size = round(size / orderbook_price, 3)
                price = min(
                    float(candle['close']),
                    float(self.orderbook['bids'][0]['price'])
                )
                price = round(price * .999, 1)
                order_params = {
                    'position_id': self.account['positionId'],
                    'market': market,
                    'side': ORDER_SIDE_BUY,
                    'order_type': ORDER_TYPE_LIMIT,
                    'post_only': True,
                    'size': str(size),
                    'price': str(price),
                    'limit_fee': '0.0005',
                    'expiration_epoch_seconds': time.time() + 10800,
                }
                if not self.buy_orders:
                    r = self.client.private.create_order(**order_params)
                    record['orderId'] = r['order']['id']
                elif record['close'] != candle['close']:
                    r = self.client.private.create_order(
                        **dict(
                            order_params,
                            price=str(price),
                            cancel_id=record['orderId'],
                        ),
                    )
                    record['orderId'] = r['order']['id']
            elif not self.sell_orders:
                price = max(
                    float(self.positions[market]['entryPrice']) * 1.001 ** 2,
                    float(self.orderbook['asks'][0]['price'])
                )
                price = round(price, 1)
                order_params = {
                    'position_id': self.account['positionId'],
                    'market': market,
                    'side': ORDER_SIDE_SELL,
                    'order_type': ORDER_TYPE_LIMIT,
                    'post_only': True,
                    'size': self.positions[market]['size'],
                    'price': str(price),
                    'limit_fee': '0.0005',
                    'expiration_epoch_seconds': time.time() + 2592000,
                }
                r = self.client.private.create_order(**order_params)

            record['close'] = candle['close']
        self.save_records()
