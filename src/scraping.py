import asyncio
import logging
from typing import Optional

import requests
from pyppeteer.browser import Browser
from pyppeteer.element_handle import ElementHandle
from pyppeteer.errors import ElementHandleError
from pyppeteer.page import Page
from requests_html import HTML

import config
from db import save_reviews_to_db
from utils import clean_text, get_new_page, get_reviews_api_key, save_cookies


async def close_cookies_footer_if_needed(page: Page,
                                         close_selector: str | None = None):
    if close_selector is None:
        close_selector = '._euwdl0'
    close_btn = await page.querySelector(close_selector)
    if close_btn is not None:
        await close_btn.click()


async def extract_filiales_data_from_divs(
        page: Page, divs: list[ElementHandle]) -> list[dict]:
    """Extract filiales links from divs"""

    data = []
    if not divs:
        return data
    for div in divs:
        html = await page.evaluate('(element) => element.outerHTML', div)
        html_object = HTML(html=clean_text(html))
        link = html_object.find('div._zjunba a',
                                first=True).attrs.get('href').split('?')[0]
        name = html_object.find('div._klarpw span._1w9o2igt',
                                first=True).text.strip()
        data.append({'name': clean_text(name), 'link': link})
    return data


async def navigate_to_next_page(page: Page) -> bool:
    """Navigate to the next page of the reviews"""
    try:
        active_btn_class = '_n5hmn94'
        secont_btn_div = await page.querySelector('._5ocwns > *:nth-child(2)')
        div_class = await page.evaluate("(node) => node.getAttribute('class')",
                                        secont_btn_div)
        if div_class == active_btn_class:
            await secont_btn_div.click()
            await page.waitForNavigation()
            await page.waitForSelector('._5ocwns')
            return True
    except ElementHandleError:
        # Navigation buttons don't exist
        pass

    return False


async def load_reviews(page: Page):
    """Load all reviews into the html page"""
    load_btn_class = '_1iczexgz'
    load_btn = await page.querySelector(f'.{load_btn_class}')
    try:
        logging.info("Loading reviews into page")
        while load_btn is not None:
            await load_btn.click()
            await asyncio.sleep(0.2)
            load_btn = await page.querySelector(f'.{load_btn_class}')
        logging.info('reviews loaded')
    except ElementHandleError:
        logging.warn('Loading failed, skipping...')


async def get_review_data(page: Page, review: ElementHandle) -> dict:
    """Get all data from a review"""
    html = await page.evaluate('(element) => element.outerHTML', review)
    html_object = HTML(html=clean_text(html))
    # Scrape the commenter's name
    name = html_object.find('div._1wz5xvq span._16s5yj36', first=True).text

    # Scrape the date of the comment
    date = html_object.find('div._4mwq3d', first=True).text

    # Scrape the images uploaded (if any)
    images = [img.attrs['src'] for img in html_object.find('img._1env6hv')]

    # Scrape the comment
    comment = None
    try:
        comment = html_object.find('div._49x36f a._ayej9u3', first=True).text
    except AttributeError:
        comment = html_object.find('a._1it5ivp', first=True).text

    # Scrape the reply (if any)
    reply_element = html_object.find('div._sgs1pz', first=True)
    reply = {}
    if reply_element:
        reply_name = reply_element.find('div._y7bbr0 span', first=True).text
        reply_date = reply_element.find('div._1fw4r5p',
                                        first=True).text.split(',')[0]
        reply_text = reply_element.find('div._j1il10', first=True).text
        reply = {'name': reply_name, 'date': reply_date, 'text': reply_text}

    return {
        'name': name,
        'date': date,
        'images': images,
        'comment': comment,
        'reply': reply
    }


async def get_filiales_data(
        page: Page,
        company_name: Optional[str] = 'Вкусно — и точка') -> tuple[str, list]:
    """Get all filiales links from 2gis.ru"""

    filiales_data = []
    await page.goto(f'https://2gis.ru/search/{company_name}')
    await page.waitForSelector('._1kf6gff')
    await close_cookies_footer_if_needed(page)

    logging.info('Extracting filiales data')
    divs = await page.querySelectorAll('._1kf6gff')
    filiales_data.extend(await extract_filiales_data_from_divs(page, divs))
    while await navigate_to_next_page(page):
        divs = await page.querySelectorAll('._1kf6gff')
        filiales_data.extend(await extract_filiales_data_from_divs(page, divs))
    logging.info(f"Extracted {len(filiales_data)} filiales' data")

    if filiales_data:
        key = await get_reviews_api_key(
            page, f"https://2gis.ru{filiales_data[0]['link']}/tab/reviews")

    await save_cookies(page)
    await page.close()
    return key, filiales_data


def safe_scrape(scraper_function,
                semaphore: asyncio.Semaphore = asyncio.Semaphore(3)):

    async def runner(*args, **kwargs):
        async with semaphore:
            await scraper_function(*args, **kwargs)

    return runner


@safe_scrape
async def scrape_filiale_reviews(filiale_data: dict,
                                 page: Page | None = None,
                                 browser: Browser | None = None,
                                 ensure_reviews_loaded: Optional[bool] = True):
    """Scrape reviews from a filiale"""

    if page is None and browser is None:
        raise RuntimeError('At least one of page or browser must be provided')
    if page is None:
        page = await get_new_page(browser)

    try:
        await page.goto(f"https://2gis.ru{filiale_data['link']}/tab/reviews",
                        {'waitUntil': "domcontentloaded"})

        logging.info(f"Extracting reviews from {filiale_data['name']}")

        if ensure_reviews_loaded:
            await load_reviews(page)

        divs = await page.querySelectorAll('._11gvyqv')
        reviews = []
        for div in divs:
            review = await get_review_data(page, div)
            reviews.append(review)

        logging.info(
            f"extracted {len(reviews)} reviews from {filiale_data['name']}")

        logging.info(f"Saving reviews from {filiale_data['name']}")
        save_reviews_to_db(filiale_data['name'], reviews)
        logging.info(
            f"Saved {len(reviews)} reviews from {filiale_data['name']}")
        await save_cookies(page)
        return reviews
    finally:
        await page.close()


def get_branch_reviews(branch_id: str, key: str) -> list:
    """Get branch reviews through public api"""
    endpoint = f"{config.REVIEW_API_URL}/{branch_id}/reviews"
    params = {'key': key, 'limit': 50}
    res = requests.get(endpoint, params=params)
    reviews = []
    data = None
    next_link = None

    while True:
        if not res.status_code == 200:
            break
        data = res.json()
        reviews.extend(data['reviews'])
        next_link = data['meta'].get('next_link')
        if not next_link:
            break
        res = requests.get(next_link)

    return reviews


def get_reviews_through_api(key: str, branches_data: list) -> list:
    branches_data = [{
        'name': item['name'],
        'branch_id': item['link'].split('/')[-1]
    } for item in branches_data]

    for name, id in branches_data:
        reviews = get_branch_reviews(id, key)
