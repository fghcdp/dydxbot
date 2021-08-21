from system import System
from indicators import BollingerBands, RelativeStrengthIndicator


class BollingerStrategy(System):
    def __init__(
        self,
        num_std=3,
        take_profit_multiplier=1.001,
        stop_loss_multiplier=.98,
        short=False,
        **kwargs
        ):
        System.__init__(self, **kwargs)
        self.num_std = num_std
        self.take_profit_multiplier = take_profit_multiplier
        self.stop_loss_multiplier = stop_loss_multiplier
        self.short = short
        self.side = 'short' if self.short else 'long'

        if self.positions.get(self.side):
            self.entry_price = float(self.positions[self.side][0]['entryPrice'])

    def get_entry_signal(self):
        return self.price_ticker < self.mean_price - self.num_std * self.mean_std

    def get_exit_signal(self):
        if self.entry_price:
            return self.entry_price * self.take_profit_multiplier < self.price_ticker

    def get_stop_signal(self):
        if self.entry_price:
            return self.price_ticker < self.entry_price * self.stop_loss_multiplier


class RSIBollingerStrategy(System):
    """
    - [x] Add candle size to params (resolution)
    - [] Add entry signal
    - [] Add exit signal
    - [] Stoploss not implemented exception
    - [] Implement shorting func
    - [] Implement periodic update of params
    """

    def __init__(
        self,
        rsi_source='close',
        rsi_length=14,
        rsi_threshold=.3,
        bollinger_source='close',
        bollinger_length=20,
        bollinger_num_stdev=2,
        max_positions=5,
        max_positions_per_side=3,
        max_risk=.02,
        stoploss_delta=.2,
        **kwargs
        ):
        System.__init__(self, **kwargs)
        self.bollinger_length = bollinger_length
        self.rsi = RelativeStrengthIndicator(
            candles=self.candles,
            source=rsi_source, 
            length=rsi_length, 
        ).indicator
        self.bollinger_bands = BollingerBands(
            candles=self.candles,
            source=bollinger_source,
            length=bollinger_length,
            num_stdev=bollinger_num_stdev,
        ).indicator

    def get_entry_signal(self, price):
        return price < self.mean_price - self.num_std * self.mean_std

    def get_take_profit_signal(self, entry_price, price):
        return entry_price * self.take_profit_multiplier < price

    def get_stop_signal(self, entry_price, price):
        return price < entry_price * self.stop_loss_multiplier


STRATEGIES = {
    'bollinger': BollingerStrategy,
    'volume_rsi': RSIBollingerStrategy,
}
