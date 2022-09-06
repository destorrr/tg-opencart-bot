import os

import logging
import redis
import requests

from dotenv import load_dotenv
from opencart_api import *
from opencart_products import OpenCartProducts
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application,
                          CommandHandler,
                          ContextTypes,
                          MessageHandler,
                          filters,
                          CallbackQueryHandler)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

s = requests.Session()

_database = None
OP_USER = os.getenv("OPENCART_DB_USER")
OP_PASSWORD = os.getenv("OPENCART_DB_PASSWORD")
OP_HOST = os.getenv("OPENCART_DB_HOST")
OP_DATABASE = os.getenv("OPENCART_DB_NAME")
API_USERNAME = os.getenv('USER_NAME')
API_KEY = os.getenv('KEY')
WEBSITE = os.getenv('WEBSITE_HOST')


def get_access_to_opencart(s):
    # Получить токен для текущей сессии.
    api_token = get_actual_api_token(s, API_USERNAME, API_KEY,
                                     user_db=OP_USER,
                                     psw=OP_PASSWORD,
                                     host=OP_HOST,
                                     db=OP_DATABASE)
    # Тестовый запрос корзины, для сброса старого токена.
    get_cart_products(s, api_token, WEBSITE)
    # # Если токен сбросился по таймауту, то получить новый для текущей сессии.
    api_token = get_actual_api_token(s, API_USERNAME, API_KEY,
                                     user_db=OP_USER,
                                     psw=OP_PASSWORD,
                                     host=OP_HOST,
                                     db=OP_DATABASE)
    return api_token


