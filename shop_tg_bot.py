import os

import logging
import json
import phonenumbers
import redis
import requests

from dotenv import load_dotenv
from geopy import distance
from opencart_api import *
from opencart_products import OpenCartProducts
from telegram import (InlineKeyboardButton,
                      InlineKeyboardMarkup,
                      Update,
                      constants,
                      KeyboardButton,
                      LabeledPrice,
                      ReplyKeyboardMarkup)
from telegram.ext import (Application,
                          CommandHandler,
                          ContextTypes,
                          MessageHandler,
                          filters,
                          CallbackQueryHandler,
                          PreCheckoutQueryHandler)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)-15s - %(levelname)-8s - (%(lineno)d)%(message)s",
    level=logging.INFO
)
logger = logging.getLogger('tg_bot')
logger.setLevel(logging.DEBUG)

s = requests.Session()
sessions = {}

_database = None
OP_USER = os.getenv("OPENCART_DB_USER")
OP_PASSWORD = os.getenv("OPENCART_DB_PASSWORD")
OP_HOST = os.getenv("OPENCART_DB_HOST")
OP_DATABASE = os.getenv("OPENCART_DB_NAME")
API_USERNAME = os.getenv('OPENCART_API_USER_NAME')
API_KEY = os.getenv('OPENCART_API_KEY')
WEBSITE = os.getenv('WEBSITE_HOST')
YA_GEO_API_KEY = os.getenv('YA_GEO_API_KEY')
PAYMENT_PROVIDER_TOKEN = os.getenv('PAYMENT_PROVIDER_TOKEN')


def fetch_coordinates(apikey, address):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']
    with open('data/geo.json', 'w', encoding='utf-8') as f:
        json.dump(found_places, f, indent=4, ensure_ascii=False)

    if not found_places:
        return None

    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")

    return lat, lon


def get_keyboard_menu(products: list, count_lines_on_page, page_num=1):
    """Клавиатура для полного списка товаров."""
    b = page_num * count_lines_on_page
    a = b - count_lines_on_page
    next_page = page_num + 1
    prev_page = page_num - 1

    keyboard = []

    for product in products[a:b]:
        button = []
        button.append(InlineKeyboardButton(product["name"],
                                           callback_data=product["id"]))
        keyboard.append(button)

    other_buttons = [
        InlineKeyboardButton('Пред', callback_data=f'page{prev_page}'),
        InlineKeyboardButton('След', callback_data=f'page{next_page}'),
    ]
    keyboard.append(other_buttons)

    cart = [InlineKeyboardButton('Корзина', callback_data=f'cart')]

    keyboard.append(cart)
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


