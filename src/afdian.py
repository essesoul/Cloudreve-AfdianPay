import hashlib
import json
import math
import os
import sqlite3
import time

import requests

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
    afdian_url = "https://afdian.net/order/create?user_id=" + os.getenv('USER_ID')
    # 解析json
    order_info = json.loads(order_info)
    order_no = order_info['order_no']
    order_url = afdian_url + "&remark=" + str(order_no) + "&custom_price=" + str(math.ceil(amount / 100))
    db_insert(order_no, str(round(amount / 100)), order_info['notify_url'])
    return order_url


def check_order(order_no, out_trade_no):
    # API主动验证
    api_data = api_check(out_trade_no)
    if api_data[0] == "":
        return ["", 0, ""]
    if api_data[1] == 0:
        return ["", 0, ""]
    # 本地数据库验证
    db_file()
    conn = sqlite3.connect('afdian_pay.db')
    c = conn.cursor()
    # 查询数据
    cursor = c.execute("SELECT order_no, amount, notify_url from afdian_pay")
    for row in cursor:
        if row[0] == order_no:
            conn.close()
            return row
    conn.close()
    return ["", 0, ""]


def api_check(out_trade_no):
    url = "https://afdian.net/api/open/query-order"
    load_dotenv('.env')
    user_id = os.environ.get('USER_ID')
    token = os.environ.get('TOKEN')
    t = time.time()
    ts = str(int(t))
    # print(ts)
    params = '{"out_trade_no":"' + out_trade_no + '"}'
    sign_data = token + "params" + params + "ts" + ts + "user_id" + user_id
    sign = hashlib.md5(sign_data.encode(encoding='UTF-8')).hexdigest()
    post_data = {"user_id": user_id, "params": params, "ts": ts, "sign": sign}
    # 发送post请求
    response = requests.post(url, data=post_data)
    total_count = json.loads(response.text)['data']["total_count"]
    if total_count == 0:
        return ["", ""]
    # 解析json
    response = json.loads(response.text)['data']["list"][0]
    total_amount = int(str(response['total_amount']).split(".")[0])
    order_no = response['remark']
    return [order_no, total_amount]
