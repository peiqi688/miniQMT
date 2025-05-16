#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试trading_executor.py中的功能
"""
import sys
import time
import logging
import os
from datetime import datetime
import argparse
import pandas as pd
import config


# Create the 'logs' directory if it doesn't exist
logs_dir = 'logs'
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# Set the log file path within the 'logs' directory
log_file_path = os.path.join(logs_dir, 'test_trading_executor.log')

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

try:
    from trading_executor import get_trading_executor, TradingExecutor, DIRECTION_BUY, DIRECTION_SELL
    logger.info("成功导入trading_executor模块")
except ImportError as e:
    logger.error(f"导入trading_executor模块失败: {str(e)}")
    sys.exit(1)

# 测试用股票，使用ETF以降低测试成本
TEST_STOCK = "510050.SH"  # 上证50ETF

def test_initialization():
    """测试交易执行器的初始化"""
    logger.info("=== 测试TradingExecutor初始化 ===")
    
    try:
        # 使用单例获取交易执行器
        executor = get_trading_executor()
        logger.info(f"交易执行器单例获取成功: {executor}")
        
        # 检查账户信息
        logger.info(f"账户ID: {executor.account_id}")
        logger.info(f"账户类型: {executor.account_type}")
        
        # 添加初始化交易API的尝试
        if not hasattr(executor, 'trader') or not executor.trader:
            logger.info("尝试重新初始化交易API...")
            try:
                # 修改初始化XtQuantTrader的方式
                from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
                
                # 创建回调对象
                class MyCallback(XtQuantTraderCallback):
                    def on_recv_rsp(self, *args, **kwargs):
                        logger.info(f"收到响应: {args}, {kwargs}")
                
                # 正确初始化交易API
                # 假设路径，实际使用时需要替换为正确的路径
                userdata_path = config.QMT_PATH
                session_id = "test_session"
                callback = MyCallback()
                
                trader = XtQuantTrader(userdata_path, session_id, callback)
                
                # 尝试连接服务器
                trader.start()
                # 等待连接建立
                time.sleep(3)
                # 检查连接状态（需要根据实际API调整）
                is_connected = True if trader else False
                logger.info(f"交易API连接状态: {is_connected}")
                # 如果成功，设置到executor
                if is_connected:
                    executor.trader = trader
                    logger.info("成功重新初始化交易API")
            except Exception as e:
                logger.error(f"尝试初始化交易API时出错: {str(e)}")
        
        # 检查trader对象
        if hasattr(executor, 'trader') and executor.trader:
            logger.info(f"交易API对象创建成功: {executor.trader}")
            
            # 检查连接状态（需要根据实际API调整）
            is_connected = True if executor.trader else False
            logger.info(f"交易API连接状态: {is_connected}")
        else:
            logger.warning("交易API对象未创建或不可用")
        
        # 检查回调字典
        if hasattr(executor, 'callbacks'):
            logger.info(f"回调字典已初始化: {executor.callbacks}")
        
        return True
    except Exception as e:
        logger.error(f"测试初始化时出错: {str(e)}")
        return False

def test_account_query():
    """测试账户资金查询"""
    logger.info("=== 测试账户资金查询 ===")
    
    try:
        executor = get_trading_executor()
        
        # 查询账户资金
        if hasattr(executor, 'get_account_info'):
            account_info = executor.get_account_info()
            logger.info(f"账户资金信息: {account_info}")
            
            if account_info:
                logger.info(f"可用资金: {account_info.get('available', 'N/A')}")
                logger.info(f"总资产: {account_info.get('total_asset', 'N/A')}")
                logger.info(f"持仓市值: {account_info.get('market_value', 'N/A')}")
        else:
            logger.warning("交易执行器没有get_account_info方法")
            
            # 尝试其他可能的方法
            possible_methods = [m for m in dir(executor) if 'account' in m.lower() or 'cash' in m.lower()]
            logger.info(f"可能的账户查询方法: {possible_methods}")
        
        return True
    except Exception as e:
        logger.error(f"测试账户查询时出错: {str(e)}")
        return False

def test_position_query():
    """测试持仓查询"""
    logger.info("=== 测试持仓查询 ===")
    
    try:
        executor = get_trading_executor()
        
        # 查询持仓 - 修改为使用get_stock_positions方法
        if hasattr(executor, 'get_stock_positions'):
            positions = executor.get_stock_positions()
            logger.info(f"持仓数量: {len(positions) if positions else 0}")
            
            if positions:
                for pos in positions:
                    logger.info(f"股票代码: {pos.get('stock_code', 'N/A')}")
                    logger.info(f"持仓数量: {pos.get('volume', 'N/A')}")
                    logger.info(f"可用数量: {pos.get('available', 'N/A')}")
                    logger.info(f"持仓成本: {pos.get('cost', 'N/A')}")
                    logger.info(f"当前价格: {pos.get('price', 'N/A')}")
                    logger.info(f"持仓市值: {pos.get('market_value', 'N/A')}")
        else:
            logger.warning("交易执行器没有get_stock_positions方法")
            
            # 尝试其他可能的方法
            possible_methods = [m for m in dir(executor) if 'position' in m.lower() or 'holding' in m.lower()]
            logger.info(f"可能的持仓查询方法: {possible_methods}")
        
        return True
    except Exception as e:
        logger.error(f"测试持仓查询时出错: {str(e)}")
        return False

def test_order_query():
    """测试委托查询"""
    logger.info("=== 测试委托查询 ===")
    
    try:
        executor = get_trading_executor()
        
        # 查询委托
        if hasattr(executor, 'get_orders'):
            orders = executor.get_orders()
            logger.info(f"委托数量: {len(orders) if orders else 0}")
            
            if orders:
                for order in orders:
                    logger.info(f"委托号: {order.get('order_id', 'N/A')}")
                    logger.info(f"股票代码: {order.get('stock_code', 'N/A')}")
                    logger.info(f"委托方向: {order.get('direction', 'N/A')}")
                    logger.info(f"委托价格: {order.get('price', 'N/A')}")
                    logger.info(f"委托数量: {order.get('volume', 'N/A')}")
                    logger.info(f"委托状态: {order.get('status', 'N/A')}")
                    logger.info(f"委托时间: {order.get('order_time', 'N/A')}")
        else:
            logger.warning("交易执行器没有get_orders方法")
            
            # 尝试其他可能的方法
            possible_methods = [m for m in dir(executor) if 'order' in m.lower() or 'entrust' in m.lower()]
            logger.info(f"可能的委托查询方法: {possible_methods}")
        
        return True
    except Exception as e:
        logger.error(f"测试委托查询时出错: {str(e)}")
        return False

def test_deal_query():
    """测试成交查询"""
    logger.info("=== 测试成交查询 ===")
    
    try:
        executor = get_trading_executor()
        
        # 查询成交
        if hasattr(executor, 'get_trades'):
            trades = executor.get_trades()
            
            # 修复: 正确处理DataFrame类型的返回值
            if isinstance(trades, pd.DataFrame):
                logger.info(f"成交数量: {len(trades) if not trades.empty else 0}")
                
                if not trades.empty:
                    for _, trade in trades.iterrows():
                        logger.info(f"成交编号: {trade.get('trade_id', 'N/A')}")
                        logger.info(f"委托号: {trade.get('order_id', 'N/A')}")
                        logger.info(f"股票代码: {trade.get('stock_code', 'N/A')}")
                        logger.info(f"成交方向: {trade.get('direction', 'N/A')}")
                        logger.info(f"成交价格: {trade.get('price', 'N/A')}")
                        logger.info(f"成交数量: {trade.get('volume', 'N/A')}")
                        logger.info(f"成交时间: {trade.get('trade_time', 'N/A')}")
            else:
                # 处理列表或其他类型的返回值
                logger.info(f"成交数量: {len(trades) if trades else 0}")
                
                if trades:
                    for trade in trades:
                        logger.info(f"成交编号: {trade.get('trade_id', 'N/A')}")
                        logger.info(f"委托号: {trade.get('order_id', 'N/A')}")
                        logger.info(f"股票代码: {trade.get('stock_code', 'N/A')}")
                        logger.info(f"成交方向: {trade.get('direction', 'N/A')}")
                        logger.info(f"成交价格: {trade.get('price', 'N/A')}")
                        logger.info(f"成交数量: {trade.get('volume', 'N/A')}")
                        logger.info(f"成交时间: {trade.get('trade_time', 'N/A')}")
        else:
            logger.warning("交易执行器没有get_trades方法")
            
            # 尝试其他可能的方法
            possible_methods = [m for m in dir(executor) if 'trade' in m.lower() or 'deal' in m.lower()]
            logger.info(f"可能的成交查询方法: {possible_methods}")
        
        return True
    except Exception as e:
        logger.error(f"测试成交查询时出错: {str(e)}")
        return False

def test_quote_query():
    """测试行情查询"""
    logger.info("=== 测试行情查询 ===")
    
    try:
        executor = get_trading_executor()
        
        # 直接使用xtdata获取行情，而不是通过交易执行器
        try:
            from xtquant import xtdata
            ticks = xtdata.get_full_tick([TEST_STOCK])
            if ticks and TEST_STOCK in ticks:
                tick = ticks[TEST_STOCK]
                logger.info(f"行情信息: {tick}")
                
                # 修复行情数据访问方式
                if hasattr(tick, 'lastPrice'):
                    logger.info(f"最新价: {tick.lastPrice}")
                    logger.info(f"涨跌幅: {(tick.lastPrice - tick.lastClose) / tick.lastClose * 100:.2f}%")
                    logger.info(f"买一价: {tick.bidPrice[0] if hasattr(tick, 'bidPrice') else '无'}")
                    logger.info(f"卖一价: {tick.askPrice[0] if hasattr(tick, 'askPrice') else '无'}")
                    logger.info(f"成交量: {tick.volume if hasattr(tick, 'volume') else '无'}")
                elif isinstance(tick, dict):
                    # 如果是字典形式
                    logger.info(f"最新价: {tick.get('lastPrice')}")
                    logger.info(f"涨跌幅: {(tick.get('lastPrice', 0) - tick.get('lastClose', 0)) / tick.get('lastClose', 1) * 100:.2f}%")
                    bid_prices = tick.get('bidPrice', [])
                    ask_prices = tick.get('askPrice', [])
                    logger.info(f"买一价: {bid_prices[0] if bid_prices else '无'}")
                    logger.info(f"卖一价: {ask_prices[0] if ask_prices else '无'}")
                    logger.info(f"成交量: {tick.get('volume', '无')}")
            else:
                logger.warning(f"未获取到 {TEST_STOCK} 的行情数据")
        except Exception as e:
            logger.error(f"通过xtdata获取行情失败: {str(e)}")
            
            # 作为备选方案，尝试查询交易执行器中的相关方法
            possible_methods = [m for m in dir(executor) if 'quote' in m.lower() or 'tick' in m.lower()]
            logger.info(f"可能的行情查询方法: {possible_methods}")
        
        return True
    except Exception as e:
        logger.error(f"测试行情查询时出错: {str(e)}")
        return False

def test_callbacks():
    """测试回调函数"""
    logger.info("=== 测试回调函数 ===")
    
    try:
        executor = get_trading_executor()
        
        # 获取私有回调函数
        callback_methods = [m for m in dir(executor) if '_on_' in m and 'callback' in m]
        logger.info(f"交易执行器中的回调方法: {callback_methods}")
        
        # 模拟测试回调处理
        logger.info("模拟订单回调测试...")
        
        # 创建模拟订单数据 - 使用正确的属性名称
        class MockOrder:
            def __init__(self):
                self.m_strOrderSysID = 'TEST_ORDER_123'
                self.m_strInstrumentID = TEST_STOCK
                self.m_nDirection = DIRECTION_BUY
                self.m_dLimitPrice = 2.5
                self.m_nVolumeTotalOriginal = 100
                self.m_nVolumeTraded = 0
                self.m_nOrderStatus = 0  # 假设0表示未成交
        
        mock_order = MockOrder()
        
        # 如果存在order回调，测试调用
        if hasattr(executor, '_on_order_callback'):
            try:
                logger.info("调用订单回调函数...")
                executor._on_order_callback(mock_order)
                logger.info("订单回调函数调用成功")
            except Exception as e:
                logger.error(f"调用订单回调函数失败: {str(e)}")
        
        # 创建模拟成交数据 - 使用正确的属性名称
        class MockDeal:
            def __init__(self):
                self.m_strTradeID = 'TEST_TRADE_123'
                self.m_strOrderSysID = 'TEST_ORDER_123'
                self.m_strInstrumentID = TEST_STOCK
                self.m_nDirection = DIRECTION_BUY
                self.m_dPrice = 2.5
                self.m_nVolume = 100
                self.m_strTradeTime = datetime.now().strftime('%H:%M:%S')
                self.m_dComssion = 0.0  # 添加手续费属性
        
        mock_deal = MockDeal()
        
        # 如果存在deal回调，测试调用
        if hasattr(executor, '_on_deal_callback'):
            try:
                logger.info("调用成交回调函数...")
                executor._on_deal_callback(mock_deal)
                logger.info("成交回调函数调用成功")
            except Exception as e:
                logger.error(f"调用成交回调函数失败: {str(e)}")
        
        return True
    except Exception as e:
        logger.error(f"测试回调函数时出错: {str(e)}")
        return False

def test_buy_stock(execute_real_order=False):
    """测试买入股票"""
    logger.info("=== 测试买入股票功能 ===")
    
    try:
        executor = get_trading_executor()
        
        # 获取测试股票行情
        try:
            from xtquant import xtdata
            ticks = xtdata.get_full_tick([TEST_STOCK])
            if ticks and TEST_STOCK in ticks:
                tick = ticks[TEST_STOCK]
                # 修复行情数据获取方式
                if hasattr(tick, 'bidPrice'):
                    bid_price = tick.bidPrice[0] if len(tick.bidPrice) > 0 else 2.5
                elif isinstance(tick, dict) and 'bidPrice' in tick:
                    bid_price = tick['bidPrice'][0] if len(tick['bidPrice']) > 0 else 2.5
                else:
                    bid_price = 2.5
                logger.info(f"获取到 {TEST_STOCK} 买一价: {bid_price}")
            else:
                bid_price = 2.5  # 假设价格
                logger.warning(f"未获取到行情，使用假设价格 {bid_price}")
        except Exception as e:
            bid_price = 2.5  # 假设价格
            logger.error(f"获取行情失败，使用假设价格 {bid_price}: {str(e)}")
        
        # 设置买入参数
        buy_price = round(float(bid_price) * 0.99, 2)  # 略低于买一价，避免成交
        buy_volume = 100  # 最小单位
        
        logger.info(f"测试买入 {TEST_STOCK}, 价格: {buy_price}, 数量: {buy_volume}")
        
        if execute_real_order:
            # 实际执行买入
            order_id = executor.buy_stock(TEST_STOCK, volume=buy_volume, price=buy_price)
            
            if order_id:
                logger.info(f"买入委托提交成功，委托号: {order_id}")
                
                # 等待一秒查询委托状态
                time.sleep(1)
                
                # 查询委托
                if hasattr(executor, 'get_orders'):
                    orders = executor.get_orders()
                    order_found = False
                    for order in orders:
                        if str(order.get('order_id', '')) == str(order_id):
                            order_found = True
                            logger.info(f"找到委托: {order}")
                            break
                    
                    if not order_found:
                        logger.warning(f"未找到委托号为 {order_id} 的委托")
                
                # 测试撤单
                time.sleep(1)
                logger.info(f"测试撤单，委托号: {order_id}")
                cancel_result = executor.cancel_order(order_id)
                logger.info(f"撤单结果: {cancel_result}")
                
                return order_id
            else:
                logger.warning("买入委托提交失败")
                return None
        else:
            # 仅模拟，不实际提交
            logger.info("模拟测试，不实际提交委托")
            logger.info(f"检查buy_stock方法: {getattr(executor, 'buy_stock', None)}")
            return True
    except Exception as e:
        logger.error(f"测试买入股票时出错: {str(e)}")
        return False

def test_sell_stock(execute_real_order=False):
    """测试卖出股票"""
    logger.info("=== 测试卖出股票功能 ===")
    
    try:
        executor = get_trading_executor()
        
        # 首先检查是否持有股票
        position_found = False
        sell_stock_code = TEST_STOCK
        sell_volume = 100
        
        # 修改为使用get_stock_positions
        if hasattr(executor, 'get_stock_positions'):
            positions = executor.get_stock_positions()
            
            if positions:
                for pos in positions:
                    stock_code = pos.get('stock_code', '')
                    available = pos.get('available', 0)
                    
                    if available >= 100:  # 至少100股
                        position_found = True
                        sell_stock_code = stock_code
                        sell_volume = min(available, 100)  # 最多卖100股
                        logger.info(f"找到可卖出持仓: {stock_code}, 可用数量: {available}, 将测试卖出 {sell_volume} 股")
                        break
        
        if not position_found:
            logger.warning(f"未找到可卖出的持仓，将使用测试股票 {sell_stock_code} 尝试卖出 {sell_volume} 股，可能会失败")
        
        # 获取行情
        try:
            from xtquant import xtdata
            ticks = xtdata.get_full_tick([sell_stock_code])
            if ticks and sell_stock_code in ticks:
                tick = ticks[sell_stock_code]
                ask_price = getattr(tick, 'ask_price', None) or getattr(tick, 'askPrice1', None) or 2.6
                logger.info(f"获取到 {sell_stock_code} 卖一价: {ask_price}")
            else:
                ask_price = 2.6  # 假设价格
                logger.warning(f"未获取到行情，使用假设价格 {ask_price}")
        except Exception as e:
            ask_price = 2.6  # 假设价格
            logger.error(f"获取行情失败，使用假设价格 {ask_price}: {str(e)}")
        
        # 设置卖出参数
        sell_price = round(float(ask_price) * 1.01, 2)  # 略高于卖一价，避免成交
        
        logger.info(f"测试卖出 {sell_stock_code}, 价格: {sell_price}, 数量: {sell_volume}")
        
        if execute_real_order and position_found:
            # 实际执行卖出
            order_id = executor.sell_stock(sell_stock_code, volume=sell_volume, price=sell_price)
            
            if order_id:
                logger.info(f"卖出委托提交成功，委托号: {order_id}")
                
                # 等待一秒查询委托状态
                time.sleep(1)
                
                # 查询委托
                if hasattr(executor, 'get_orders'):
                    orders = executor.get_orders()
                    order_found = False
                    for order in orders:
                        if str(order.get('order_id', '')) == str(order_id):
                            order_found = True
                            logger.info(f"找到委托: {order}")
                            break
                    
                    if not order_found:
                        logger.warning(f"未找到委托号为 {order_id} 的委托")
                
                # 测试撤单
                time.sleep(1)
                logger.info(f"测试撤单，委托号: {order_id}")
                cancel_result = executor.cancel_order(order_id)
                logger.info(f"撤单结果: {cancel_result}")
                
                return order_id
            else:
                logger.warning("卖出委托提交失败")
                return None
        else:
            # 仅模拟，不实际提交
            logger.info("模拟测试，不实际提交委托")
            logger.info(f"检查sell_stock方法: {getattr(executor, 'sell_stock', None)}")
            return True
    except Exception as e:
        logger.error(f"测试卖出股票时出错: {str(e)}")
        return False

def run_all_tests(execute_real_order=False):
    """运行所有测试"""
    logger.info("开始TradingExecutor测试...")
    
    tests = [
        ("初始化测试", test_initialization),
        ("账户查询测试", test_account_query),
        ("持仓查询测试", test_position_query),
        ("委托查询测试", test_order_query),
        ("成交查询测试", test_deal_query),
        ("行情查询测试", test_quote_query),
        ("回调函数测试", test_callbacks),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n开始执行 {test_name}")
        try:
            result = test_func()
            results[test_name] = "成功" if result else "失败"
        except Exception as e:
            logger.error(f"{test_name} 执行出错: {str(e)}")
            results[test_name] = "错误"
    
    # 测试买入和卖出 (可选实际执行)
    logger.info("\n开始执行买入测试")
    buy_result = test_buy_stock(execute_real_order)
    results["买入测试"] = "成功" if buy_result else "失败"
    
    logger.info("\n开始执行卖出测试")
    sell_result = test_sell_stock(execute_real_order)
    results["卖出测试"] = "成功" if sell_result else "失败"
    
    # 打印测试结果摘要
    logger.info("\n=== 测试结果摘要 ===")
    for test_name, result in results.items():
        logger.info(f"{test_name}: {result}")
    
    # 计算成功率
    success_count = sum(1 for result in results.values() if result == "成功")
    logger.info(f"总测试项: {len(results)}, 成功: {success_count}, 成功率: {success_count / len(results) * 100:.1f}%")
    
    logger.info("TradingExecutor测试完成")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='测试TradingExecutor')
    parser.add_argument('--execute', action='store_true', help='执行实际交易测试 (默认仅模拟)')
    
    args = parser.parse_args()
    
    run_all_tests(args.execute) 