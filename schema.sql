-- 创建数据库
CREATE DATABASE IF NOT EXISTS market_data;
USE market_data;

-- 美元指数表
CREATE TABLE IF NOT EXISTS usd_index (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    value DECIMAL(12, 6) NOT NULL,
    INDEX idx_timestamp (timestamp)
);

-- 汇率表
CREATE TABLE IF NOT EXISTS exchange_rates (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    from_currency VARCHAR(10) NOT NULL,
    to_currency VARCHAR(10) NOT NULL,
    rate DECIMAL(20, 6) NOT NULL,
    INDEX idx_timestamp (timestamp),
    INDEX idx_currency_pair (from_currency, to_currency)
);

-- 加密货币表
CREATE TABLE IF NOT EXISTS crypto_prices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    price_usd DECIMAL(20, 8) NOT NULL,
    market_cap_usd DECIMAL(20, 2),
    volume_24h_usd DECIMAL(20, 2),
    INDEX idx_timestamp (timestamp),
    INDEX idx_symbol (symbol)
);

-- 股票价格表
CREATE TABLE IF NOT EXISTS stock_prices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    market VARCHAR(10) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(20, 6) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    volume BIGINT,
    INDEX idx_timestamp (timestamp),
    INDEX idx_market_symbol (market, symbol)
); 