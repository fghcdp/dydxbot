from strategies import STRATEGIES


def run_strategy(name: str, **kwargs):
    # TODO Make it possible to run different strategies based on market
    strategy = STRATEGIES[name](**kwargs)
    if strategy.get_entry_signal():
        strategy.execute_entry()
    elif strategy.get_exit_signal():
        strategy.execute_exit()
    if strategy.get_stop_signal():
        strategy.execute_stoploss()


# NOTE TEMP!!!
from config import (
    MARKETS,
    PARAMETERS,
    STRATEGY,
    TASK_INTERVAL,
)
for market in MARKETS:
    kwargs = PARAMETERS
    kwargs['market'] = market
    run_strategy(STRATEGY, **kwargs)
