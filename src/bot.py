import asyncio
import datetime
import logging

import emoji
from dateutil.parser import isoparse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

import db
from config import REVIEW_KEY
from scraping import get_branch_reviews, get_branches
from utils import get_cached_datetime, set_cached_datetime, send_reviews

users_db = db.get_users_collection()
companies_db = db.get_companies_collection()
branches_db = db.get_branches_collection()


def build_branches_markup(branches: list) -> InlineKeyboardMarkup:
    colums = []
    for branch in branches:
        colums.append(
            InlineKeyboardButton(text=branch['name'],
                                 callback_data=branch['id']))
    return InlineKeyboardMarkup.from_column(colums)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    username = update.effective_chat.username
    if users_db.find_one({'id': user_id}) is None:
        users_db.insert_one({
            'id': user_id,
            'username': username,
            'branches': [],
            'created_at': datetime.datetime.now()
        })
    logging.info("User %s started the bot" % (user_id))
    start_message = emoji.emojize(
        ":party_popper: Hey and welcome, I'm the bot that sends reviews from 2gis !"
    )
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
        data = get_branches(company_name=input_text)
        if not data:
            logging.info('no branches found')
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text='No branches found')
            return
        company_name = data[0]['org_name']
        confirmation_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text='Correct', callback_data=data)],
             [InlineKeyboardButton(text='Not correct', callback_data='No')]])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Confirm company: {company_name}",
            reply_markup=confirmation_markup,
        )
        return

    branches = branches_db.find({'company': company})
    branches_markup = build_branches_markup(branches)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Choose branch",
        reply_markup=branches_markup,
    )


async def confirm_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm company choice"""
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    if callback_data == 'No':
        await query.edit_message_text(text='Company not confirmed')
        return

    await query.edit_message_text(
        text=f'Company has {len(callback_data)} branches')

    lookup = {'name': callback_data[0]['org_name']}
    result = companies_db.replace_one(lookup, lookup, upsert=True)
    company = companies_db.find_one({'_id': result.upserted_id})
    for branch in callback_data:
        branch.pop('org_name')
        branch['company'] = company

    branches_markup = build_branches_markup(callback_data)
    await query.edit_message_text(
        text=f'Choose branch',
        reply_markup=branches_markup,
    )
    branches_db.insert_many(callback_data)
    context.drop_callback_data(query)


async def branch_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage branch choice"""
    query = update.callback_query
    await query.answer()
    branch_id = query.data
    user = users_db.find_one({'id': query.from_user.id})
    branch = branches_db.find_one({'id': branch_id})
    if branch not in user['branches']:
        users_db.update_one({'id': query.from_user.id},
                            {'$push': {
                                'branches': branch
                            }})

    await query.edit_message_text(text=f'Branch {branch_id} chosen')


async def send_each_minute(context: ContextTypes.DEFAULT_TYPE):
    try:
        last_sent_at = get_cached_datetime()
        logging.info(f"Last sent at {last_sent_at.isoformat()}")
        branches_with_users_ids = db.get_branches_with_users(users_db)
        logging.info("Sending repeating message")
        sent = False
        for dico in branches_with_users_ids:
            user_ids, branch_name, company_name = dico['user_ids'], dico[
                'branch_name'], dico['company']
            reviews = get_branch_reviews(dico['branch_id'],
                                         REVIEW_KEY,
                                         limit=5)
            reviews_to_send = [
                review for review in reviews
                if isoparse(review['date']).astimezone() > last_sent_at
            ]
            if not reviews_to_send:
                logging.info(f"No reviews to send for {branch_name}")
                continue
            logging.info(f"Sending {len(reviews_to_send)} reviews")
            await send_reviews(context, user_ids, reviews_to_send, branch_name,
                               company_name)
            if not sent:
                sent = True
    except Exception as e:
        logging.error(e)
    else:
        if sent:
            logging.info("Sending repeating message done")
            set_cached_datetime(datetime.datetime.now())


def setup(app: Application):
    """Set the bot handlers and job queue"""
    app.add_handler(CommandHandler(command='start', callback=start))
    app.add_handler(MessageHandler(filters=filters.TEXT, callback=subscribe))
    app.add_handler(
        CallbackQueryHandler(callback=confirm_company, pattern=list))
    app.add_handler(CallbackQueryHandler(callback=branch_choice, pattern=str))
    # job_queue = app.job_queue
    # job_queue.run_repeating(send_each_minute, interval=60, first=0)