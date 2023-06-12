import locale
import logging

from telegram import Update
from telegram.ext import ApplicationBuilder

from config import TG_TOKEN


def main():
    format = "%(levelname)s:%(asctime)s:%(message)s"
    logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")

    # Higher logging level for httpx to avoid all GET and POST requests being logged
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # For datetime formatting
    # locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')

    app = ApplicationBuilder().token(TG_TOKEN).arbitrary_callback_data(
        True).build()
    setup(app)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
