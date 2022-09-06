import os
import json

from datetime import datetime
from ftplib import FTP

import mysql.connector
import requests

from dotenv import load_dotenv

load_dotenv()

OP_USER = os.getenv("OPENCART_DB_USER")
OP_PASSWORD = os.getenv("OPENCART_DB_PASSWORD")
OP_HOST = os.getenv("OPENCART_DB_HOST")
OP_DATABASE = os.getenv("OPENCART_DB_NAME")
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASSWORD = os.getenv("FTP_PASSWORD")
# Статус на складе - в наличии.
STOCK_STATUS_ID = 7
STATUS = 1


def create_product(cnx, name='Новый товар', description='Описание', price=100,
                   quantity=10):
    """Добавление товара в БД MySQL."""
    cursor = cnx.cursor()

    meta_title = name

    date_added = date_modified = date_available = datetime.now()

    image_path = f'catalog/food/{name.strip().replace(" ", "_")}.jpg'

    new_product = ('INSERT INTO oc_product SET '
                   # f'product_id={max_id},'
                   f'model="{name}",'
                   f'quantity={quantity},'
                   f'price={price},'
                   f'stock_status_id={STOCK_STATUS_ID},'
                   f'date_available="{date_available}",'
                   f'date_added="{date_added}",'
                   f'date_modified="{date_modified}",'
                   f'status={STATUS},'
                   f'image="{image_path}"')

    try:
        cursor.execute(new_product)
        product_id = cursor.lastrowid

        new_description = ('INSERT INTO oc_product_description SET '
                           f'product_id={product_id},'
                           f'name="{name}",'
                           f'description="{description}",'
                           f'meta_title="{meta_title}",'
                           'language_id=1')

        cursor.execute(new_description)

        new_image = ('INSERT INTO oc_product_image SET '
                     f'product_id={product_id},'
                     f'image="{image_path}"')
        cursor.execute(new_image)

    except mysql.connector.Error as err:
        print(f'[-] Новая запись не добавлена.')
        print(f'[-] ОШИБКА: {err}')
    else:
        print(f'[+] Новая запись добавлена. ')
        cnx.commit()

    cursor.close()


def ftp_upload(ftp, path, filename, ftype='TXT'):
    """Функция для загрузки файлов на FTP-сервер.
    @param ftp: Объект протокола передачи файлов.
    @param path: Путь к файлу для загрузки.
    @param filename: Имя файла для загрузки.
    """
    if ftype == 'TXT':
        with open(path) as fobj:
            ftp.storlines('STOR ' + filename, fobj)
    else:
        with open(path, 'rb') as fobj:
            ftp.storbinary('STOR ' + filename, fobj, 1024)


def upload_from_url_to_ftp(url, filename):
    """Загрузка файла из url на ftp."""
    r = requests.get(url)
    filename = f'{filename.strip().replace(" ", "_")}.jpg'
    path_to_file = f'data/{filename}'

    if r.status_code == 200:
        # Скачиваем файл локально.
        with open(path_to_file, "wb") as f:
            f.write(r.content)

        with FTP(host=FTP_HOST, user=FTP_USER, passwd=FTP_PASSWORD) as ftp:
            print(f'[+] Началась загрузка файла "{filename}"" на ftp ...')
            ftp.cwd('/www/kras-yagoda.site/image/catalog/food/')
            ftp_upload(ftp, path_to_file, filename, ftype='jpg')
            # ftp.dir()

        print(f'[+] Файл "{filename}" загружен.')
        # Удаляем локальный файл.
        if os.path.isfile(path_to_file):
            os.remove(path_to_file)
    else:
        print(f'[-] Файл "{filename}" не загружен.')
        print(f'[-] Status code: {r.status_code}')


def main():
    cnx = mysql.connector.connect(user=OP_USER,
                                  password=OP_PASSWORD,
                                  host=OP_HOST,
                                  database=OP_DATABASE)

    with open('data/menu.json', encoding='utf-8') as f:
        menu = json.load(f)

    for dish in menu:
        # print(dish)
        dish_description = dish["description"]
        dish_price = dish["price"]
        dish_name = dish["name"]
        dish_image_path = dish["product_image"]["url"]
        upload_from_url_to_ftp(dish_image_path, filename=dish_name)
        create_product(cnx, name=dish_name, price=dish_price,
                       description=dish_description)

    cnx.close()


if __name__ == '__main__':
    main()
