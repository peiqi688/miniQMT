"""
持仓管理模块，负责跟踪和管理持仓
"""
import pandas as pd
import sqlite3
from datetime import datetime
import time
import threading
import sys
import os
import json
import Methods
import config
from logger import get_logger
from data_manager import get_data_manager
from easy_qmt_trader import easy_qmt_trader

# 获取logger
logger = get_logger("position_manager")

class PositionManager:
    """持仓管理类，负责跟踪和管理持仓"""
    
    def __init__(self):
        """初始化持仓管理器"""
        self.data_manager = get_data_manager()
        self.conn = self.data_manager.conn
        self.stock_positions_file = config.STOCK_POOL_FILE

        # 持仓监控线程
        self.monitor_thread = None
        self.stop_flag = False
        
        # 初始化easy_qmt_trader
        account_config = config.get_account_config()
        self.qmt_trader = easy_qmt_trader(
            path= config.QMT_PATH,
            account=account_config.get('account_id'),
            account_type=account_config.get('account_type', 'STOCK')
        )
        self.qmt_trader.connect()

    
    def get_all_positions(self):
        """
        获取所有持仓
        
        返回:
        pandas.DataFrame: 所有持仓数据
        """
        try:
            # 判断是否为测试环境
            if not self._is_test_environment():
                # 获取实盘持仓数据
                real_positions_df = self.qmt_trader.position()
                
                # 同步实盘持仓数据到数据库
                if not real_positions_df.empty:
                    self._sync_real_positions_to_db(real_positions_df)

            query = "SELECT * FROM positions"
            df = pd.read_sql_query(query, self.conn)
            logger.debug(f"获取到 {len(df)} 条持仓记录")
            return df
        except Exception as e:
            logger.error(f"获取所有持仓信息时出错: {str(e)}")
            return pd.DataFrame()
    
    def get_position(self, stock_code):
        """
        获取指定股票的持仓
        
        参数:
        stock_code (str): 股票代码
        
        返回:
        dict: 持仓信息
        """
        try:
            # 判断是否为测试环境
            if not self._is_test_environment():
                # 获取实盘持仓数据
                real_positions_df = self.qmt_trader.position()
                
                # 同步实盘持仓数据到数据库
                if not real_positions_df.empty:
                    self._sync_real_positions_to_db(real_positions_df)

            query = "SELECT * FROM positions WHERE stock_code=?"
            df = pd.read_sql_query(query, self.conn, params=(stock_code,))
            
            if df.empty:
                logger.debug(f"未找到 {stock_code} 的持仓信息")
                return None
            
            # 转换为字典
            position = df.iloc[0].to_dict()
            return position
        except Exception as e:
            logger.error(f"获取 {stock_code} 的持仓信息时出错: {str(e)}")
            return None
        
    def _is_test_environment(self):
        """判断是否为测试环境"""
        # 可以根据需要修改判断逻辑
        return 'unittest' in sys.modules

    
    def _sync_real_positions_to_db(self, real_positions_df):
        """
        将实盘持仓数据同步到数据库
        
        参数:
        real_positions_df (pandas.DataFrame): 实盘持仓数据
        """
        try:
            # 获取数据库中所有持仓的股票代码
            cursor = self.conn.cursor()
            cursor.execute("SELECT stock_code FROM positions")
            db_stock_codes = {row[0] for row in cursor.fetchall()}
            current_positions = set()

            # 遍历实盘持仓数据
            for _, row in real_positions_df.iterrows():
                stock_code = row['证券代码']
                volume = row['股票余额']
                cost_price = row['成本价']
                
                # 获取当前价格
                latest_quote = self.data_manager.get_latest_data(stock_code)
                if latest_quote:
                    current_price = latest_quote.get('lastPrice')
                else:
                    logger.warning(f"未能获取 {stock_code} 的最新价格，使用成本价")
                    current_price = cost_price
                
                # 查询数据库中是否已存在该股票的持仓记录
                cursor.execute("SELECT profit_triggered, open_date, highest_price FROM positions WHERE stock_code=?", (stock_code,))
                result = cursor.fetchone()
                
                if result:
                    # 如果存在，则更新持仓信息，但不修改open_date
                    profit_triggered, open_date, highest_price = result
                    self.update_position(stock_code, volume, cost_price, current_price, profit_triggered, highest_price, open_date)
                else:
                    # 如果不存在，则新增持仓记录
                    self.update_position(stock_code, volume, cost_price, current_price)
                
                # 从数据库股票代码集合中移除已处理的股票代码
                db_stock_codes.discard(stock_code)
                current_positions.add(stock_code)

            # 处理数据库中存在但实盘已清仓的股票
            for stock_code in db_stock_codes:
                self.remove_position(stock_code)

            # Update stock_positions.json
            self._update_stock_positions_file(current_positions)

            logger.info("实盘持仓数据已同步到数据库")
        except Exception as e:
            logger.error(f"同步实盘持仓数据到数据库时出错: {str(e)}")
            self.conn.rollback()

    def _update_stock_positions_file(self, current_positions):
        """
        更新 stock_positions.json 文件，如果内容有变化则写入。

        参数:
        current_positions (set): 当前持仓的股票代码集合
        """
        try:
            if os.path.exists(self.stock_positions_file):
                with open(self.stock_positions_file, "r") as f:
                    try:
                        existing_positions = set(json.load(f))
                    except json.JSONDecodeError:
                        logger.warning(f"Error decoding JSON from {self.stock_positions_file}. Overwriting with current positions.")
                        existing_positions = set()
            else:
                existing_positions = set()

            if existing_positions != current_positions:
                with open(self.stock_positions_file, "w") as f:
                    json.dump(sorted(list(current_positions)), f, indent=4, ensure_ascii=False)  # Sort for consistency
                logger.info(f"更新 {self.stock_positions_file} with new positions.")
            # else:
            #     logger.info(f"{self.stock_positions_file} is up to date.")

        except Exception as e:
            logger.error(f"更新出错 {self.stock_positions_file}: {str(e)}")

    def update_position(self, stock_code, volume, cost_price, current_price=None, profit_triggered=False, highest_price=None, open_date=None, stop_loss_price=None):
        """
        更新持仓信息
        
        参数:
        stock_code (str): 股票代码
        volume (int): 持仓数量
        cost_price (float): 成本价
        current_price (float): 当前价格，如果为None，会获取最新行情
        profit_triggered (bool): 是否已经触发首次止盈
        highest_price (float): 历史最高价
        open_date (str): 开仓时间，如果为None，则使用当前时间
        stop_loss_price (float): 当前止损价格，如果为None，则重新计算
        
        返回:
        bool: 是否更新成功
        """
        try:
            # 如果当前价格为None，获取最新行情
            if current_price is None:
                # 先尝试用xtdata获取tick数据
                latest_quote = self.data_manager.get_latest_xtdata(stock_code)
                if latest_quote is None:
                    # 再尝试用mootdx获取日线数据
                    latest_data = self.data_manager.get_latest_data(stock_code)
                    if latest_data:
                        current_price = latest_data.get('lastPrice')
                    else:
                        logger.warning(f"未能获取 {stock_code} 的最新行情，使用成本价")
                        current_price = cost_price
                else:
                    current_price = latest_quote.get('lastPrice')
                    
            # 计算市值和收益率
            market_value = round(volume * current_price, 2)
            profit_ratio = 100*round((current_price - cost_price) / cost_price if cost_price > 0 else 0, 4)
            cost_price = round(cost_price, 2)
            current_price = round(current_price, 2)
            highest_price = round(highest_price, 2) if highest_price else None
            stop_loss_price = round(stop_loss_price, 2) if stop_loss_price else None
            
            # 获取当前时间
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 检查是否已有持仓记录
            cursor = self.conn.cursor()
            cursor.execute("SELECT open_date, profit_triggered, highest_price, stop_loss_price FROM positions WHERE stock_code=?", (stock_code,))
            result = cursor.fetchone()
            
            if result:
                # 更新持仓
                if open_date is None:
                    open_date = result[0]  # 获取已有的open_date
                old_highest_price = result[2]
                if old_highest_price is None:
                    old_highest_price = current_price
                if highest_price is None:
                    highest_price = max(old_highest_price, current_price)
                else:
                    highest_price = max(highest_price,old_highest_price)
                # 如果没有传入止损价格，则重新计算
                if stop_loss_price is None:
                    stop_loss_price = self.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
                    stop_loss_price = round(stop_loss_price, 2)
                else:
                    stop_loss_price = min(stop_loss_price, self.calculate_stop_loss_price(cost_price, highest_price, profit_triggered))
                    stop_loss_price = round(stop_loss_price, 2)

                cursor.execute("""
                    UPDATE positions 
                    SET volume=?, cost_price=?, current_price=?, market_value=?, 
                        profit_ratio=?, last_update=?, highest_price=?, stop_loss_price=?
                    WHERE stock_code=?
                """, (volume, cost_price, current_price, market_value, profit_ratio, now, highest_price, stop_loss_price, stock_code))

                if profit_triggered != result[1]:
                    logger.info(f"更新 {stock_code} 持仓: 首次止盈触发: 从 {result[1]} 到 {profit_triggered}")
                elif highest_price != result[2]:
                    logger.info(f"更新 {stock_code} 持仓: 最高价: 从 {result[2]} 到 {highest_price}") 
                elif stop_loss_price != result[3]:
                    logger.info(f"更新 {stock_code} 持仓: 止损价: 从 {result[3]} 到 {stop_loss_price}")

            else:
                # 新增持仓
                if open_date is None:
                    open_date = now  # 新建仓时记录当前时间为open_date
                profit_triggered = False
                if highest_price is None:
                    highest_price = current_price
                # 计算止损价格
                stop_loss_price = self.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
                stop_loss_price = round(stop_loss_price, 2)
                cursor.execute("""
                    INSERT INTO positions 
                    (stock_code, volume, cost_price, current_price, market_value, profit_ratio, last_update, open_date, profit_triggered, highest_price, stop_loss_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (stock_code, volume, cost_price, current_price, market_value, profit_ratio, now, open_date, profit_triggered, highest_price, stop_loss_price))
                logger.info(f"新增 {stock_code} 持仓: 数量: {volume}, 成本价: {cost_price}, 当前价: {current_price}, 首次止盈触发: {profit_triggered}, 最高价: {highest_price}, 止损价: {stop_loss_price}")
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"更新 {stock_code} 持仓Error: {str(e)}")
            self.conn.rollback()
            return False


    def remove_position(self, stock_code):
        """
        删除持仓记录
        
        参数:
        stock_code (str): 股票代码
        
        返回:
        bool: 是否删除成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM positions WHERE stock_code=?", (stock_code,))
            self.conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"已删除 {stock_code} 的持仓记录")
                return True
            else:
                logger.warning(f"未找到 {stock_code} 的持仓记录，无需删除")
                return False
                
        except Exception as e:
            logger.error(f"删除 {stock_code} 的持仓记录时出错: {str(e)}")
            self.conn.rollback()
            return False

    def update_all_positions_highest_price(self):
        """更新所有持仓的最高价"""
        try:
            positions = self.get_all_positions()
            if positions.empty:
                logger.debug("当前没有持仓，无需更新最高价")
                return

            for _, position in positions.iterrows():
                stock_code = position['stock_code']

                open_date_str = position['open_date']

                # Convert open_date to datetime object if it's a string
                if isinstance(open_date_str, str):
                    open_date = datetime.strptime(open_date_str, '%Y-%m-%d %H:%M:%S')
                else:
                    open_date = open_date_str

                # Format open_date to YYYY-MM-DD for getStockData
                open_date_formatted = open_date.strftime('%Y-%m-%d')

                # Get today's date for getStockData
                today_formatted = datetime.now().strftime('%Y-%m-%d')

                # 获取从开仓日期到今天的历史数据
                try:
                    # Get the latest data 
                    history_data = Methods.getStockData(
                        code=stock_code,
                        fields="high",
                        start_date=open_date_formatted,
                        freq= 'd',  # 日线
                        adjustflag= '2'
                    )                    

                except Exception as e:
                    logger.error(f"获取 {stock_code} 从 {open_date_formatted} 到 {today_formatted} 的历史数据时出错: {str(e)}")
                    continue

                if history_data is not None and not history_data.empty:
                    # 找到最高价
                    highest_price = history_data['high'].astype(float).max()

                    if highest_price > position['highest_price']:
                        # 更新持仓"最高价”信息
                        self.update_position(
                            stock_code=stock_code,
                            volume=position['volume'],
                            cost_price=position['cost_price'],
                            current_price=position['current_price'],
                            profit_triggered=position['profit_triggered'],
                            highest_price=highest_price,
                            open_date=position['open_date'],
                            stop_loss_price=position['stop_loss_price']
                        )
                        logger.info(f"更新 {stock_code} 的最高价为 {highest_price:.2f}")
                else:
                    logger.warning(f"未能获取 {stock_code} 从 {open_date_formatted} 到 {today_formatted} 的历史数据，跳过更新最高价")

        except Exception as e:
            logger.error(f"更新所有持仓的最高价时出错: {str(e)}")


    def update_all_positions_price(self):
        """更新所有持仓的最新价格"""
        try:
            positions = self.get_all_positions()
            if positions.empty:
                logger.debug("当前没有持仓，无需更新价格")
                return
            
            for _, position in positions.iterrows():
                stock_code = position['stock_code']
                volume = position['volume']
                cost_price = position['cost_price']
                profit_triggered = position['profit_triggered']
                highest_price = position['highest_price']
                open_date = position['open_date']
                # 获取最新价格
                latest_quote = self.data_manager.get_latest_data(stock_code)
                if latest_quote:
                    current_price = latest_quote.get('lastPrice')
                    # Only update if the price has changed significantly
                    old_price = position['current_price']
                    if abs(current_price - old_price) / old_price > 0.003:  # 0.3% threshold
                        # 计算止损价格
                        stop_loss_price = self.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
                        # 更新持仓信息，传入最高价和止损价
                        self.update_position(stock_code, volume, cost_price, current_price, profit_triggered, highest_price, open_date, stop_loss_price)
                    else:
                        logger.debug(f"{stock_code} 价格变化小于0.5%，跳过更新")
                else:
                    logger.warning(f"未能获取 {stock_code} 的最新价格，跳过更新")
                
        except Exception as e:
            logger.error(f"更新所有持仓价格时出错: {str(e)}")


    
    def get_grid_trades(self, stock_code, status=None):
        """
        获取网格交易记录
        
        参数:
        stock_code (str): 股票代码
        status (str): 状态筛选，如 'PENDING', 'ACTIVE', 'COMPLETED'
        
        返回:
        pandas.DataFrame: 网格交易记录
        """
        try:
            query = "SELECT * FROM grid_trades WHERE stock_code=?"
            params = [stock_code]
            
            if status:
                query += " AND status=?"
                params.append(status)
                
            query += " ORDER BY grid_level"
            
            df = pd.read_sql_query(query, self.conn, params=params)
            logger.debug(f"获取到 {stock_code} 的 {len(df)} 条网格交易记录")
            return df
            
        except Exception as e:
            logger.error(f"获取 {stock_code} 的网格交易记录时出错: {str(e)}")
            return pd.DataFrame()
    
    def add_grid_trade(self, stock_code, grid_level, buy_price, sell_price, volume):
        """
        添加网格交易记录
        
        参数:
        stock_code (str): 股票代码
        grid_level (int): 网格级别
        buy_price (float): 买入价格
        sell_price (float): 卖出价格
        volume (int): 交易数量
        
        返回:
        int: 新增网格记录的ID，失败返回-1
        """
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO grid_trades 
                (stock_code, grid_level, buy_price, sell_price, volume, status, create_time, update_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_code, grid_level, buy_price, sell_price, volume, 'PENDING', now, now))
            
            self.conn.commit()
            grid_id = cursor.lastrowid
            
            logger.info(f"添加 {stock_code} 的网格交易记录成功，ID: {grid_id}, 级别: {grid_level}, 买入价: {buy_price}, 卖出价: {sell_price}, 数量: {volume}")
            return grid_id
            
        except Exception as e:
            logger.error(f"添加 {stock_code} 的网格交易记录时出错: {str(e)}")
            self.conn.rollback()
            return -1
    
    def update_grid_trade_status(self, grid_id, status):
        """
        更新网格交易状态
        
        参数:
        grid_id (int): 网格交易ID
        status (str): 新状态，如 'PENDING', 'ACTIVE', 'COMPLETED'
        
        返回:
        bool: 是否更新成功
        """
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE grid_trades 
                SET status=?, update_time=?
                WHERE id=?
            """, (status, now, grid_id))
            
            self.conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"更新网格交易 {grid_id} 的状态为 {status} 成功")
                return True
            else:
                logger.warning(f"未找到网格交易 {grid_id}，无法更新状态")
                return False
                
        except Exception as e:
            logger.error(f"更新网格交易 {grid_id} 的状态时出错: {str(e)}")
            self.conn.rollback()
            return False
    
    def check_grid_trade_signals(self, stock_code):
        """
        检查网格交易信号
        
        参数:
        stock_code (str): 股票代码
        
        返回:
        dict: 网格交易信号，包含 'buy_signals' 和 'sell_signals'
        """
        try:
            # 获取最新价格
            latest_quote = self.data_manager.get_latest_data(stock_code)
            if not latest_quote:
                logger.warning(f"未能获取 {stock_code} 的最新行情，无法检查网格信号")
                return {'buy_signals': [], 'sell_signals': []}
            
            current_price = latest_quote.get('lastPrice')
            
            # 获取网格交易记录
            grid_trades = self.get_grid_trades(stock_code)
            
            buy_signals = []
            sell_signals = []
            
            # 检查每个网格的买入/卖出信号
            for _, grid in grid_trades.iterrows():
                grid_id = grid['id']
                status = grid['status']
                buy_price = grid['buy_price']
                sell_price = grid['sell_price']
                volume = grid['volume']
                
                # 检查买入信号
                if status == 'PENDING' and current_price <= buy_price:
                    buy_signals.append({
                        'grid_id': grid_id,
                        'price': buy_price,
                        'volume': volume
                    })
                
                # 检查卖出信号
                if status == 'ACTIVE' and current_price >= sell_price:
                    sell_signals.append({
                        'grid_id': grid_id,
                        'price': sell_price,
                        'volume': volume
                    })
            
            signals = {
                'buy_signals': buy_signals,
                'sell_signals': sell_signals
            }
            
            if buy_signals or sell_signals:
                logger.info(f"{stock_code} 网格交易信号: 买入={len(buy_signals)}, 卖出={len(sell_signals)}")
            
            return signals
            
        except Exception as e:
            logger.error(f"检查 {stock_code} 的网格交易信号时出错: {str(e)}")
            return {'buy_signals': [], 'sell_signals': []}

    def calculate_stop_loss_price(self, cost_price, highest_price, profit_triggered):
        """
        计算止损价格
        
        参数:
        cost_price (float): 成本价
        highest_price (float): 历史最高价
        profit_triggered (bool): 是否已经触发首次止盈
        
        返回:
        float: 止损价格
        """
        if profit_triggered:
            # 动态止损
            highest_profit_ratio = (highest_price - cost_price) / cost_price
            take_profit_coefficient = 1.0  # Default to no take-profit
            for profit_level, coefficient in config.DYNAMIC_TAKE_PROFIT:
                if highest_profit_ratio >= profit_level:
                    take_profit_coefficient = coefficient
                    break  # Stop at the first matching level
            dynamic_take_profit_price = highest_price * take_profit_coefficient
            return dynamic_take_profit_price
        else:
            # 固定止损
            return cost_price * (1 + config.STOP_LOSS_RATIO)


    def check_stop_loss(self, stock_code):
        """
        检查止损条件
        
        参数:
        stock_code (str): 股票代码
        
        返回:
        bool: 是否触发止损
        """
        try:
            position = self.get_position(stock_code)
            if not position:
                logger.debug(f"未持有 {stock_code}，不需要检查止损")
                return False
            
            # 获取当前价格和止损价格
            current_price = position['current_price']
            stop_loss_price = position['stop_loss_price']
            
            # 检查是否达到止损条件
            if current_price <= stop_loss_price:
                logger.warning(f"{stock_code} 触发止损条件，当前价格: {current_price:.2f}, 止损价格: {stop_loss_price:.2f}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"检查 {stock_code} 的止损条件时出错: {str(e)}")
            return False

    
    def check_dynamic_take_profit(self, stock_code):
        """
        检查动态止盈条件
        
        参数:
        stock_code (str): 股票代码
        
        返回:
        tuple: (是否触发止盈, 止盈信号类型)，止盈信号类型可以是 'HALF', 'FULL' 或 None
        """
        try:
            position = self.get_position(stock_code)
            if not position:
                logger.debug(f"未持有 {stock_code}，不需要检查止盈")
                return False, None
            
            # 获取当前收益率
            current_price = position['current_price']
            cost_price = position['cost_price']
            profit_ratio = (current_price - cost_price) / cost_price if cost_price > 0 else 0
            profit_triggered = position['profit_triggered']
            highest_price = position['highest_price']

            # 检查初次止盈（盈利5%卖出半仓）
            # 检查是否已经触发过首次止盈
            if config.ENABLE_DYNAMIC_STOP_PROFIT:
                if profit_triggered == False:
                    if profit_ratio >= config.INITIAL_TAKE_PROFIT_RATIO:
                        logger.info(f"{stock_code} 触发初次止盈，当前盈利: {profit_ratio:.2%}, 初次止盈阈值: {config.INITIAL_TAKE_PROFIT_RATIO:.2%}")
                        # 计算止损价格
                        stop_loss_price = self.calculate_stop_loss_price(cost_price, highest_price, True)
                        self.update_position(stock_code=stock_code, volume=position['volume'] / 2, cost_price=position['cost_price'], current_price=position['current_price'], profit_triggered=True, highest_price=highest_price, open_date=position['open_date'], stop_loss_price=stop_loss_price)
                        return True, 'HALF'
                
                # 检查动态止盈
                if profit_triggered:
                    # 计算最高价相对持仓成本价的涨幅
                    highest_profit_ratio = (highest_price - cost_price) / cost_price
                    
                    # 确定止盈位系数
                    take_profit_coefficient = 1.0  # Default to no take-profit
                    for profit_level, coefficient in config.DYNAMIC_TAKE_PROFIT:
                        if highest_profit_ratio >= profit_level:
                            take_profit_coefficient = coefficient
                            break  # Stop at the first matching level
                    
                    # 计算动态止盈位
                    dynamic_take_profit_price = highest_price * take_profit_coefficient
                    
                    # 如果当前价格小于动态止盈位，触发止盈
                    if current_price < dynamic_take_profit_price:
                        logger.info(f"{stock_code} 触发动态止盈，当前价格: {current_price:.2f}, 动态止盈位: {dynamic_take_profit_price:.2f}, 最高价: {highest_price:.2f}")
                        # 清仓
                        stop_loss_price = self.calculate_stop_loss_price(cost_price, highest_price, True)
                        self.update_position(stock_code=stock_code, volume=0, cost_price=position['cost_price'], current_price=position['current_price'], profit_triggered=True, highest_price=highest_price, open_date=position['open_date'], stop_loss_price=stop_loss_price)
                        return True, 'FULL'
                    else:
                        #更新最高价和止损价
                        stop_loss_price = self.calculate_stop_loss_price(cost_price, max(highest_price,current_price), True)
                        self.update_position(stock_code=stock_code, volume=position['volume'], cost_price=position['cost_price'], current_price=position['current_price'], profit_triggered=True, highest_price=max(highest_price,current_price), open_date=position['open_date'], stop_loss_price=stop_loss_price)
                        return False, None
            
            return False, None
            
        except Exception as e:
            logger.error(f"检查 {stock_code} 的动态止盈条件时出错: {str(e)}")
            return False, None

    def calculate_stop_loss_price(self, cost_price, highest_price, profit_triggered):
        """
        计算止损价格
        
        参数:
        cost_price (float): 成本价
        highest_price (float): 历史最高价
        profit_triggered (bool): 是否已经触发首次止盈
        
        返回:
        float: 止损价格
        """
        if profit_triggered:
            # 动态止损
            highest_profit_ratio = (highest_price - cost_price) / cost_price
            take_profit_coefficient = 0.97  # Default to no take-profit (in case no level is met)

            # Iterate through the DYNAMIC_TAKE_PROFIT levels
            for profit_level, coefficient in config.DYNAMIC_TAKE_PROFIT:
                if highest_profit_ratio >= profit_level:
                    take_profit_coefficient = coefficient
                    # We don't break here, because we want to find the highest applicable level
                    # The last level that meets the condition will be used

            # Calculate the dynamic stop-loss price
            dynamic_take_profit_price = highest_price * take_profit_coefficient
            return dynamic_take_profit_price
        else:
            # 固定止损
            return cost_price * (1 + config.STOP_LOSS_RATIO)


    def mark_profit_triggered(self, stock_code):
        """标记股票已触发首次止盈"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE positions SET profit_triggered = ? WHERE stock_code = ?", (True, stock_code))
            self.conn.commit()
            logger.info(f"已在数据库中标记 {stock_code} 触发首次止盈")
        except Exception as e:
            logger.error(f"标记 {stock_code} 触发首次止盈时出错: {str(e)}")
            self.conn.rollback()

    def start_position_monitor_thread(self):
        """启动持仓监控线程"""
        if not config.ENABLE_POSITION_MONITOR:
            logger.info("持仓监控功能已关闭，不启动监控线程")
            return
            
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("持仓监控线程已在运行")
            return
            
        self.stop_flag = False
        self.monitor_thread = threading.Thread(target=self._position_monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("持仓监控线程已启动")
    
    def stop_position_monitor_thread(self):
        """停止持仓监控线程"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.stop_flag = True
            self.monitor_thread.join(timeout=5)
            logger.info("持仓监控线程已停止")
    
    def _position_monitor_loop(self):
        """持仓监控循环"""
        while not self.stop_flag:
            try:
                # 判断是否在交易时间
                if config.is_trade_time():
                    # 更新所有持仓的最新价格
                    self.update_all_positions_price()

                    # 更新所有持仓的最高价，需要open_date至今的K线
                    self.update_all_positions_highest_price()

                    # 获取所有持仓
                    positions = self.get_all_positions()
                    
                    # 检查每个持仓的止损止盈条件
                    for _, position in positions.iterrows():
                        stock_code = position['stock_code']
                        volume = position['volume']
                        cost_price = position['cost_price']
                        profit_triggered = position['profit_triggered']
                        highest_price = position['highest_price']
                        open_date = position['open_date']
                        # 检查止损条件
                        stop_loss_triggered = self.check_stop_loss(stock_code)
                        
                        # 检查止盈条件
                        take_profit_triggered, take_profit_type = self.check_dynamic_take_profit(stock_code)
                        
                        # 检查网格交易信号
                        if config.ENABLE_GRID_TRADING:
                            grid_signals = self.check_grid_trade_signals(stock_code)
                        
                        # 记录信号到日志，实际交易会在策略模块中执行
                        if stop_loss_triggered:
                            logger.warning(f"{stock_code} 触发止损信号")
                        
                        if take_profit_triggered:
                            logger.info(f"{stock_code} 触发止盈信号，类型: {take_profit_type}")
                
                # 等待下一次监控
                for _ in range(60):  # 每分钟检查一次
                    if self.stop_flag:
                        break
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"持仓监控循环出错: {str(e)}")
                time.sleep(60)  # 出错后等待一分钟再继续



# 单例模式
_instance = None

def get_position_manager():
    """获取PositionManager单例"""
    global _instance
    if _instance is None:
        _instance = PositionManager()
    return _instance
