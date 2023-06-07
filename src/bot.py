import datetime
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from db import (
    get_branches_collection,
    get_companies_collection,
    get_reviews_collection,
    get_users_collection,
)
from scraping import get_branches

users_db = get_users_collection()
companies_db = get_companies_collection()
branches_db = get_branches_collection()
reviews_db = get_reviews_collection()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    username = update.effective_chat.username
    if users_db.find_one({'id': user_id}) is None:
        users_db.insert_one({
            'id': user_id,
            'username': username,
            'created_at': datetime.datetime.now()
        })
    logging.info("User %s started the bot" % (user_id))
    start_message = """
    Hello! I'm a bot 
    """
    await context.bot.send_message(chat_id=user_id, text=start_message)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage company subscription"""

    input_text = update.message.text
    company = None
    logging.info("User %s subscribing to %s" %
                 (update.effective_chat.id, input_text))
    company = companies_db.find_one({"$text": {"$search": input_text}})
    if company is None:
        logging.info("Company not in db, scraping...")
        data = get_branches(company_name=company)
        if not data:
            logging.info('no branches found')
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text='No branches found')
            return

        inserted = companies_db.insert_one({'name': data[0]['org_name']})
        company = companies_db.find_one({'_id': inserted.inserted_id})
        for branch in data:
            branch.pop('org_name')
            branch['company'] = company

        branches_db.insert_many(data)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Company found: {company['name']}",
    )


async def send_daily_timetable(context: ContextTypes.DEFAULT_TYPE):
    pass


async def send_each_minute(context: ContextTypes.DEFAULT_TYPE):

    logging.info("Sending repeating message")
    # await context.bot.send_message(
    #     chat_id=1101717289,
    #     text="This message is sent every minute",
    # )


def setup(app):
    start_handler = CommandHandler(command='start', callback=start)
    subscribe_handler = MessageHandler(filters=filters.TEXT,
                                       callback=subscribe)

    app.add_handler(start_handler)
    app.add_handler(subscribe_handler)

    job_queue = app.job_queue
    job_queue.run_repeating(send_each_minute, interval=60, first=0)