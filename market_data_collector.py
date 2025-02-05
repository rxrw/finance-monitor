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
        self.db = mysql.connector.connect(**DB_CONFIG)
        self.cursor = self.db.cursor()

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
                # 添加verify=False来处理SSL问题
                data = yf.download(
                    symbol, 
                    period='1d', 
                    interval='1m', 
                    progress=False,
                    verify=False
                )
                if not data.empty:
                    latest = data.iloc[-1]
                    return {
                        'Close': float(latest['Close'].iloc[0]) if hasattr(latest['Close'], 'iloc') else float(latest['Close']),
                        'Volume': int(latest['Volume'].iloc[0]) if hasattr(latest['Volume'], 'iloc') else int(latest['Volume']) if 'Volume' in latest else 0
                    }
            except Exception as e:
                logger.error(f"第{attempt + 1}次获取{symbol}数据失败: {e}")
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))  # 递增等待时间
        return None

    def fetch_usd_index(self):
        """获取美元指数"""
        try:
            # 使用EUR/USD来计算美元指数
            data = self.get_latest_data('EURUSD=X')
            if data is not None:
                rate = data['Close']
                # 使用EUR/USD汇率的倒数乘以标准系数来近似美元指数
                usd_index = self.round_decimal((1 / rate) * 88.3)
                
                query = "INSERT INTO usd_index (timestamp, value) VALUES (%s, %s)"
                self.cursor.execute(query, (datetime.now(), usd_index))
                self.db.commit()
                logger.info(f"USD Index updated: {usd_index}")
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
                    
                    query = "INSERT INTO exchange_rates (timestamp, from_currency, to_currency, rate) VALUES (%s, %s, %s, %s)"
                    self.cursor.execute(query, (datetime.now(), 'USD', currency, rate))
                    self.db.commit()
                    logger.info(f"Exchange rate updated for USD/{currency}: {rate}")
                else:
                    logger.error(f"未能获取到 {currency} 的数据")
                
                time.sleep(2)  # 避免请求过于频繁
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
                        
                        query = """INSERT INTO stock_prices 
                                  (timestamp, market, symbol, price, currency, volume) 
                                  VALUES (%s, %s, %s, %s, %s, %s)"""
                        self.cursor.execute(query, (datetime.now(), market, symbol, price, currency, volume))
                        self.db.commit()
                        logger.info(f"Stock index updated for {market}:{symbol}: {price} {currency}")
                    
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Error fetching stock index for {market}:{symbol}: {e}")

    def fetch_historical_data(self, start_date):
        """获取历史数据"""
        # 这里需要使用不同的API endpoint来获取历史数据
        # 实现逻辑类似，但使用时间序列API
        pass

    def run(self):
        """主运行循环"""
        while True:
            self.fetch_usd_index()
            self.fetch_exchange_rates()
            self.fetch_stock_prices()
            time.sleep(FETCH_INTERVAL)

if __name__ == "__main__":
    collector = MarketDataCollector()
    collector.run() 