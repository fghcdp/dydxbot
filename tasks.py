from celery import Celery
from app import Bot
from config import BROKER


app = Celery('tasks', broker=BROKER)


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(10.0, run_meanreversion_strategy.s())


@app.task
def run_meanreversion_strategy():
    bot = Bot()
    bot.run_meanreversion_strategy()
