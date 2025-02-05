# Finance Monitor

实时监控汇率、股票指数等金融数据的工具。

## 功能

- 实时监控美元指数
- 监控多种货币汇率
- 监控主要股票指数
- 支持历史数据导入
- 支持自定义监控配置

## 快速开始

1. 创建配置文件：
```bash
cp .env.example .env
# 编辑 .env 文件设置您的配置
```

2. 运行服务：
```bash
docker run -d --env-file .env ghcr.io/rxrw/finance-monitor
```

## 配置说明

在 .env 文件中配置以下环境变量：

```env
# 数据库配置
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=market_data

# 数据采集间隔（秒）
FETCH_INTERVAL=3600

# 历史数据起始日期
HISTORY_START_DATE=2017-07-01

# 货币配置 (JSON格式)
CURRENCIES=["CNH","CNY","HKD","JPY","KRW","SGD","RUB","TWD","AUD","GBP","EUR"]

# 股票指数配置 (JSON格式)
STOCKS={"US":["^DJI","^GSPC","^IXIC"],"HK":["^HSI"],"CN":["000001.SS","399001.SZ"]}
```

## 数据库表结构

```sql
-- 美元指数表
CREATE TABLE usd_index (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    value DECIMAL(12, 6) NOT NULL,
    INDEX idx_timestamp (timestamp)
);

-- 汇率表
CREATE TABLE exchange_rates (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    from_currency VARCHAR(10) NOT NULL,
    to_currency VARCHAR(10) NOT NULL,
    rate DECIMAL(20, 6) NOT NULL,
    INDEX idx_timestamp (timestamp),
    INDEX idx_currency_pair (from_currency, to_currency)
);

-- 股票价格表
CREATE TABLE stock_prices (
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
```

## 历史数据导入

要仅导入历史数据：

```bash
docker run --rm --env-file .env ghcr.io/rxrw/finance-monitor historical
```

## 开发

1. 克隆仓库：
```bash
git clone https://github.com/rxrw/finance-monitor.git
cd finance-monitor
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 运行测试：
```bash
python -m pytest
```

## License

MIT 