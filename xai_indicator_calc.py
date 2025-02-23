# indicator_calc.py
import pandas as pd
import sqlite3
import xtquant.xtdata as xtdata
import configparser
import logging
import os

# 读取配置文件
config = configparser.ConfigParser()
config.read('config.ini')

# 数据库路径
DB_PATH = config['database']['path']

# 指标参数
MACD_FAST = int(config['indicators']['macd.fast_period'])
MACD_SLOW = int(config['indicators']['macd.slow_period'])
MACD_SIGNAL = int(config['indicators']['macd.signal_period'])
MA_PERIODS = [int(p) for p in config['indicators']['ma.periods'].split(',')]

# 日志配置
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
logging.basicConfig(filename=os.path.join(LOG_DIR, 'indicator_calc.log'), level=logging.INFO)

def calculate_indicators(stock_code):
    """
    计算指定股票的技术指标。
    
    :param stock_code: 股票代码
    :return: DataFrame 包含指标数据
    """
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        query = f"SELECT date, close, volume FROM historical_data WHERE stock_code = '{stock_code}' ORDER BY date"
        df = pd.read_sql_query(query, conn, parse_dates=['date'])
        conn.close()
        
        if df.empty:
            raise ValueError(f"No data available for {stock_code}")
        
        # 计算 MACD
        df['ema_fast'] = df['close'].ewm(span=MACD_FAST, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=MACD_SLOW, adjust=False).mean()
        df['dif'] = df['ema_fast'] - df['ema_slow']
        df['dea'] = df['dif'].ewm(span=MACD_SIGNAL, adjust=False).mean()
        df['macd'] = df['dif'] - df['dea']
        
        # 获取流通股本并计算换手率
        instrument_detail = xtdata.get_instrument_detail(stock_code)
        circulating_shares = instrument_detail.get('TotalShares', 1e8)  # 默认值1亿股
        df['turnover'] = df['volume'] / circulating_shares
        
        # 计算均线
        for period in MA_PERIODS:
            df[f'ma_{period}'] = df['close'].rolling(window=period).mean()
        
        logging.info(f"Successfully calculated indicators for {stock_code}")
        return df
    except Exception as e:
        logging.error(f"Error calculating indicators for {stock_code}: {e}")
        raise

def generate_trade_signal(df, weights):
    """
    根据指标生成交易信号。
    
    :param df: DataFrame 包含指标数据
    :param weights: 字典，指标权重
    :return: 交易信号（1: 买入，-1: 卖出，0: 持有）
    """
    try:
        # 计算综合得分
        latest = df.iloc[-1]
        ma_signals = sum(weights[f'ma_{period}'] * (latest['close'] > latest[f'ma_{period}']) for period in MA_PERIODS)
        score = (
            weights['macd'] * latest['macd'] +
            weights['turnover'] * latest['turnover'] +
            ma_signals
        )
        if score > 0.8:
            return 1  # 买入
        elif score < -0.8:
            return -1  # 卖出
        else:
            return 0  # 持有
    except Exception as e:
        logging.error(f"Error generating trade signal: {e}")
        raise

if __name__ == "__main__":
    stock_code = '600000.SH'
    df = calculate_indicators(stock_code)
    weights = {
        'macd': 0.4,
        'turnover': 0.2,
        'ma_10': 0.1,
        'ma_20': 0.1,
        'ma_30': 0.1,
        'ma_60': 0.1
    }
    signal = generate_trade_signal(df, weights)
    print(f"Trade signal: {signal}")