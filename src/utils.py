import asyncio
import datetime
import json
import pickle
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import emoji
from dateutil.parser import isoparse
from fake_useragent import UserAgent
from pyppeteer.browser import Browser
from pyppeteer.launcher import launch
from pyppeteer.network_manager import Request
from pyppeteer.page import Page
from telegram import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config

####
## Scraping utils
####


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


async def get_new_page(browser: Browser or None = None,
                       page: Page or None = None) -> Page:
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


async def get_reviews_api_key(
        reviews_url:
    str = "https://2gis.ru/ufa/branches/2393075273031352/firm/70000001007027017/tab/reviews",
        page: Page or None = None) -> str:
    if page is None:
        raise RuntimeError('page must be provided')
    intercepted_request = None
    page.on('request', lambda req: asyncio.ensure_future(intercept(req)))

    async def intercept(request: Request):
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


####
## Telegram utils
####

# File path to store the cached datetime
cache_file = "cached_datetime.pickle"


def get_cached_datetime():
    try:

        with open(cache_file, "rb") as file:
            cached_datetime = pickle.load(file)
    except (FileNotFoundError, pickle.UnpicklingError):
        cached_datetime = datetime.datetime.now()
        with open(cache_file, "wb") as file:
            pickle.dump(cached_datetime, file)

    return cached_datetime.astimezone()


def set_cached_datetime(new_datetime: datetime.datetime):
    with open(cache_file, "wb") as file:
        pickle.dump(new_datetime.astimezone(), file)


async def _send_review(context: ContextTypes.DEFAULT_TYPE, user_ids: list,
                       review: dict):
    photos_urls = review['photos']
    rating_str = emoji.emojize(':star:' * review['rating'] + ':new_moon:' *
                               (5 - review['rating']))

    # TODO: Better way to handle timezones
    # As for now, just adapting to ufa timezone
    date_str = (isoparse(review['date']) -
                datetime.timedelta(hours=2)).strftime('%d %B %Y %H:%M')

    text = f'<b>{rating_str} {review["name"]}</b>\n<i>{date_str}</i>\n\n{review["text"]}\n\n'
    for user_id in user_ids:
        if photos_urls:
            media = [InputMediaPhoto(url) for url in photos_urls]
            await context.bot.send_media_group(chat_id=user_id,
                                               media=media,
                                               caption=text,
                                               parse_mode=ParseMode.HTML)
        else:
            await context.bot.send_message(chat_id=user_id,
                                           text=text,
                                           parse_mode=ParseMode.HTML)


async def _notify_branch(context: ContextTypes.DEFAULT_TYPE, user_ids: list,
                         branch_name: str, company_name: str):
    text = emoji.emojize(f'<b>{company_name}</b>\n\n📍 {branch_name} 📍')
    for user_id in user_ids:
        await context.bot.send_message(chat_id=user_id,
                                       text=text,
                                       parse_mode=ParseMode.HTML)


async def send_reviews(context: ContextTypes.DEFAULT_TYPE, user_ids: list,
                       reviews: list, branch_name: str, company_name: str):
    await _notify_branch(context, user_ids, branch_name, company_name)
    sending_tasks = [
        _send_review(context, user_ids, review) for review in reviews
    ]
    await asyncio.gather(*sending_tasks)


def build_branches_markup(
        branches: list,
        with_company_name: bool = False) -> InlineKeyboardMarkup:
    colums = []
    for branch in branches:
        text = branch['name']
        if with_company_name:
            company_name = branch['company']['name'].split(',')[0]
            text = f"{company_name} - {text}"
        colums.append(
            InlineKeyboardButton(text=text, callback_data=branch['id']))
    return InlineKeyboardMarkup.from_column(colums)