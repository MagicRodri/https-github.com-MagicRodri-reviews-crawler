import asyncio
import json
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fake_useragent import UserAgent
from pyppeteer.browser import Browser
from pyppeteer.page import Page

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