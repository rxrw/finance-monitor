#!/bin/bash

# 等待MySQL就绪
until mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" &> /dev/null
do
    echo "Waiting for MySQL to be ready..."
    sleep 1
done

# 导入历史数据
echo "Importing historical data..."
python historical_data_importer.py

# 如果是实时采集模式，则启动采集器
if [ "$1" != "historical" ]; then
    echo "Running real-time data collector..."
    python market_data_collector.py
fi 