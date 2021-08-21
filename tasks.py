from celery import Celery
from operations import run_strategy
from config import (
    MARKETS,
    PARAMETERS,
    STRATEGY,
    TASK_INTERVAL,
)


app = Celery('tasks', task_always_eager=True)


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(TASK_INTERVAL, run_bot.s(STRATEGY, **PARAMETERS))


@app.task
def run_bot(args, **kwargs):
    for market in MARKETS:
        kwargs['market'] = market
        run_strategy(args, **kwargs)
