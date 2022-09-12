import mysql.connector
import json


def get_api_token(session, username, key, website):
    """Сгенерировать новый api_token."""
    res = session.post(
        f'http://{website}/index.php?route=api/login',
        data={'username': username, 'key': key}
    )
    # api_token_content = res.text.split('</b>')[-1]
    # print(f'Получен новый токен - {json.loads(api_token_content)}\n')
    if res.text != '[]':
        print(json.loads(res.text))
        return True
    else:
        print(f'Error get_api_token OpenCart.')
        print(f'User API OpenCart - {username}.')
        print(f'Key API OpenCart - {key}.')
        return False


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
    print(f'api-token - "{api_token}"\n')
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
    user_session = res.text.split('</b>')[-1]
    print(f'Установление сеанса для {username} - {json.loads(user_session)}\n')


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
    cart_add = res.text.split('</b>')[-1]
    print(f'Добавлено в корзину - {json.loads(cart_add)}\n')


def cart_edit(session, api_token, cart_id, website, quantity):
    """Изменяем кол-во товара в корзине. (key = cart_id)"""
    session.post(
        f'http://{website}/index.php?route=api/cart/edit',
        params={'api_token': api_token},
        data={'key': cart_id,
              'quantity': quantity}
    )


def cart_remove(session, api_token, cart_id, website):
    """Удаляем товар из корзины. (key = cart_id)"""
    session.post(
        f'http://{website}/index.php?route=api/cart/remove',
        params={'api_token': api_token},
        data={'key': cart_id}
    )


def get_cart_products(session, api_token, website):
    """Содержимое корзины."""
    res = session.post(
        f'http://{website}/index.php?route=api/cart/products',
        params={'api_token': api_token},
        data={}
    )
    cart_content = res.text.split('</b>')[-1]
    # print(json.loads(cart_content), '\n')
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
    customer = res.text.split('</b>')[-1]
    print(json.loads(customer), '\n')


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
    shipping_address = res.text.split('</b>')[-1]
    print(json.loads(shipping_address), '\n')


def get_shipping_methods(session, api_token, website):
    """Получить доступные методы доставки."""
    res = session.post(
        f'http://{website}/index.php?route=api/shipping/methods',
        params={'api_token': api_token},
    )
    shipping_methods = res.text.split('</b>')[-1]
    print(json.loads(shipping_methods), '\n')


def set_shipping_method(session, api_token, website):
    """Установить способ доставки для сеанса (самовывоз)."""
    res = session.post(
        f'http://{website}/index.php?route=api/shipping/method',
        params={'api_token': api_token},
        data={
            'shipping_method': 'pickup.pickup'
        }
    )
    shipping_content = res.text.split('</b>')[-1]
    print(json.loads(shipping_content), '\n')


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
    payment_address = res.text.split('</b>')[-1]
    print(json.loads(payment_address), '\n')


def get_payment_methods(session, api_token, website):
    """Получить доступные методы оплаты."""
    res = session.post(
        f'http://{website}/index.php?route=api/payment/methods',
        params={'api_token': api_token},
    )
    payment_methods = res.text.split('</b>')[-1]
    print(json.loads(payment_methods), '\n')


def set_payment_method(session, api_token, website):
    """Установить способ оплаты."""
    res = session.post(
        f'http://{website}/index.php?route=api/payment/method',
        params={'api_token': api_token},
        data={
            'payment_method': 'cod'
        }
    )
    payment_method = res.text.split('</b>')[-1]
    print(json.loads(payment_method), '\n')


def order_add(session, api_token, website):
    """Новый заказ по содержимому корзины."""
    res = session.post(
        f'http://{website}/index.php?route=api/order/add',
        params={'api_token': api_token},
    )
    order_content = json.loads(res.text.split('</b>')[-1])
    print(order_content, '\n')
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
    order_edit = res.text.split('</b>')[-1]
    print(json.loads(order_edit), '\n')


def order_delete(session, api_token, order_id, website):
    """Удалить заказа."""
    res = session.post(
        f'http://{website}/index.php?route=api/order/delete',
        params={'api_token': api_token,
                'order_id': order_id},
        data={}
    )
    order_delete = res.text.split('</b>')[-1]
    print(json.loads(order_delete), '\n')


def get_order_info(session, api_token, order_id, website):
    """Информация о заказе."""
    res = session.post(
        f'http://{website}/index.php?route=api/order/info',
        params={'api_token': api_token,
                'order_id': order_id},
        data={}
    )
    order_info = res.text.split('</b>')[-1]
    print(json.loads(order_info), '\n')
    return order_info


def get_order_history(session, api_token, order_id, website):
    """История заказа."""
    res = session.post(
        f'http://{website}/index.php?route=api/order/history',
        params={'api_token': api_token,
                'order_id': order_id},
        data={}
    )
    order_history = res.text.split('</b>')[-1]
    print(json.loads(order_history), '\n')


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
