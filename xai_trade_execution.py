# trade_execution.py
import xtquant.xttrader as xttrader
import xtquant.xtdata as xtdata
import sqlite3
import configparser
import logging
import os

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
logging.basicConfig(filename=os.path.join(LOG_DIR, 'trade_execution.log'), level=logging.INFO)

# 初始化交易客户端（需根据实际账户配置）
xt_trader = xttrader.XtTrader()

def check_account(stock_code):
    """检查账户余额和持仓"""
    account_info = xt_trader.query_account_info()
    positions = xt_trader.query_stock_positions()
    cash = account_info.get('AvailableCash', 0)
    current_position = sum(p['Volume'] for p in positions if p['StockCode'] == stock_code)
    return cash, current_position

def manual_buy(stock_code, price, amount):
    """
    手动买入
    
    :param stock_code: 股票代码
    :param price: 买入价格
    :param amount: 买入数量
    :return: 订单 ID
    """
    try:
        cash, current_position = check_account(stock_code)
        if cash < price * amount:
            raise ValueError("Insufficient cash")
        order_id = xt_trader.buy(stock_code, price, amount, price_type=11)  # 固定价格
        logging.info(f"Manual buy order placed: {order_id}")
        return order_id
    except Exception as e:
        logging.error(f"Error placing manual buy order: {e}")
        raise

def manual_sell(stock_code, price, amount):
    """
    手动卖出
    
    :param stock_code: 股票代码
    :param price: 卖出价格
    :param amount: 卖出数量
    :return: 订单 ID
    """
    try:
        _, current_position = check_account(stock_code)
        if current_position < amount:
            raise ValueError("Insufficient position")
        order_id = xt_trader.sell(stock_code, price, amount, price_type=11)
        logging.info(f"Manual sell order placed: {order_id}")
        return order_id
    except Exception as e:
        logging.error(f"Error placing manual sell order: {e}")
        raise

def cancel_order(order_id):
    """
    撤单
    
    :param order_id: 订单 ID
    """
    try:
        xt_trader.cancel_order(order_id)
        logging.info(f"Order cancelled: {order_id}")
    except Exception as e:
        logging.error(f"Error cancelling order: {e}")
        raise

def auto_trade(stock_code, signal):
    """
    根据交易信号自动执行交易
    
    :param stock_code: 股票代码
    :param signal: 交易信号（1: 买入，-1: 卖出）
    """
    try:
        current_price = xtdata.get_market_data_ex([stock_code], period='tick')['last'].iloc[-1]
        cash, current_position = check_account(stock_code)
        
        if signal == 1 and cash >= POSITION_SIZE:
            amount = int(POSITION_SIZE / current_price / 100) * 100  # 按手调整
            if current_position + amount <= MAX_POSITION:
                order_id = xt_trader.buy(stock_code, current_price, amount, price_type=11)
                logging.info(f"Auto buy order placed: {order_id}")
        elif signal == -1 and current_position > 0:
            amount = min(current_position, 100)  # 每次卖出100股
            order_id = xt_trader.sell(stock_code, current_price, amount, price_type=11)
            logging.info(f"Auto sell order placed: {order_id}")
    except Exception as e:
        logging.error(f"Error in auto trade: {e}")
        raise

if __name__ == "__main__":
    stock_code = '600000.SH'
    order_id = manual_buy(stock_code, 10.0, 100)
    print(f"Order ID: {order_id}")