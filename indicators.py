import pandas


class BollingerBands:

    def __init__(
        self,
        candles: list,
        source='close',
        length=20,
        num_stdev=2,
        ):
        self.candles = candles
        self.source = source
        self.length = length
        self.num_stdev = num_stdev
        self.indicator = self.create_indicator()

    def create_indicator(self):
        df = pandas.DataFrame(self.candles, dtype=float)
        df['sma'] = df[self.source].rolling(self.length, min_periods=1).mean()
        df['stdev'] = df[self.source].rolling(self.length, min_periods=1).std()
        df['boll'] = df.sma - df.stdev * self.num_stdev
        df['bolu'] = df.sma + df.stdev * self.num_stdev
        return df[['boll', 'sma', 'bolu']].to_dict('records')


class RelativeStrengthIndicator:

    def __init__(
        self,
        candles: list,
        source: str = 'close',
        length: int = 14,
        ):
        self.candles = candles
        self.source = source
        self.length = length
        self.indicator = self.create_indicator()

    def create_indicator(self): 
        df = pandas.DataFrame(self.candles, dtype=float)
        delta = df[self.source].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=self.length, adjust=False).mean()
        ema_down = down.ewm(com=self.length, adjust=False).mean()
        rs = ema_up / ema_down
        return (100 - (100 / (1 + rs))).tolist()
