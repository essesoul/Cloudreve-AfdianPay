import hashlib
import json
import os
import sqlite3
import time

import requests

try:
    from dotenv import load_dotenv
except:
    print("未找到dotenv模块")
    exit()

def db_file():
    conn = sqlite3.connect('afdian_pay.db')
    c = conn.cursor()
    # 创建表
    c.execute('''CREATE TABLE IF NOT EXISTS afdian_pay
           (order_no TEXT PRIMARY KEY,
            amount TEXT,
            notify_url TEXT,
            is_paid BOOLEAN DEFAULT 0,
            notify_status INTEGER DEFAULT 0,
            notify_attempts INTEGER DEFAULT 0,
            notify_next_at INTEGER DEFAULT 0,
            notify_last_at INTEGER DEFAULT 0,
            notify_last_error TEXT DEFAULT ''
           )''')
    conn.commit()

    # WAL
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        print("[WARN] Failed to enable WAL")
        pass

    conn.commit()
    conn.close()
    return


def db_insert(order_no, amount, notify_url):
    db_file()
    now = int(time.time())
    conn = sqlite3.connect('afdian_pay.db')
    c = conn.cursor()
    # 插入数据
    c.execute("""
            INSERT OR REPLACE INTO afdian_pay
            (order_no, amount, notify_url, is_paid, notify_status, notify_attempts, notify_next_at, notify_last_at, notify_last_error)
            VALUES (?, ?, ?, 0, 0, 0, ?, 0, '')
        """, (order_no, amount, notify_url, now))

    conn.commit()
    conn.close()
    return True


# 创建订单
def new_order(order_info, amount):
    load_dotenv('.env')
    afdian_url = "https://afdian.com/order/create?user_id=" + os.getenv('USER_ID')
    # 解析json
    order_info = json.loads(order_info)
    order_no = order_info['order_no']
    order_url = afdian_url + "&remark=" + str(order_no) + "&custom_price=" + f"{round(amount / 100, 2):.2f}"
    db_insert(order_no, f"{round(amount / 100, 2):.2f}", order_info['notify_url'])
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
    c.execute("SELECT order_no, amount, notify_url FROM afdian_pay WHERE order_no = ? LIMIT 1", (order_no,))
    row = c.fetchone()
    conn.close()
    if not row:
        return ["", 0, ""]
    return row


def mark_order_paid_and_enqueue_notify(order_no):
    db_file()
    now = int(time.time())
    conn = sqlite3.connect('afdian_pay.db')
    c = conn.cursor()
    c.execute("""
        UPDATE afdian_pay
        SET is_paid = 1,
            notify_status = 0,
            notify_next_at = ?,
            notify_last_error = ''
        WHERE order_no = ?
    """, (now, order_no))
    conn.commit()
    conn.close()
    return True

def _notify_backoff_seconds(attempts: int) -> int:
    """
    attempts 从 1 开始计数。
    5s, 10s, 20s, 40s... 最长 30min
    """
    base = 5
    sec = base * (2 ** (attempts - 1))
    return min(sec, 1800)

def fetch_due_notify_jobs(now: int):
    db_file()
    conn = sqlite3.connect('afdian_pay.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT order_no, notify_url, notify_attempts
        FROM afdian_pay
        WHERE is_paid = 1
          AND notify_url != ''
          AND notify_status != 1
          AND notify_status != 3
          AND notify_next_at <= ?
        ORDER BY notify_next_at ASC
        LIMIT ?
    """, (now, 10)) #最多批量回调10项
    rows = c.fetchall()
    conn.close()
    return rows

def mark_notify_success(order_no: str):
    now = int(time.time())
    conn = sqlite3.connect('afdian_pay.db')
    c = conn.cursor()
    c.execute("""
        UPDATE afdian_pay
        SET notify_status = 1,
            notify_last_at = ?,
            notify_last_error = ''
        WHERE order_no = ?
    """, (now, order_no))
    conn.commit()
    conn.close()

def mark_notify_failure(order_no: str, attempts_after: int, err: str):
    now = int(time.time())
    next_at = now + _notify_backoff_seconds(attempts_after)
    status = 2
    if attempts_after >= 20:
        status = 3  # giving up
    conn = sqlite3.connect('afdian_pay.db')
    c = conn.cursor()
    c.execute("""
        UPDATE afdian_pay
        SET notify_status = ?,
            notify_attempts = ?,
            notify_last_at = ?,
            notify_next_at = ?,
            notify_last_error = ?
        WHERE order_no = ?
    """, (status, attempts_after, now, next_at, err[:500], order_no))
    conn.commit()
    conn.close()

def try_notify_once(url: str) -> tuple[bool, str]:
    try:
        resp = requests.get(url, timeout=(3, 5))
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        try:
            j = resp.json()
        except Exception:
            return False, "Invalid JSON"
        if j.get("code") == 0:
            return True, ""
        return False, f"code={j.get('code')}, body={resp.text[:200]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def get_order_status(order_no):
    """获取订单支付状态"""
    db_file()
    conn = sqlite3.connect('afdian_pay.db')
    c = conn.cursor()
    c.execute("SELECT is_paid FROM afdian_pay WHERE order_no = ?", (order_no,))
    result = c.fetchone()
    conn.close()
    return bool(result[0]) if result else False


def api_check(out_trade_no):
    url = "https://afdian.com/api/open/query-order"
    load_dotenv('.env')
    user_id = os.environ.get('USER_ID')
    token = os.environ.get('TOKEN')
    t = time.time()
    ts = str(int(t))
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