async def start(
        api_token, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Send a message when the command /start is issued."""
    op_products = OpenCartProducts(user=OP_USER,
                                   password=OP_PASSWORD,
                                   host=OP_HOST,
                                   database=OP_DATABASE,
                                   website=WEBSITE)
    products = op_products.get_my_products()

    keyboard = []
    for product in products:
        button = []
        if product['id'] < 31:
            button.append(InlineKeyboardButton(product["name"],
                                               callback_data=product["id"]))
        keyboard.append(button)
    cart = [InlineKeyboardButton('Корзина', callback_data=f'cart')]
    keyboard.append(cart)
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        user = update.effective_user
        await update.message.reply_html(
            rf"Hi {user.mention_html()}! Доступные услуги для заказа:",
            reply_markup=reply_markup,
        )
    elif update.callback_query:
        chat_id = update.callback_query.message.chat_id
        message_id = update.callback_query.message.message_id
        await context.bot.delete_message(chat_id=chat_id,
                                         message_id=message_id)
        await context.bot.send_message(text='Доступные услуги для заказа:',
                                       chat_id=chat_id,
                                       reply_markup=reply_markup)

    return 'HANDLE_MENU'


async def handle_menu(
        api_token, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    chat_id = update.callback_query.message.chat_id
    message_id = update.callback_query.message.message_id
    await query.answer()

    if query.data == 'cart':
        return await get_cart(api_token, update, context)
    else:
        op_products = OpenCartProducts(user=OP_USER,
                                       password=OP_PASSWORD,
                                       host=OP_HOST,
                                       database=OP_DATABASE,
                                       website=WEBSITE)
        product = op_products.get_my_product(id_my_product=int(query.data))
        text = (f'{product["name"]}\n\n'
                f'{product["price"]} руб. за ящик.\n'
                f'Остаток ящиков - {product["quantity"]}.\n\n'
                f'Свежий продукт. Прямые поставки из Киргизии.')

        keyboard = [
            [
                InlineKeyboardButton('1 ящик',
                                     callback_data=f'{query.data},1'),
                InlineKeyboardButton('2 ящика',
                                     callback_data=f'{query.data},2'),
                InlineKeyboardButton('3 ящика',
                                     callback_data=f'{query.data},3'),
            ],
            [
                InlineKeyboardButton('Корзина', callback_data=f'cart')
            ],
            [
                InlineKeyboardButton('Назад', callback_data=f'back'),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.delete_message(chat_id=chat_id,
                                         message_id=message_id)

        await context.bot.send_photo(chat_id=chat_id,
                                     photo=product['image'],
                                     caption=text,
                                     reply_markup=reply_markup)
        return 'HANDLE_DESCRIPTION'


async def get_cart(
        api_token, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    chat_id = update.callback_query.message.chat_id
    message_id = update.callback_query.message.message_id
    # api_token = get_access_to_opencart(s)
    cart_content = get_cart_products(s, api_token, WEBSITE)
    print(f'Содержимое корзины - {cart_content}')
    await query.answer()

    keyboard = []

    if cart_content['products']:
        button = []
        total_text = f'Содержимое корзины:\n\n'
        for product in cart_content['products']:
            button.append(InlineKeyboardButton(
                f'Убрать из корзины {product["name"]}',
                callback_data=product["cart_id"]))
            keyboard.append(button)
            button = []
            text = (f"{product['name']}\n"
                    f"{product['price']} руб. за ящик.\n"
                    f"Ящиков в корзине - {product['quantity']} "
                    f"на {product['total']}\n\n")
            total_text += text
        total_text += f'Итого: {cart_content["totals"][-1]["text"]}'
        order = [InlineKeyboardButton('Сделать заказ', callback_data=f'order')]
        keyboard.append(order)
        menu = [InlineKeyboardButton('В меню', callback_data=f'menu')]
        keyboard.append(menu)
        state = 'HANDLE_CART'

    else:
        total_text = 'Корзина пуста...'
        keyboard = [
            [InlineKeyboardButton('В меню', callback_data=f'menu')]
        ]
        state = 'START'

    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    await context.bot.send_message(text=total_text,
                                   chat_id=chat_id,
                                   reply_markup=reply_markup)

    return state


async def handle_description(
        api_token, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    chat_id = update.callback_query.message.chat_id

    await query.answer()

    print(f'query.data - {query.data}')
    if query.data == 'cart':
        return await get_cart(api_token, update, context)
    elif query.data == 'back':
        return await start(api_token, update, context)
    else:
        user_reply = query.data.split(',')
        product_id = user_reply[0]
        product_quantity = int(user_reply[1])
        print(f'Product_id - {product_id}')
        print(f'Product_quantity - {product_quantity}')
        cart_add(s, api_token, product_id, WEBSITE, product_quantity)

        if product_quantity:
            await context.bot.send_message(
                text=f'Товар добавлен в количестве {product_quantity}',
                chat_id=chat_id
            )

        return 'HANDLE_DESCRIPTION'


async def handle_cart(
        api_token, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    await query.answer()

    if query.data == 'menu':
        return await start(api_token, update, context)
    elif query.data == 'order':
        return await get_contacts(api_token, update, context)
    else:
        cart_remove(s, api_token, cart_id=query.data)
        cart_content = get_cart_products(s, api_token, WEBSITE)
        print(f'Содержимое корзины - {cart_content}')
        await get_cart(api_token, update, context)
        return 'GET_CART'


async def get_contacts(
        api_token, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    if update.callback_query:
        query = update.callback_query
        chat_id = update.callback_query.message.chat_id
        user_reply = query.data.split(',')
        if user_reply[-1] == '_true':
            order_id = create_order(s, api_token,
                                    telephone=user_reply[0],
                                    lastname=chat_id,
                                    website=WEBSITE)
            print(f'Номер телефона - {user_reply[0]}')
            text = (f'Заказ сохранен.\n'
                    f'Номер заказа - {order_id}.\n'
                    f'Как будет товар, мы вас оповестим.')
            await context.bot.send_message(text=text,
                                           chat_id=chat_id)
            return await start(api_token, update, context)
        elif user_reply[-1] == '_false':
            await context.bot.send_message(text=f'Введите еще раз номер',
                                           chat_id=chat_id)
            return 'WAITING_CONTACTS'
        else:
            await context.bot.send_message(text=f'Ведите ваш номер телефона',
                                           chat_id=chat_id)
            return 'WAITING_CONTACTS'
    elif update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id

        keyboard = [
            [InlineKeyboardButton('Верно',
                                  callback_data=f'{user_reply},_true')],
            [InlineKeyboardButton('Не верно', callback_data=f'_false')],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        text = f'Ваш номер - {user_reply}. Верно?'
        await update.message.reply_text(text=text,
                                        reply_markup=reply_markup)
        return 'WAITING_CONTACTS'


async def handle_users_reply(
        update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_database_connection()
    api_token = get_access_to_opencart(s)
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
        print(f'Current state first - {user_state}')
    else:
        user_state = db.get(chat_id)
        print(f'Current state from DB - {user_state}')

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'GET_CART': get_cart,
        'HANDLE_CART': handle_cart,
        'WAITING_CONTACTS': get_contacts,
    }
    state_handler = states_functions[user_state]

    try:
        next_state = await state_handler(api_token, update, context)
        print(f'Next state - {next_state}')
        db.set(chat_id, next_state)
    except Exception as err:
        print(f'Ошибка - {err}')


def get_database_connection():
    global _database
    if _database is None:
        password = os.getenv("PASS_REDIS")
        host = os.getenv("HOST_REDIS")
        port = os.getenv("PORT_REDIS")
        _database = redis.Redis(host=host,
                                port=port,
                                password=password,
                                charset="utf-8",
                                decode_responses=True)
    return _database


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Извините, я не понял эту команду..."
    )


def main() -> None:

    token = os.getenv("TOKEN_TG")

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", handle_users_reply))
    application.add_handler(CallbackQueryHandler(handle_users_reply))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                           handle_users_reply))
    application.add_handler(MessageHandler(filters.TEXT | filters.COMMAND,
                                           unknown))

    application.run_polling()


if __name__ == '__main__':
    main()
