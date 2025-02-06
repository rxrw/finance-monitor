import os
import json

# 数据库配置
MYSQL_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'market_data')
}

# 数据库开关
USE_MYSQL = os.environ.get('USE_MYSQL', 'true').lower() == 'true'
USE_INFLUXDB = os.environ.get('USE_INFLUXDB', 'false').lower() == 'true'

# InfluxDB配置
INFLUXDB_CONFIG = {
    'url': os.environ.get('INFLUXDB_URL', 'http://192.168.6.135:8086'),
    'token': os.environ.get('INFLUXDB_TOKEN', 'BzxenmJ17wCEcyCDydUI-LKkolBXpbFJ0jsMT5cyOZz8xHJNcUlM1SOkwVfIkGjSd9sxxQE-opTTvudWjTOI2w=='),
    'org': os.environ.get('INFLUXDB_ORG', 'rxrw'),
    'bucket': os.environ.get('INFLUXDB_BUCKET', 'rate')
}

# 从环境变量获取货币配置，默认值使用JSON格式
DEFAULT_CURRENCIES = [
    'CNH', 'CNY', 'HKD', 'JPY', 'KRW',
    'SGD', 'RUB', 'TWD', 'AUD', 'GBP', 'EUR'
]
CURRENCIES = json.loads(os.environ.get('CURRENCIES', json.dumps(DEFAULT_CURRENCIES)))

# 从环境变量获取股票配置
DEFAULT_STOCKS = {
    'US': ['^DJI', '^GSPC', '^IXIC'],  # 道琼斯、标普500、纳斯达克
    'HK': ['^HSI'],                     # 恒生指数
    'CN': [
        '000001.SS',   # 上证指数
        '399001.SZ',   # 深证成指
        '899050.BJ'    # 北证50
    ]
}
STOCKS = json.loads(os.environ.get('STOCKS', json.dumps(DEFAULT_STOCKS)))

# 其他配置
FETCH_INTERVAL = int(os.environ.get('FETCH_INTERVAL', 3600))
HISTORY_START_DATE = os.environ.get('HISTORY_START_DATE', '2017-07-01')

# 添加历史数据配置
HISTORY_FETCH_ENABLED = os.environ.get('HISTORY_FETCH_ENABLED', 'false').lower() == 'true'

# 历史数据导入开关
IMPORT_HISTORY = os.environ.get('IMPORT_HISTORY', 'false').lower() == 'true' 