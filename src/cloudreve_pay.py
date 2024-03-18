import json
import math
import os
import time

import requests

import afdian

try:
    from flask import Flask, request, Response
except:
    print("未找到flask模块")

try:
    from gevent import pywsgi
except:
    print("未找到gevent模块")
try:
    from dotenv import load_dotenv
except:
    print("未找到dotenv模块")
app = Flask(__name__)


# 初始化检查
def check():
    # 判断.env文件是否存在
    if os.path.exists('.env'):
        if os.environ.get('SITE_URL') == "":
            print("SITE_URL未设置,已停止运行")
            exit()
        if os.environ.get('USER_ID') == "":
            print("USER_ID未设置,已停止运行")
            exit()
        if os.environ.get('TOKEN') == "":
            print("TOKEN未设置,已停止运行")
            exit()
        if os.environ.get('PORT') == "":
            print("PORT未设置,已停止运行")
            exit()
        print("初始化检查通过")
        return
    else:
        print("未找到.env文件,已停止运行")
        exit()


@app.route('/afdian', methods=['POST'])
def respond():
    # 解析返回的json值
    data = request.get_data()
    data = json.loads(data)['data']['order']
    out_trade_no = data['out_trade_no']
    # 获取订单信息（remark）
    order_no = data['remark']
    # 获取订单amount
    afd_amount = str(data['total_amount']).split(".")[0]
    afd_amount = int(afd_amount)
    # 查询订单
    amount = 0
    notify_url = ""
    raw = afdian.check_order(order_no, out_trade_no)
    if raw[1] != 0:
        amount = raw[1]
    if afd_amount == int(amount):
        # 订单金额相同
        # 通知网站
        notify_url = raw[2]
        url = notify_url
        # 发送get请求
        requests.get(url)
    # json格式化
    back = '{"ec":200,"em":""}'
    json.dumps(back, ensure_ascii=False)
    return Response(back, mimetype='application/json')


@app.route('/order/create', methods=['post'])
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
    # 获取Authorization
    authorization = request.headers.get('Authorization').split("Bearer")[1].strip()
    # sign = authorization.split(":")[0]
    timestamp = authorization.split(":")[1]
    t = str(int(time.time()))
    if t > timestamp:
        back = {"code": 412, "error": "时间戳验证失败"}
        return Response(back, mimetype='application/json')
    # 读取post内容
    data = request.get_data()
    # 解析json
    data = json.loads(data)
    order_no = data['order_no']
    amount = data['amount']
    # 金额处理（自行修改下面的数值）
    # amount = amount * 1
    amount = math.ceil(amount)
    if amount < 500:
        # 返回错误信息
        back = {"code": 417, "error": "金额需要大于等于5元"}
        back = json.dumps(back, ensure_ascii=False)
        return Response(back, mimetype='application/json')
    notify_url = data['notify_url']
    order_info = {"order_no": order_no, "amount": amount, "notify_url": notify_url}
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


# 初始化检查
check()

print("Cloudreve Afdian Pay Server\t已启动\nGithub: https://github.com/essesoul/Cloudreve-AfdianPay")
print("-------------------------")
load_dotenv('.env')
port = str(os.getenv('PORT'))
print("程序运行端口：" + port)
server = pywsgi.WSGIServer(('0.0.0.0', int(port)), app)
server.serve_forever()
