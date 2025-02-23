# data_fetch.py
import sqlite3
import xtquant.xtdata as xtdata  # 迅投MiniQMT的数据获取模块
import configparser
import logging
import os
from datetime import datetime, timedelta

# 读取配置文件
config = configparser.ConfigParser()
config.read('config.ini')

# 数据库路径
DB_PATH = config['database']['path']

# 数据时间范围
TIME_RANGE = config['data']['time_range']  # 例如 '1_year'

# 日志配置
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
logging.basicConfig(filename=os.path.join(LOG_DIR, 'data_fetch.log'), level=logging.INFO)

def fetch_and_store_data(stock_code):
    """
    获取指定股票的历史数据并存储到数据库中。
    
    :param stock_code: 股票代码（如 '600000.SH'）
    """
    try:
        # 根据TIME_RANGE计算开始时间
        if TIME_RANGE == '1_year':
            start_time = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        elif TIME_RANGE == '6_months':
            start_time = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d')
        else:
            start_time = '19700101'  # 默认从最早时间开始

        # 获取历史数据
        data = xtdata.get_market_data_ex(
            stock_list=[stock_code],
            period='1d',  # 日K线
            start_time=start_time,
            end_time=datetime.now().strftime('%Y%m%d')
        )

        # 检查数据是否为空
        if data.empty:
            logging.warning(f"No data fetched for {stock_code}")
            return

        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 创建表（如果不存在）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historical_data (
                date TEXT,
                stock_code TEXT,
                open REAL,
                close REAL,
                high REAL,
                low REAL,
                volume INTEGER,
                PRIMARY KEY (date, stock_code)
            )
        ''')
        
        # 插入数据
        for index, row in data.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO historical_data (date, stock_code, open, close, high, low, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (index.strftime('%Y-%m-%d'), stock_code, row['open'], row['close'], row['high'], row['low'], int(row['volume'])))
        
        conn.commit()
        conn.close()
        logging.info(f"Successfully fetched and stored data for {stock_code}")
    except Exception as e:
        logging.error(f"Error fetching data for {stock_code}: {e}")
        raise

if __name__ == "__main__":
    stock_code = '600000.SH'  # 示例股票代码
    fetch_and_store_data(stock_code)