from celery import Celery
from app import MarketMaker


app = Celery('tasks')


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(60.0, run_bot.s())


@app.task
def run_bot():
    bot = MarketMaker()
    bot.trade()
