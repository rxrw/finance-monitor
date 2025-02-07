import time
import yfinance as yf
import mysql.connector
from datetime import datetime, timedelta
import logging
from config import *
from decimal import Decimal, ROUND_HALF_UP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MarketDataCollector:
    def __init__(self):
        self.use_mysql = USE_MYSQL
        if self.use_mysql:
            self.db = mysql.connector.connect(**MYSQL_CONFIG)
            self.cursor = self.db.cursor()
        
        self.use_influxdb = USE_INFLUXDB
        if self.use_influxdb:
            from influxdb_client import InfluxDBClient
            self.influx_client = InfluxDBClient(
                url=INFLUXDB_CONFIG['url'],
                token=INFLUXDB_CONFIG['token'],
                org=INFLUXDB_CONFIG['org']
            )
            self.write_api = self.influx_client.write_api()

    def round_decimal(self, value, places=6):
        """智能四舍五入处理数值"""
        try:
            if isinstance(value, (float, int)):
                value = str(value)
            dec = Decimal(value)
            
            # 处理接近整数的情况（如0.9999或1.0001）
            nearest_int = round(float(dec))
            if abs(float(dec) - nearest_int) < 0.0001:
                return float(nearest_int)
            
            # 处理接近x.5的情况（如7.4999或7.5001）
            nearest_half = round(float(dec) * 2) / 2
            if abs(float(dec) - nearest_half) < 0.0001:
                return float(nearest_half)
            
            # 处理接近x.25或x.75的情况
            nearest_quarter = round(float(dec) * 4) / 4
            if abs(float(dec) - nearest_quarter) < 0.0001:
                return float(nearest_quarter)
            
            # 其他情况保留6位小数
            return float(dec.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP))
        except Exception as e:
            logger.error(f"数值转换错误 {value}: {e}")
            return value

    def get_latest_data(self, symbol, retries=3):
        """获取最新数据，带重试机制"""
        for attempt in range(retries):
            try:
                # 对于货币对特殊处理
                if symbol.endswith('=X'):
                    data = yf.download(
                        symbol, 
                        period='1d', 
                        interval='1m',
                        progress=False
                    )
                    if not data.empty:
                        latest = data.iloc[-1]
                        return {
                            'timestamp': data.index[-1],
                            'Close': float(latest['Close'].iloc[0]) if hasattr(latest['Close'], 'iloc') else float(latest['Close']),
                            'Volume': int(latest['Volume'].iloc[0]) if hasattr(latest['Volume'], 'iloc') else int(latest['Volume']) if 'Volume' in latest else 0
                        }
                else:
                    # 非货币对的处理
                    if symbol.startswith('^'):  # 美股指数
                        period = '2d'
                        interval = '1h'
                    else:  # 其他市场
                        period = '1d'
                        interval = '1m'
                        
                    data = yf.download(
                        symbol, 
                        period=period,
                        interval=interval,
                        progress=False
                    )
                    if not data.empty:
                        latest = data.iloc[-1]
                        logger.info(f"获取到 {symbol} 数据: 时间={data.index[-1]}, 价格={latest['Close']}")
                        return {
                            'timestamp': data.index[-1],
                            'Close': float(latest['Close'].iloc[0]) if hasattr(latest['Close'], 'iloc') else float(latest['Close']),
                            'Volume': int(latest['Volume'].iloc[0]) if hasattr(latest['Volume'], 'iloc') else int(latest['Volume']) if 'Volume' in latest else 0
                        }
                
                logger.error(f"未能获取到 {symbol} 的数据")
            except Exception as e:
                logger.error(f"第{attempt + 1}次获取{symbol}数据失败: {e}")
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))
        return None

    def write_to_mysql(self, query, params, retries=3):
        """MySQL写入，带重试机制"""
        if not self.use_mysql:
            return
            
        for attempt in range(retries):
            try:
                self.cursor.execute(query, params)
                self.db.commit()
                return True
            except mysql.connector.Error as e:
                logger.error(f"MySQL写入错误 (尝试 {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    try:
                        self.db.ping(reconnect=True)  # 尝试重连
                        time.sleep(1 * (attempt + 1))  # 递增等待时间
                    except Exception as e:
                        logger.error(f"MySQL重连失败: {e}")
                else:
                    logger.error("MySQL写入最终失败")
                    return False
        return False

    def write_to_influxdb(self, measurement, tags, fields, timestamp, retries=3):
        """写入数据到InfluxDB，带重试机制"""
        if not self.use_influxdb:
            logger.info("InfluxDB写入已禁用")
            return False
            
        for attempt in range(retries):
            try:
                from influxdb_client import Point
                point = Point(measurement)
                
                # 添加所有标签
                for tag_key, tag_value in tags.items():
                    point = point.tag(tag_key, tag_value)
                
                # 添加所有字段
                for field_key, field_value in fields.items():
                    point = point.field(field_key, field_value)
                
                # 设置时间戳
                point = point.time(timestamp)
                
                logger.info(f"正在写入InfluxDB: measurement={measurement}, tags={tags}, fields={fields}, timestamp={timestamp}")
                
                # 写入数据
                self.write_api.write(
                    bucket=INFLUXDB_CONFIG['bucket'],
                    record=point
                )
                
                logger.info(f"InfluxDB写入成功: {measurement}")
                return True
                
            except Exception as e:
                logger.error(f"InfluxDB写入错误 (尝试 {attempt + 1}/{retries}): {e}")
                logger.error(f"详细信息: measurement={measurement}, tags={tags}, fields={fields}, timestamp={timestamp}")
                if attempt < retries - 1:
                    time.sleep(1 * (attempt + 1))
                else:
                    logger.error("InfluxDB写入最终失败")
                    return False
        return False

    def fetch_usd_index(self):
        """获取美元指数"""
        try:
            data = self.get_latest_data('EURUSD=X')
            if data is not None:
                rate = data['Close']
                usd_index = self.round_decimal((1 / rate) * 88.3)
                timestamp = data['timestamp']  # 使用数据的实际时间戳
                
                # MySQL写入
                mysql_success = self.write_to_mysql(
                    "INSERT INTO usd_index (timestamp, value) VALUES (%s, %s)",
                    (timestamp, usd_index)
                )
                
                # InfluxDB写入
                influx_success = self.write_to_influxdb(
                    measurement="usd_index",
                    tags={},
                    fields={"value": usd_index},
                    timestamp=timestamp
                )
                
                if mysql_success or influx_success:
                    logger.info(f"USD Index updated: {usd_index}")
                else:
                    logger.error("USD Index 更新失败：所有数据库写入都失败了")
        except Exception as e:
            logger.error(f"Error fetching USD index: {e}")

    def fetch_exchange_rates(self):
        """获取汇率数据"""
        for currency in CURRENCIES:
            try:
                symbol = f'USD{currency}=X'
                
                # 对CNH特殊处理
                if currency == 'CNH':
                    for symbol_try in ['USDCNH=X', 'CNH=F', 'CNHUSD=X']:
                        data = self.get_latest_data(symbol_try)
                        if data is not None:
                            break
                else:
                    data = self.get_latest_data(symbol)
                
                if data is not None:
                    rate = self.round_decimal(data['Close'])
                    timestamp = data['timestamp']  # 使用数据的实际时间戳
                    
                    # MySQL写入
                    mysql_success = self.write_to_mysql(
                        "INSERT INTO exchange_rates (timestamp, from_currency, to_currency, rate) VALUES (%s, %s, %s, %s)",
                        (timestamp, 'USD', currency, rate)
                    )
                    
                    # InfluxDB写入
                    influx_success = self.write_to_influxdb(
                        measurement="exchange_rates",
                        tags={
                            "from_currency": "USD",
                            "to_currency": currency
                        },
                        fields={"rate": rate},
                        timestamp=timestamp
                    )
                    
                    if mysql_success or influx_success:
                        logger.info(f"Exchange rate updated for USD/{currency}: {rate}")
                    else:
                        logger.error(f"Exchange rate 更新失败 USD/{currency}: 所有数据库写入都失败了")
                else:
                    logger.error(f"未能获取到 {currency} 的数据")
                
                time.sleep(2)
            except Exception as e:
                logger.error(f"Error fetching exchange rate for {currency}: {e}")

    def fetch_stock_prices(self):
        """获取股票指数价格"""
        for market, symbols in STOCKS.items():
            for symbol in symbols:
                try:
                    # 修正股票代码格式
                    if market == 'HK':
                        yf_symbol = "^HSI"  # 恒生指数特殊处理
                    elif market == 'CN':
                        if symbol == '000001.SS':
                            yf_symbol = '000001.SS'  # 上证指数
                        elif symbol == '399001.SZ':
                            yf_symbol = '399001.SZ'  # 深证成指
                        elif symbol == '899050.BJ':
                            yf_symbol = '899050.BJ'  # 北证50
                    else:
                        yf_symbol = symbol
                    
                    data = self.get_latest_data(yf_symbol)
                    if data is not None:
                        price = self.round_decimal(data['Close'])
                        volume = data['Volume']
                        currency = 'USD' if market == 'US' else 'HKD' if market == 'HK' else 'CNY'
                        timestamp = data['timestamp']  # 使用数据的实际时间戳
                        
                        # MySQL写入
                        mysql_success = self.write_to_mysql(
                            """INSERT INTO stock_prices 
                               (timestamp, market, symbol, price, currency, volume) 
                               VALUES (%s, %s, %s, %s, %s, %s)""",
                            (timestamp, market, symbol, price, currency, volume)
                        )
                        
                        # InfluxDB写入
                        influx_success = self.write_to_influxdb(
                            measurement="stock_prices",
                            tags={
                                "market": market,
                                "symbol": symbol,
                                "currency": currency
                            },
                            fields={
                                "price": price,
                                "volume": volume
                            },
                            timestamp=timestamp
                        )
                        
                        if mysql_success or influx_success:
                            logger.info(f"Stock index updated for {market}:{symbol}: {price} {currency}")
                        else:
                            logger.error(f"Stock index 更新失败 {market}:{symbol}: 所有数据库写入都失败了")
                    
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Error fetching stock index for {market}:{symbol}: {e}")

    def get_historical_data(self, symbol, start, end, interval, retries=3):
        """获取历史数据，带重试机制"""
        for attempt in range(retries):
            try:
                data = yf.download(
                    symbol,
                    start=start,
                    end=end,
                    interval=interval,
                    progress=False
                )
                if not data.empty:
                    return data
                    
            except Exception as e:
                logger.error(f"第{attempt + 1}次获取{symbol}数据失败: {e}")
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))
        
        logger.error(f"无法获取 {symbol} 的数据，所有尝试都失败了")
        return None

    def fetch_historical_data(self, start_date):
        """获取历史数据"""
        try:
            end_date = datetime.now()
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            days_diff = (end_date - start_datetime).days
            
            # 根据时间跨度确定数据间隔
            def get_interval(days):
                if days <= 7:  # 7天内用15分钟
                    return '15m'
                elif days <= 60:  # 60天内用1小时
                    return '1h'
                else:  # 超过60天用天级别
                    return '1d'
            
            # 分段获取数据
            segments = [
                (start_datetime, min(start_datetime + timedelta(days=60), end_date), '1d'),  # 60天以前的数据
                (max(end_date - timedelta(days=60), start_datetime), end_date - timedelta(days=7), '1h'),  # 7-60天的数据
                (end_date - timedelta(days=7), end_date, '15m')  # 最近7天的数据
            ]
            
            # 过滤掉无效的时间段
            segments = [(start, end, interval) for start, end, interval in segments if start < end]

            for currency in CURRENCIES:
                symbol = f'USD{currency}=X'
                
                for start, end, interval in segments:
                    logger.info(f"获取 {symbol} 从 {start} 到 {end} 的 {interval} 数据")
                    data = self.get_historical_data(symbol, start, end, interval)
                    
                    for timestamp, row in data.iterrows():
                        rate = self.round_decimal(row['Close'])
                        
                        # MySQL写入
                        if self.use_mysql:
                            query = "INSERT INTO exchange_rates (timestamp, from_currency, to_currency, rate) VALUES (%s, %s, %s, %s)"
                            self.cursor.execute(query, (timestamp, 'USD', currency, rate))
                            self.db.commit()
                        
                        # InfluxDB写入
                        self.write_to_influxdb(
                            measurement="exchange_rates",
                            tags={
                                "from_currency": "USD",
                                "to_currency": currency
                            },
                            fields={"rate": rate},
                            timestamp=timestamp
                        )
                    
                    time.sleep(1)  # 短暂暂停避免请求过快
                
                logger.info(f"历史汇率数据已导入: USD/{currency}")
                time.sleep(2)  # 避免请求过于频繁

            # 获取股票历史数据
            for market, symbols in STOCKS.items():
                for symbol in symbols:
                    if market == 'HK':
                        yf_symbol = "^HSI"
                    elif market == 'CN':
                        yf_symbol = symbol
                    else:
                        yf_symbol = symbol
                    
                    for start, end, interval in segments:
                        logger.info(f"获取 {market}:{symbol} 从 {start} 到 {end} 的 {interval} 数据")
                        data = self.get_historical_data(yf_symbol, start, end, interval)
                        
                        currency = 'USD' if market == 'US' else 'HKD' if market == 'HK' else 'CNY'
                        
                        for timestamp, row in data.iterrows():
                            price = self.round_decimal(row['Close'])
                            volume = int(row['Volume']) if 'Volume' in row else 0
                            
                            # MySQL写入
                            if self.use_mysql:
                                query = """INSERT INTO stock_prices 
                                         (timestamp, market, symbol, price, currency, volume) 
                                         VALUES (%s, %s, %s, %s, %s, %s)"""
                                self.cursor.execute(query, (timestamp, market, symbol, price, currency, volume))
                                self.db.commit()
                            
                            # InfluxDB写入
                            self.write_to_influxdb(
                                measurement="stock_prices",
                                tags={
                                    "market": market,
                                    "symbol": symbol,
                                    "currency": currency
                                },
                                fields={
                                    "price": price,
                                    "volume": volume
                                },
                                timestamp=timestamp
                            )
                        
                        time.sleep(1)  # 短暂暂停避免请求过快
                    
                    logger.info(f"历史股票数据已导入: {market}:{symbol}")
                    time.sleep(2)  # 避免请求过于频繁

        except Exception as e:
            logger.error(f"获取历史数据时发生错误: {e}")

    def run(self, fetch_historical=False):
        """主运行循环"""
        try:
            if fetch_historical:
                logger.info("开始获取历史数据...")
                self.fetch_historical_data(HISTORY_START_DATE)
                logger.info("历史数据获取完成")
            
            while True:
                self.fetch_usd_index()
                self.fetch_exchange_rates()
                self.fetch_stock_prices()
                time.sleep(FETCH_INTERVAL)
        except KeyboardInterrupt:
            logger.info("程序正在退出...")
            self.cleanup()
        except Exception as e:
            logger.error(f"运行时发生错误: {e}")
            self.cleanup()

    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'write_api') and self.write_api:
                logger.info("正在关闭 InfluxDB write_api...")
                self.write_api.close()
            if hasattr(self, 'influx_client') and self.influx_client:
                logger.info("正在关闭 InfluxDB client...")
                self.influx_client.close()
            if hasattr(self, 'cursor') and self.cursor:
                logger.info("正在关闭 MySQL cursor...")
                self.cursor.close()
            if hasattr(self, 'db') and self.db:
                logger.info("正在关闭 MySQL connection...")
                self.db.close()
        except Exception as e:
            logger.error(f"清理资源时发生错误: {e}")

    def __del__(self):
        """析构函数"""
        self.cleanup()

if __name__ == "__main__":
    collector = MarketDataCollector()
    collector.run(fetch_historical=HISTORY_FETCH_ENABLED) 