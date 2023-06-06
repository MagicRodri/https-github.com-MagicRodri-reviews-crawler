import argparse
import asyncio
import logging
import sys

from pyppeteer import launch

from db import create_db
from scraping import (get_filiales_data, get_reviews_through_api,
                      scrape_filiale_reviews)
from utils import get_new_page


async def main(headless):
    format = "%(levelname)s:%(asctime)s:%(message)s"
    logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")
    create_db()
    browser = await launch(executablePath='/usr/bin/microsoft-edge',
                           headless=headless,
                           args=['--no-sandbox', '--disable-setuid-sandbox'])

    pages = await browser.pages()
    page = await get_new_page(page=pages[0])

    key, data = await get_filiales_data(page, company_name='ташир пицца')

    # get_reviews_through_api(key, data)

    if not data:
        logging.info('no filiales found')
        await browser.close()
        sys.exit(0)

    tasks = [
        asyncio.create_task(scrape_filiale_reviews(filiale, browser=browser))
        for filiale in data
    ]

    await asyncio.gather(*tasks)

    await browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--headless',
                        action='store_true',
                        default=False,
                        help='Run in headless mode')
    args = parser.parse_args()

    asyncio.run(main(headless=args.headless))
