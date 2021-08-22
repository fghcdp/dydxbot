from strategies import STRATEGIES


def run_strategy(name: str, **kwargs):
    # TODO Make it possible to run different strategies based on market
    strategy = STRATEGIES[name](**kwargs)
    if strategy.get_long_entry_signal():
        strategy.execute_long_entry()
    if strategy.get_short_entry_signal():
        strategy.execute_short_entry()
    if strategy.get_long_exit_signal():
        strategy.execute_long_exit()
    if strategy.get_short_exit_signal():
        strategy.execute_short_exit()
    if strategy.get_long_stop_signal():
        strategy.execute_long_stoploss()
    if strategy.get_short_stop_signal():
        strategy.execute_short_stoploss()
    strategy.update_limit_orders()