async def start(
        api_token, update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> str:
    """Отправляет сообщение, когда введена команда /start."""
    op_products = OpenCartProducts(user=OP_USER,
                                   password=OP_PASSWORD,
                                   host=OP_HOST,
                                   database=OP_DATABASE,
                                   website=WEBSITE)
    logger.debug(f'op_products: {op_products}')
    # Если category_id=None, то получим список всех товаров.
    # Иначе список товаров определенной категории.
    category_pizza = 59
    products = op_products.get_my_products(category_id=category_pizza)
    user = update.effective_user

    total_count_products = len(products)
    count_lines_on_page = 8
    page_count = int(total_count_products / count_lines_on_page)
    if total_count_products % count_lines_on_page > 0:
        page_count = int(page_count + 1)

    if update.message:
        reply_markup = get_keyboard_menu(products, count_lines_on_page)
        await update.message.reply_html(
            rf'Привет {user.mention_html()}! Выбирай то, что тебе нравится:',
            reply_markup=reply_markup,
        )
    elif update.callback_query:
        logger.debug(f'callback_query.data: {update.callback_query.data}')
        chat_id = update.callback_query.message.chat_id
        message_id = update.callback_query.message.message_id

        reply_markup = get_keyboard_menu(products, count_lines_on_page)

        if (update.callback_query.data == 'menu'
                or update.callback_query.data == 'back'
                or update.callback_query.data.split(',')[-1] == '_true'
                or update.callback_query.data.split(',')[0] == 'pickup'
                or update.callback_query.data.split(';')[0] == 'pickup'
                or update.callback_query.data.split(';')[0] == 'delivery'):
            await context.bot.delete_message(chat_id=chat_id,
                                             message_id=message_id)
            text = 'Выбирай то, что тебе нравится:'
            await context.bot.send_message(text=text,
                                           chat_id=chat_id,
                                           reply_markup=reply_markup)
        else:
            query = update.callback_query.data.lstrip('page')
            logger.debug(f'QUERY: {query}')
            page_num = int(query)
            if page_num > page_count:
                page_num = 1
            elif page_num < 1:
                page_num = page_count

            reply_markup = get_keyboard_menu(products,
                                             count_lines_on_page,
                                             page_num=page_num)

            await context.bot.delete_message(chat_id=chat_id,
                                             message_id=message_id)
            await context.bot.send_message(
                text=f'Выбирай то, что тебе нравится:',
                chat_id=chat_id,
                reply_markup=reply_markup,
            )
            # return 'START'
    return 'HANDLE_MENU'


async def handle_menu(
        api_token, update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    chat_id = update.callback_query.message.chat_id
    message_id = update.callback_query.message.message_id
    await query.answer()

    logger.debug(f'QUERY_DATA in HANDLE_MENU: {query.data}')

    if query.data == 'cart':
        return await get_cart(api_token, update, context)
    elif query.data.startswith('page'):
        return await start(api_token, update, context)
    else:
        op_products = OpenCartProducts(user=OP_USER,
                                       password=OP_PASSWORD,
                                       host=OP_HOST,
                                       database=OP_DATABASE,
                                       website=WEBSITE)
        product = op_products.get_my_product(id_my_product=int(query.data))

        cart_content = get_cart_products(s, api_token, WEBSITE)
        cart_products = cart_content['products']
        if cart_products:
            for cart_product in cart_products:
                if cart_product['name'] == product["name"]:
                    quantity = cart_product['quantity']
                    break
                else:
                    quantity = '0'
        else:
            quantity = '0'

        text = (f'{product["name"]}\n'
                f'Стоимость: {product["price"]} руб.\n\n'
                f'{product["description"]}.\n\n'
                f"Наличие этого товара в корзине: {quantity} шт.")

        keyboard = [
            [
                InlineKeyboardButton('Положить в корзину',
                                     callback_data=f'{query.data},1'),
            ],
            [
                InlineKeyboardButton('Корзина', callback_data=f'cart'),
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
                                     reply_markup=reply_markup,
                                     parse_mode=constants.ParseMode.HTML)
        return 'HANDLE_DESCRIPTION'


async def get_cart(
        api_token, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    chat_id = update.callback_query.message.chat_id
    message_id = update.callback_query.message.message_id
    cart_content = get_cart_products(s, api_token, WEBSITE)
    await query.answer()

    keyboard = []

    if cart_content['products']:
        button = []
        total_text = f'<b>Содержимое корзины:</b>\n\n'
        for product in cart_content['products']:
            button.append(InlineKeyboardButton(
                f'Убрать из корзины {product["name"]}',
                callback_data=product["cart_id"]))
            keyboard.append(button)
            button = []
            text = (f"<u><b>{product['name']}</b></u>\n"
                    f"Цена: <i>{product['price']}</i>\n"
                    f"Количество в корзине - <i>{product['quantity']} "
                    f"на {product['total']}</i>\n\n")
            total_text += text
        total_text += f'<b>Итого:</b> {cart_content["totals"][-1]["text"]}'
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
                                   reply_markup=reply_markup,
                                   parse_mode=constants.ParseMode.HTML)

    return state


async def handle_description(
        api_token, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query

    logger.debug(f'query.data - {query.data}')
    if query.data == 'cart':
        await query.answer()
        return await get_cart(api_token, update, context)
    elif query.data == 'back':
        await query.answer()
        return await start(api_token, update, context)
    else:
        user_reply = query.data.split(',')
        product_id = user_reply[0]
        product_quantity = int(user_reply[1])
        logger.debug(f'Product_id - {product_id}')
        logger.debug(f'Product_quantity - {product_quantity}')
        cart_add(s, api_token, product_id, WEBSITE, product_quantity)

        if product_quantity:
            text = (f'Добавлено в корзину, \n'
                    f'в количестве {product_quantity} порция.')
            await query.answer(text=text, show_alert=True)

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
        cart_remove(s, api_token, cart_id=query.data, website=WEBSITE)
        await get_cart(api_token, update, context)
        return 'GET_CART'


async def get_contacts(
        api_token, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    if update.callback_query:
        query = update.callback_query
        chat_id = update.callback_query.message.chat_id
        user = update.effective_user
        user_reply = query.data.split(',')
        logger.debug(f'user_reply: {user_reply}')
        if user_reply[-1] == '_true':
            # order_id = create_order(s, api_token,
            #                         telephone=user_reply[0],
            #                         lastname=chat_id,
            #                         website=WEBSITE)
            logger.debug(f'Номер телефона: {user_reply[0]}')
            logger.debug(f'User: {user}')
            logger.debug(f'User_id: {user["id"]}')
            logger.debug(f'Chat_id: {chat_id}')
            db = get_database_connection()
            db.set(user['id'] + 1, user_reply[0])
            logger.debug(f'Номер телефона в Redis:{db.get(user["id"] + 1)}')
            # text = (f'Заказ сохранен.\n'
            #         f'Номер заказа - {order_id}.\n'
            #         f'Как будет товар, мы вас оповестим.')
            text = (f'Для расчета стоимости доставки отправьте свой адрес '
                    f'или свою геопозицию.')
            await context.bot.send_message(text=text,
                                           chat_id=chat_id)
            # return await start(api_token, update, context)
            # return await handle_location(api_token, update, context)
            return 'LOCATION'

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

        phone_number = user_reply
        logger.debug(f'phone_number: {phone_number}')
        text = (f'<b>Некорректно введен номер телефона.</b>\n\n'
                f'Попробуйте еще раз\n'
                f'или введите /start для возврата в начало.')
        try:
            x = phonenumbers.parse(phone_number, 'RU')
        except phonenumbers.phonenumberutil.NumberParseException:
            await update.message.reply_text(
                text=text,
                parse_mode=constants.ParseMode.HTML)
            return 'WAITING_CONTACTS'

        possible = phonenumbers.is_possible_number(x)
        valid = phonenumbers.is_valid_number(x)

        if not possible or not valid:
            await update.message.reply_text(
                text=text,
                parse_mode=constants.ParseMode.HTML)

        else:
            number = phonenumbers.format_number(
                x, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            text = f'Ваш номер: <b>{number}</b>. Верно?'

            logger.debug(f'user_reply: {user_reply}')
            keyboard = [
                [InlineKeyboardButton('Верно',
                                      callback_data=f'{user_reply},_true')],
                [InlineKeyboardButton('Не верно', callback_data=f'_false')],
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=constants.ParseMode.HTML)

        return 'WAITING_CONTACTS'


async def handle_location(
        api_token, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    if update.message:
        chat_id = update.message.chat_id
        logger.debug(f'update.message: {update.message}')
        stores_locations = get_all_stores_locations(OP_USER, OP_PASSWORD,
                                                    OP_HOST, OP_DATABASE)
        try:
            coords = fetch_coordinates(YA_GEO_API_KEY, update.message.text)
            logger.debug(f'Координаты от яндекса - {coords}')
        except requests.exceptions.HTTPError as err:
            logger.error(f'Error: {err}')
            lat = update.message.location.latitude
            lon = update.message.location.longitude
            current_pos = (lat, lon)
            logger.debug(f'Геолокация от пользователя - {current_pos}')
            distances = get_distance_to_stores(current_pos, stores_locations)
            min_distance = min(distances, key=get_distance)
            store_name = min_distance['name']
            logger.debug(f'Магазин (яндекс координаты): {store_name}')
            deliveryman_id = get_deliveryman_id(store_name,
                                                OP_USER, OP_PASSWORD,
                                                OP_HOST, OP_DATABASE)
            await update.message.reply_text(text=get_shipping(min_distance))

            text = f'Делаем доставку или самовывоз?'
            keyboard = [
                [InlineKeyboardButton('Доставка',
                                      callback_data=f'delivery;{deliveryman_id};{current_pos}')],
                [InlineKeyboardButton('Самовывоз', callback_data=f'pickup;{store_name}')],
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(text=text,
                                           chat_id=chat_id,
                                           reply_markup=reply_markup,
                                           parse_mode=constants.ParseMode.HTML)
            return 'DELIVERY_OPTIONS'

        else:
            if coords:
                distances = get_distance_to_stores(coords,
                                                   stores_locations)
                min_distance = min(distances, key=get_distance)
                store_name = min_distance['name']
                logger.debug(f'Магазин (геопозиция): {store_name}')
                deliveryman_id = get_deliveryman_id(store_name, OP_USER,
                                                    OP_PASSWORD, OP_HOST,
                                                    OP_DATABASE)
                await update.message.reply_text(
                    text=get_shipping(min_distance))
                text = f'Делаем доставку или самовывоз?'
                keyboard = [
                [InlineKeyboardButton('Доставка',
                                      callback_data=f'delivery;{deliveryman_id};{coords}')],
                [InlineKeyboardButton('Самовывоз', callback_data=f'pickup;{store_name}')],
                ]

                reply_markup = InlineKeyboardMarkup(keyboard)

                await context.bot.send_message(text=text,
                                               chat_id=chat_id,
                                               reply_markup=reply_markup,
                                               parse_mode=constants.ParseMode.HTML)
                # await update.message.reply_text(text=text)
                return 'DELIVERY_OPTIONS'
            else:
                logger.debug(f'Нераспознанный текст - {update.message.text}')
                await update.message.reply_text(
                    'Введите корректный адрес или отправьте геолокацию.')
    else:
        logger.debug(f'Не выполнено условие.')
        chat_id = update.callback_query.message.chat_id
        location_keyboard = KeyboardButton(text="Передать геолокацию",
                                           request_location=True)
        custom_keyboard = [[location_keyboard]]
        reply_markup = ReplyKeyboardMarkup(custom_keyboard,
                                           resize_keyboard=True)
        text = ('Для продолжения необходимо или передать вашу геолокацию '
                'или ввести адрес.')
        await context.bot.send_message(text=text,
                                       reply_markup=reply_markup,
                                       chat_id=chat_id)
    return 'LOCATION'


def get_deliveryman_id(store_name, OP_USER, OP_PASSWORD, OP_HOST, OP_DATABASE):
    cnx = mysql.connector.connect(user=OP_USER,
                                  password=OP_PASSWORD,
                                  host=OP_HOST,
                                  database=OP_DATABASE)

    cursor = cnx.cursor()
    query = ('SELECT c.custom_field as custom_field '
             'FROM oc_customer as c '
             'left JOIN oc_customer_group_description as cgd '
             'on cgd.customer_group_id = c.customer_group_id '
             f"where cgd.name = '{store_name}'")
    cursor.execute(query)
    deliverymans_id_list = []
    for custom_field in cursor:
        dlvman_id_list = custom_field[0].lstrip('{').rstrip('}').split(':')
        deliveryman_id = dlvman_id_list[1].strip('"')
        logger.debug(f'deliveryman_id: {deliveryman_id}')
        deliverymans_id_list.append(deliveryman_id)
    cnx.close()
    logger.debug(f'deliverymans_id_list: {deliverymans_id_list}')
    logger.debug(f'deliverymans_id_list[0]: {deliverymans_id_list[0]}')
    return deliverymans_id_list[0]


async def delivery_options(api_token,
                           update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        logger.debug(f'callback_query.data: {update.callback_query.data}')
        user_reply = update.callback_query.data.split(';')
        chat_id = update.callback_query.message.chat_id
        user = update.effective_user
        logger.debug(f'user_reply: {user_reply}')
        logger.debug(f'user: {user}')
        logger.debug(f'user id: {user["id"]}')
        db = get_database_connection()
        telephone = db.get(user['id'] + 1)
        logger.debug(f'Телефон из Redis: {telephone}')

        if user_reply[0] == 'pickup':
            text = (f'Ближайшая к вам пиццерия - {user_reply[-1]}.\n')
            await context.bot.send_message(text=text, chat_id=chat_id)
            order_id = create_order(s, api_token,
                                    telephone=telephone,
                                    lastname=chat_id,
                                    website=WEBSITE)
        else:
            deliveryman_id = user_reply[1]
            coords = user_reply[2]
            logger.debug(f'ID доставщика: {deliveryman_id}')
            logger.debug(f'Координаты клиента: {user_reply[2]}')
            text = (f'Ваш заказ передан в доставку.')
            await context.bot.send_message(text=text, chat_id=chat_id)
            order_id = create_order(s, api_token,
                                    telephone=telephone,
                                    lastname=chat_id,
                                    website=WEBSITE)
            await delivery(order_id, deliveryman_id, coords,
                           OP_USER, OP_PASSWORD, OP_HOST, OP_DATABASE,
                           update, context)
            # Запуск шедулера, для отправки сообщения 60 сек.
            name = update.effective_chat.full_name
            seconds = 60
            context.job_queue.run_once(callback_alarm, seconds,
                                       name=str(chat_id), data=name,
                                       chat_id=chat_id)

        text = (f'Номер заказа - {order_id}.\n'
                f'Спасибо за заказ, ждем вас снова!')

        await context.bot.send_message(text=text, chat_id=chat_id)

        text = f'Оплачиваем онлайн или на месте?'
        keyboard = [
            [InlineKeyboardButton('Оплата онлайн',
                                  callback_data=f'online_payment;{order_id}')],
            [InlineKeyboardButton('Оплата на месте',
                                  callback_data=f'payment_after_delivery')],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(text=text,
                                       chat_id=chat_id,
                                       reply_markup=reply_markup,
                                       parse_mode=constants.ParseMode.HTML)

        return 'PAYMENT'
        # return await start(api_token, update, context)
    else:
        chat_id = update.message.chat_id
        text = f'Вводить ничего не надо. Выберите вариант доставки.'
        await context.bot.send_message(text=text, chat_id=chat_id)
        return 'DELIVERY_OPTIONS'


async def payment(api_token,
                  update: Update,
                  context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug(f'Входим в payment')
    user_reply = update.callback_query.data.split(';')
    logger.debug(f'update: {update}')
    chat_id = update.callback_query.message.chat_id
    logger.debug(f'chat_id: {chat_id}')
    logger.debug(f'user_reply: {user_reply}')
    if user_reply[0] == 'online_payment':
        order_id = user_reply[1]
        order_info = get_order_info(s, api_token, order_id, website=WEBSITE)
        logger.debug(f'Alarm after order_info!!!')
        total = int(float(json.loads(order_info)['order']['total']))
        logger.debug(f'total: {total}')
        logger.debug(f'type of total: {type(total)}')
        title = "Оплата заказа"
        description = "Общая сумма вашего заказа"
        payload = "Custom-Payload"
        currency = "RUB"
        # price = 100
        prices = [LabeledPrice("Test", total * 100)]

        logger.debug(f'Prices: {prices}')

        await context.bot.send_invoice(chat_id=chat_id,
                                       title=title,
                                       description=description,
                                       payload=payload,
                                       provider_token=PAYMENT_PROVIDER_TOKEN,
                                       currency=currency,
                                       prices=prices)
    else:
        text = (f'Спасибо за заказ!\n\n'
                f'Для продолжения покупок отправьте любое сообщение '
                f'или /start.')
        await context.bot.send_message(text=text, chat_id=chat_id)
    logger.debug(f'Alarm!!!')
    return 'START'


async def precheckout_callback(update: Update,
                               context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answers the PreQecheckoutQuery"""
    query = update.pre_checkout_query
    # check the payload, is this from your bot?
    if query.invoice_payload != "Custom-Payload":
        # answer False pre_checkout_query
        await query.answer(ok=False, error_message="Something went wrong...")
    else:
        await query.answer(ok=True)


async def successful_payment_callback(update: Update,
                                      context: ContextTypes.DEFAULT_TYPE) -> None:
    """Подтверждение успешного платежа."""
    await update.message.reply_text(
        f"Спасибо вам за ваш платеж!\n\n"
        f'Для продолжения покупок отправьте любое сообщение или /start.'
    )


async def callback_alarm(context: ContextTypes.DEFAULT_TYPE):
    # Узнать, доставили ли заказ:
    await context.bot.send_message(chat_id=context.job.chat_id,
                                   text=f'Вам привезли пиццу?')


async def delivery(order_id, deliveryman_id, coords,
                   OP_USER, OP_PASSWORD, OP_HOST, OP_DATABASE,
                   update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f'Entering the delivery function')
    coords_list = coords.lstrip('(').rstrip(')').split(', ')
    logger.debug(f'Coords: {coords}')
    logger.debug(f'Coords_list: {coords_list}')
    lat = float(coords_list[0].strip("'"))
    logger.debug(f'Latitude: {lat}')
    lon = float(coords_list[1].strip("'"))
    logger.debug(f'Longitude: {lon}')
    text = get_order_content(order_id, user_db=OP_USER,
                             psw=OP_PASSWORD, host=OP_HOST, db=OP_DATABASE)
    await context.bot.send_message(text=text, chat_id=deliveryman_id)
    await context.bot.send_location(chat_id=deliveryman_id,
                                    latitude=lat, longitude=lon)
    pass


def get_all_stores_locations(OP_USER, OP_PASSWORD, OP_HOST, OP_DATABASE):
    cnx = mysql.connector.connect(user=OP_USER,
                                  password=OP_PASSWORD,
                                  host=OP_HOST,
                                  database=OP_DATABASE)

    cursor = cnx.cursor()
    query = ('SELECT name, geocode from oc_location')
    cursor.execute(query)

    locations = []
    for name, geocode in cursor:
        location_store = {}
        location_store['name'] = name
        location_store['geocode'] = geocode
        locations.append(location_store)

    cnx.close()
    logger.debug(f'stores_locations: {locations}')
    return locations


def get_distance_to_stores(user_geocode, stores_locations: list):
    distances_list = []
    for store_location in stores_locations:
        distance_to_store = {}
        store_geocode = store_location['geocode']
        dist = distance.distance(store_geocode, user_geocode).km
        distance_to_store['name'] = store_location['name']
        distance_to_store['distance'] = dist
        distances_list.append(distance_to_store)
    logger.debug(f'distances: {distances_list}')
    return distances_list


def get_distance(distances):
    return distances['distance']


def get_store_name(distances):
    return distances['name']


def get_shipping(min_distance):
    logger.debug(f'min_distance: {min_distance["distance"]}')
    if min_distance['distance'] <= 0.5:
        shipping = 'Самовывоз или бесплатная доставка.'
    elif min_distance['distance'] > 0.5 and min_distance['distance'] <= 5:
        shipping = 'Доставка 100 руб.'
    elif min_distance['distance'] > 5 and min_distance['distance'] <= 20:
        shipping = 'Доставка 300 руб.'
    else:
        shipping = 'Сюда нет доставки.'
    logger.debug(f'shipping_text: {shipping}')
    return shipping


async def handle_users_reply(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_database_connection()
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    try:
        api_token = get_session(chat_id, s)
    except Exception as err:
        logger.error(f'Ошибка получения токена OpenCart: {err}')
    if user_reply == '/start':
        user_state = 'START'
    # Если category_id=None, то получим список всех товаров.
    # Иначе список товаров определенной категории.
        logger.debug(f'Current state first - {user_state}')
    else:
        user_state = db.get(chat_id)
        logger.debug(f'Current state from DB - {user_state}')

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'GET_CART': get_cart,
        'HANDLE_CART': handle_cart,
        'WAITING_CONTACTS': get_contacts,
        'LOCATION': handle_location,
        'DELIVERY_OPTIONS': delivery_options,
        'PAYMENT': payment,
    }
    state_handler = states_functions[user_state]

    try:
        next_state = await state_handler(api_token, update, context)
        logger.debug(f'Next state - {next_state}')
        db.set(chat_id, next_state)
    except Exception as err:
        logger.error(f'Ошибка - {err}')


def get_session(chat_id, s):
    # Проверить, существует ли сессия для этого пользователя.
    if chat_id not in sessions:
        sessions[chat_id] = get_api_token(s,
                                          username=API_USERNAME,
                                          key=API_KEY,
                                          website=WEBSITE)
    return sessions[chat_id]


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
    logger.debug(f'Database Redis: {_database}')
    return _database


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Извините, я не понял эту команду..."
    )


def main() -> None:
    logger.info('Start application.')
    token = os.getenv("TOKEN_TG")

    application = Application.builder().token(token).build()

    application.add_handler(
        CommandHandler("start", handle_users_reply))
    application.add_handler(
        CallbackQueryHandler(handle_users_reply))

    # Pre-checkout handler to final check
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))

    # Success! Notify your user!
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback)
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND,
                       handle_users_reply))
    application.add_handler(
        MessageHandler(filters.LOCATION, handle_users_reply))
    application.add_handler(
        MessageHandler(filters.TEXT | filters.COMMAND, unknown))

    application.run_polling()


if __name__ == '__main__':
    main()
