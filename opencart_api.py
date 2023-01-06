import logging

import mysql.connector
import json


logger = logging.getLogger('tg_bot.oc_api')


def get_api_token(session, username, key, website):
    """Сгенерировать новый api_token."""
    res = session.post(
        f'http://{website}/index.php?route=api/login',
        data={'username': username, 'key': key}
    )
    res.raise_for_status()
    result_dict = json.loads(res.text)
    if res.text == '[]':
        text = (f'Error OpenCart API: api_token is empty.\n'
                f'User API OpenCart - {username}.\n'
                f'Key API OpenCart - {key}.')
        logger.error(text)
        return False
    elif 'error' in result_dict:
        logger.error(f'Error OpenCart API: {result_dict["error"]}')
        return False
    else:
        return result_dict['api_token']


def get_actual_api_token(
        session, username, key, user_db, psw, host, db, website):
    """Получить существующий или сгенерить новый api_token."""
    cnx = mysql.connector.connect(user=user_db,
                                  password=psw,
                                  host=host,
                                  database=db)
    cursor_api = cnx.cursor()
    query_api = ('SELECT session_id FROM oc_api_session')
    flag = True
    while flag:
        try:
            # Читаем api_token из БД.
            cursor_api.execute(query_api)
            api_token_list = []
            for session_id in cursor_api:
                api_token_list.append(session_id)
            api_token = str(list(api_token_list[0])[0])
            flag = False
        except IndexError:
            # Получаем api_token для сессии, если его нет в БД.
            if not get_api_token(session, username, key, website):
                flag = False

    cursor_api.close()
    logger.debug(f'get_actual_api_token: api-token - "{api_token}"\n')
    return api_token


def set_session_for_api_user(session, api_token, username, key, website):
    """Установление сеанса для пользователя API."""
    res = session.post(
        f'http://{website}/index.php?route=api/shipping/address',
        params={'api_token': api_token},
        data={
            'username': username,
            'key': key
        }
    )
    res.raise_for_status()
    user_session = res.text.split('</b>')[-1]
    logger.debug(f'Cеанса для {username} : {json.loads(user_session)}')
    return json.loads(user_session)


def cart_add(session, api_token, product_id, website, quantity='1'):
    """ Добавляем товар в корзину."""
    res = session.post(
        f'http://{website}/index.php?route=api/cart/add',
        params={'api_token': api_token},
        data={
            'product_id': product_id,
            'quantity': quantity,
        }
    )
    res.raise_for_status()
    cart_add = res.text.split('</b>')[-1]
    logger.debug(f'cart_add: Добавлено в корзину - {json.loads(cart_add)}')


def cart_edit(session, api_token, cart_id, website, quantity):
    """Изменяем кол-во товара в корзине. (key = cart_id)"""
    res = session.post(
        f'http://{website}/index.php?route=api/cart/edit',
        params={'api_token': api_token},
        data={'key': cart_id,
              'quantity': quantity}
    )
    res.raise_for_status()
    cart_edit = res.text.split('</b>')[-1]
    logger.debug(f'cart_edit: {json.loads(cart_edit)}')


def cart_remove(session, api_token, cart_id, website):
    """Удаляем товар из корзины. (key = cart_id)"""
    res = session.post(
        f'http://{website}/index.php?route=api/cart/remove',
        params={'api_token': api_token},
        data={'key': cart_id}
    )
    res.raise_for_status()
    cart_remove = res.text.split('</b>')[-1]
    logger.debug(f'cart_remove: {json.loads(cart_remove)}')


def get_cart_products(session, api_token, website):
    """Содержимое корзины."""
    res = session.post(
        f'http://{website}/index.php?route=api/cart/products',
        params={'api_token': api_token},
        data={}
    )
    res.raise_for_status()

    cart_content = res.text.split('</b>')[-1]
    logger.debug(f'cart_content: {json.loads(cart_content)}')
    return json.loads(cart_content)


def set_customer(session,
                 api_token,
                 website,
                 telephone='+71111111111',
                 firstname='chat_id',
                 lastname='Ivanov!',
                 email='example@gmail.com'):
    """Установить клиента для текущей сессии."""
    res = session.post(
        f'http://{website}/index.php?route=api/customer',
        params={'api_token': api_token},
        data={
            'firstname': firstname,
            'lastname': lastname,
            'email': email,
            'telephone': telephone,
        }
    )
    res.raise_for_status()
    customer = res.text.split('</b>')[-1]
    logger.debug(f'customer: {json.loads(customer)}')


def set_shipping_address(session, api_token, website):
    """Установить адрес доставки."""
    res = session.post(
        f'http://{website}/index.php?route=api/shipping/address',
        params={'api_token': api_token},
        data={
            'firstname': 'Клиент',
            'lastname': 'по умолчанию',
            'address_1': 'Адрес по умолчанию',
            'city': 'Минусинск',
            'country_id': 'RUS',
            'zone_id': 'KGD'
        }
    )
    res.raise_for_status()
    shipping_address = res.text.split('</b>')[-1]
    logger.debug(f'shipping_address: {json.loads(shipping_address)}')


def get_shipping_methods(session, api_token, website):
    """Получить доступные методы доставки."""
    res = session.post(
        f'http://{website}/index.php?route=api/shipping/methods',
        params={'api_token': api_token},
    )
    res.raise_for_status()
    shipping_methods = res.text.split('</b>')[-1]
    logger.debug(f'shipping_methods: {json.loads(shipping_methods)}')
    return json.loads(shipping_methods)


def set_shipping_method(session, api_token, website):
    """Установить способ доставки для сеанса (самовывоз)."""
    res = session.post(
        f'http://{website}/index.php?route=api/shipping/method',
        params={'api_token': api_token},
        data={
            'shipping_method': 'pickup.pickup'
        }
    )
    res.raise_for_status()
    shipping_method = res.text.split('</b>')[-1]
    logger.debug(f'shipping_method: {json.loads(shipping_method)}')


