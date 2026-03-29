import hmac
import hashlib
import base64
import json
import os
import time
import afdian
from urllib.parse import unquote

try:
    import requests
except:
    print("未找到requests模块")
    exit()
try:
    from flask import Flask, request, Response
except:
    print("未找到flask模块")
    exit()
try:
    from currency_converter import CurrencyConverter
except:
    print("未找到CurrencyConverter模块")
    exit()
try:
    import gevent
    from gevent import pywsgi
except:
    print("未找到gevent模块")
    exit()
try:
    from dotenv import load_dotenv
except:
    print("未找到dotenv模块")
    exit()
app = Flask(__name__)

def notify_worker_loop():
    print("[INFO] notify worker started")
    while True:
        try:
            now = int(time.time())
            jobs = afdian.fetch_due_notify_jobs(now)
            if not jobs:
                gevent.sleep(1.0)
                continue

            for job in jobs:
                order_no = job["order_no"]
                url = job["notify_url"]
                attempts = int(job["notify_attempts"] or 0)
                ok, err = afdian.try_notify_once(url)
                if ok:
                    print(f"[INFO] notify success order_no={order_no}")
                    afdian.mark_notify_success(order_no)
                else:
                    attempts_after = attempts + 1
                    print(f"[WARN] notify failed order_no={order_no} attempts={attempts_after} err={err}")
                    afdian.mark_notify_failure(order_no, attempts_after, err)
            # 防止一轮处理过久饿死其他 greenlet
            gevent.sleep(0)
        except Exception as e:
            print(f"[ERROR] notify worker exception: {type(e).__name__}: {e}")
            gevent.sleep(2.0)

# 初始化检查
def check():
    # .env文件可选，有则加载（不覆盖已有环境变量）
    load_dotenv('.env')
    for key in ('SITE_URL', 'COMMUNICATION_KEY', 'USER_ID', 'TOKEN', 'PORT'):
        if not os.environ.get(key):
            print(f"{key}未设置,已停止运行")
            exit()
    print("初始化检查通过")

@app.route('/afdian', methods=['POST'])
def respond():
    # 解析返回的json值
    data = request.get_data()
    data = json.loads(data)['data']['order']
    out_trade_no = data['out_trade_no']
    # 获取订单信息（remark）
    order_no = data['remark']
    # 获取订单amount
    afd_amount = str(data['total_amount'])
    # 查询订单
    amount = 0
    raw = afdian.check_order(order_no, out_trade_no)
    if raw[1] != 0:
        amount = raw[1]
    if afd_amount == amount:
        # 订单金额相同
        # 标记订单为已支付、可回调
        afdian.mark_order_paid_and_enqueue_notify(order_no)

    # json格式化
    back = '{"ec":200,"em":""}'
    json.dumps(back, ensure_ascii=False)
    return Response(back, mimetype='application/json')


def verify_signature(request, signature, timestamp):
    communication_key = os.environ.get('COMMUNICATION_KEY', '')
    current_time = int(time.time())
    if current_time > int(timestamp):
        return False, "时间戳验证失败"

    if request.method == 'POST':
        # 获取X-Cr-前缀的请求头
        signed_headers = []
        for key, value in request.headers.items():
            if key.startswith('X-Cr-'):
                signed_headers.append(f"{key}={value}")
        signed_headers.sort()
        signed_headers_str = "&".join(signed_headers)
        path = request.path or "/"
        body = request.get_data(as_text=True)

        sign_raw = {
            "Path": path,
            "Header": signed_headers_str,
            "Body": body
        }
        sign_content = json.dumps(sign_raw, separators=(',', ':'), ensure_ascii=False)
        sign_content = sign_content.replace("&", "\\u0026") # 转义&符号
    else:
        sign_content = request.path or "/"

    sign_content_final = f"{sign_content}:{timestamp}"

    # 签名（HMAC-SHA256）
    h = hmac.new(communication_key.encode(), sign_content_final.encode(), hashlib.sha256)
    computed_signature = base64.urlsafe_b64encode(h.digest()).decode()
    if computed_signature != signature:
        return False, "签名无效"

    return True, ""

