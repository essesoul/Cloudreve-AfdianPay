import json
import math
import os
import sqlite3

try:
    from dotenv import load_dotenv
except:
    os.system("pip install -r requirements.txt")
    from dotenv import load_dotenv


def db_file():
    # 判断afdian_pay.db是否存在
    if os.path.exists("afdian_pay.db"):
        return
    else:
        # 创建数据库
        conn = sqlite3.connect('afdian_pay.db')
        c = conn.cursor()
        # 创建表
        c.execute('''CREATE TABLE afdian_pay
               (order_no text, amount text, notify_url text)''')
        conn.commit()
        conn.close()
        return


def db_insert(order_no, amount, notify_url):
    db_file()
    conn = sqlite3.connect('afdian_pay.db')
    c = conn.cursor()
    # 插入数据
    c.execute("INSERT INTO afdian_pay VALUES ('" + order_no + "', '" + amount + "', '" + notify_url + "')")
    conn.commit()
    conn.close()
    return True


# 创建订单
def new_order(order_info, amount):
    load_dotenv('.env')
    afdian_url = "https://afdian.net/order/create?user_id=" + os.getenv('afdian_url')
    # 解析json
    order_info = json.loads(order_info)
    order_no = order_info['order_no']
    order_url = afdian_url + "&remark=" + str(order_no) + "&custom_price=" + str(math.ceil(amount / 100))
    db_insert(order_no, str(round(amount / 100)), order_info['notify_url'])
    return order_url


def check_order(order_no):
    db_file()
    conn = sqlite3.connect('afdian_pay.db')
    c = conn.cursor()
    # 查询数据
    cursor = c.execute("SELECT order_no, amount, notify_url from afdian_pay")
    for row in cursor:
        if row[0] == order_no:
            return row
    conn.close()
    return ["", 0, ""]
