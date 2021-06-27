#TODO
'''
- [x] Create a task that runs every minute (t = 60)
- [x] Import dydx package and init client (existing stark key and api creds)
- [x] Collect latest candle
- [x] Check account balances
- [x] Check open positions and open orders
- [x] If no open positions -> open buy limit order: price = latest close * .999 & amount = all USDC
- [x] Else if BUY orders and latest close * .999 != order price -> modify order: price = latest close * .999
- [x] Else if open position and no BUY orders -> open sell limit order: price = last BUY order price * 1.002 & amount = all base asset
'''
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
        self.orders = []
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

    def get_orders(self, market: str):
        orders = self.client.private.get_orders(
            market=market,
            status=ORDER_STATUS_OPEN,
            side=ORDER_SIDE_BUY,
            limit=1,
        )
        self.orders = orders['orders']

    def get_fills(self, market: str):
        fills = self.client.private.get_fills(market=market)
        self.fills = fills['fills']

    def trade(self):
        for market in self.candles:
            record = self.records[market]
            candle = self.candles[market]['candles'][0]
            self.get_orderbook(market)
            self.get_orders(market)
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
                if not self.orders:
                    r = self.client.private.create_order(**order_params)
                    record['orderId'] = r['order']['id']
                elif self.orders and record['close'] != candle['close']:
                    r = self.client.private.create_order(
                        **dict(
                            order_params,
                            price=str(price),
                            cancel_id=record['orderId'],
                        ),
                    )
                    record['orderId'] = r['order']['id']
            else:
                order_params = {
                    'position_id': self.account['positionId'],
                    'market': market,
                    'side': ORDER_SIDE_SELL,
                    'order_type': ORDER_TYPE_LIMIT,
                    'post_only': True,
                    'size': self.positions[market]['size'],
                    'price': str(
                        round(
                            float(
                                self.positions[market]['entryPrice']
                            ) * 1.001 ** 2,
                            1
                        )
                    ),
                    'limit_fee': '0.0005',
                    'expiration_epoch_seconds': time.time() + 2592000,
                }
                r = self.client.private.create_order(**order_params)

            record['close'] = candle['close']
        self.save_records()


        
mmaker = MarketMaker()
mmaker.trade()

'''
'openPositions': {
    'ETH-USD': {
        'market': 'ETH-USD',
        'status': 'OPEN',
        'side': 'LONG',
        'size': '0.01',
        'maxSize': '0.01',
        'entryPrice': '1824.400000',
        'exitPrice': '0.000000',
        'unrealizedPnl': '-0.011200',
        'realizedPnl': '0.000000',
        'createdAt': '2021-06-27T17:33:17.159Z',
        'closedAt': None,
        'sumOpen': '0.01',
        'sumClose': '0',
        'netFunding': '0'
    }
}
'''

'''
ORDER:
{
    'id': '0d2ca42c11d0b4a4ef496eaef3d01d3360e6b1b26d3f0a1bf6a89123a8c4d95',
    'clientId': '44105382277918936',
    'accountId': '0cb83e33-39c3-5c76-895e-ff0d76db91c5',
    'market': 'BTC-USD',
    'side': 'BUY',
    'price': '30000',
    'triggerPrice': None,
    'trailingPercent': None,
    'size': '0.001',
    'remainingSize': '0.001',
    'type': 'LIMIT',
    'createdAt': '2021-06-27T18:20:03.050Z',
    'unfillableAt': None,
    'expiresAt': '2021-06-27T21:20:02.611Z',
    'status': 'OPEN',
    'timeInForce': 'GTT',
    'postOnly': True,
    'cancelReason': None
}
'''
