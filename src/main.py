import logging

from telegram import Update
from telegram.ext import ApplicationBuilder

from bot import setup
from config import TG_TOKEN


def main():
    format = "%(levelname)s:%(asctime)s:%(message)s"
    logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")
    app = ApplicationBuilder().token(TG_TOKEN).arbitrary_callback_data(
        True).build()
    setup(app)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
