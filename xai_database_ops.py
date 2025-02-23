# database_ops.py
import sqlite3
import configparser
import logging
import os

# 读取配置文件
config = configparser.ConfigParser()
config.read('config.ini')

# 数据库路径
DB_PATH = config['database']['path']

# 日志配置
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
logging.basicConfig(filename=os.path.join(LOG_DIR, 'database_ops.log'), level=logging.INFO)

def init_database():
    """
    初始化数据库，创建表
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 创建交易记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_records (
                trade_id TEXT PRIMARY KEY,
                date TEXT,
                stock_code TEXT,
                direction TEXT,
                price REAL,
                volume INTEGER,
                amount REAL
            )
        ''')
        
        # 创建持仓表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                stock_code TEXT PRIMARY KEY,
                cost_price REAL,
                quantity INTEGER,
                max_price REAL
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        raise

def record_trade(trade_id, date, stock_code, direction, price, volume, amount):
    """
    记录交易信息
    
    :param trade_id: 交易 ID
    :param date: 交易日期
    :param stock_code: 股票代码
    :param direction: 买卖方向 ('buy' 或 'sell')
    :param price: 成交价格
    :param volume: 成交数量
    :param amount: 成交金额
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trade_records (trade_id, date, stock_code, direction, price, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (trade_id, date, stock_code, direction, price, volume, amount))
        conn.commit()
        conn.close()
        logging.info(f"Trade recorded: {trade_id}")
    except Exception as e:
        logging.error(f"Error recording trade: {e}")
        raise

def update_position(stock_code, cost_price, quantity, max_price):
    """
    更新持仓信息
    
    :param stock_code: 股票代码
    :param cost_price: 持仓成本价
    :param quantity: 持仓数量
    :param max_price: 历史最高价
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO positions (stock_code, cost_price, quantity, max_price)
            VALUES (?, ?, ?, ?)
        ''', (stock_code, cost_price, quantity, max_price))
        conn.commit()
        conn.close()
        logging.info(f"Position updated for {stock_code}")
    except Exception as e:
        logging.error(f"Error updating position: {e}")
        raise

if __name__ == "__main__":
    init_database()
    record_trade('123456', '2023-01-01', '600000.SH', 'buy', 10.0, 100, 1000.0)
    update_position('600000.SH', 10.0, 100, 10.5)