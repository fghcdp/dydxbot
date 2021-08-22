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
        return self.ticker < self.mean_price - self.num_std * self.mean_std

    def get_exit_signal(self):
        if self.entry_price:
            return self.entry_price * self.take_profit_multiplier < self.ticker

    def get_stop_signal(self):
        if self.entry_price:
            return self.ticker < self.entry_price * self.stop_loss_multiplier


class RSIBollingerStrategy(System):

    def __init__(
        self,
        rsi_source='close',
        rsi_length=14,
        rsi_threshold=.3,
        bollinger_source='close',
        bollinger_length=20,
        bollinger_num_stdev=2,
        **kwargs
        ):
        System.__init__(self, **kwargs)
        self.rsi_threshold = rsi_threshold
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
        self.close = float(self.candles[-1]['close'])
        self.boll = self.bollinger_bands[-1]['boll']
        self.sma = self.bollinger_bands[-1]['sma']
        self.stdev = (self.sma - self.boll) / bollinger_num_stdev

    def get_long_entry_signal(self):
        rsi_oversold = self.rsi_threshold * 100
        return (
            self.rsi[-1] < rsi_oversold
            and self.close < self.boll
            and self.ticker <= self.close
        )

    def get_short_entry_signal(self):
        rsi_overbought = (1 - self.rsi_threshold) * 100
        return (
            self.rsi[-1] > rsi_overbought
            and self.close > self.sma
            and self.ticker >= self.close
        )

    def get_long_exit_signal(self):
        return self.ticker > self.boll + self.stdev * .1

    def get_short_exit_signal(self):
        return self.ticker < self.sma - self.stdev * .1

    def get_long_stop_signal(self):
        for position in self.positions['long']:
            entry_price = float(position['entryPrice'])
            return self.ticker < entry_price * (1 - self.stoploss_delta)

    def get_short_stop_signal(self):
        for position in self.positions['short']:
            entry_price = float(position['entryPrice'])
            return self.ticker > entry_price * (1 + self.stoploss_delta)

STRATEGIES = {
    'bollinger': BollingerStrategy,
    'volume_rsi': RSIBollingerStrategy,
}
