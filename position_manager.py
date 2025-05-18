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
    """根据自动交易策略，调用easy QMT Trader自动执行交易指令"""
    
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

        # 创建内存数据库
        self.memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._create_memory_table()
        self._sync_db_to_memory()

        # 添加模拟交易模式的提示日志
        if hasattr(config, 'ENABLE_SIMULATION_MODE') and config.ENABLE_SIMULATION_MODE:
            logger.warning("系统以模拟交易模式运行 - 持仓变更只在内存中进行，不会写入数据库")

        # 添加缓存机制
        self.last_position_update_time = 0
        self.position_update_interval = 3  # 5秒更新间隔
        self.positions_cache = None        

        # 定时同步线程
        self.sync_thread = None
        self.sync_stop_flag = False
        self.start_sync_thread()

    def _create_memory_table(self):
        """创建内存数据库表结构"""
        cursor = self.memory_conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            stock_code TEXT PRIMARY KEY,
            stock_name TEXT,
            volume INTEGER,
            available REAL,           
            cost_price REAL,
            current_price REAL,
            market_value REAL,
            profit_ratio REAL,
            last_update TIMESTAMP,
            open_date TIMESTAMP,
            profit_triggered BOOLEAN DEFAULT FALSE,
            highest_price REAL,
            stop_loss_price REAL                      
        )
        ''')
        self.memory_conn.commit()
        logger.info("内存数据库表结构已创建")


    def _sync_real_positions_to_memory(self, real_positions_df):
        """将实盘持仓数据同步到内存数据库"""
        try:
            # 首先检查输入数据
            if real_positions_df is None or not isinstance(real_positions_df, pd.DataFrame) or real_positions_df.empty:
                logger.warning("传入的实盘持仓数据无效，跳过同步")
                return
                
            # 确保必要的列存在
            required_columns = ['证券代码', '股票余额', '可用余额', '成本价', '市值']
            missing_columns = [col for col in required_columns if col not in real_positions_df.columns]
            if missing_columns:
                logger.warning(f"实盘持仓数据缺少必要列: {missing_columns}，无法同步")
                return

            # 获取内存数据库中所有持仓的股票代码
            cursor = self.memory_conn.cursor()
            cursor.execute("SELECT stock_code FROM positions")
            memory_stock_codes = {row[0] for row in cursor.fetchall() if row[0] is not None}
            current_positions = set()

            # 遍历实盘持仓数据
            for _, row in real_positions_df.iterrows():
                try:
                    # 安全提取并转换数据
                    stock_code = str(row['证券代码']) if row['证券代码'] is not None else None
                    if not stock_code:
                        continue  # 跳过无效数据
                        
                    # 安全提取并转换数值
                    try:
                        volume = int(float(row['股票余额'])) if row['股票余额'] is not None else 0
                    except (ValueError, TypeError):
                        volume = 0
                        
                    try:
                        available = int(float(row['可用余额'])) if row['可用余额'] is not None else 0
                    except (ValueError, TypeError):
                        available = 0
                        
                    try:
                        cost_price = float(row['成本价']) if row['成本价'] is not None else 0.0
                    except (ValueError, TypeError):
                        cost_price = 0.0
                        
                    try:
                        market_value = float(row['市值']) if row['市值'] is not None else 0.0
                    except (ValueError, TypeError):
                        market_value = 0.0
                    
                    # 获取当前价格
                    current_price = cost_price  # 默认使用成本价
                    try:
                        latest_quote = self.data_manager.get_latest_data(stock_code)
                        if latest_quote and isinstance(latest_quote, dict) and 'lastPrice' in latest_quote and latest_quote['lastPrice'] is not None:
                            current_price = float(latest_quote['lastPrice'])
                    except Exception as e:
                        logger.warning(f"获取 {stock_code} 的最新价格失败: {str(e)}，使用成本价")
                    
                    # 查询内存数据库中是否已存在该股票的持仓记录
                    cursor.execute("SELECT profit_triggered, open_date, highest_price, stop_loss_price FROM positions WHERE stock_code=?", (stock_code,))
                    result = cursor.fetchone()
                    
                    if result:
                        # 如果存在，则更新持仓信息，但不修改open_date
                        profit_triggered = result[0] if result[0] is not None else False
                        open_date = result[1] if result[1] is not None else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        highest_price = result[2] if result[2] is not None else 0.0
                        stop_loss_price = result[3] if result[3] is not None else 0.0
                        
                        # 所有参数都确保有有效值
                        self.update_position(
                            stock_code=stock_code, 
                            volume=volume, 
                            cost_price=cost_price, 
                            available=available, 
                            market_value=market_value, 
                            current_price=current_price, 
                            profit_triggered=profit_triggered, 
                            highest_price=highest_price, 
                            open_date=open_date, 
                            stop_loss_price=stop_loss_price
                        )
                    else:
                        # 如果不存在，则新增持仓记录
                        self.update_position(
                            stock_code=stock_code, 
                            volume=volume, 
                            cost_price=cost_price, 
                            available=available, 
                            market_value=market_value, 
                            current_price=current_price, 
                            open_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        )
                    
                    # 添加到当前持仓集合
                    current_positions.add(stock_code)
                    memory_stock_codes.discard(stock_code)
                
                except Exception as e:
                    logger.error(f"处理持仓行数据时出错: {str(e)}")
                    continue  # 跳过这一行，继续处理其他行
            
            # 处理内存数据库中存在但实盘已清仓的股票
            if current_positions:  # 只有当至少有一个有效的当前持仓时才执行删除
                for stock_code in memory_stock_codes:
                    if stock_code:  # 确保stock_code不为None
                        self.remove_position(stock_code)

            # 更新 stock_positions.json
            self._update_stock_positions_file(current_positions)

        except Exception as e:
            logger.error(f"同步实盘持仓数据到内存数据库时出错: {str(e)}")
            self.memory_conn.rollback()


    def _sync_db_to_memory(self):
        """将数据库数据同步到内存数据库"""
        try:
            db_positions = pd.read_sql_query("SELECT * FROM positions", self.conn)
            if not db_positions.empty:
                db_positions.to_sql("positions", self.memory_conn, if_exists="replace", index=False)
                self.memory_conn.commit()
                logger.info("数据库数据已同步到内存数据库")
        except Exception as e:
            logger.error(f"数据库数据同步到内存数据库时出错: {str(e)}")

    def _sync_memory_to_db(self):
        """将内存数据库数据同步到数据库"""
        try:
            # 添加模拟交易模式检查，模拟模式下不同步到SQLite
            if hasattr(config, 'ENABLE_SIMULATION_MODE') and config.ENABLE_SIMULATION_MODE:
                logger.debug("模拟交易模式：跳过内存数据库到SQLite数据库的同步")
                return
        
            memory_positions = pd.read_sql_query("SELECT stock_code, open_date, profit_triggered, highest_price, stop_loss_price FROM positions", self.memory_conn)
            if not memory_positions.empty:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for _, row in memory_positions.iterrows():
                    stock_code = row['stock_code']
                    open_date = row['open_date']
                    profit_triggered = row['profit_triggered']
                    highest_price = row['highest_price']
                    stop_loss_price = row['stop_loss_price']
                    
                    # 查询数据库中的对应记录
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT open_date, profit_triggered, highest_price, stop_loss_price FROM positions WHERE stock_code=?", (stock_code,))  # 确保查询所有需要持久化的字段
                    db_row = cursor.fetchone()

                    if db_row:
                        db_open_date, db_profit_triggered, db_highest_price, db_stop_loss_price = db_row
                        # 比较字段是否不同
                        if (db_open_date != open_date) or (db_profit_triggered != profit_triggered) or (db_highest_price != highest_price) or (db_stop_loss_price != stop_loss_price):
                            # 如果内存数据库中的 open_date 与 SQLite 数据库中的不一致，则使用 SQLite 数据库中的值
                            if db_open_date != open_date:
                                open_date = db_open_date
                                row['open_date'] = open_date  # 更新内存数据库中的 open_date
                            # 更新数据库，确保所有字段都得到更新
                            cursor.execute("UPDATE positions SET open_date=?, profit_triggered=?, highest_price=?, stop_loss_price=?, last_update=? WHERE stock_code=?", (open_date, profit_triggered, highest_price, stop_loss_price, now, stock_code))
                            logger.info(f"更新内存数据库的 {stock_code} 到sql数据库")
                    else:
                        # 插入新记录，使用当前日期作为 open_date
                        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        cursor.execute("""
                            INSERT INTO positions (stock_code, open_date, profit_triggered, highest_price, stop_loss_price, last_update) 
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (stock_code, current_date, profit_triggered, highest_price, stop_loss_price, now))
                        # 插入新记录后，立即从数据库读取 open_date，以确保内存数据库与数据库一致
                        cursor.execute("SELECT open_date FROM positions WHERE stock_code=?", (stock_code,))
                        open_date = cursor.fetchone()[0]
                        row['open_date'] = open_date  # 更新内存数据库中的 open_date
                        logger.warning(f"在数据库中未找到 {stock_code} 的记录")
                        logger.info(f"在数据库中插入新的 {stock_code} 记录，使用当前日期 {current_date} 作为 open_date")

                self.conn.commit()
                # logger.info("内存数据库数据已同步到数据库")
        except Exception as e:
            logger.error(f"内存数据库数据同步到数据库时出错: {str(e)}")
            self.conn.rollback()

    def start_sync_thread(self):
        """启动定时同步线程"""
        self.sync_stop_flag = False
        self.sync_thread = threading.Thread(target=self._sync_loop)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        logger.info("定时同步线程已启动")

    def stop_sync_thread(self):
        """停止定时同步线程"""
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_stop_flag = True
            self.sync_thread.join(timeout=5)
            logger.info("定时同步线程已停止")

    def _sync_loop(self):
        """定时同步循环"""
        while not self.sync_stop_flag:
            try:
                self._sync_memory_to_db()
                for _ in range(5):
                    if self.sync_stop_flag:
                        break
                    time.sleep(1)
            except Exception as e:
                logger.error(f"定时同步循环出错: {str(e)}")
                time.sleep(60)  # 出错后等待一分钟再继续

    def get_all_positions(self):
        """获取所有持仓"""
        try:
            current_time = time.time()
            
            # 只在时间间隔到达后更新数据
            if (current_time - self.last_position_update_time) >= self.position_update_interval:
                # 获取实盘持仓数据
                try:
                    real_positions_df = self.qmt_trader.position()
                    
                    # 检查实盘数据
                    if real_positions_df is None:
                        logger.warning("实盘持仓数据获取失败，返回None")
                        real_positions_df = pd.DataFrame()  # 使用空DataFrame而不是None
                    elif not isinstance(real_positions_df, pd.DataFrame):
                        logger.warning(f"实盘持仓数据类型错误: {type(real_positions_df)}，将转换为DataFrame")
                        try:
                            # 尝试转换为DataFrame
                            real_positions_df = pd.DataFrame(real_positions_df)
                        except:
                            real_positions_df = pd.DataFrame()  # 转换失败则使用空DataFrame
                    
                    # 同步实盘持仓数据到内存数据库
                    if not real_positions_df.empty:
                        self._sync_real_positions_to_memory(real_positions_df)
                    
                    # 更新缓存和时间戳
                    query = "SELECT * FROM positions"
                    self.positions_cache = pd.read_sql_query(query, self.memory_conn)
                    
                    # 确保所有列都有合适的默认值
                    if not self.positions_cache.empty:
                        # 确保数值列为数值类型
                        numeric_columns = ['volume', 'available', 'cost_price', 'current_price', 
                                            'market_value', 'profit_ratio', 'highest_price', 'stop_loss_price']
                        for col in numeric_columns:
                            if col in self.positions_cache.columns:
                                # 转换为数值，无效值替换为0
                                self.positions_cache[col] = pd.to_numeric(self.positions_cache[col], errors='coerce').fillna(0)
                        
                        # 确保布尔列为布尔类型
                        if 'profit_triggered' in self.positions_cache.columns:
                            self.positions_cache['profit_triggered'] = self.positions_cache['profit_triggered'].fillna(False)
                    
                    self.last_position_update_time = current_time
                    logger.debug(f"更新持仓缓存，共 {len(self.positions_cache)} 条记录")
                except Exception as e:
                    logger.error(f"获取和处理持仓数据时出错: {str(e)}")
                    # 如果出错，返回上次的缓存，或者空DataFrame
                    if self.positions_cache is None:
                        self.positions_cache = pd.DataFrame()
                
            # 返回缓存数据的副本
            return self.positions_cache.copy() if self.positions_cache is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"获取所有持仓信息时出错: {str(e)}")
            return pd.DataFrame()  # 出错时返回空DataFrame
    
    def get_position(self, stock_code):
        """获取指定股票的持仓"""
        try:
            # 从缓存获取所有持仓
            all_positions = self.get_all_positions()
            
            # 从缓存中筛选指定股票
            position_row = all_positions[all_positions['stock_code'] == stock_code]
            
            if position_row.empty:
                return None
            
            # 转换为字典
            position = position_row.iloc[0].to_dict()
            
            # 确保数值字段转换为浮点数
            numeric_fields = ['volume', 'available', 'cost_price', 'current_price', 'market_value', 'profit_ratio', 'highest_price', 'stop_loss_price']
            for field in numeric_fields:
                if field in position and position[field] is not None:
                    try:
                        position[field] = float(position[field])
                    except ValueError:
                        position[field] = 0.0
            
            return position
        except Exception as e:
            logger.error(f"获取 {stock_code} 的持仓信息时出错: {str(e)}")
            return None
        
    def _is_test_environment(self):
        """判断是否为测试环境"""
        # 可以根据需要修改判断逻辑
        return 'unittest' in sys.modules

 
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

    def update_position(self, stock_code, volume, cost_price, available=None, market_value=None, current_price=None, profit_triggered=False, highest_price=None, open_date=None, stop_loss_price=None, stock_name=None):
        """更新持仓信息"""
        # Convert inputs to appropriate numeric types at the beginning
        try:
            # 确保stock_code有效
            if stock_code is None or stock_code == "":
                logger.error("股票代码不能为空")
                return False

            if stock_name is None:
                try:
                    # 使用data_manager获取股票名称
                    from data_manager import get_data_manager
                    data_manager = get_data_manager()
                    stock_name = data_manager.get_stock_name(stock_code)
                except Exception as e:
                    logger.warning(f"获取股票 {stock_code} 名称时出错: {str(e)}")
                    stock_name = stock_code  # 如果无法获取名称，使用代码代替
        

            # volume is typically int, but float conversion is safer for general arithmetic
            p_volume = int(float(volume)) if volume is not None else 0
            p_cost_price = float(cost_price) if cost_price is not None else 0.0

            # current_price can be None if it needs to be fetched
            p_current_price = float(current_price) if current_price is not None else None

            # available defaults to volume if not provided
            p_available = int(float(available)) if available is not None else p_volume
            
            # highest_price and stop_loss_price can be None
            p_highest_price = float(highest_price) if highest_price is not None else None
            p_stop_loss_price = float(stop_loss_price) if stop_loss_price is not None else None

            # profit_triggered 布尔值转换
            if isinstance(profit_triggered, str):
                p_profit_triggered = profit_triggered.lower() in ['true', '1', 't', 'y', 'yes']
            else:
                p_profit_triggered = bool(profit_triggered)

        except (ValueError, TypeError) as e:
            logger.error(f"Error converting inputs for {stock_code} to float: {e}. volume='{volume}', cost_price='{cost_price}', current_price='{current_price}'")
            self.memory_conn.rollback() # Ensure rollback on early error
            return False

        try:
            # 如果当前价格为None，获取最新行情
            if p_current_price is None:
                # 获取最新数据
                latest_data = self.data_manager.get_latest_data(stock_code)
                if latest_data and isinstance(latest_data, dict) and 'lastPrice' in latest_data and latest_data['lastPrice'] is not None:
                    p_current_price = float(latest_data['lastPrice'])
                else:
                    logger.debug(f"未能获取 {stock_code} 的最新价格，使用成本价")
                    p_current_price = p_cost_price
            
            # Ensure p_current_price is a float, default to cost_price if it's still None
            if p_current_price is None:
                p_current_price = p_cost_price if p_cost_price is not None else 0.0
                    
            # 计算市值和收益率
            # Use the converted variables (p_volume, p_current_price, p_cost_price)
            p_market_value = round(p_volume * p_current_price, 2)
            
            # 防止除零错误
            if p_cost_price > 0:
                p_profit_ratio = round(100 * (p_current_price - p_cost_price) / p_cost_price, 2)
            else:
                p_profit_ratio = 0.0
            
            # Round the final values before storing or using in DB operations
            final_cost_price = round(p_cost_price, 2)
            final_current_price = round(p_current_price, 2)
            
            # 处理最高价
            if p_highest_price is not None:
                final_highest_price = round(p_highest_price, 2)
            else:
                final_highest_price = final_current_price  # 默认使用当前价格
            
            # 处理止损价格
            if p_stop_loss_price is not None:
                final_stop_loss_price = round(p_stop_loss_price, 2)
            else:
                # 计算默认止损价格
                calculated_slp = self.calculate_stop_loss_price(final_cost_price, final_highest_price, p_profit_triggered)
                final_stop_loss_price = round(calculated_slp, 2) if calculated_slp is not None else None
            
            # 获取当前时间
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 处理open_date
            if open_date is None:
                open_date = now
            
            # 检查是否已有持仓记录
            cursor = self.memory_conn.cursor()
            cursor.execute("SELECT open_date, profit_triggered, highest_price, stop_loss_price FROM positions WHERE stock_code=?", (stock_code,))
            result = cursor.fetchone()
            
            if result:
                # 更新持仓
                if open_date is None:
                    open_date = result[0]  # 获取已有的open_date
                old_db_highest_price = float(result[2]) if result[2] is not None else None # from DB
                if final_highest_price is None: # if not passed or calculated yet
                    final_highest_price = max(old_db_highest_price, final_current_price) if old_db_highest_price is not None else final_current_price
                # else:
                #     highest_price = max(highest_price,old_highest_price)
                # 如果没有传入止损价格，则重新计算
                if final_stop_loss_price is None:
                    calculated_slp = self.calculate_stop_loss_price(final_cost_price, final_highest_price, profit_triggered)
                    final_stop_loss_price = round(calculated_slp, 2) if calculated_slp is not None else None
                else:
                    calculated_slp = self.calculate_stop_loss_price(final_cost_price, final_highest_price, profit_triggered)
                    if calculated_slp is not None:
                        final_stop_loss_price = min(final_stop_loss_price, calculated_slp)
                        final_stop_loss_price = round(final_stop_loss_price, 2)
            
                cursor.execute("""
                    UPDATE positions 
                    SET volume=?, cost_price=?, current_price=?, market_value=?, available=?,
                        profit_ratio=?, last_update=?, highest_price=?, stop_loss_price=?, profit_triggered=?, stock_name=?
                    WHERE stock_code=?
                """, (int(p_volume), final_cost_price, final_current_price, p_market_value, int(p_available), 
                    p_profit_ratio, now, final_highest_price, final_stop_loss_price, profit_triggered, stock_name, stock_code))
                    

                # cursor.execute("""
                #     UPDATE positions 
                #     SET volume=?, cost_price=?, current_price=?, market_value=?, available=?,
                #         profit_ratio=?, last_update=?, highest_price=?, stop_loss_price=?, profit_triggered=?
                #     WHERE stock_code=?
                # """, (int(p_volume), final_cost_price, final_current_price, p_market_value, int(p_available), p_profit_ratio, now, final_highest_price, final_stop_loss_price, profit_triggered, stock_code))

                if profit_triggered != result[1]:
                    logger.info(f"更新 {stock_code} 持仓: 首次止盈触发: 从 {result[1]} 到 {profit_triggered}")
                elif final_highest_price != (float(result[2]) if result[2] is not None else None):
                    logger.info(f"更新 {stock_code} 持仓: 最高价: 从 {result[2]} 到 {final_highest_price}")
                elif final_stop_loss_price != (float(result[3]) if result[3] is not None else None):
                    logger.info(f"更新 {stock_code} 持仓: 止损价: 从 {result[3]} 到 {final_stop_loss_price}")

            else:
                # 新增持仓
                if open_date is None:
                    open_date = now  # 新建仓时记录当前时间为open_date
                profit_triggered = False
                if final_highest_price is None:
                    final_highest_price = final_current_price
                # 计算止损价格
                calculated_slp = self.calculate_stop_loss_price(final_cost_price, final_highest_price, profit_triggered)
                final_stop_loss_price = round(calculated_slp, 2) if calculated_slp is not None else None

                cursor.execute("""
                    INSERT INTO positions 
                    (stock_code, stock_name, volume, cost_price, current_price, market_value, available, profit_ratio, last_update, open_date, profit_triggered, highest_price, stop_loss_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (stock_code, stock_name, int(p_volume), final_cost_price, final_current_price, p_market_value, 
                    int(p_available), p_profit_ratio, now, open_date, profit_triggered, final_highest_price, final_stop_loss_price))
        
                # cursor.execute("""
                #     INSERT INTO positions 
                #     (stock_code, volume, cost_price, current_price, market_value, available, profit_ratio, last_update, open_date, profit_triggered, highest_price, stop_loss_price)
                #     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                # """, (stock_code, int(p_volume), final_cost_price, final_current_price, p_market_value, int(p_available), p_profit_ratio, now, open_date, profit_triggered, final_highest_price, final_stop_loss_price))
                # logger.info(f"新增 {stock_code} 持仓: 数量: {int(p_volume)}, 成本价: {final_cost_price}, 当前价: {final_current_price}, 首次止盈触发: {profit_triggered}, 最高价: {final_highest_price}, 止损价: {final_stop_loss_price}")
            
            self.memory_conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"更新 {stock_code} 持仓Error: {str(e)}")
            self.memory_conn.rollback()
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
            cursor = self.memory_conn.cursor()
            cursor.execute("DELETE FROM positions WHERE stock_code=?", (stock_code,))
            self.memory_conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"已删除 {stock_code} 的持仓记录")
                return True
            else:
                logger.warning(f"未找到 {stock_code} 的持仓记录，无需删除")
                return False
                
        except Exception as e:
            logger.error(f"删除 {stock_code} 的持仓记录时出错: {str(e)}")
            self.memory_conn.rollback()
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

                # 安全获取最高价，确保不为None
                current_highest_price = 0.0
                if position['highest_price'] is not None:
                    try:
                        current_highest_price = float(position['highest_price'])
                    except (ValueError, TypeError):
                        current_highest_price = 0.0
                
                # 安全获取开仓日期
                open_date_str = position['open_date']
                try:
                    if isinstance(open_date_str, str):
                        open_date = datetime.strptime(open_date_str, '%Y-%m-%d %H:%M:%S')
                    else:
                        open_date = datetime.now()
                    
                    open_date_formatted = open_date.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    open_date_formatted = datetime.now().strftime('%Y-%m-%d')

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
                    # 找到开仓后日线数据最高价
                    highest_price = history_data['high'].astype(float).max()
                else:
                    highest_price = 0.0
                    logger.warning(f"未能获取 {stock_code} 从 {open_date_formatted} 到 {today_formatted} 的历史数据，跳过更新最高价")

                # 开盘时间，获取最新tick数据
                if config.is_trade_time:
                    latest_data = self.data_manager.get_latest_data(stock_code)
                    if latest_data:
                        current_price = latest_data.get('lastPrice')
                        current_high_price = latest_data.get('high')
                        if current_high_price > highest_price:
                            highest_price = current_high_price
                
                if highest_price > current_highest_price:
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

        except Exception as e:
            logger.error(f"更新所有持仓的最高价时出错: {str(e)}")


    def update_all_positions_price(self):
        """更新所有持仓的最新价格"""
        try:
            # 首先检查是否有持仓数据
            positions = self.get_all_positions()
            
            # 检查positions是否为None或空DataFrame
            if positions is None or positions.empty:
                logger.debug("当前没有持仓，无需更新价格")
                return
            
            # 检查positions是否含有必要的列
            required_columns = ['stock_code', 'volume', 'cost_price', 'current_price', 'highest_price']
            missing_columns = [col for col in required_columns if col not in positions.columns]
            if missing_columns:
                logger.warning(f"持仓数据缺少必要列: {missing_columns}，无法更新价格")
                return
            
            for _, position in positions.iterrows():
                try:
                    # 提取数据并安全转换
                    stock_code = position['stock_code']
                    if stock_code is None:
                        continue  # 跳过无效数据
                    
                    # 安全提取和转换所有数值
                    safe_numeric_values = {}
                    for field in ['volume', 'cost_price', 'current_price', 'highest_price', 'profit_triggered', 'available', 'market_value', 'stop_loss_price']:
                        if field in position:
                            value = position[field]
                            # 布尔值特殊处理
                            if field == 'profit_triggered':
                                safe_numeric_values[field] = bool(value) if value is not None else False
                            # 数值处理
                            elif field in ['volume', 'available']:
                                safe_numeric_values[field] = int(float(value)) if value is not None else 0
                            else:
                                safe_numeric_values[field] = float(value) if value is not None else 0.0
                        else:
                            # 设置默认值
                            if field == 'profit_triggered':
                                safe_numeric_values[field] = False
                            elif field in ['volume', 'available']:
                                safe_numeric_values[field] = 0
                            else:
                                safe_numeric_values[field] = 0.0
                    
                    # 安全处理open_date
                    open_date = position.get('open_date')
                    if open_date is None:
                        open_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 获取最新价格
                    try:
                        latest_quote = self.data_manager.get_latest_data(stock_code)
                        if latest_quote and isinstance(latest_quote, dict) and 'lastPrice' in latest_quote and latest_quote['lastPrice'] is not None:
                            current_price = float(latest_quote['lastPrice'])
                            
                            # 只有价格有显著变化时才更新
                            old_price = safe_numeric_values['current_price']
                            if abs(current_price - old_price) / max(old_price, 0.01) > 0.003:  # 防止除零
                                # 使用安全转换后的值来更新
                                self.update_position(
                                    stock_code=stock_code, 
                                    volume=safe_numeric_values['volume'],
                                    cost_price=safe_numeric_values['cost_price'],
                                    available=safe_numeric_values['available'],
                                    market_value=safe_numeric_values['market_value'],
                                    current_price=current_price,  # 使用最新价格
                                    profit_triggered=safe_numeric_values['profit_triggered'],
                                    highest_price=safe_numeric_values['highest_price'],
                                    open_date=open_date,
                                    stop_loss_price=safe_numeric_values['stop_loss_price']
                                )
                                logger.debug(f"更新 {stock_code} 的最新价格为 {current_price:.2f}")
                    except Exception as e:
                        logger.error(f"获取 {stock_code} 最新价格时出错: {str(e)}")
                        continue  # 跳过这只股票，继续处理其他股票
                        
                except Exception as e:
                    logger.error(f"处理 {position.get('stock_code', 'unknown')} 持仓数据时出错: {str(e)}")
                    continue  # 跳过这只股票，继续处理其他股票
            
        except Exception as e:
            logger.error(f"更新所有持仓价格时出错: {str(e)}")

    def get_account_info(self):
        """获取账户信息"""
        try:

            # 如果是模拟交易模式，直接返回模拟账户信息（由trading_executor模块管理）
            if hasattr(config, 'ENABLE_SIMULATION_MODE') and config.ENABLE_SIMULATION_MODE:
                logger.info(f"返回模拟账户信息，余额: {config.SIMULATION_BALANCE}")
                # 计算持仓市值
                positions = self.get_all_positions()
                market_value = 0
                if not positions.empty:
                    for _, pos in positions.iterrows():
                        pos_market_value = pos.get('market_value')
                        if pos_market_value is not None:
                            try:
                                market_value += float(pos_market_value)
                            except (ValueError, TypeError):
                                # 忽略无效值
                                pass
                
                # 确保返回的所有值都是有效数值
                return {
                    'account_id': 'SIMULATION',
                    'account_type': 'SIMULATION',
                    'balance': float(config.SIMULATION_BALANCE),
                    'available': float(config.SIMULATION_BALANCE) - market_value,
                    'market_value': float(market_value),
                    'profit_loss': 0.0
                }

            # 使用qmt_trader获取账户信息
            account_df = self.qmt_trader.balance()
            
            if account_df.empty:
                return None
            
            # 转换为字典格式
            account_info = {
                'account_id': account_df['资金账户'].iloc[0] if '资金账户' in account_df.columns and not account_df['资金账户'].empty else '--',
                'account_type': account_df['账号类型'].iloc[0] if '账号类型' in account_df.columns and not account_df['账号类型'].empty else '--',
                'available': float(account_df['可用金额'].iloc[0]) if '可用金额' in account_df.columns and not account_df['可用金额'].empty else 0.0,
                'frozen_cash': float(account_df['冻结金额'].iloc[0]) if '冻结金额' in account_df.columns and not account_df['冻结金额'].empty else 0.0,
                'market_value': float(account_df['持仓市值'].iloc[0]) if '持仓市值' in account_df.columns and not account_df['持仓市值'].empty else 0.0,
                'total_asset': float(account_df['总资产'].iloc[0]) if '总资产' in account_df.columns and not account_df['总资产'].empty else 0.0,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            return account_info
        except Exception as e:
            logger.error(f"获取账户信息时出错: {str(e)}")
            return None
    
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
            if current_price is not None and stop_loss_price is not None and current_price <= stop_loss_price:
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
                    if profit_ratio is not None and profit_ratio >= config.INITIAL_TAKE_PROFIT_RATIO:
                        logger.info(f"{stock_code} 触发初次止盈，当前盈利: {profit_ratio:.2%}, 初次止盈阈值: {config.INITIAL_TAKE_PROFIT_RATIO:.2%}")
                        # 计算止损价格
                        stop_loss_price = self.calculate_stop_loss_price(cost_price, highest_price, True)
                        self.update_position(stock_code=stock_code, volume=position['volume'] / 2, cost_price=position['cost_price'], current_price=position['current_price'], profit_triggered=True, highest_price=highest_price, open_date=position['open_date'], stop_loss_price=stop_loss_price)
                        return True, 'HALF'
                
                # 检查动态止盈
                if profit_triggered:
                    # 计算最高价相对持仓成本价的涨幅, 确保 highest_price 不为 None
                    if highest_price is not None:
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
                    if current_price is not None and current_price < dynamic_take_profit_price:
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


    def _check_stop_loss_with_data(self, position, latest_quote):
        """
        基于传入的持仓数据和最新行情检查止损条件
        
        参数:
        position (dict): 持仓数据
        latest_quote (dict): 最新行情数据
        
        返回:
        bool: 是否触发止损
        """
        try:
            if not position:
                return False
            
            # 确保类型转换
            try:
                # 当前价格（优先使用最新行情）
                current_price = float(latest_quote.get('lastPrice', 0)) if latest_quote else float(position.get('current_price', 0))
                
                # 止损价格
                stop_loss_price = float(position.get('stop_loss_price', 0)) if position.get('stop_loss_price') is not None else 0
            except (TypeError, ValueError) as e:
                stock_code = position.get('stock_code', 'unknown')
                logger.error(f"止损价格数据类型转换错误 - {stock_code}: {e}")
                return False
            
            # 检查是否达到止损条件
            if stop_loss_price > 0 and current_price <= stop_loss_price:
                stock_code = position['stock_code']
                logger.warning(f"{stock_code} 触发止损条件，当前价格: {current_price:.2f}, 止损价格: {stop_loss_price:.2f}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"检查持仓的止损条件时出错: {str(e)}")
            return False

    def _check_take_profit_with_data(self, position, latest_quote):
        """
        基于传入的持仓数据和最新行情检查动态止盈条件
        
        参数:
        position (dict): 持仓数据
        latest_quote (dict): 最新行情数据
        
        返回:
        tuple: (是否触发止盈, 止盈信号类型)
        """
        try:
            if not position:
                return False, None
            
            # 获取股票代码
            stock_code = position['stock_code']
            
            # 转换所有价格和比率为数值类型
            try:
                # 当前价格（优先使用最新行情）
                current_price = float(latest_quote.get('lastPrice', 0)) if latest_quote else float(position.get('current_price', 0))
                
                # 成本价
                cost_price = float(position.get('cost_price', 0))
                
                # 计算利润率
                profit_ratio = (current_price - cost_price) / cost_price if cost_price > 0 else 0
                
                # 获取止盈标志和最高价
                profit_triggered = bool(position.get('profit_triggered', False))
                highest_price = float(position.get('highest_price', 0))
            except (TypeError, ValueError) as e:
                logger.error(f"价格数据类型转换错误 - {stock_code}: {e}")
                logger.debug(f"当前价格数据: current_price={latest_quote.get('lastPrice') if latest_quote else position.get('current_price')}, "
                            f"cost_price={position.get('cost_price')}, highest_price={position.get('highest_price')}")
                return False, None

            # 检查初次止盈（盈利达到设定阈值卖出半仓）
            if config.ENABLE_DYNAMIC_STOP_PROFIT:
                if not profit_triggered:
                    if profit_ratio >= config.INITIAL_TAKE_PROFIT_RATIO:
                        logger.info(f"{stock_code} 触发初次止盈，当前盈利: {profit_ratio:.2%}, 初次止盈阈值: {config.INITIAL_TAKE_PROFIT_RATIO:.2%}")
                        return True, 'HALF'
                
                # 检查动态止盈
                if profit_triggered and highest_price > 0:
                    # 计算最高价相对持仓成本价的涨幅
                    highest_profit_ratio = (highest_price - cost_price) / cost_price
                    
                    # 确定止盈位系数
                    take_profit_coefficient = 1.0
                    for profit_level, coefficient in config.DYNAMIC_TAKE_PROFIT:
                        if highest_profit_ratio >= profit_level:
                            take_profit_coefficient = coefficient
                    
                    # 计算动态止盈位
                    dynamic_take_profit_price = highest_price * take_profit_coefficient
                    
                    # 如果当前价格小于动态止盈位，触发止盈
                    if current_price < dynamic_take_profit_price:
                        logger.info(f"{stock_code} 触发动态止盈，当前价格: {current_price:.2f}, 止盈位: {dynamic_take_profit_price:.2f}, 最高价: {highest_price:.2f}")
                        return True, 'FULL'
            
            return False, None
            
        except Exception as e:
            logger.error(f"检查持仓的动态止盈条件时出错: {str(e)}")
            # 添加更详细的日志，帮助调试
            if position:
                logger.debug(f"持仓数据: {position}")
            if latest_quote:
                logger.debug(f"行情数据: {latest_quote}")
            return False, None

    def calculate_stop_loss_price(self, cost_price, highest_price, profit_triggered):
        """计算止损价格"""
        # 确保输入都是有效的数值
        try:
            if cost_price is None or cost_price <= 0:
                return 0.0  # 如果成本价无效，返回0作为止损价
                
            if highest_price is None or highest_price <= 0:
                highest_price = cost_price  # 如果最高价无效，使用成本价
            
            # 确保profit_triggered是布尔值
            if isinstance(profit_triggered, str):
                profit_triggered = profit_triggered.lower() in ['true', '1', 't', 'y', 'yes']
            else:
                profit_triggered = bool(profit_triggered)
            
            # 后续计算基本保持不变，但添加额外的安全检查
            if profit_triggered:
                # 动态止损
                if cost_price > 0:  # 防止除零
                    highest_profit_ratio = (highest_price - cost_price) / cost_price
                else:
                    highest_profit_ratio = 0.0
                    
                take_profit_coefficient = 0.97  # 默认值
                
                # 遍历止盈级别
                for profit_level, coefficient in config.DYNAMIC_TAKE_PROFIT:
                    if highest_profit_ratio >= profit_level:
                        take_profit_coefficient = coefficient
                
                # 计算动态止损价
                dynamic_take_profit_price = highest_price * take_profit_coefficient
                return dynamic_take_profit_price
            else:
                # 固定止损 - 确保STOP_LOSS_RATIO存在且有效
                stop_loss_ratio = getattr(config, 'STOP_LOSS_RATIO', -0.07)  # 默认-7%
                return cost_price * (1 + stop_loss_ratio)
        except Exception as e:
            logger.error(f"计算止损价格时出错: {str(e)}")
            return 0.0  # 出错时返回0作为止损价


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

    def get_all_positions_with_all_fields(self):
        """获取所有持仓的所有字段（包括内存数据库中的所有字段）"""
        try:
            query = "SELECT * FROM positions"
            df = pd.read_sql_query(query, self.memory_conn)
            
            # 批量获取所有股票的行情
            if not df.empty:
                stock_codes = df['stock_code'].tolist()
                all_latest_data = {}
                
                # 批量获取所有股票的最新行情（如果交易时间）
                if config.is_trade_time():
                    for stock_code in stock_codes:
                        latest_data = self.data_manager.get_latest_xtdata(stock_code)
                        if latest_data:
                            all_latest_data[stock_code] = latest_data
                
                # 计算涨跌幅
                change_percentages = {}
                for stock_code in df['stock_code']:
                    latest_data = all_latest_data.get(stock_code)
                    if latest_data:
                        lastPrice = latest_data.get('lastPrice')
                        lastClose = latest_data.get('lastClose')
                        if lastPrice is not None and lastClose is not None and lastClose != 0:
                            change_percentage = round((lastPrice - lastClose) / lastClose * 100, 2)
                            change_percentages[stock_code] = change_percentage
                        else:
                            change_percentages[stock_code] = 0.0
                    else:
                        change_percentages[stock_code] = 0.0
                
                # 将涨跌幅添加到 DataFrame 中
                df['change_percentage'] = df['stock_code'].map(change_percentages)
            
            logger.debug(f"获取到 {len(df)} 条持仓记录（所有字段），并计算了涨跌幅")
            return df
        except Exception as e:
            logger.error(f"获取所有持仓信息（所有字段）时出错: {str(e)}")
            return pd.DataFrame()
        
    def _position_monitor_loop(self):
        """持仓监控循环"""
        while not self.stop_flag:
            try:
                # 判断是否在交易时间
                if config.is_trade_time():

                    # 首先更新所有持仓的最高价
                    self.update_all_positions_highest_price()

                    # 一次性获取所有持仓数据
                    positions_df = self.get_all_positions()
                    
                    if positions_df.empty:
                        logger.debug("当前没有持仓，无需监控")
                        time.sleep(60)
                        continue
                    
                    # 批量获取最新行情数据
                    stock_codes = positions_df['stock_code'].tolist()
                    latest_quotes = {}
                    for code in stock_codes:
                        quote = self.data_manager.get_latest_data(code)
                        if quote:
                            latest_quotes[code] = quote
                    
                    # 处理所有持仓
                    for _, position_row in positions_df.iterrows():
                        stock_code = position_row['stock_code']
                        
                        # 转换为字典
                        position = position_row.to_dict()
                        latest_quote = latest_quotes.get(stock_code)
                        
                        # 检查止损条件
                        stop_loss_triggered = self._check_stop_loss_with_data(position, latest_quote)
                        
                        # 检查止盈条件
                        take_profit_triggered, take_profit_type = self._check_take_profit_with_data(position, latest_quote)
                        
                        # 记录信号到日志
                        if stop_loss_triggered:
                            logger.warning(f"{stock_code} 触发止损信号 $$$$$$$$$$$$$$$$$$$$----------------------------")
                        
                        if take_profit_triggered:
                            logger.info(f"{stock_code} 触发止盈信号，类型: {take_profit_type} $$$$$$$$$$$$$$$$$$$$+++++")
                            
                            # 根据止盈类型更新持仓状态
                            if take_profit_type == 'HALF':
                                # 首次盈利触发，更新标记
                                new_stop_loss = self.calculate_stop_loss_price(
                                    position['cost_price'], 
                                    position['highest_price'], 
                                    True
                                )
                                self.update_position(
                                    stock_code=stock_code,
                                    volume=position['volume'],
                                    cost_price=position['cost_price'],
                                    profit_triggered=True,
                                    highest_price=position['highest_price'],
                                    open_date=position['open_date'],
                                    stop_loss_price=new_stop_loss
                                )
                        
                        # 更新最高价（如果当前价格更高）
                        if latest_quote:
                            try:
                                current_price = float(latest_quote.get('lastPrice', 0))
                                highest_price = float(position.get('highest_price', 0))
                                
                                if current_price > highest_price:
                                    new_highest_price = current_price
                                    new_stop_loss_price = self.calculate_stop_loss_price(
                                        float(position.get('cost_price', 0)), 
                                        new_highest_price,
                                        bool(position.get('profit_triggered', False))
                                    )
                                    self.update_position(
                                        stock_code=stock_code,
                                        volume=int(position.get('volume', 0)),
                                        cost_price=float(position.get('cost_price', 0)),
                                        highest_price=new_highest_price,
                                        profit_triggered=bool(position.get('profit_triggered', False)),
                                        open_date=position.get('open_date'),
                                        stop_loss_price=new_stop_loss_price
                                    )
                            except (TypeError, ValueError) as e:
                                logger.error(f"更新最高价时类型转换错误 - {stock_code}: {e}")
                    
                    # 等待下一次监控
                    for _ in range(5):  # 每5s检查一次
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