@app.route('/order', methods=['post','get'])
def order():
    load_dotenv('.env')
    # 删除SITE_URL尾部的“/”
    if os.environ.get('SITE_URL')[-1] == "/":
        os.environ['SITE_URL'] = os.environ.get('SITE_URL')[:-1]
    # 读取请求头中的X-Cr-Site-Url
    site_url = request.headers.get('X-Cr-Site-Url')
    if site_url != os.environ.get('SITE_URL'):
        back = {"code": 412, "error": "验证失败，请检查.env文件"}
        back = json.dumps(back, ensure_ascii=False)
        return Response(back, mimetype='application/json')
    if request.method == 'POST':
        # 获取Authorization
        authorization = request.headers.get('Authorization', '')
        if not authorization.startswith("Bearer Cr "):
            back = {"code": 412, "error": "无效的Authorization头格式"}
            back = json.dumps(back, ensure_ascii=False)
            return Response(back, mimetype='application/json')

        signature_part = authorization[len("Bearer Cr "):]
        parts = signature_part.split(":")
        if len(parts) != 2:
            back = {"code": 412, "error": "无效的签名格式"}
            back = json.dumps(back, ensure_ascii=False)
            return Response(back, mimetype='application/json')
        signature, timestamp = parts[0], parts[1]
    else:
        sign_param = request.args.get('sign', '')
        if not sign_param:
            back = {"code": 412, "error": "未获取到签名信息"}
            back = json.dumps(back, ensure_ascii=False)
            return Response(back, mimetype='application/json')
        decoded_sign = unquote(sign_param)
        parts = decoded_sign.split(":")
        if len(parts) != 2:
            back = {"code": 412, "error": "URL中无效的签名格式"}
            back = json.dumps(back, ensure_ascii=False)
            return Response(back, mimetype='application/json')
        signature, timestamp = parts[0], parts[1]
    is_valid, message = verify_signature(request, signature, timestamp)
    if not is_valid:
        back = {"code": 412, "error": message}
        back = json.dumps(back, ensure_ascii=False)
        return Response(back, mimetype='application/json')
    if request.method == 'POST':
        return create_order()
    else:
        return check_order()
def create_order():
    # 读取post内容
    data = request.get_data()
    # 解析json
    data = json.loads(data)
    order_no = data['order_no']
    amount = data['amount']
    currency = data['currency']
    if currency != "CNY":
        if currency not in CURRENCY_UNIT:
            back = {"code": 417, "error": "不支持的货币"}
            back = json.dumps(back, ensure_ascii=False)
            return Response(back, mimetype='application/json')
        else:
            c = CurrencyConverter()
            amount = c.convert(amount / CURRENCY_UNIT[currency], currency, 'CNY') * 100
    # 金额处理（自行修改下面的数值）
    # amount = amount * 1
    if amount < 500:
        # 返回错误信息
        back = {"code": 417, "error": "CNY金额需要大于等于5元"}
        back = json.dumps(back, ensure_ascii=False)
        return Response(back, mimetype='application/json')
    notify_url = data['notify_url']
    order_info = {"order_no": order_no, "amount": amount, "currency": currency, "notify_url": notify_url}
    # json格式化order_info
    order_info = json.dumps(order_info, ensure_ascii=False)
    order_url = afdian.new_order(order_info, amount)
    back = {
        "code": 0,
        "data": order_url
    }
    # json格式化back
    back = json.dumps(back, ensure_ascii=False)
    return Response(back, mimetype='application/json')
def check_order():
    order_no = request.args.get('order_no')
    try:
        status = afdian.get_order_status(order_no)
        back = {"code": 0, "data": "PAID" if status else "UNPAID"}
        back = json.dumps(back, ensure_ascii=False)
        return Response(back, mimetype='application/json')
    except Exception as e:
        back = {"code": 500, "error": "Failed to query order status."}
        back = json.dumps(back, ensure_ascii=False)
        return Response(back, mimetype='application/json')

# 初始化检查、载入配置
check()
# 设置货币最小单位
CURRENCY_UNIT = {'USD': 100, 'EUR': 100, 'GBP': 100, 'JPY': 1, 'CNY': 100, 'HKD': 100, 'SGD': 100, 'KRW': 1, 'INR': 100, 'RUB': 100, 'BRL': 100, 'AUD': 100, 'CAD': 100, 'CHF': 100}
# 启动后台回调worker
gevent.spawn(notify_worker_loop)
print("Cloudreve Afdian Pay Server\t已启动\nGithub: https://github.com/essesoul/Cloudreve-AfdianPay")
print("-------------------------")
port = str(os.getenv('PORT'))
print("程序运行端口：" + port)
server = pywsgi.WSGIServer(('0.0.0.0', int(port)), app)
server.serve_forever()
