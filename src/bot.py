import datetime
import logging

import emoji
from dateutil.parser import isoparse
from pymongo.errors import BulkWriteError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ConversationHandler, ContextTypes, MessageHandler,
                          filters)

import db
from config import REVIEW_KEY, TG_LINK, SENDING_INTERVAL
from scraping import get_branch_reviews, get_branches
from utils import get_cached_datetime, send_reviews, set_cached_datetime, build_branches_markup

users_db = db.get_users_collection()
companies_db = db.get_companies_collection()
branches_db = db.get_branches_collection()

ADD, REMOVE, SHOW = ['✅Добавить', '❌Удалить', 'Показать']
main_menu_markup = ReplyKeyboardMarkup([[ADD, REMOVE], [SHOW]],
                                       one_time_keyboard=True,
                                       resize_keyboard=True)
(COMPANY_INPUT, COMPANY_CONFIRMATION, ADD_BRANCH_CHOICE, REMOVE_BRANCH_CHOICE,
 SHOW_BRANCH_CHOICE) = range(1, 6)


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
    start_message = "🎊 <b>Добро пожаловать</b> 🎊 \n\n Я собираю отзывы компаний с 2гис."
    await context.bot.send_message(chat_id=user_id,
                                   text=start_message,
                                   parse_mode=ParseMode.HTML)
    await show_menu(update, context)


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=emoji.emojize(":mobile_phone:<b>Выберите действие</b>"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_markup)


