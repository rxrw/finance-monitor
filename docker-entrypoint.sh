#!/bin/bash

# 等待MySQL就绪
until mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" &> /dev/null
do
    echo "Waiting for MySQL to be ready..."
    sleep 1
done

# 根据环境变量决定是否导入历史数据
if [ "$IMPORT_HISTORY" = "true" ]; then
    echo "Importing historical data..."
    python historical_data_importer.py
else
    echo "Skipping historical data import..."
fi

# 启动实时数据采集器
echo "Running real-time data collector..."
python market_data_collector.py 