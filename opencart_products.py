import mysql.connector


class OpenCartProducts():
    """
    Общий класс для получения данных о продуктах, хранящихся в БД OpenCart.
    """

    def __init__(
            self, user, password, host, database, website):
        """Инициализировать атрибуты данных."""
        self.user = user
        self.password = password
        self.host = host
        self.database = database
        self.image_path = f'https://{website}/image/'
        self.query = ('SELECT p.product_id as id, '
                      'pd.name as name, '
                      'p.price as price, '
                      'p.quantity as quantity,'
                      'p.image as image, '
                      'pd.description as description '
                      'FROM oc_product as p '
                      'left JOIN oc_product_description as pd '
                      'on pd.product_id = p.product_id')

    def get_my_product(self, id_my_product=None):
        """Получить данные определенного продукта."""
        cnx = mysql.connector.connect(user=self.user,
                                      password=self.password,
                                      host=self.host,
                                      database=self.database)
        cursor = cnx.cursor()
        cursor.execute(self.query)
        product = {}

        for (id, name, price, quantity, image, description) in cursor:
            if id == id_my_product:
                product['id'] = id
                product['name'] = name
                product['price'] = int(price)
                product['quantity'] = quantity
                product['image'] = self.image_path + image
                product['description'] = description

        cursor.close()
        cnx.close()
        return product

    def get_my_products(self):
        """Получить данные всех продуктов."""
        cnx = mysql.connector.connect(user=self.user,
                                      password=self.password,
                                      host=self.host,
                                      database=self.database)
        cursor = cnx.cursor()
        cursor.execute(self.query)
        products = []
        for (id, name, price, quantity, image, description) in cursor:
            product = {}
            product['id'] = id
            product['name'] = name
            product['price'] = int(price)
            product['quantity'] = quantity
            product['image'] = self.image_path + image
            product['description'] = description

            products.append(product)
        cursor.close()
        cnx.close()
        return products
