import asyncio
import concurrent.futures
import logging
from typing import Optional

from pyppeteer.browser import Browser
from pyppeteer.element_handle import ElementHandle
from pyppeteer.errors import ElementHandleError
from pyppeteer.page import Page
from requests_html import HTML, HTMLSession

import config
from utils import (
    clean_text,
    get_new_page,
    get_reviews_api_key,
    safe_close_page,
    save_cookies,
)


async def _close_cookies_footer_if_needed(page: Page,
                                          close_selector: str | None = None):
    if close_selector is None:
        close_selector = '._euwdl0'
    close_btn = await page.querySelector(close_selector)
    if close_btn is not None:
        await close_btn.click()


async def extract_branches_data_from_divs(
        page: Page, divs: list[ElementHandle]) -> list[dict]:
    """Extract branches links from divs"""

    data = []
    if not divs:
        return data
    org_name = None
    for div in divs:
        html = await page.evaluate('(element) => element.outerHTML', div)
        html_object = HTML(html=clean_text(html))
        if org_name is None:
            org_name = html_object.find('div span._1al0wlf span',
                                        first=True).text
            additional = html_object.find('span._oqoid', first=True).text
            if additional:
                org_name = f'{org_name}, {additional}'.capitalize()
        link = html_object.find('div._zjunba a',
                                first=True).attrs.get('href').split('?')[0]
        name = html_object.find('div._klarpw span._1w9o2igt',
                                first=True).text.strip()
        data.append({
            'id': link.split('/')[-1],
            'name': clean_text(name),
            'link': link,
            'org_name': org_name
        })
    return data


async def _navigate_to_next_page(page: Page) -> bool:
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


async def _load_reviews(page: Page):
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

    # Scrape the photos uploaded (if any)
    photos = [img.attrs['src'] for img in html_object.find('img._1env6hv')]

    # Scrape the comment
    text = None
    try:
        text = html_object.find('div._49x36f a._ayej9u3', first=True).text
    except AttributeError:
        text = html_object.find('a._1it5ivp', first=True).text

    # Scrape the reply (if any)
    reply_element = html_object.find('div._sgs1pz', first=True)
    reply = {}
    if reply_element:
        reply_name = reply_element.find('div._y7bbr0 span', first=True).text
        reply_date = reply_element.find('div._1fw4r5p',
                                        first=True).text.split(',')[0]
        reply_text = reply_element.find('div._j1il10', first=True).text
        reply = {
            'org_name': clean_text(reply_name),
            'date': reply_date,
            'text': clean_text(reply_text)
        }

    return {
        'name': name,
        'date': date,
        'photos': photos,
        'text': clean_text(text),
        'reply': reply
    }


async def get_branches_data(
        page: Page,
        city: Optional[str] = 'ufa',
        company_name: Optional[str] = 'Вкусно — и точка') -> tuple[str, list]:
    """Get all branches links from 2gis.ru"""

    branches_data = []
    await page.goto(f'https://2gis.ru/{city}/search/{company_name}')
    await page.waitForSelector('._1kf6gff')
    await _close_cookies_footer_if_needed(page)

    logging.info('Extracting branches data')
    divs = await page.querySelectorAll('._1kf6gff')
    branches_data.extend(await extract_branches_data_from_divs(page, divs))
    while await _navigate_to_next_page(page):
        divs = await page.querySelectorAll('._1kf6gff')
        branches_data.extend(await extract_branches_data_from_divs(page, divs))
    logging.info(f"Extracted {len(branches_data)} branches' data")

    if branches_data:
        key = await get_reviews_api_key(
            page, f"https://2gis.ru{branches_data[0]['link']}/tab/reviews")

    await save_cookies(page)
    await safe_close_page(page)
    return key, branches_data


def safe_scrape(scraper_function,
                semaphore: asyncio.Semaphore = asyncio.Semaphore(3)):

    async def runner(*args, **kwargs):
        async with semaphore:
            await scraper_function(*args, **kwargs)

    return runner


@safe_scrape
async def scrape_branch_reviews(branch_data: dict,
                                page: Page | None = None,
                                browser: Browser | None = None,
                                ensure_reviews_loaded: Optional[bool] = True):
    """Scrape reviews from a branch"""
    if page is None and browser is None:
        raise RuntimeError('At least one of page or browser must be provided')
    if page is None:
        page = await get_new_page(browser)

    try:
        await page.goto(f"https://2gis.ru{branch_data['link']}/tab/reviews",
                        {'waitUntil': "domcontentloaded"})

        logging.info(f"Extracting reviews from {branch_data['name']}")

        if ensure_reviews_loaded:
            await _load_reviews(page)

        divs = await page.querySelectorAll('._11gvyqv')
        reviews = []
        for div in divs:
            review = await get_review_data(page, div)
            reviews.append(review)

        logging.info(
            f"extracted {len(reviews)} reviews from {branch_data['name']}")

        await save_cookies(page)

    finally:
        await page.close()
        return reviews


def get_branches(company_name: Optional[str] = "ташир пицца",
                 city: Optional[str] = 'ufa') -> list[dict]:

    url = f"https://2gis.ru/{city}/search/{company_name}"
    session = HTMLSession()
    res = session.get(url)
    first_response_url = res.url
    is_empty_page = False
    branches = []
    counter = 1
    org_name = None
    while True:
        url = f"https://2gis.ru/{city}/search/{company_name}"
        divs = res.html.find('div._1kf6gff')
        for div in divs:
            if org_name is None:
                org_name = div.find('div span._1al0wlf span', first=True).text
                additional = div.find('span._oqoid', first=True).text
                if additional:
                    org_name = f'{org_name}, {additional}'.capitalize()
            name = div.find('div._klarpw span._1w9o2igt', first=True).text
            link = div.find('div._zjunba a',
                            first=True).attrs.get('href').split('?')[0]
            branch = {
                'id': link.split('/')[-1],
                'name': clean_text(name),
                'link': link,
                'org_name': org_name
            }
            branches.append(branch)

        # TODO: Deal with url returning down to first page
        counter += 1
        res = session.get(f"{url}/page/{counter}")
        is_empty_page = res.html.find(
            'div._1wpb8t2',
            first=True) is not None or res.url == first_response_url
        if is_empty_page:
            break

    return branches


def clean_api_reviews(reviews: list) -> list:

    cleaned = [{
        'id':
        review['id'],
        'name':
        review['user']['name'],
        'text':
        review['text'],
        'date':
        review['date_created'],
        'photos': [photo['preview_urls']['url'] for photo in review['photos']],
        'reply':
        review['official_answer']
    } for review in reviews]

    return cleaned


def get_branch_reviews(branch_id: str,
                       key: str,
                       branch_name: str | None = None) -> list:
    """Get branch reviews through public api"""
    if branch_name is not None:
        logging.info(f'Getting reviews for {branch_name}')
    endpoint = f"{config.REVIEW_API_URL}/{branch_id}/reviews"
    params = {'key': key, 'limit': 50}
    session = HTMLSession()
    res = session.get(endpoint, params=params)
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
        res = session.get(next_link)

    if branch_name is not None:
        logging.info(f'Got reviews for {branch_name}')
    return clean_api_reviews(reviews)


def get_reviews_through_api(key: str, branches_data: list) -> list:
    """Get reviews through public api"""
    end_data = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = [
            executor.submit(get_branch_reviews, branch_data['id'], key,
                            branch_data['name'])
            for branch_data in branches_data
        ]
        for f in concurrent.futures.as_completed(results):
            end_data.extend(f.result())

    return end_data
