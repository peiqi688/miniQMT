from easy_qmt_trader import easy_qmt_trader,MyXtQuantTraderCallback
from xtquant import xtdata
from xtquant import xtconstant
import time
import pandas as pd
import logging
import os

# Create the 'logs' directory if it doesn't exist
logs_dir = 'logs'
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# Set the log file path within the 'logs' directory
log_file_path = os.path.join(logs_dir, 'easy_qmt_trader_test.log')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file_path, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

#继承交易类
trader=easy_qmt_trader(path= r'd:/江海证券QMT实盘_交易/userdata_mini',
                account='80392832',account_type='STOCK',
                )
#连接qmt
trader.connect()
#账户信息
account=trader.balance()
logger.info(f"账户信息: \n{account}")
#持仓数量
position=trader.position()
logger.info(f"持仓信息: \n{position}")

test_stock = '513100.SH'

# 获取卖三价
try:
    ticks = xtdata.get_full_tick([test_stock])
    if ticks and test_stock in ticks:
        tick = ticks[test_stock]
        if hasattr(tick, 'askPrice') and len(tick.askPrice) >= 3:
            sell_price = tick.askPrice[2]
        elif hasattr(tick, 'askPrice') and len(tick.askPrice) >= 1:
            sell_price = tick.askPrice[0]
        elif isinstance(tick, dict) and 'askPrice' in tick and len(tick['askPrice']) >= 3:
            sell_price = tick['askPrice'][2]
        elif isinstance(tick, dict) and 'askPrice' in tick and len(tick['askPrice']) >= 1:
            sell_price = tick['askPrice'][0]
        else:
            sell_price = 1.644
            logger.warning(f"未获取到 {test_stock} 卖三价，使用默认卖三价: {sell_price}")
        logger.info(f"获取到 {test_stock} 卖三价: {sell_price}")
    else:
        sell_price = 1.644
        logger.warning(f"未获取到 {test_stock} 行情，使用默认卖三价: {sell_price}")
except Exception as e:
    sell_price = 1.644
    logger.error(f"获取 {test_stock} 行情失败: {str(e)}，使用默认卖三价: {sell_price}")

# 1. Place a Buy Order and Capture the Order ID
buy_order_id = trader.buy(security=test_stock, price=sell_price, amount=100, price_type=5, strategy_name='测试', order_remark='12212')

if buy_order_id:
    logger.info(f"Buy order placed successfully. Order ID: {buy_order_id}")
    
    # 等待回调函数返回订单编号
    time.sleep(2)
    
    # 获取qmt返回的订单编号
    buy_qmt_order_id = trader.order_id_map.get(buy_order_id)
    if buy_qmt_order_id:
        logger.info(f"Buy order qmt id: {buy_qmt_order_id}")
    else:
        logger.warning(f"未获取到买入委托的qmt订单编号")
        buy_qmt_order_id = None

    # 获取买三价
    try:
        ticks = xtdata.get_full_tick([test_stock])
        if ticks and test_stock in ticks:
            tick = ticks[test_stock]
            if hasattr(tick, 'bidPrice') and len(tick.bidPrice) >= 3:
                buy_price = tick.bidPrice[2]
            elif hasattr(tick, 'bidPrice') and len(tick.bidPrice) >= 1:
                buy_price = tick.bidPrice[0]
            elif isinstance(tick, dict) and 'bidPrice' in tick and len(tick['bidPrice']) >= 3:
                buy_price = tick['bidPrice'][2]
            elif isinstance(tick, dict) and 'bidPrice' in tick and len(tick['bidPrice']) >= 1:
                buy_price = tick['bidPrice'][0]
            else:
                buy_price = 1.644
                logger.warning(f"未获取到 {test_stock} 买三价，使用默认买三价: {buy_price}")
            logger.info(f"获取到 {test_stock} 买三价: {buy_price}")
        else:
            buy_price = 1.644
            logger.warning(f"未获取到 {test_stock} 行情，使用默认买三价: {buy_price}")
    except Exception as e:
        buy_price = 1.644
        logger.error(f"获取 {test_stock} 行情失败: {str(e)}，使用默认买三价: {buy_price}")

    # 2. Place a Sell Order and Capture the Order ID
    sell_order_id = trader.sell(security=test_stock, price=buy_price, amount=100, price_type=5, strategy_name='测试', order_remark='12212')
    if sell_order_id:
        logger.info(f"Sell order placed successfully. Order ID: {sell_order_id}")
        
        # 等待回调函数返回订单编号
        time.sleep(2)
        
        # 获取qmt返回的订单编号
        sell_qmt_order_id = trader.order_id_map.get(sell_order_id)
        if sell_qmt_order_id:
            logger.info(f"Sell order qmt id: {sell_qmt_order_id}")
        else:
            logger.warning(f"未获取到卖出委托的qmt订单编号")
            sell_qmt_order_id = None
        
        # 3. Wait for a short time (for demonstration purposes)
        time.sleep(2)  # In a real application, you'd use callbacks instead of waiting

        # 4. Cancel the Buy Order
        if buy_qmt_order_id:
            cancel_result = trader.cancel_order_stock_async(order_id=buy_qmt_order_id)
            if cancel_result:
                logger.info(f"Cancel request sent for buy order {buy_qmt_order_id}. Result: {cancel_result}")
            else:
                logger.warning(f"Failed to send cancel request for buy order {buy_qmt_order_id}")
        else:
            logger.warning(f"无法撤销买入委托，未获取到qmt订单编号")
        
        # 5. Cancel the Sell Order
        if sell_qmt_order_id:
            cancel_result = trader.cancel_order_stock_async(order_id=sell_qmt_order_id)
            if cancel_result:
                logger.info(f"Cancel request sent for sell order {sell_qmt_order_id}. Result: {cancel_result}")
            else:
                logger.warning(f"Failed to send cancel request for sell order {sell_qmt_order_id}")
        else:
            logger.warning(f"无法撤销卖出委托，未获取到qmt订单编号")

        # 6. Check the order status
        df_entrusts = trader.today_entrusts()
        logger.info(f"委托信息: \n{df_entrusts}")
        
        # 7. Check the deal status
        df_trades = trader.today_trades()
        logger.info(f"成交信息: \n{df_trades}")
        
        # 打印成交记录
        if not df_trades.empty:
            logger.info(f"成交记录:")
            for index, row in df_trades.iterrows():
                logger.info(f"  成交编号: {row['成交编号']}, 订单编号: {row['订单编号']}, 证券代码: {row['证券代码']}, 成交价格: {row['成交均价']}, 成交数量: {row['成交数量']}, 成交时间: {row['成交时间']}")
        else:
            logger.info("  没有成交记录")
        
        # 8. Get the latest order id and cancel it
        if not df_entrusts.empty:
            latest_order_id = df_entrusts['订单编号'].iloc[-1]  # 获取最后一行的'订单编号'
            logger.info(f"最新一条订单记录的编号是：{latest_order_id}")
            #撤单
            cancel_result = trader.cancel_order_stock_async(order_id=latest_order_id)
            if cancel_result:
                logger.info(f"Cancel request sent for order {latest_order_id}. Result: {cancel_result}")
            else:
                logger.warning(f"Failed to send cancel request for order {latest_order_id}")
        else:
            logger.info("当天没有委托记录，无法撤单")
    else:
        logger.warning("Failed to place sell order.")
else:
    logger.warning("Failed to place buy order.")
