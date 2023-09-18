# Cloudreve-AfdianPay
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Fessesoul%2FCloudreve-AfdianPay.svg?type=shield)](https://app.fossa.com/projects/git%2Bgithub.com%2Fessesoul%2FCloudreve-AfdianPay?ref=badge_shield)


Cloudreve自定义付款渠道-爱发电接口

参考 https://docs.cloudreve.org/use/pro/pay 构建

推荐使用 **Python3.11**

## 使用方法

### 部署

使用爱发电接口

- 需要先[注册爱发电](https://afdian.net/)账户
- 在[开发人员页面](https://afdian.net/dashboard/dev)获取**user_id**
- 在[开发人员页面](https://afdian.net/dashboard/dev)底部获取**API Token**

------

下载 `src` 文件夹，运行 `pip install -r requirements.txt` 安装依赖包

修改 `.env` 文件中的内容

```
SITE_URL="你的网站url，不带斜杠，例如 https://demo.cloudreve.org"
USER_ID="你的爱发电user_id"
TOKEN="你的爱发电api token"
PORT="5000"# 监听端口，默认5000
```

例如

```
SITE_URL="https://demo.cloudreve.org"
USER_ID="abcxxxxxxx123"
TOKEN="aAABBB123xxxxzzz"
PORT="5000"
```

运行 `cloudreve_pay.py` 文件即可

默认监听5000端口，可以自行修改 `.env` 文件的 `PORT` 参数

```
PORT="5000"# 监听端口，默认5000
```

------

### 配置

在[爱发电开发者页面](https://afdian.net/dashboard/dev)设置**Webhook URL** `http://example.com:5000/afdian`
将 `example.com` 更换为你的域名或IP，点击保存

如果没有报错则说明成功

在Cloudreve管理后台-参数设置-增值服务-自定义付款渠道中填写付款方式名称、支付接口地址、通信密钥

接口地址为： `http://example.com:5000/order/create`  将 `example.com` 更换为你的域名或IP，点击保存

通信密钥可以随意填写，暂时还没加入签名验证



## License
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Fessesoul%2FCloudreve-AfdianPay.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2Fessesoul%2FCloudreve-AfdianPay?ref=badge_large)