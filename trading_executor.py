"""
交易执行模块，负责执行交易指令
"""
import time
from datetime import datetime
import threading
import pandas as pd
import numpy as np
import sqlite3
from xtquant import xtdata as xt
from xtquant import xttrader as xtt

import config
from logger import get_logger
from data_manager import get_data_manager
from position_manager import get_position_manager

# 获取logger
logger = get_logger("trading_executor")

# 常量定义，替代枚举类型
DIRECTION_BUY = 48   # 买入方向
DIRECTION_SELL = 49  # 卖出方向

class TradingExecutor:
    """交易执行类，负责执行交易指令"""
    
    def __init__(self):
        """初始化交易执行器"""
        self.data_manager = get_data_manager()
        self.position_manager = get_position_manager()
        self.conn = self.data_manager.conn
        
        # 交易API客户端
        self.trader = None
        
        # 初始化迅投交易API
        self._init_xttrader()
        
        # 回调字典，用于存储订单状态变化回调
        self.callbacks = {}
        
        # 委托记录缓存
        self.order_cache = {}
        
        # 交易锁，防止并发交易
        self.trade_lock = threading.Lock()
        
        # 模拟交易订单ID计数器
        self.sim_order_counter = 0
    
    def _init_xttrader(self):
        """初始化迅投交易API"""
        try:
            # 从配置获取账户信息
            account_config = config.get_account_config()
            self.account_id = account_config.get('account_id', '')
            self.account_type = account_config.get('account_type', 'STOCK')
            
            if not self.account_id:
                logger.warning("未配置交易账户ID，交易功能将不可用")
                return
            
            # 打印可用的交易API方法，便于调试
            # logger.info(f"xtquant.xttrader支持的方法: {[f for f in dir(xtt) if not f.startswith('_')]}")
            
            # 检查可能的交易API初始化方法
            if hasattr(xtt, 'create_trader'):
                # 尝试创建交易API客户端
                self.trader = xtt.create_trader()
                logger.info("使用create_trader()创建交易API客户端")
                
                # 登录账户
                result = self.trader.login(self.account_id, self.account_type)
                logger.info(f"登录账户结果: {result}")
                
                # 等待账户连接
                is_connected = False
                for _ in range(5):
                    if hasattr(self.trader, 'is_connected') and self.trader.is_connected():
                        is_connected = True
                        logger.info(f"交易账户 {self.account_id} 连接成功")
                        break
                    time.sleep(1)
                
                if not is_connected:
                    logger.warning(f"交易账户 {self.account_id} 连接状态未确认")

            elif hasattr(xtt, 'connect'):
                # 尝试直接连接
                result = xtt.connect()
                logger.info(f"使用connect()连接交易API，结果: {result}")
                
                # 添加账户
                if hasattr(xtt, 'add_account'):
                    result = xtt.add_account(self.account_type, self.account_id)
                    logger.info(f"添加账户结果: {result}")
                    
                    # 注册回调函数
                    self._register_callbacks()
                    
            else:
                # 尝试其他可能的初始化方法
                init_methods = [m for m in dir(xtt) if m.lower() in ["start", "initialize", "login"]]
                
                if init_methods:
                    logger.info(f"找到可能的初始化方法: {init_methods}")
                    # 尝试第一个可能的方法
                    method_name = init_methods[0]
                    init_method = getattr(xtt, method_name)
                    
                    if method_name.lower() == "start":
                        # start方法可能不需要参数
                        result = init_method()
                        logger.info(f"调用 {method_name} 方法初始化交易API，结果: {result}")
                        
                        # 尝试添加账户
                        if hasattr(xtt, 'add_account'):
                            result = xtt.add_account(self.account_type, self.account_id)
                            logger.info(f"添加账户结果: {result}")
                    else:
                        # 其他方法可能需要账户参数
                        try:
                            result = init_method(self.account_id, self.account_type)
                            logger.info(f"调用 {method_name} 方法初始化交易API，结果: {result}")
                        except TypeError:
                            # 如果参数不匹配，尝试不带参数
                            result = init_method()
                            logger.info(f"无参数调用 {method_name} 方法初始化交易API，结果: {result}")
                    
                    # 注册回调函数
                    self._register_callbacks()
                # else:
                #     logger.error("未找到可用的交易API初始化方法")
            
            # Retry logic if initial connection fails
            if not (self.trader and hasattr(self.trader, 'is_connected') and self.trader.is_connected()) and hasattr(xtt, 'connect'):
                max_retries = 3
                retry_delay = 5  # seconds
                for attempt in range(max_retries):
                    logger.info(f"尝试重新连接交易API (尝试 {attempt + 1}/{max_retries})")
                    result = xtt.connect()
                    if result == 0:
                        logger.info("重新连接成功")
                        if hasattr(xtt, 'add_account'):
                            xtt.add_account(self.account_type, self.account_id)
                            self._register_callbacks()
                        break
                    else:
                        logger.warning(f"重新连接失败，{retry_delay}秒后重试")
                        time.sleep(retry_delay)

        except Exception as e:
            logger.error(f"初始化交易API出错: {str(e)}")
    
    def _trade_callback(self, callback_type, data):
        """统一的交易回调函数"""
        try:
            if callback_type == "order":
                self._on_order_callback(data)
            elif callback_type == "deal":
                self._on_deal_callback(data)
            elif callback_type == "account":
                self._on_account_callback(data)
            elif callback_type == "position":
                self._on_position_callback(data)
            elif callback_type == "error":
                self._on_error_callback(data)
            else:
                logger.warning(f"收到未知类型的回调: {callback_type}")
                
        except Exception as e:
            logger.error(f"处理交易回调时出错: {str(e)}")
    
    def _register_callbacks(self):
        """注册交易回调函数"""
        try:
            # 注册成交回调
            if hasattr(xtt, 'register_callback'):
                xtt.register_callback('deal_callback', self._on_deal_callback)
                # 注册委托回调
                xtt.register_callback('order_callback', self._on_order_callback)
                # 注册账户资金回调
                xtt.register_callback('account_callback', self._on_account_callback)
                # 注册持仓回调
                xtt.register_callback('position_callback', self._on_position_callback)
                # 注册错误回调
                xtt.register_callback('error_callback', self._on_error_callback)
                
                logger.info("交易回调函数注册成功")
            elif hasattr(xtt, 'set_callback'):
                # 另一种可能的回调注册方法
                xtt.set_callback(self._trade_callback)
                logger.info("设置统一回调函数成功")
            elif self.trader and hasattr(self.trader, 'set_callback'):
                # 对象方法的回调注册
                self.trader.set_callback(self._trade_callback)
                logger.info("设置交易对象回调函数成功")
            else:
                logger.warning("未找到支持的回调注册方法")
            
        except Exception as e:
            logger.error(f"注册交易回调函数出错: {str(e)}")
    
    def _on_deal_callback(self, deal_info):
        """
        成交回调函数
        
        参数:
        deal_info: 成交信息对象
        """
        try:
            # 检查是否为模拟交易模式
            if hasattr(config, 'ENABLE_SIMULATION_MODE') and config.ENABLE_SIMULATION_MODE:
                logger.info("模拟交易模式，忽略成交回调")
                return

            logger.info(f"收到成交回调: {deal_info.m_strInstrumentID}, 成交价: {deal_info.m_dPrice}, 成交量: {deal_info.m_nVolume}")
            
            # 提取成交信息
            stock_code = deal_info.m_strInstrumentID
            trade_type = 'BUY' if deal_info.m_nDirection == DIRECTION_BUY else 'SELL'
            price = deal_info.m_dPrice
            volume = deal_info.m_nVolume
            amount = price * volume
            trade_id = deal_info.m_strTradeID
            commission = deal_info.m_dComssion
            trade_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 保存成交记录到数据库
            self._save_trade_record(stock_code, trade_time, trade_type, price, volume, amount, trade_id, commission)
            
            # 更新持仓信息
            self._update_position_after_trade(stock_code, trade_type, price, volume)
            
            # 处理网格交易
            if config.GRID_TRADING_ENABLED:
                self._handle_grid_trade_after_deal(stock_code, trade_type, price, volume, trade_id)
            
            # 执行回调函数
            if trade_id in self.callbacks:
                callback_fn = self.callbacks.pop(trade_id)
                callback_fn(deal_info)
                
        except Exception as e:
            logger.error(f"处理成交回调时出错: {str(e)}")
    
    def _on_order_callback(self, order_info):
        """
        委托回调函数
        
        参数:
        order_info: 委托信息对象
        """
        try:
            order_id = order_info.m_strOrderSysID
            stock_code = order_info.m_strInstrumentID
            status = order_info.m_nOrderStatus
            
            # 缓存委托记录
            self.order_cache[order_id] = order_info
            
            status_desc = {
                48: "未报",
                49: "待报",
                50: "已报",
                51: "已报待撤",
                52: "部成待撤",
                53: "部撤",
                54: "已撤",
                55: "部成",
                56: "已成",
                57: "废单"
            }
            
            logger.info(f"收到委托回调: {stock_code}, 委托号: {order_id}, 状态: {status_desc.get(status, '未知')}")
            
            # 如果委托已完成（已成、已撤、废单），移除回调
            if status in [54, 56, 57]:
                if order_id in self.callbacks:
                    logger.debug(f"委托 {order_id} 已完成，移除回调")
                    # 不要在这里执行回调，因为成交回调会处理
                
        except Exception as e:
            logger.error(f"处理委托回调时出错: {str(e)}")
    
    def _on_account_callback(self, account_info):
        """
        账户资金回调函数
        
        参数:
        account_info: 账户资金信息对象
        """
        try:
            logger.debug(f"收到账户回调: 可用资金: {account_info.m_dAvailable}, 总资产: {account_info.m_dBalance}")
            
        except Exception as e:
            logger.error(f"处理账户回调时出错: {str(e)}")
    
    def _on_position_callback(self, position_info):
        """
        持仓回调函数
        
        参数:
        position_info: 持仓信息对象
        """
        try:
            stock_code = position_info.m_strInstrumentID
            volume = position_info.m_nVolume
            cost_price = position_info.m_dOpenPrice
            current_price = position_info.m_dLastPrice
            
            logger.debug(f"收到持仓回调: {stock_code}, 数量: {volume}, 成本价: {cost_price}, 当前价: {current_price}")
            
            # 更新持仓信息
            if volume > 0:
                self.position_manager.update_position(stock_code, volume, cost_price, current_price)
            else:
                # 如果数量为0，删除持仓记录
                self.position_manager.remove_position(stock_code)
                
        except Exception as e:
            logger.error(f"处理持仓回调时出错: {str(e)}")
    
    def _on_error_callback(self, error_info):
        """
        错误回调函数
        
        参数:
        error_info: 错误信息对象
        """
        try:
            logger.error(f"交易API错误: {error_info}")
            
        except Exception as e:
            logger.error(f"处理错误回调时出错: {str(e)}")
    
    def _save_trade_record(self, stock_code, trade_time, trade_type, price, volume, amount, trade_id, commission, strategy='default'):
        """
        保存交易记录到数据库
        
        参数:
        stock_code (str): 股票代码
        trade_time (str): 交易时间
        trade_type (str): 交易类型（BUY/SELL）
        price (float): 成交价格
        volume (int): 成交数量
        amount (float): 成交金额
        trade_id (str): 成交编号
        commission (float): 手续费
        strategy (str): 策略名称
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trade_records 
                (stock_code, trade_time, trade_type, price, volume, amount, trade_id, commission, strategy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_code, trade_time, trade_type, price, volume, amount, trade_id, commission, strategy))
            
            self.conn.commit()
            logger.info(f"保存交易记录成功: {stock_code}, {trade_type}, 价格: {price}, 数量: {volume}")
            
        except Exception as e:
            logger.error(f"保存交易记录时出错: {str(e)}")
            self.conn.rollback()
    
    def _update_position_after_trade(self, stock_code, trade_type, price, volume):
        """
        交易后更新持仓信息
        
        参数:
        stock_code (str): 股票代码
        trade_type (str): 交易类型（BUY/SELL）
        price (float): 成交价格
        volume (int): 成交数量
        """
        try:
            # 获取当前持仓
            position = self.position_manager.get_position(stock_code)
            
            if trade_type == 'BUY':
                if position:
                    # 已有持仓，计算新的持仓量和成本价
                    old_volume = position['volume']
                    old_cost = position['cost_price']
                    new_volume = old_volume + volume
                    new_cost = (old_volume * old_cost + volume * price) / new_volume
                    
                    # 更新持仓
                    self.position_manager.update_position(stock_code, new_volume, new_cost, price)
                else:
                    # 新建持仓
                    self.position_manager.update_position(stock_code, volume, price, price)
            else:  # SELL
                if position:
                    # 减少持仓
                    old_volume = position['volume']
                    old_cost = position['cost_price']
                    new_volume = old_volume - volume
                    
                    if new_volume > 0:
                        # 更新持仓
                        self.position_manager.update_position(stock_code, new_volume, old_cost, price)
                    else:
                        # 清仓
                        self.position_manager.remove_position(stock_code)
                else:
                    logger.warning(f"卖出 {stock_code} 时未找到持仓记录")
                    
        except Exception as e:
            logger.error(f"更新 {stock_code} 的持仓信息时出错: {str(e)}")
    
    def _handle_grid_trade_after_deal(self, stock_code, trade_type, price, volume, trade_id):
        """
        成交后处理网格交易
        
        参数:
        stock_code (str): 股票代码
        trade_type (str): 交易类型（BUY/SELL）
        price (float): 成交价格
        volume (int): 成交数量
        trade_id (str): 成交编号
        """
        try:
            if trade_type == 'BUY':
                # 检查是否有网格买入记录
                grid_trades = self.position_manager.get_grid_trades(stock_code, status='PENDING')
                for _, grid in grid_trades.iterrows():
                    grid_id = grid['id']
                    buy_price = grid['buy_price']
                    
                    # 如果买入价格接近网格买入价，更新网格状态为激活
                    if abs(price - buy_price) / buy_price < 0.01:  # 价差小于1%
                        self.position_manager.update_grid_trade_status(grid_id, 'ACTIVE')
                        logger.info(f"网格交易 {grid_id} 买入成交，更新状态为激活")
                        
                        # 创建卖出网格
                        sell_price = price * (1 + config.GRID_STEP_RATIO)
                        self.create_grid_trade(stock_code, buy_price, sell_price, int(volume * config.GRID_POSITION_RATIO))
                        
            elif trade_type == 'SELL':
                # 检查是否有网格卖出记录
                grid_trades = self.position_manager.get_grid_trades(stock_code, status='ACTIVE')
                for _, grid in grid_trades.iterrows():
                    grid_id = grid['id']
                    sell_price = grid['sell_price']
                    
                    # 如果卖出价格接近网格卖出价，更新网格状态为完成
                    if abs(price - sell_price) / sell_price < 0.01:  # 价差小于1%
                        self.position_manager.update_grid_trade_status(grid_id, 'COMPLETED')
                        logger.info(f"网格交易 {grid_id} 卖出成交，更新状态为完成")
                        
                        # 如果有持仓，创建新的买入网格
                        position = self.position_manager.get_position(stock_code)
                        if position and position['volume'] > 0:
                            buy_price = price * (1 - config.GRID_STEP_RATIO)
                            self.create_grid_trade(stock_code, buy_price, price, int(volume * config.GRID_POSITION_RATIO))
                
        except Exception as e:
            logger.error(f"处理 {stock_code} 的网格交易成交后逻辑时出错: {str(e)}")
    
    def create_grid_trade(self, stock_code, buy_price, sell_price, volume):
        """
        创建网格交易
        
        参数:
        stock_code (str): 股票代码
        buy_price (float): 买入价格
        sell_price (float): 卖出价格
        volume (int): 交易数量
        
        返回:
        int: 网格交易ID
        """
        try:
            # 获取当前网格数量
            grid_trades = self.position_manager.get_grid_trades(stock_code)
            
            # 如果网格数量已达上限，不再创建新的网格
            if len(grid_trades) >= config.GRID_MAX_LEVELS:
                logger.warning(f"{stock_code} 的网格数量已达上限 {config.GRID_MAX_LEVELS}，不再创建新的网格")
                return -1
            
            # 确定网格级别
            grid_level = len(grid_trades) + 1
            
            # 创建网格交易记录
            grid_id = self.position_manager.add_grid_trade(stock_code, grid_level, buy_price, sell_price, volume)
            
            logger.info(f"创建 {stock_code} 的网格交易成功，ID: {grid_id}, 买入价: {buy_price}, 卖出价: {sell_price}, 数量: {volume}")
            return grid_id
            
        except Exception as e:
            logger.error(f"创建 {stock_code} 的网格交易时出错: {str(e)}")
            return -1
    
    def get_account_info(self):
        """
        获取账户信息
        
        返回:
        dict: 账户信息
        """
        try:
            account_info = None
            
            # 尝试不同的API调用方式获取账户信息
            if self.trader and hasattr(self.trader, 'query_account'):
                # 如果使用对象API
                account_info = self.trader.query_account()
            elif hasattr(xtt, 'query_account'):
                # 如果使用函数式API
                account_info = xtt.query_account(self.account_id, self.account_type)
            
            if not account_info:
                logger.warning(f"未能获取账户 {self.account_id} 的信息")
                return None
            
            return {
                'account_id': self.account_id,
                'account_type': self.account_type,
                'balance': getattr(account_info, 'm_dBalance', 0),  # 总资产
                'available': getattr(account_info, 'm_dAvailable', 0),  # 可用资金
                'market_value': getattr(account_info, 'm_dInstrumentValue', 0),  # 持仓市值
                'profit_loss': getattr(account_info, 'm_dPositionProfit', 0)  # 持仓盈亏
            }
            
        except Exception as e:
            logger.error(f"获取账户信息时出错: {str(e)}")
            return None
    
    def get_stock_positions(self):
        """
        获取股票持仓信息
        
        返回:
        list: 持仓信息列表
        """
        try:
            positions = None
            
            # 尝试不同的API调用方式获取持仓信息
            if self.trader and hasattr(self.trader, 'query_position'):
                # 如果使用对象API
                positions = self.trader.query_position()
            elif hasattr(xtt, 'query_position'):
                # 如果使用函数式API
                positions = xtt.query_position(self.account_id, self.account_type)
                
            if not positions:
                return []
            
            position_list = []
            for pos in positions:
                position_list.append({
                    'stock_code': pos.m_strInstrumentID,
                    'stock_name': pos.m_strInstrumentName,
                    'volume': pos.m_nVolume,
                    'available': pos.m_nCanUseVolume,
                    'cost_price': pos.m_dOpenPrice,
                    'current_price': pos.m_dLastPrice,
                    'market_value': pos.m_dMarketValue,
                    'profit_ratio': pos.m_dProfitRate
                })
            
            return position_list
            
        except Exception as e:
            logger.error(f"获取持仓信息时出错: {str(e)}")
            return []
    
    def _check_trade_rules(self, stock_code, volume, price, is_buy=True):
        """
        检查交易规则
        
        参数:
        stock_code (str): 股票代码
        volume (int): 交易数量
        price (float): 交易价格
        is_buy (bool): 是否为买入交易
        
        返回:
        tuple: (是否通过检查, 错误消息)
        """
        try:
            error_msg = None
            
            # 检查交易量是否为100的整数倍
            if volume <= 0 or volume % 100 != 0:
                error_msg = f"交易数量必须为100的整数倍: {volume}"
                return False, error_msg
            
            # 获取账户信息
            account_info = self.get_account_info()
            if not account_info:
                error_msg = "无法获取账户信息，交易取消"
                return False, error_msg
            
            if is_buy:
                # 检查是否允许买入
                if hasattr(config, 'ENABLE_ALLOW_BUY') and not config.ENABLE_ALLOW_BUY:
                    error_msg = "系统当前不允许买入操作"
                    return False, error_msg
                
                # 计算所需资金
                required_amount = volume * price * 1.003  # 考虑手续费
                
                # 检查是否有足够资金
                if account_info['available'] < required_amount:
                    error_msg = f"可用资金不足，需要 {required_amount:.2f}，可用 {account_info['available']:.2f}"
                    return False, error_msg
            else:
                # 检查是否允许卖出
                if hasattr(config, 'ENABLE_ALLOW_SELL') and not config.ENABLE_ALLOW_SELL:
                    error_msg = "系统当前不允许卖出操作"
                    return False, error_msg
                
                # 获取持仓信息
                position = self.position_manager.get_position(stock_code)
                if not position:
                    error_msg = f"未持有股票 {stock_code}，无法卖出"
                    return False, error_msg
                
                # 检查是否有足够持仓
                if position['available'] < volume:
                    error_msg = f"可用持仓不足，需要 {volume}，可用 {position['available']}"
                    return False, error_msg
            
            return True, None
            
        except Exception as e:
            logger.error(f"检查交易规则时出错: {str(e)}")
            return False, f"检查交易规则时出错: {str(e)}"
    
    def _adjust_price_for_market(self, stock_code, price, is_buy=True):
        """
        根据市场情况动态调整价格
        
        参数:
        stock_code (str): 股票代码
        price (float): 原始价格
        is_buy (bool): 是否为买入交易
        
        返回:
        float: 调整后的价格
        """
        try:
            # 获取最新行情
            latest_quote = self.data_manager.get_latest_data(stock_code)
            if not latest_quote:
                logger.warning(f"未能获取 {stock_code} 的最新行情，使用原始价格")
                return price
            
            # 提取关键价格
            current_price = latest_quote.get('lastPrice', 0)
            if current_price == 0:
                return price
            
            if is_buy:
                # 买入价格调整逻辑
                # 如果行情数据中有卖三价
                sell3_price = latest_quote.get('askPrice3', None)
                if sell3_price:
                    # 确保买入价不低于卖三价，提高成交概率
                    # 但也不要高于卖三价太多
                    adjusted_price = min(price, sell3_price * 1.003)
                else:
                    # 如果没有卖三价，使用当前价格加小幅调整
                    adjusted_price = current_price * 1.002
            else:
                # 卖出价格调整逻辑
                # 如果行情数据中有买三价
                buy3_price = latest_quote.get('bidPrice3', None)
                if buy3_price:
                    # 确保卖出价不高于买三价，提高成交概率
                    # 但也不要低于买三价太多
                    adjusted_price = max(price, buy3_price * 0.997)
                else:
                    # 如果没有买三价，使用当前价格减小幅调整
                    adjusted_price = current_price * 0.998
            
            # 确保价格在合理范围内
            adjusted_price = round(adjusted_price, 2)
            if adjusted_price <= 0:
                return price
            
            # 如果调整后的价格与原始价格差异太大，记录日志
            if abs(adjusted_price - price) / price > 0.01:
                logger.info(f"{stock_code} 价格调整: 从 {price:.2f} 到 {adjusted_price:.2f}")
            
            return adjusted_price
            
        except Exception as e:
            logger.error(f"调整 {stock_code} 的交易价格时出错: {str(e)}")
            return price
    
    def _generate_sim_order_id(self):
        """生成模拟交易订单ID"""
        self.sim_order_counter += 1
        return f"SIM{datetime.now().strftime('%Y%m%d%H%M%S')}{self.sim_order_counter:04d}"
    
    def buy_stock(self, stock_code, volume=None, price=None, amount=None, price_type=0, callback=None):
        """
        买入股票
        
        参数:
        stock_code (str): 股票代码
        volume (int): 买入数量，与amount二选一
        price (float): 买入价格，为None时使用市价
        amount (float): 买入金额，与volume二选一
        price_type (int): 价格类型，0-限价，1-市价
        callback (function): 成交回调函数
        
        返回:
        str: 委托编号，失败返回None
        """
        with self.trade_lock:
            try:
                # 检查是否在交易时间
                if not config.is_trade_time():
                    logger.warning("当前不是交易时间，无法下单")
                    return None
                
                # 检查全局监控总开关
                if hasattr(config, 'ENABLE_AUTO_TRADING') and not config.ENABLE_AUTO_TRADING:
                    logger.warning("全局监控总开关已关闭，无法买入")
                    return None
                
                # 检查买入权限
                if hasattr(config, 'ENABLE_ALLOW_BUY') and not config.ENABLE_ALLOW_BUY:
                    logger.warning("系统当前不允许买入操作")
                    return None
                
                # 获取最新价格
                if price is None:
                    latest_quote = self.data_manager.get_latest_data(stock_code)
                    if not latest_quote:
                        logger.error(f"未能获取 {stock_code} 的最新行情，无法下单")
                        return None
                    price = latest_quote.get('lastPrice') or 0
                
                # 如果指定了金额而不是数量，计算数量
                if volume is None and amount is not None:
                    volume = int(amount / price / 100) * 100  # 向下取整到100的整数倍
                
                if volume <= 0:
                    logger.error(f"买入数量必须大于0: {volume}")
                    return None
                
                # 检查交易规则
                pass_check, error_msg = self._check_trade_rules(stock_code, volume, price, is_buy=True)
                if not pass_check:
                    logger.error(f"买入 {stock_code} 未通过交易规则检查: {error_msg}")
                    return None
                
                # 调整价格
                adjusted_price = self._adjust_price_for_market(stock_code, price, is_buy=True)
                
                # 检查是否为模拟交易模式
                if hasattr(config, 'ENABLE_SIMULATION_MODE') and config.ENABLE_SIMULATION_MODE:
                    # 处理模拟交易
                    sim_order_id = self._generate_sim_order_id()
                    trade_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 记录模拟交易
                    self._save_trade_record(
                        stock_code=stock_code,
                        trade_time=trade_time,
                        trade_type='BUY',
                        price=adjusted_price,
                        volume=volume,
                        amount=adjusted_price * volume,
                        trade_id=sim_order_id,
                        commission=adjusted_price * volume * 0.0003,  # 模拟手续费
                        strategy='simulation'
                    )
                    
                    # 更新持仓
                    self._update_position_after_trade(stock_code, 'BUY', adjusted_price, volume)
                    
                    logger.info(f"[模拟] 买入 {stock_code} 成功，委托号: {sim_order_id}, 价格: {adjusted_price}, 数量: {volume}")
                    return sim_order_id
                
                # 实盘交易
                order_id = None
                
                # 尝试不同的API调用方式
                if self.trader:
                    # 如果使用对象API
                    if hasattr(self.trader, 'limit_order') and hasattr(self.trader, 'market_order'):
                        if price_type == 1:  # 市价单
                            order_id = self.trader.market_order(stock_code, DIRECTION_BUY, volume)
                        else:  # 限价单
                            order_id = self.trader.limit_order(stock_code, DIRECTION_BUY, adjusted_price, volume)
                elif hasattr(xtt, 'limit_order') and hasattr(xtt, 'market_order'):
                    # 如果使用函数式API
                    if price_type == 1:  # 市价单
                        order_id = xtt.market_order(self.account_id, self.account_type, stock_code, DIRECTION_BUY, volume)
                    else:  # 限价单
                        order_id = xtt.limit_order(self.account_id, self.account_type, stock_code, DIRECTION_BUY, adjusted_price, volume)
                else:
                    # 尝试通用下单接口
                    if hasattr(xtt, 'order'):
                        order_type = 1 if price_type == 1 else 0  # 1可能是市价，0可能是限价
                        order_id = xtt.order(self.account_id, self.account_type, stock_code, DIRECTION_BUY, adjusted_price, volume, order_type)
                    else:
                        logger.error("没有找到可用的下单方法")
                        return None
                
                if not order_id:
                    logger.error(f"买入 {stock_code} 失败")
                    return None
                
                logger.info(f"买入 {stock_code} 下单成功，委托号: {order_id}, 价格: {adjusted_price}, 数量: {volume}")
                
                # 注册回调
                if callback:
                    self.callbacks[order_id] = callback
                
                return order_id
                
            except Exception as e:
                logger.error(f"买入 {stock_code} 时出错: {str(e)}")
                return None
    
    def sell_stock(self, stock_code, volume=None, price=None, ratio=None, price_type=0, callback=None):
        """
        卖出股票
        
        参数:
        stock_code (str): 股票代码
        volume (int): 卖出数量，与ratio二选一
        price (float): 卖出价格，为None时使用市价
        ratio (float): 卖出比例，0-1之间，与volume二选一
        price_type (int): 价格类型，0-限价，1-市价
        callback (function): 成交回调函数
        
        返回:
        str: 委托编号，失败返回None
        """
        with self.trade_lock:
            try:
                # 检查是否在交易时间
                if not config.is_trade_time():
                    logger.warning("当前不是交易时间，无法下单")
                    return None
                
                # 检查全局监控总开关
                if hasattr(config, 'ENABLE_AUTO_TRADING') and not config.ENABLE_AUTO_TRADING:
                    logger.warning("全局监控总开关已关闭，无法卖出")
                    return None
                
                # 检查卖出权限
                if hasattr(config, 'ENABLE_ALLOW_SELL') and not config.ENABLE_ALLOW_SELL:
                    logger.warning("系统当前不允许卖出操作")
                    return None
                
                # 获取最新价格
                if price is None:
                    latest_quote = self.data_manager.get_latest_data(stock_code)
                    if not latest_quote:
                        logger.error(f"未能获取 {stock_code} 的最新行情，无法下单")
                        return None
                    price = latest_quote.get('lastPrice') or 0
                
                # 如果指定了比例而不是数量，计算数量
                if volume is None and ratio is not None:
                    position = self.position_manager.get_position(stock_code)
                    if not position:
                        logger.error(f"未持有 {stock_code}，无法卖出")
                        return None
                    
                    total_volume = position['volume']
                    volume = int(total_volume * ratio / 100) * 100  # 向下取整到100的倍数
                
                if volume <= 0:
                    logger.error(f"卖出数量必须大于0: {volume}")
                    return None
                
                # 检查交易规则
                pass_check, error_msg = self._check_trade_rules(stock_code, volume, price, is_buy=False)
                if not pass_check:
                    logger.error(f"卖出 {stock_code} 未通过交易规则检查: {error_msg}")
                    return None
                
                # 调整价格
                adjusted_price = self._adjust_price_for_market(stock_code, price, is_buy=False)
                
                # 检查是否为模拟交易模式
                if hasattr(config, 'ENABLE_SIMULATION_MODE') and config.ENABLE_SIMULATION_MODE:
                    # 处理模拟交易
                    sim_order_id = self._generate_sim_order_id()
                    trade_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 记录模拟交易
                    self._save_trade_record(
                        stock_code=stock_code,
                        trade_time=trade_time,
                        trade_type='SELL',
                        price=adjusted_price,
                        volume=volume,
                        amount=adjusted_price * volume,
                        trade_id=sim_order_id,
                        commission=adjusted_price * volume * 0.0013,  # 模拟手续费(含印花税)
                        strategy='simulation'
                    )
                    
                    # 更新持仓
                    self._update_position_after_trade(stock_code, 'SELL', adjusted_price, volume)
                    
                    logger.info(f"[模拟] 卖出 {stock_code} 成功，委托号: {sim_order_id}, 价格: {adjusted_price}, 数量: {volume}")
                    return sim_order_id
                
                # 实盘交易
                order_id = None
                
                # 尝试不同的API调用方式
                if self.trader:
                    # 如果使用对象API
                    if hasattr(self.trader, 'limit_order') and hasattr(self.trader, 'market_order'):
                        if price_type == 1:  # 市价单
                            order_id = self.trader.market_order(stock_code, DIRECTION_SELL, volume)
                        else:  # 限价单
                            order_id = self.trader.limit_order(stock_code, DIRECTION_SELL, adjusted_price, volume)
                elif hasattr(xtt, 'limit_order') and hasattr(xtt, 'market_order'):
                    # 如果使用函数式API
                    if price_type == 1:  # 市价单
                        order_id = xtt.market_order(self.account_id, self.account_type, stock_code, DIRECTION_SELL, volume)
                    else:  # 限价单
                        order_id = xtt.limit_order(self.account_id, self.account_type, stock_code, DIRECTION_SELL, adjusted_price, volume)
                else:
                    # 尝试通用下单接口
                    if hasattr(xtt, 'order'):
                        order_type = 1 if price_type == 1 else 0  # 1可能是市价，0可能是限价
                        order_id = xtt.order(self.account_id, self.account_type, stock_code, DIRECTION_SELL, adjusted_price, volume, order_type)
                    else:
                        logger.error("没有找到可用的下单方法")
                        return None
                
                if not order_id:
                    logger.error(f"卖出 {stock_code} 失败")
                    return None
                
                logger.info(f"卖出 {stock_code} 下单成功，委托号: {order_id}, 价格: {adjusted_price}, 数量: {volume}")
                
                # 注册回调
                if callback:
                    self.callbacks[order_id] = callback
                
                return order_id
                
            except Exception as e:
                logger.error(f"卖出 {stock_code} 时出错: {str(e)}")
                return None
    
    def cancel_order(self, order_id):
        """
        撤销委托
        
        参数:
        order_id (str): 委托编号
        
        返回:
        bool: 是否成功发送撤单请求
        """
        try:
            # 检查是否为模拟交易模式下的订单
            if order_id.startswith("SIM"):
                logger.info(f"[模拟] 撤单请求已处理，委托号: {order_id}")
                return True
            
            # 调用交易API撤单
            ret = False
            
            # 尝试不同的API调用方式
            if self.trader and hasattr(self.trader, 'cancel_order'):
                # 如果使用对象API
                ret = self.trader.cancel_order(order_id)
            elif hasattr(xtt, 'cancel_order'):
                # 如果使用函数式API
                ret = xtt.cancel_order(self.account_id, self.account_type, order_id)
            else:
                logger.error("没有找到可用的撤单方法")
                return False
            
            if ret:
                logger.info(f"撤单请求已发送，委托号: {order_id}")
                return True
            else:
                logger.error(f"撤单请求发送失败，委托号: {order_id}")
                return False
                
        except Exception as e:
            logger.error(f"撤销委托 {order_id} 时出错: {str(e)}")
            return False
    
    def get_orders(self, status=None):
        """
        获取委托列表
        
        参数:
        status (int): 委托状态过滤，为None时获取所有委托
        
        返回:
        list: 委托列表
        """
        try:
            orders = None
            
            # 尝试不同的API调用方式
            if self.trader and hasattr(self.trader, 'query_order'):
                # 如果使用对象API
                orders = self.trader.query_order()
            elif hasattr(xtt, 'query_order'):
                # 如果使用函数式API
                orders = xtt.query_order(self.account_id, self.account_type)
            
            if not orders:
                return []
            
            order_list = []
            for order in orders:
                # 如果指定了状态过滤，跳过不匹配的委托
                if status is not None and order.m_nOrderStatus != status:
                    continue
                
                order_list.append({
                    'order_id': order.m_strOrderSysID,
                    'stock_code': order.m_strInstrumentID,
                    'stock_name': order.m_strInstrumentName,
                    'direction': 'BUY' if order.m_nDirection == DIRECTION_BUY else 'SELL',
                    'price': order.m_dLimitPrice,
                    'volume': order.m_nVolumeTotalOriginal,
                    'traded_volume': order.m_nVolumeTraded,
                    'status': order.m_nOrderStatus,
                    'status_desc': self._get_order_status_desc(order.m_nOrderStatus),
                    'submit_time': order.m_strInsertTime
                })
            
            return order_list
            
        except Exception as e:
            logger.error(f"获取委托列表时出错: {str(e)}")
            return []
    
    def _get_order_status_desc(self, status):
        """获取委托状态描述"""
        status_dict = {
            48: "未报",
            49: "待报",
            50: "已报",
            51: "已报待撤",
            52: "部成待撤",
            53: "部撤",
            54: "已撤",
            55: "部成",
            56: "已成",
            57: "废单"
        }
        return status_dict.get(status, "未知")
    
    def get_trades(self, start_date=None, end_date=None):
        """
        获取成交记录
        
        参数:
        start_date (str): 开始日期，格式 'YYYY-MM-DD'
        end_date (str): 结束日期，格式 'YYYY-MM-DD'
        
        返回:
        pandas.DataFrame: 成交记录
        """
        try:
            query = "SELECT * FROM trade_records"
            params = []
            
            if start_date:
                query += " WHERE trade_time >= ?"
                params.append(start_date + " 00:00:00")
                
                if end_date:
                    query += " AND trade_time <= ?"
                    params.append(end_date + " 23:59:59")
            elif end_date:
                query += " WHERE trade_time <= ?"
                params.append(end_date + " 23:59:59")
            
            query += " ORDER BY trade_time DESC"
            
            df = pd.read_sql_query(query, self.conn, params=params)
            return df
            
        except Exception as e:
            logger.error(f"获取成交记录时出错: {str(e)}")
            return pd.DataFrame()
    
    def close(self):
        """关闭交易执行器"""
        try:
            # 尝试不同的关闭方法
            if self.trader:
                # 如果使用对象API
                if hasattr(self.trader, 'logout'):
                    self.trader.logout()
                elif hasattr(self.trader, 'close'):
                    self.trader.close()
            else:
                # 如果使用函数式API
                if hasattr(xtt, 'stop'):
                    xtt.stop()
                elif hasattr(xtt, 'disconnect'):
                    xtt.disconnect()
                
                # 取消数据订阅
                if hasattr(xtt, 'unsubscribe_trade_data'):
                    xtt.unsubscribe_trade_data(self.account_id, self.account_type)
            
            logger.info("交易执行器已关闭")
            
        except Exception as e:
            logger.error(f"关闭交易执行器时出错: {str(e)}")


# 单例模式
_instance = None

def get_trading_executor():
    """获取TradingExecutor单例"""
    global _instance
    if _instance is None:
        _instance = TradingExecutor()
    return _instance