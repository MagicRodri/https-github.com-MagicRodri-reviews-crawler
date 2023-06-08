import asyncio
import datetime
import json
import pickle
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fake_useragent import UserAgent
from pyppeteer.browser import Browser
from pyppeteer.page import Page
from telegram import InputMediaPhoto
from telegram.ext import ContextTypes

import config


def clean_text(raw_text: str) -> str:
    # Remove special characters
    cleaned_text = unicodedata.normalize('NFKD', raw_text).encode(
        'utf-8', 'replace').decode('utf-8')

    return cleaned_text


def get_user_agent():
    ua = UserAgent(verify_ssl=False)
    return ua.random


async def load_cookies(page: Page):
    if Path('cookies.json').exists():
        with open('cookies.json', 'r') as f:
            cookies = json.load(f)
            await page.setCookie(*cookies)


async def save_cookies(page: Page):
    cookies = await page.cookies()
    with open('cookies.json', 'w') as f:
        json.dump(cookies, f)


async def get_new_page(browser: Browser | None = None,
                       page: Page | None = None) -> Page:
    if browser is None and page is None:
        raise RuntimeError('browser or page must be provided')
    if browser:
        page = await browser.newPage()
    page.setDefaultNavigationTimeout(0)
    await load_cookies(page)
    return page


async def safe_close_page(page):
    pages = await page.browser.pages()
    if len(pages) > 1:
        await page.close()
        return True
    return False


async def get_reviews_api_key(page: Page, reviews_url: str) -> str:

    intercepted_request = None
    page.on('request', lambda req: asyncio.ensure_future(intercept(req)))

    async def intercept(request):
        nonlocal intercepted_request
        if request.url.startswith(config.REVIEW_API_URL):
            intercepted_request = request

    # Navigate to the page where the request will be made
    await page.goto(reviews_url)
    await page.waitForRequest(lambda _: intercepted_request is not None)

    parsed_url = urlparse(intercepted_request.url)
    query_params = parse_qs(parsed_url.query)
    # the key or an empty string
    key = query_params.get('key', [''])[0]

    return key


# File path to store the cached datetime
cache_file = "cached_datetime.pickle"


def get_cached_datetime():
    try:

        with open(cache_file, "rb") as file:
            cached_datetime = pickle.load(file)
    except (FileNotFoundError, pickle.UnpicklingError):
        cached_datetime = datetime.datetime.now().astimezone()
        with open(cache_file, "wb") as file:
            pickle.dump(cached_datetime, file)

    return cached_datetime


def set_cached_datetime(new_datetime: datetime.datetime):
    with open(cache_file, "wb") as file:
        pickle.dump(new_datetime.astimezone(), file)


async def send_review(context: ContextTypes.DEFAULT_TYPE, user_id: str,
                      review: dict):
    photos_urls = [
        "https://cachizer1.2gis.com/reviews-photos/2a9d0f18-5436-4154-992e-5525c7f6e47e.jpg",
        "https://cachizer1.2gis.com/reviews-photos/fab3e57a-bb66-4cd7-a817-159ed5b22530.jpg",
        "https://cachizer1.2gis.com/reviews-photos/6260b11b-cbf5-4765-afb5-c0f9f801e95c.jpg"
    ]

    text = f"{review['name']}:\n{review['text']}"
    if photos_urls:
        media = [InputMediaPhoto(media=url) for url in photos_urls]
        await context.bot.send_media_group(chat_id=user_id,
                                           media=media,
                                           caption=text)

    await context.bot.send_message(chat_id=user_id, text=text)