def set_payment_address(session, api_token, website):
    """Установить платежный адрес."""
    res = session.post(
        f'http://{website}/index.php?route=api/payment/address',
        params={'api_token': api_token},
        data={
            'firstname': 'Клиент',
            'lastname': 'по умолчанию',
            'address_1': 'Адрес по умолчанию',
            'city': 'Минусинск',
            'country_id': 'RUS',
            'zone_id': 'KGD'
        }
    )
    res.raise_for_status()
    payment_address = res.text.split('</b>')[-1]
    logger.debug(f'payment_address: {json.loads(payment_address)}')


def get_payment_methods(session, api_token, website):
    """Получить доступные методы оплаты."""
    res = session.post(
        f'http://{website}/index.php?route=api/payment/methods',
        params={'api_token': api_token},
    )
    res.raise_for_status()
    payment_methods = res.text.split('</b>')[-1]
    logger.debug(f'payment_methods: {json.loads(payment_methods)}')


def set_payment_method(session, api_token, website):
    """Установить способ оплаты."""
    res = session.post(
        f'http://{website}/index.php?route=api/payment/method',
        params={'api_token': api_token},
        data={
            'payment_method': 'cod'
        }
    )
    res.raise_for_status()
    payment_method = res.text.split('</b>')[-1]
    logger.debug(f'payment_method: {json.loads(payment_method)}')


def order_add(session, api_token, website):
    """Новый заказ по содержимому корзины."""
    res = session.post(
        f'http://{website}/index.php?route=api/order/add',
        params={'api_token': api_token},
    )
    res.raise_for_status()
    order_content = json.loads(res.text.split('</b>')[-1])
    logger.debug(f'order_content: {order_content}')
    return order_content['order_id']


def order_edit(session, api_token, order_id, website):
    """Редактировать заказа."""
    res = session.post(
        f'http://{website}/index.php?route=api/order/edit',
        params={'api_token': api_token,
                'order_id': order_id,
                'product_id': 28,
                'quantity': 9},
        data={}
    )
    res.raise_for_status()
    order_edit = res.text.split('</b>')[-1]
    logger.debug(f'order_edit: {json.loads(order_edit)}')


def order_delete(session, api_token, order_id, website):
    """Удалить заказа."""
    res = session.post(
        f'http://{website}/index.php?route=api/order/delete',
        params={'api_token': api_token,
                'order_id': order_id},
        data={}
    )
    res.raise_for_status()
    order_delete = res.text.split('</b>')[-1]
    logger.debug(f'order_delete: {json.loads(order_delete)}')


def get_order_info(session, api_token, order_id, website):
    """Информация о заказе."""
    res = session.post(
        f'http://{website}/index.php?route=api/order/info',
        params={'api_token': api_token,
                'order_id': order_id},
        data={}
    )
    res.raise_for_status()
    order_info = res.text.split('</b>')[-1]
    logger.debug(f'order_info: {json.loads(order_info)}')
    return order_info


def get_order_history(session, api_token, order_id, website):
    """История заказа."""
    res = session.post(
        f'http://{website}/index.php?route=api/order/history',
        params={'api_token': api_token,
                'order_id': order_id},
        data={}
    )
    res.raise_for_status()
    order_history = res.text.split('</b>')[-1]
    logger.debug(f'order_history: {json.loads(order_history)}')


def get_order_content(order_id, user_db, psw, host, db):
    """Получить содержимое заказа."""
    cnx = mysql.connector.connect(user=user_db,
                                  password=psw,
                                  host=host,
                                  database=db)
    cursor = cnx.cursor()
    query_order = ('SELECT telephone, total '
                   f'FROM oc_order WHERE order_id = {order_id}')
    query_order_product = ('SELECT name, quantity '
                           'FROM oc_order_product '
                           f'WHERE order_id = {order_id}')

    cursor.execute(query_order)
    order_dict = {}
    for (telephone, total) in cursor:
        order_dict['telephone'] = telephone
        order_dict['total'] = total

    cursor.close()

    cursor = cnx.cursor()
    cursor.execute(query_order_product)
    order_products_list = []
    for (name, quantity) in cursor:
        product_dict = {}
        product_dict['name'] = name
        product_dict['quantity'] = quantity
        order_products_list.append(product_dict)

    cursor.close()

    text = (f'Сообщение доставщику\n'
            f'--------------------------\n'
            f'Номер заказа: {order_id}\n')
    for dish in order_products_list:
        text += f'{dish["name"]} - {dish["quantity"]} шт.\n'

    text += (f'Итоговая сумма заказа: {order_dict["total"]}\n'
             f'Номер телефона клиента: {order_dict["telephone"]}')
    logger.info(f'Текст сообщения доставщику: \n{text}')
    return text


def create_order(s, api_token, lastname, telephone, website):
    """Создать заказ."""
    # Установить адрес доставки.
    set_shipping_address(s, api_token, website)

    # Получить доступные методы доставки.
    get_shipping_methods(s, api_token, website)

    # Установить способ доставки для сеанса (самовывоз).
    set_shipping_method(s, api_token, website)

    # Установить платежный адрес.
    set_payment_address(s, api_token, website)

    # Получить доступные методы оплаты.
    get_payment_methods(s, api_token, website)

    # Установить способ оплаты.
    set_payment_method(s, api_token, website)

    # Установить клиента для текущей сессии.
    set_customer(s, api_token, website, telephone, lastname=lastname)

    # Новый заказ по содержимому корзины.
    order_id = order_add(s, api_token, website)
    return order_id
