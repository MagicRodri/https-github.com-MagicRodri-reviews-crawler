import argparse
import asyncio
import json
import logging
import pprint
import sys

from pyppeteer import launch

from scraping import get_branches_data, get_reviews_through_api
from utils import get_new_page


async def main(headless):
    format = "%(levelname)s:%(asctime)s:%(message)s"
    logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")
    browser = await launch(executablePath='microsoft-edge',
                           headless=headless,
                           args=['--no-sandbox', '--disable-setuid-sandbox'])

    pages = await browser.pages()
    page = await get_new_page(page=pages[0])

    key, data = await get_branches_data(page, company_name='ташир пицца')

    if not data:
        logging.info('no branches found')
        await browser.close()
        sys.exit(0)
    reviews = get_reviews_through_api(key, data)
    pprint.pprint(reviews)
    with open('scraped.json', 'w') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=4)

    await browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--headless',
                        action='store_true',
                        default=False,
                        help='Run in headless mode')
    args = parser.parse_args()

    asyncio.run(main(headless=args.headless))
