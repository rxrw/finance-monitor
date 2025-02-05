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
        self.db = mysql.connector.connect(**DB_CONFIG)
        self.cursor = self.db.cursor()
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

    def get_historical_data(self, symbol, retries=3):
        """获取历史数据，带重试机制"""
        for attempt in range(retries):
            try:
                data = yf.download(
                    symbol,
                    start=self.start_date,
                    end=self.end_date,
                    interval='1d',
                    progress=False
                )
                if not data.empty:
                    return data
            except Exception as e:
                logger.error(f"第{attempt + 1}次获取{symbol}数据失败: {e}")
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))  # 递增等待时间
        return None

    def import_historical_exchange_rates(self):
        """导入历史汇率数据"""
        logger.info("开始导入历史汇率数据...")
        
        for currency in CURRENCIES:
            try:
                symbol = f'USD{currency}=X'
                
                # 对CNH特殊处理
                if currency == 'CNH':
                    # 尝试不同的CNH数据源
                    data = None
                    for symbol_try in ['USDCNH=X', 'CNH=F', 'CNHUSD=X']:
                        logger.info(f"尝试使用{symbol_try}获取CNH数据...")
                        data = self.get_historical_data(symbol_try)
                        if data is not None and not data.empty:
                            break
                else:
                    data = self.get_historical_data(symbol)
                
                if data is None or data.empty:
                    logger.error(f"未能获取到 {currency} 的数据")
                    continue
                
                for index, row in data.iterrows():
                    try:
                        date = index.to_pydatetime()
                        close_price = float(row['Close'].iloc[0]) if hasattr(row['Close'], 'iloc') else float(row['Close'])
                        rate = self.round_decimal(close_price)
                        
                        # 检查是否已存在相同记录
                        check_query = """SELECT id FROM exchange_rates 
                                       WHERE timestamp = %s AND from_currency = %s 
                                       AND to_currency = %s"""
                        self.cursor.execute(check_query, (date, 'USD', currency))
                        exists = self.cursor.fetchone()
                        
                        if not exists:
                            query = """INSERT INTO exchange_rates 
                                     (timestamp, from_currency, to_currency, rate) 
                                     VALUES (%s, %s, %s, %s)"""
                            self.cursor.execute(query, (date, 'USD', currency, rate))
                            self.db.commit()
                            logger.info(f"导入汇率数据: {date.date()} USD/{currency} - {rate}")
                        else:
                            logger.info(f"跳过已存在的记录: {date.date()} USD/{currency}")
                            
                    except Exception as e:
                        logger.error(f"处理{currency}数据时出错: {e}")
                        continue
                
                logger.info(f"完成货币 {currency} 的历史数据导入")
                time.sleep(2)  # 避免请求过于频繁
                
            except Exception as e:
                logger.error(f"导入汇率数据失败 {currency}: {e}")
                time.sleep(5)

    def import_historical_stock_prices(self):
        """导入历史股票数据"""
        logger.info("开始导入历史股票数据...")
        
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
                    
                    data = self.get_historical_data(yf_symbol)
                    
                    for index, row in data.iterrows():
                        try:
                            date = index.to_pydatetime()
                            close_price = float(row['Close'].iloc[0]) if hasattr(row['Close'], 'iloc') else float(row['Close'])
                            price = self.round_decimal(close_price)
                            volume = int(row['Volume'].iloc[0]) if hasattr(row['Volume'], 'iloc') else int(row['Volume'])
                            currency = 'USD' if market == 'US' else 'HKD' if market == 'HK' else 'CNY'
                            
                            # 检查是否已存在相同记录
                            check_query = """SELECT id FROM stock_prices 
                                           WHERE timestamp = %s AND market = %s 
                                           AND symbol = %s"""
                            self.cursor.execute(check_query, (date, market, symbol))
                            exists = self.cursor.fetchone()
                            
                            if not exists:
                                query = """INSERT INTO stock_prices 
                                         (timestamp, market, symbol, price, currency, volume) 
                                         VALUES (%s, %s, %s, %s, %s, %s)"""
                                self.cursor.execute(query, (date, market, symbol, price, currency, volume))
                                self.db.commit()
                                logger.info(f"导入股票数据: {date.date()} {market}:{symbol} - {price} {currency}")
                            else:
                                logger.info(f"跳过已存在的记录: {date.date()} {market}:{symbol}")
                                
                        except Exception as e:
                            logger.error(f"处理股票数据时出错 {market}:{symbol}: {e}")
                            continue
                    
                    logger.info(f"完成股票 {market}:{symbol} 的历史数据导入")
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"导入股票数据失败 {market}:{symbol}: {e}")
                    time.sleep(5)

    def import_historical_usd_index(self):
        """导入历史美元指数数据"""
        logger.info("开始导入历史美元指数数据...")
        
        try:
            # 使用欧元兑美元的历史数据来计算美元指数
            data = self.get_historical_data('EURUSD=X')
            
            if data is not None and not data.empty:
                for index, row in data.iterrows():
                    try:
                        date = index.to_pydatetime()
                        eur_usd_rate = float(row['Close'].iloc[0]) if hasattr(row['Close'], 'iloc') else float(row['Close'])
                        # 使用EUR/USD汇率的倒数乘以标准系数来计算美元指数
                        usd_index = self.round_decimal((1 / eur_usd_rate) * 88.3)
                        
                        # 检查是否已存在相同记录
                        check_query = "SELECT id FROM usd_index WHERE timestamp = %s"
                        self.cursor.execute(check_query, (date,))
                        exists = self.cursor.fetchone()
                        
                        if not exists:
                            query = "INSERT INTO usd_index (timestamp, value) VALUES (%s, %s)"
                            self.cursor.execute(query, (date, usd_index))
                            self.db.commit()
                            logger.info(f"导入美元指数数据: {date.date()} - {usd_index}")
                        else:
                            logger.info(f"跳过已存在的记录: {date.date()}")
                            
                    except Exception as e:
                        logger.error(f"处理美元指数数据时出错 {date}: {e}")
                        continue
                
                logger.info("完成美元指数历史数据导入")
            else:
                logger.error("未能获取到美元指数历史数据")
            
        except Exception as e:
            logger.error(f"导入美元指数历史数据失败: {e}")

    def run(self):
        """运行所有历史数据导入"""
        self.import_historical_usd_index()  # 添加美元指数历史数据导入
        self.import_historical_exchange_rates()
        self.import_historical_stock_prices()
        logger.info("历史数据导入完成")

if __name__ == "__main__":
    importer = HistoricalDataImporter()
    importer.run() 