FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    default-mysql-client \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 更新证书
RUN update-ca-certificates

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 复制项目文件
COPY requirements.txt .
COPY *.py .
COPY docker-entrypoint.sh /

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量默认值
ENV DB_HOST=localhost \
    DB_USER=root \
    DB_PASSWORD="" \
    DB_NAME=market_data \
    FETCH_INTERVAL=3600 \
    HISTORY_START_DATE="2017-07-01" \
    CURRENCIES='["CNH","CNY","HKD","JPY","KRW","SGD","RUB","TWD","AUD","GBP","EUR"]' \
    STOCKS='{"US":["^DJI","^GSPC","^IXIC"],"HK":["^HSI"],"CN":["000001.SS","399001.SZ"]}'

RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"] 