async def reply_keyboard_callback(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
    """Manage reply keyboard"""
    input_text = update.message.text
    user_id = update.effective_chat.id
    if input_text == ADD:
        await context.bot.send_message(
            chat_id=user_id,
            text=emoji.emojize(":pencil: <b>Введите название компании</b>"),
            parse_mode=ParseMode.HTML)
        return COMPANY_INPUT
    elif input_text == REMOVE:
        user = users_db.find_one({'id': user_id})
        if not user['branches']:
            await context.bot.send_message(
                chat_id=user_id,
                text=emoji.emojize(
                    ":confused_face: <i>Вы еще не добавили ни одной компании</i>"
                ),
                parse_mode=ParseMode.HTML)
            await show_menu(update, context)
            return
        branches = user['branches']
        branches_markup = build_branches_markup(branches,
                                                with_company_name=True)
        await context.bot.send_message(
            chat_id=user_id,
            text="<i>Выберите компанию, которую хотите удалить</i>",
            reply_markup=branches_markup,
            parse_mode=ParseMode.HTML)
        return REMOVE_BRANCH_CHOICE
    elif input_text == SHOW:
        user = users_db.find_one({'id': user_id})
        if not user['branches']:
            await context.bot.send_message(
                chat_id=user_id,
                text=emoji.emojize(
                    ":confused_face: <i>Вы еще не добавили ни одной компании</i>"
                ),
                parse_mode=ParseMode.HTML)
            await show_menu(update, context)
            return
        branches = user['branches']
        branches_markup = build_branches_markup(branches,
                                                with_company_name=True)
        await context.bot.send_message(
            chat_id=user_id,
            text=emoji.emojize(
                ":pencil: <i>Выберите компанию, отзывы которой хотите посмотреть</i>"
            ),
            reply_markup=branches_markup,
            parse_mode=ParseMode.HTML)
        return SHOW_BRANCH_CHOICE


async def company_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage company subscription"""

    input_text = update.message.text
    logging.info("User %s subscribing to %s" %
                 (update.effective_chat.id, input_text))

    logging.info("Scraping...")
    data = get_branches(company_name=input_text)
    if not data:
        logging.info('no branches found')
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=emoji.emojize(
                ":confused_face: <i>Ничего не нашел, попробуйте еще раз</i>"),
            parse_mode=ParseMode.HTML)
        return
    company_name = data[0]['org_name']
    confirmation_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text='Да', callback_data=data),
            InlineKeyboardButton(text='Нет', callback_data=['No'])
        ],
    ])
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"<i>Найдено</i>: <b>{company_name}</b>",
        reply_markup=confirmation_markup,
        parse_mode=ParseMode.HTML)
    return COMPANY_CONFIRMATION


async def confirm_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm company choice"""
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    if callback_data[0] == 'No':
        await query.edit_message_text(
            text=emoji.emojize(":pencil: <b>Введите название компании</b>"),
            parse_mode=ParseMode.HTML)
        return COMPANY_INPUT

    lookup = {'name': callback_data[0]['org_name']}
    result = companies_db.replace_one(lookup, lookup, upsert=True)
    company = companies_db.find_one({'_id': result.upserted_id})
    for branch in callback_data:
        branch.pop('org_name')
        branch['company'] = company

    branches_markup = build_branches_markup(callback_data)
    await query.edit_message_text(
        text=emoji.emojize(f"<i>Выберите филиал компании</i>:"),
        reply_markup=branches_markup,
        parse_mode=ParseMode.HTML)
    try:
        branches_db.insert_many(callback_data, ordered=False)
    except BulkWriteError as bwe:
        # Duplicate key error
        pass
    return ADD_BRANCH_CHOICE


async def add_branch_choice(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
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

        await query.edit_message_text(text=emoji.emojize(
            f"✅<i>Добавлено</i>: <b>{branch['company']['name']}, {branch['name']}</b>"
        ),
                                      parse_mode=ParseMode.HTML)
    else:
        await query.edit_message_text(text=emoji.emojize(
            f"<i>Уже добавлено</i>: <b>{branch['company']['name']}, {branch['name']}</b>"
        ),
                                      parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def remove_branch_choice(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    """Remove branch callback"""
    query = update.callback_query
    await query.answer()
    branch_id = query.data
    user = users_db.find_one({'id': query.from_user.id})
    branch = branches_db.find_one({'id': branch_id})
    if branch in user['branches']:
        users_db.update_one({'id': query.from_user.id},
                            {'$pull': {
                                'branches': branch
                            }})

    await query.edit_message_text(text=emoji.emojize(
        f"❌<i>Удалено</i>: <b>{branch['company']['name']}, {branch['name']}</b>"
    ),
                                  parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def show_branch_reviews(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    """Show branch reviews"""
    query = update.callback_query
    await query.answer()
    branch_id = query.data

    reviews = get_branch_reviews(branch_id, REVIEW_KEY, limit=5)
    if not reviews:
        await query.edit_message_text(
            text=emoji.emojize(f":confused_face:<i>Нет отзывов</i>"),
            parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    branch = branches_db.find_one({'id': branch_id})
    user_id = query.from_user.id
    await send_reviews(context=context,
                       user_ids=[user_id],
                       reviews=reviews,
                       branch_name=branch['name'],
                       company_name=branch['company']['name'])
    await show_menu(update, context)
    return ConversationHandler.END


async def send_repeating(context: ContextTypes.DEFAULT_TYPE):
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


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation and return to main menu"""
    user = update.effective_user
    logging.info(f"User {user.id} canceled the conversation.")
    await show_menu(update, context)
    return ConversationHandler.END


async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send feedback"""
    button = InlineKeyboardButton(text="📧", url=TG_LINK)
    markup = InlineKeyboardMarkup([[button]])

    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=f"<i>Отправьте ваш отзыв</i>",
                                   reply_markup=markup,
                                   parse_mode=ParseMode.HTML)


def setup(app: Application):
    """Set the bot handlers and job queue"""

    app.add_handler(CommandHandler(command='start', callback=start))

    add_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters=filters.Text([ADD]),
                           callback=reply_keyboard_callback),
        ],
        states={
            COMPANY_INPUT: [
                MessageHandler(filters=filters.TEXT & (~filters.COMMAND),
                               callback=company_input)
            ],
            COMPANY_CONFIRMATION:
            [CallbackQueryHandler(callback=confirm_company, pattern=list)],
            ADD_BRANCH_CHOICE:
            [CallbackQueryHandler(callback=add_branch_choice, pattern=str)]
        },
        fallbacks=[
            CommandHandler(command='cancel', callback=cancel),
        ],
        allow_reentry=True,
        per_user=True,
        per_chat=True,
        per_message=False,
        name='add_branch')

    remove_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters=filters.Text([REMOVE]),
                           callback=reply_keyboard_callback),
        ],
        states={
            REMOVE_BRANCH_CHOICE:
            [CallbackQueryHandler(callback=remove_branch_choice, pattern=str)]
        },
        fallbacks=[
            CommandHandler(command='cancel', callback=cancel),
        ],
        allow_reentry=True,
        per_user=True,
        per_chat=True,
        per_message=False,
        name='remove_branch')

    show_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters=filters.Text([SHOW]),
                           callback=reply_keyboard_callback),
        ],
        states={
            SHOW_BRANCH_CHOICE:
            [CallbackQueryHandler(callback=show_branch_reviews, pattern=str)]
        },
        fallbacks=[
            CommandHandler(command='cancel', callback=cancel),
        ],
        allow_reentry=True,
        per_user=True,
        per_chat=True,
        per_message=False,
        name='show_branch')

    app.add_handler(add_handler)
    app.add_handler(remove_handler)
    app.add_handler(show_handler)
    app.add_handler(CommandHandler(command='feedback', callback=feedback))

    job_queue = app.job_queue
    job_queue.run_repeating(send_repeating, interval=SENDING_INTERVAL, first=0)
