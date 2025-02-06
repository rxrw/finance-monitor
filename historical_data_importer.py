import yfinance as yf
import mysql.connector
from datetime import datetime, timedelta
import logging
from config import *
import time
from decimal import Decimal, ROUND_HALF_UP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HistoricalDataImporter:
    def __init__(self):
        # MySQL 初始化
        self.use_mysql = USE_MYSQL
        if self.use_mysql:
            self.db = mysql.connector.connect(**MYSQL_CONFIG)
            self.cursor = self.db.cursor()
        
        # InfluxDB 初始化
        self.use_influxdb = USE_INFLUXDB
        if self.use_influxdb:
            from influxdb_client import InfluxDBClient
            self.influx_client = InfluxDBClient(
                url=INFLUXDB_CONFIG['url'],
                token=INFLUXDB_CONFIG['token'],
                org=INFLUXDB_CONFIG['org']
            )
            self.write_api = self.influx_client.write_api()

        self.start_date = datetime.strptime(HISTORY_START_DATE, '%Y-%m-%d')
        self.end_date = datetime.now()

    def round_decimal(self, value, places=4):
        """智能四舍五入处理数值"""
        try:
            if isinstance(value, (float, int)):
                value = str(value)
            # 将数值转换为Decimal进行精确计算
            dec = Decimal(value)
            
            # 处理接近整数的情况（如0.999999）
            # 如果与最近的整数的差异小于0.0001，则取整
            nearest_int = round(float(dec))
            if abs(float(dec) - nearest_int) < 0.0001:
                return float(Decimal(str(nearest_int)))
            
            # 其他情况正常四舍五入到指定位数
            return float(dec.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))
        except Exception as e:
            logger.error(f"数值转换错误 {value}: {e}")
            return value

    def safe_float(self, value):
        """安全地将值转换为float"""
        try:
            if hasattr(value, 'iloc'):
                return float(value.iloc[0])
            return float(value)
        except Exception as e:
            logger.error(f"转换float失败: {e}")
            return 0.0

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
                    time.sleep(5 * (attempt + 1))  # 递增等待时间
        return None

    def get_data_segments(self):
        """根据时间跨度返回数据获取分段"""
        end_date = datetime.now()
        days_diff = (end_date - self.start_date).days
        
        segments = [
            (self.start_date, min(self.start_date + timedelta(days=60), end_date), '1d'),  # 60天以前的数据
            (max(end_date - timedelta(days=60), self.start_date), end_date - timedelta(days=7), '1h'),  # 7-60天的数据
            (end_date - timedelta(days=7), end_date, '1m')  # 最近7天的数据
        ]
        
        # 过滤掉无效的时间段
        return [(start, end, interval) for start, end, interval in segments if start < end]

    def import_historical_exchange_rates(self):
        """导入历史汇率数据"""
        logger.info("开始导入历史汇率数据...")
        segments = self.get_data_segments()
        
        for currency in CURRENCIES:
            try:
                symbol = f'USD{currency}=X'
                
                # 对CNH特殊处理
                if currency == 'CNH':
                    symbols_to_try = ['USDCNH=X', 'CNH=F', 'CNHUSD=X']
                else:
                    symbols_to_try = [symbol]
                
                for segment_start, segment_end, interval in segments:
                    logger.info(f"获取 {currency} 从 {segment_start} 到 {segment_end} 的 {interval} 数据")
                    
                    data = None
                    for symbol_try in symbols_to_try:
                        data = self.get_historical_data(symbol_try, segment_start, segment_end, interval)
                        if data is not None and not data.empty:
                            break
                    
                    if data is None or data.empty:
                        logger.error(f"未能获取到 {currency} 的数据")
                        continue
                    
                    for index, row in data.iterrows():
                        try:
                            timestamp = index.to_pydatetime()
                            rate = self.round_decimal(self.safe_float(row['Close']))
                            
                            # MySQL写入
                            if self.use_mysql:
                                check_query = """SELECT id FROM exchange_rates 
                                               WHERE timestamp = %s AND from_currency = %s 
                                               AND to_currency = %s"""
                                self.cursor.execute(check_query, (timestamp, 'USD', currency))
                                if not self.cursor.fetchone():
                                    query = """INSERT INTO exchange_rates 
                                             (timestamp, from_currency, to_currency, rate) 
                                             VALUES (%s, %s, %s, %s)"""
                                    self.cursor.execute(query, (timestamp, 'USD', currency, rate))
                                    self.db.commit()
                            
                            # InfluxDB写入
                            if self.use_influxdb:
                                from influxdb_client import Point
                                point = Point("exchange_rates") \
                                    .tag("from_currency", "USD") \
                                    .tag("to_currency", currency) \
                                    .field("rate", rate) \
                                    .time(timestamp)
                                self.write_api.write(bucket=INFLUXDB_CONFIG['bucket'], record=point)
                            
                            logger.info(f"导入汇率数据: {timestamp} USD/{currency} - {rate}")
                            
                        except Exception as e:
                            logger.error(f"处理{currency}数据时出错: {e}")
                            continue
                    
                    time.sleep(1)  # 短暂暂停避免请求过快
                
                logger.info(f"完成货币 {currency} 的历史数据导入")
                time.sleep(2)  # 避免请求过于频繁
                
            except Exception as e:
                logger.error(f"导入汇率数据失败 {currency}: {e}")
                time.sleep(5)

    def import_historical_stock_prices(self):
        """导入历史股票数据"""
        logger.info("开始导入历史股票数据...")
        segments = self.get_data_segments()
        
        for market, symbols in STOCKS.items():
            for symbol in symbols:
                try:
                    # 修正股票代码格式
                    if market == 'HK':
                        yf_symbol = "^HSI"
                    elif market == 'CN':
                        yf_symbol = symbol
                    else:
                        yf_symbol = symbol
                    
                    for segment_start, segment_end, interval in segments:
                        logger.info(f"获取 {market}:{symbol} 从 {segment_start} 到 {segment_end} 的 {interval} 数据")
                        data = self.get_historical_data(yf_symbol, segment_start, segment_end, interval)
                        
                        if data is None or data.empty:
                            logger.error(f"未能获取到 {market}:{symbol} 的数据")
                            continue
                        
                        currency = 'USD' if market == 'US' else 'HKD' if market == 'HK' else 'CNY'
                        
                        for index, row in data.iterrows():
                            try:
                                timestamp = index.to_pydatetime()
                                price = self.round_decimal(self.safe_float(row['Close']))
                                volume = int(self.safe_float(row['Volume'])) if 'Volume' in row else 0
                                
                                # MySQL写入
                                if self.use_mysql:
                                    check_query = """SELECT id FROM stock_prices 
                                                   WHERE timestamp = %s AND market = %s 
                                                   AND symbol = %s"""
                                    self.cursor.execute(check_query, (timestamp, market, symbol))
                                    if not self.cursor.fetchone():
                                        query = """INSERT INTO stock_prices 
                                                 (timestamp, market, symbol, price, currency, volume) 
                                                 VALUES (%s, %s, %s, %s, %s, %s)"""
                                        self.cursor.execute(query, (timestamp, market, symbol, price, currency, volume))
                                        self.db.commit()
                                
                                # InfluxDB写入
                                if self.use_influxdb:
                                    from influxdb_client import Point
                                    point = Point("stock_prices") \
                                        .tag("market", market) \
                                        .tag("symbol", symbol) \
                                        .tag("currency", currency) \
                                        .field("price", price) \
                                        .field("volume", volume) \
                                        .time(timestamp)
                                    self.write_api.write(bucket=INFLUXDB_CONFIG['bucket'], record=point)
                                
                                logger.info(f"导入股票数据: {timestamp} {market}:{symbol} - {price} {currency}")
                                
                            except Exception as e:
                                logger.error(f"处理股票数据时出错 {market}:{symbol}: {e}")
                                continue
                        
                        time.sleep(1)  # 短暂暂停避免请求过快
                    
                    logger.info(f"完成股票 {market}:{symbol} 的历史数据导入")
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"导入股票数据失败 {market}:{symbol}: {e}")
                    time.sleep(5)

    def import_historical_usd_index(self):
        """导入历史美元指数数据"""
        logger.info("开始导入历史美元指数数据...")
        segments = self.get_data_segments()
        
        try:
            for segment_start, segment_end, interval in segments:
                logger.info(f"获取美元指数从 {segment_start} 到 {segment_end} 的 {interval} 数据")
                data = self.get_historical_data('EURUSD=X', segment_start, segment_end, interval)
                
                if data is not None and not data.empty:
                    for index, row in data.iterrows():
                        try:
                            timestamp = index.to_pydatetime()
                            eur_usd_rate = self.safe_float(row['Close'])
                            usd_index = self.round_decimal((1 / eur_usd_rate) * 88.3)
                            
                            # MySQL写入
                            if self.use_mysql:
                                check_query = "SELECT id FROM usd_index WHERE timestamp = %s"
                                self.cursor.execute(check_query, (timestamp,))
                                if not self.cursor.fetchone():
                                    query = "INSERT INTO usd_index (timestamp, value) VALUES (%s, %s)"
                                    self.cursor.execute(query, (timestamp, usd_index))
                                    self.db.commit()
                            
                            # InfluxDB写入
                            if self.use_influxdb:
                                from influxdb_client import Point
                                point = Point("usd_index") \
                                    .field("value", usd_index) \
                                    .time(timestamp)
                                self.write_api.write(bucket=INFLUXDB_CONFIG['bucket'], record=point)
                            
                            logger.info(f"导入美元指数数据: {timestamp} - {usd_index}")
                            
                        except Exception as e:
                            logger.error(f"处理美元指数数据时出错 {timestamp}: {e}")
                            continue
                    
                    time.sleep(1)  # 短暂暂停避免请求过快
                
                logger.info(f"完成时间段 {segment_start} 到 {segment_end} 的美元指数数据导入")
            
        except Exception as e:
            logger.error(f"导入美元指数历史数据失败: {e}")

    def run(self):
        """运行所有历史数据导入"""
        self.import_historical_usd_index()  # 添加美元指数历史数据导入
        self.import_historical_exchange_rates()
        self.import_historical_stock_prices()
        logger.info("历史数据导入完成")

    def __del__(self):
        """清理资源"""
        if hasattr(self, 'cursor') and self.cursor:
            self.cursor.close()
        if hasattr(self, 'db') and self.db:
            self.db.close()
        if hasattr(self, 'write_api') and self.write_api:
            self.write_api.close()
        if hasattr(self, 'influx_client') and self.influx_client:
            self.influx_client.close()

if __name__ == "__main__":
    importer = HistoricalDataImporter()
    importer.run() 