# trade_strategy.py
import sqlite3
import configparser
import logging
import os
import xtquant.xttrader as xttrader
import xtquant.xtdata as xtdata

# 读取配置文件
config = configparser.ConfigParser()
config.read('config.ini')

# 数据库路径
DB_PATH = config['database']['path']

# 交易参数
POSITION_SIZE = float(config['trade']['position_size'])
MAX_POSITION = float(config['trade']['max_position'])
STOP_LOSS = float(config['trade']['stop_loss'])
GRID_HEIGHT = [float(h) for h in config['trade']['grid_height'].split(',')]
GRID_TRADE_RATIO = float(config['trade']['grid_trade_ratio'])

# 日志配置
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
logging.basicConfig(filename=os.path.join(LOG_DIR, 'trade_strategy.log'), level=logging.INFO)

# 交易客户端
xt_trader = xttrader.XtTrader()

def get_position(stock_code):
    """
    获取持仓信息
    
    :param stock_code: 股票代码
    :return: 持仓信息字典
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT cost_price, quantity, max_price FROM positions WHERE stock_code = ?", (stock_code,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {'cost_price': row[0], 'quantity': row[1], 'max_price': row[2]}
        return None
    except Exception as e:
        logging.error(f"Error getting position for {stock_code}: {e}")
        raise

def calculate_stop_loss(position, current_price):
    """
    计算是否触发止损
    
    :param position: 持仓信息
    :param current_price: 当前价格
    :return: 是否止损
    """
    if position is None:
        return False
    cost_price = position['cost_price']
    loss_ratio = (current_price - cost_price) / cost_price
    return loss_ratio < STOP_LOSS

def calculate_dynamic_take_profit(position, current_price):
    """
    计算动态止盈位
    
    :param position: 持仓信息
    :param current_price: 当前价格
    :return: 止盈价格
    """
    if position is None:
        return None
    max_price = max(position['max_price'], current_price)
    cost_price = position['cost_price']
    profit_ratio = (max_price - cost_price) / cost_price
    if profit_ratio < 0.1:
        return max_price * 0.93
    elif profit_ratio < 0.15:
        return max_price * 0.90
    elif profit_ratio < 0.3:
        return max_price * 0.87
    return max_price * 0.85

def grid_trade(stock_code, current_price):
    """
    网格交易逻辑
    
    :param stock_code: 股票代码
    :param current_price: 当前价格
    """
    position = get_position(stock_code)
    if position is None:
        return
    quantity = position['quantity']
    trade_amount = int(quantity * GRID_TRADE_RATIO / 100) * 100
    for height in GRID_HEIGHT:
        buy_price = current_price * (1 - height)
        sell_price = current_price * (1 + height)
        xt_trader.buy(stock_code, buy_price, trade_amount, price_type=11)
        xt_trader.sell(stock_code, sell_price, trade_amount, price_type=11)
        logging.info(f"Grid trade placed for {stock_code}: buy at {buy_price}, sell at {sell_price}")

if __name__ == "__main__":
    stock_code = '600000.SH'
    current_price = xtdata.get_market_data_ex([stock_code], period='tick')['last'].iloc[-1]
    position = get_position(stock_code)
    if calculate_stop_loss(position, current_price):
        print("Trigger stop loss")
    take_profit = calculate_dynamic_take_profit(position, current_price)
    print(f"Take profit price: {take_profit}")
    grid_trade(stock_code, current_price)