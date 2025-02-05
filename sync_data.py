import mysql.connector
from config import *
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sync_database():
    """同步数据库，删除不再需要的数据，保留当前配置中的数据"""
    db = mysql.connector.connect(**DB_CONFIG)
    cursor = db.cursor()
    
    try:
        # 同步汇率数据
        cursor.execute("SELECT DISTINCT to_currency FROM exchange_rates")
        existing_currencies = {row[0] for row in cursor.fetchall()}
        
        # 删除不在当前配置中的货币数据
        currencies_to_remove = existing_currencies - set(CURRENCIES)
        if currencies_to_remove:
            cursor.execute(
                "DELETE FROM exchange_rates WHERE to_currency IN (%s)" % 
                ','.join(['%s'] * len(currencies_to_remove)),
                tuple(currencies_to_remove)
            )
            logger.info(f"已删除货币数据: {currencies_to_remove}")
        
        # 同步股票数据
        cursor.execute("SELECT DISTINCT market, symbol FROM stock_prices")
        existing_stocks = {(row[0], row[1]) for row in cursor.fetchall()}
        current_stocks = {(market, symbol) 
                         for market, symbols in STOCKS.items() 
                         for symbol in symbols}
        
        # 删除不在当前配置中的股票数据
        stocks_to_remove = existing_stocks - current_stocks
        if stocks_to_remove:
            for market, symbol in stocks_to_remove:
                cursor.execute(
                    "DELETE FROM stock_prices WHERE market = %s AND symbol = %s",
                    (market, symbol)
                )
            logger.info(f"已删除股票数据: {stocks_to_remove}")
        
        db.commit()
        logger.info("数据同步完成")
        
    except Exception as e:
        logger.error(f"数据同步失败: {e}")
        db.rollback()
    finally:
        cursor.close()
        db.close()

if __name__ == "__main__":
    sync_database() 