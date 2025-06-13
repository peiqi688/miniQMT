import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import sqlite3
import os
import traceback
import sys

# 设置字体解决中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

# 添加详细日志
def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

# 创建临时数据库
def setup_test_db():
    try:
        db_path = 'test_grid_trading.db'
        # 检查是否存在测试数据库，如果存在则删除
        if os.path.exists(db_path):
            log(f"删除已存在的数据库文件: {db_path}")
            os.remove(db_path)
        
        # 创建新的测试数据库
        log(f"创建新的测试数据库: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建所需表结构
        log("创建数据表结构")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            stock_code TEXT PRIMARY KEY,
            volume INTEGER,
            available INTEGER,           
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
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            trade_time TIMESTAMP,
            trade_type TEXT,
            price REAL,
            volume INTEGER,
            amount REAL,
            trade_id TEXT,
            commission REAL,
            strategy TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grid_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            grid_level INTEGER,
            buy_price REAL,
            sell_price REAL,
            volume INTEGER,
            status TEXT,
            create_time TIMESTAMP,
            update_time TIMESTAMP
        )
        ''')
        
        conn.commit()
        return conn
    except Exception as e:
        log(f"创建数据库时出错: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

# 模拟数据管理器
class MockDataManager:
    def __init__(self, conn, price_data):
        self.conn = conn
        self.price_data = price_data
        self.current_index = 0
    
    def get_latest_data(self, stock_code):
        try:
            if self.current_index >= len(self.price_data):
                return None
            
            price = self.price_data[self.current_index]
            return {'lastPrice': price, 'high': price, 'low': price}
        except Exception as e:
            log(f"获取最新数据时出错: {str(e)}")
            return None
    
    def update_stock_data(self, stock_code):
        # 在测试中不做实际操作
        pass

# 模拟持仓管理器
class MockPositionManager:
    def __init__(self, conn):
        self.conn = conn
    
    def get_position(self, stock_code):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM positions WHERE stock_code=?", (stock_code,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            columns = [col[0] for col in cursor.description]
            position = dict(zip(columns, row))
            return position
        except Exception as e:
            log(f"获取持仓数据时出错: {str(e)}")
            return None
    
    def update_position(self, stock_code, volume, cost_price, available=None, market_value=None, current_price=None, profit_triggered=False, highest_price=None, open_date=None, stop_loss_price=None):
        try:
            cursor = self.conn.cursor()
            
            # 设置默认值
            if available is None:
                available = volume
            if current_price is None:
                current_price = cost_price
            if market_value is None:
                market_value = volume * current_price
            if open_date is None:
                open_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 计算利润率
            profit_ratio = (current_price - cost_price) / cost_price if cost_price > 0 else 0
            
            # 检查是否已存在
            cursor.execute("SELECT * FROM positions WHERE stock_code=?", (stock_code,))
            if cursor.fetchone():
                # 更新
                cursor.execute("""
                    UPDATE positions 
                    SET volume=?, cost_price=?, current_price=?, market_value=?, available=?,
                        profit_ratio=?, last_update=?, highest_price=?, stop_loss_price=?, profit_triggered=?
                    WHERE stock_code=?
                """, (volume, cost_price, current_price, market_value, available, profit_ratio, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), highest_price, stop_loss_price, profit_triggered, stock_code))
            else:
                # 插入
                cursor.execute("""
                    INSERT INTO positions 
                    (stock_code, volume, cost_price, current_price, market_value, available, profit_ratio, last_update, open_date, profit_triggered, highest_price, stop_loss_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (stock_code, volume, cost_price, current_price, market_value, available, profit_ratio, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), open_date, profit_triggered, highest_price, stop_loss_price))
            
            self.conn.commit()
            return True
        except Exception as e:
            log(f"更新持仓时出错: {str(e)}")
            self.conn.rollback()
            return False
    
    def remove_position(self, stock_code):
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM positions WHERE stock_code=?", (stock_code,))
            self.conn.commit()
        except Exception as e:
            log(f"删除持仓时出错: {str(e)}")
            self.conn.rollback()
    
    def add_grid_trade(self, stock_code, grid_level, buy_price, sell_price, volume):
        try:
            cursor = self.conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                INSERT INTO grid_trades 
                (stock_code, grid_level, buy_price, sell_price, volume, status, create_time, update_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_code, grid_level, buy_price, sell_price, volume, 'PENDING', now, now))
            
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            log(f"添加网格交易时出错: {str(e)}")
            self.conn.rollback()
            return -1
    
    def update_grid_trade_status(self, grid_id, status):
        try:
            cursor = self.conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                UPDATE grid_trades 
                SET status=?, update_time=?
                WHERE id=?
            """, (status, now, grid_id))
            
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            log(f"更新网格交易状态时出错: {str(e)}")
            self.conn.rollback()
            return False
    
    def get_grid_trades(self, stock_code, status=None):
        try:
            cursor = self.conn.cursor()
            query = "SELECT * FROM grid_trades WHERE stock_code=?"
            params = [stock_code]
            
            if status:
                query += " AND status=?"
                params.append(status)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            if not rows:
                return pd.DataFrame()
            
            columns = [col[0] for col in cursor.description]
            result = pd.DataFrame([dict(zip(columns, row)) for row in rows])
            return result
        except Exception as e:
            log(f"获取网格交易时出错: {str(e)}")
            return pd.DataFrame()
    
    def check_grid_trade_signals(self, stock_code, current_price):
        try:
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
            
            return signals
        except Exception as e:
            log(f"检查网格交易信号时出错: {str(e)}")
            return {'buy_signals': [], 'sell_signals': []}

# 模拟交易执行器
class MockTradingExecutor:
    def __init__(self, conn):
        self.conn = conn
        self.order_id_counter = 1000
    
    def buy_stock(self, stock_code, volume=None, price=None, amount=None, price_type=0, callback=None):
        try:
            # 生成订单ID
            order_id = f"BUY_{self.order_id_counter}"
            self.order_id_counter += 1
            
            # 计算交易金额
            if amount is not None and volume is None:
                volume = int(amount / price)
            
            amount = price * volume
            commission = amount * 0.0003  # 模拟手续费
            
            # 保存交易记录
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trade_records 
                (stock_code, trade_time, trade_type, price, volume, amount, trade_id, commission, strategy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_code, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'BUY', price, volume, amount, order_id, commission, 'grid_trading'))
            
            self.conn.commit()
            
            return order_id
        except Exception as e:
            log(f"买入股票时出错: {str(e)}")
            self.conn.rollback()
            return None
    
    def sell_stock(self, stock_code, volume=None, price=None, ratio=None, price_type=0, callback=None):
        try:
            # 生成订单ID
            order_id = f"SELL_{self.order_id_counter}"
            self.order_id_counter += 1
            
            amount = price * volume
            commission = amount * 0.0013  # 模拟手续费(含印花税)
            
            # 保存交易记录
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trade_records 
                (stock_code, trade_time, trade_type, price, volume, amount, trade_id, commission, strategy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_code, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'SELL', price, volume, amount, order_id, commission, 'grid_trading'))
            
            self.conn.commit()
            
            return order_id
        except Exception as e:
            log(f"卖出股票时出错: {str(e)}")
            self.conn.rollback()
            return None

# 网格交易策略类
class GridTradingStrategy:
    def __init__(self, data_manager, position_manager, trading_executor, config):
        self.data_manager = data_manager
        self.position_manager = position_manager
        self.trading_executor = trading_executor
        self.config = config
        self.last_trade_time = {}
    
    def init_grid_trading(self, stock_code):
        """初始化网格交易"""
        try:
            if not self.config['ENABLE_GRID_TRADING']:
                log(f"网格交易功能未启用，跳过 {stock_code} 的网格初始化")
                return False
            
            # 获取持仓信息
            position = self.position_manager.get_position(stock_code)
            if not position:
                log(f"未持有 {stock_code}，无法初始化网格交易")
                return False
            
            # 获取最新行情
            latest_quote = self.data_manager.get_latest_data(stock_code)
            if not latest_quote:
                log(f"未能获取 {stock_code} 的最新行情，无法初始化网格交易")
                return False
            
            current_price = latest_quote.get('lastPrice')
            position_volume = position['volume']
            
            # 创建网格
            grid_count = min(self.config['GRID_MAX_LEVELS'], 5)  # 最多创建5个网格
            grid_volume = int(position_volume * self.config['GRID_POSITION_RATIO'] / grid_count)
            
            if grid_volume < 100:
                log(f"{stock_code} 持仓量不足，无法创建有效的网格交易")
                return False
            
            for i in range(grid_count):
                # 买入价格递减，卖出价格递增
                buy_price = current_price * (1 - self.config['GRID_STEP_RATIO'] * (i + 1))
                sell_price = current_price * (1 + self.config['GRID_STEP_RATIO'] * (i + 1))
                
                # 创建网格交易
                grid_id = self.position_manager.add_grid_trade(
                    stock_code, i + 1, buy_price, sell_price, grid_volume
                )
                
                if grid_id < 0:
                    log(f"创建 {stock_code} 的网格交易记录失败")
                    return False
            
            log(f"初始化 {stock_code} 的网格交易成功，创建了 {grid_count} 个网格")
            return True
            
        except Exception as e:
            log(f"初始化 {stock_code} 的网格交易时出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def execute_grid_trading(self, stock_code):
        """执行网格交易策略"""
        try:
            if not self.config['ENABLE_GRID_TRADING']:
                return False
            
            # 获取最新价格
            latest_quote = self.data_manager.get_latest_data(stock_code)
            if not latest_quote:
                return False
            
            current_price = latest_quote.get('lastPrice')
            
            # 检查是否有网格交易信号
            grid_signals = self.position_manager.check_grid_trade_signals(stock_code, current_price)
            
            # 处理买入信号
            for signal in grid_signals['buy_signals']:
                grid_id = signal['grid_id']
                price = signal['price']
                volume = signal['volume']
                
                # 检查同一网格是否已经在冷却期
                cool_key = f"grid_buy_{stock_code}_{grid_id}"
                if cool_key in self.last_trade_time:
                    last_time = self.last_trade_time[cool_key]
                    if (datetime.now() - last_time).total_seconds() < 300:  # 5分钟冷却期
                        log(f"{stock_code} 网格 {grid_id} 买入信号在冷却期内，跳过")
                        continue
                
                # 执行买入
                log(f"执行 {stock_code} 网格 {grid_id} 买入，价格: {price}, 数量: {volume}")
                order_id = self.trading_executor.buy_stock(stock_code, volume, price)
                
                if order_id:
                    # 更新网格状态为活跃
                    self.position_manager.update_grid_trade_status(grid_id, 'ACTIVE')
                    
                    # 记录交易时间
                    self.last_trade_time[cool_key] = datetime.now()
                    
                    # 更新持仓
                    position = self.position_manager.get_position(stock_code)
                    if position:
                        # 更新持仓
                        new_volume = position['volume'] + volume
                        new_cost = (position['volume'] * position['cost_price'] + volume * price) / new_volume
                        self.position_manager.update_position(
                            stock_code, 
                            new_volume, 
                            new_cost, 
                            new_volume, 
                            new_volume * current_price, 
                            current_price
                        )
                    else:
                        # 新建持仓
                        self.position_manager.update_position(
                            stock_code, 
                            volume, 
                            price, 
                            volume, 
                            volume * current_price, 
                            current_price
                        )
            
            # 处理卖出信号
            for signal in grid_signals['sell_signals']:
                grid_id = signal['grid_id']
                price = signal['price']
                volume = signal['volume']
                
                # 检查同一网格是否已经在冷却期
                cool_key = f"grid_sell_{stock_code}_{grid_id}"
                if cool_key in self.last_trade_time:
                    last_time = self.last_trade_time[cool_key]
                    if (datetime.now() - last_time).total_seconds() < 300:  # 5分钟冷却期
                        log(f"{stock_code} 网格 {grid_id} 卖出信号在冷却期内，跳过")
                        continue
                
                # 执行卖出
                log(f"执行 {stock_code} 网格 {grid_id} 卖出，价格: {price}, 数量: {volume}")
                order_id = self.trading_executor.sell_stock(stock_code, volume, price)
                
                if order_id:
                    # 更新网格状态为完成
                    self.position_manager.update_grid_trade_status(grid_id, 'COMPLETED')
                    
                    # 记录交易时间
                    self.last_trade_time[cool_key] = datetime.now()
                    
                    # 更新持仓
                    position = self.position_manager.get_position(stock_code)
                    if position:
                        new_volume = position['volume'] - volume
                        if new_volume > 0:
                            # 更新持仓
                            self.position_manager.update_position(
                                stock_code, 
                                new_volume, 
                                position['cost_price'], 
                                new_volume, 
                                new_volume * current_price, 
                                current_price
                            )
                        else:
                            # 清仓
                            self.position_manager.remove_position(stock_code)
            
            return True
            
        except Exception as e:
            log(f"执行 {stock_code} 的网格交易时出错: {str(e)}")
            traceback.print_exc()
            return False

# 生成随机价格序列，模拟股票价格波动
def generate_price_sequence(initial_price, days, points_per_day, volatility=0.02, trend=0):
    try:
        """
        生成随机价格序列
        
        参数:
        initial_price (float): 初始价格
        days (int): 天数
        points_per_day (int): 每天生成的价格点数
        volatility (float): 波动率
        trend (float): 趋势系数，正值表示上涨趋势，负值表示下跌趋势
        
        返回:
        list: 价格序列
        """
        total_points = days * points_per_day
        prices = [initial_price]
        
        log(f"生成价格序列：初始价格={initial_price}, 天数={days}, 每天点数={points_per_day}, 波动率={volatility}, 趋势={trend}")
        
        for i in range(1, total_points):
            # 加入趋势和随机波动
            random_change = np.random.normal(0, 1) * volatility
            trend_change = trend / points_per_day
            
            # 确保价格不会变为负数
            new_price = max(0.01, prices[-1] * (1 + random_change + trend_change))
            prices.append(new_price)
        
        return prices
    except Exception as e:
        log(f"生成价格序列时出错: {str(e)}")
        traceback.print_exc()
        return [initial_price] * (days * points_per_day)

# 计算网格交易的收益 (修正版)
def calculate_grid_trading_profit(conn, stock_code, initial_investment):
    try:
        """计算网格交易的收益"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                trade_type, 
                SUM(amount) as total_amount, 
                SUM(commission) as total_commission
            FROM 
                trade_records 
            WHERE 
                stock_code=? AND 
                strategy='grid_trading'
            GROUP BY 
                trade_type
        """, (stock_code,))
        
        rows = cursor.fetchall()
        
        buy_amount = 0
        sell_amount = 0
        buy_commission = 0
        sell_commission = 0
        
        for row in rows:
            trade_type, amount, commission = row
            if trade_type == 'BUY':
                buy_amount += amount
                buy_commission += commission
            elif trade_type == 'SELL':
                sell_amount += amount
                sell_commission += commission
        
        # 获取当前持仓价值
        cursor.execute("SELECT volume, current_price FROM positions WHERE stock_code=?", (stock_code,))
        position = cursor.fetchone()
        
        current_position_value = 0
        if position:
            volume, current_price = position
            current_position_value = volume * current_price
            
            # 输出详细的持仓信息用于调试
            log(f"当前持仓: {volume}股, 当前价格: {current_price}, 持仓价值: {current_position_value}")
        
        # 计算总投入
        total_investment = initial_investment + buy_amount
        
        # 计算总收益 (修正版)
        total_profit = current_position_value - initial_investment - buy_amount + sell_amount - (buy_commission + sell_commission)
        profit_ratio = total_profit / total_investment if total_investment > 0 else 0
        
        # 输出详细的收益计算信息用于调试
        log(f"收益计算详情: 当前持仓价值({current_position_value}) - 初始投资({initial_investment}) - 买入金额({buy_amount}) + 卖出金额({sell_amount}) - 手续费({buy_commission + sell_commission}) = 总收益({total_profit})")
        
        return {
            'total_profit': total_profit,
            'profit_ratio': profit_ratio,
            'buy_amount': buy_amount,
            'sell_amount': sell_amount,
            'commission': buy_commission + sell_commission,
            'current_position_value': current_position_value,
            'total_investment': total_investment
        }
    except Exception as e:
        log(f"计算网格交易收益时出错: {str(e)}")
        traceback.print_exc()
        return {
            'total_profit': 0,
            'profit_ratio': 0,
            'buy_amount': 0,
            'sell_amount': 0,
            'commission': 0,
            'current_position_value': 0,
            'total_investment': 0
        }

# 获取交易记录用于绘图
def get_trade_records(conn, stock_code):
    try:
        """获取交易记录"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                trade_time, 
                trade_type, 
                price, 
                volume, 
                amount, 
                commission 
            FROM 
                trade_records 
            WHERE 
                stock_code=? AND 
                strategy='grid_trading'
            ORDER BY 
                trade_time
        """, (stock_code,))
        
        rows = cursor.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        columns = ['trade_time', 'trade_type', 'price', 'volume', 'amount', 'commission']
        df = pd.DataFrame(rows, columns=columns)
        
        # 转换时间格式
        df['trade_time'] = pd.to_datetime(df['trade_time'])
        
        # 添加累计收益
        df['profit'] = 0.0
        buy_amount = 0.0
        sell_amount = 0.0
        total_commission = 0.0
        
        for i in range(len(df)):
            if df.iloc[i]['trade_type'] == 'BUY':
                buy_amount += df.iloc[i]['amount']
            else:  # SELL
                sell_amount += df.iloc[i]['amount']
            
            total_commission += df.iloc[i]['commission']
            df.iloc[i, df.columns.get_loc('profit')] = sell_amount - buy_amount - total_commission
        
        return df
    except Exception as e:
        log(f"获取交易记录时出错: {str(e)}")
        traceback.print_exc()
        return pd.DataFrame()

# 主函数
def run_grid_trading_test():
    try:
        log("============ 开始网格交易测试 ============")
        
        # 初始参数
        stock_code = '600000.SH'
        initial_price = 10.0
        initial_position = 10000  # 初始持仓数量
        days = 30
        points_per_day = 8  # 每天生成8个价格点
        
        # 配置参数
        config = {
            'ENABLE_GRID_TRADING': True,
            'GRID_STEP_RATIO': 0.05,  # 网格步长5%
            'GRID_POSITION_RATIO': 0.2,  # 每个网格的仓位比例20%
            'GRID_MAX_LEVELS': 6      # 最大网格数量
        }
        
        # 生成价格序列 - 设置震荡模式（适合网格交易）
        log("生成价格序列...")
        prices = generate_price_sequence(initial_price, days, points_per_day, volatility=0.015, trend=-0.001)  # 修改为震荡下跌趋势
        
        # 设置测试数据库和模拟对象
        log("创建测试环境...")
        conn = setup_test_db()
        data_manager = MockDataManager(conn, prices)
        position_manager = MockPositionManager(conn)
        trading_executor = MockTradingExecutor(conn)
        
        # 创建网格交易策略对象
        grid_strategy = GridTradingStrategy(data_manager, position_manager, trading_executor, config)
        
        # 初始化持仓
        log(f"初始化持仓: {stock_code}, 数量: {initial_position}, 价格: {initial_price}")
        position_manager.update_position(
            stock_code, 
            initial_position, 
            initial_price, 
            initial_position, 
            initial_position * initial_price, 
            initial_price
        )
        
        # 初始化网格交易
        log("初始化网格交易...")
        grid_strategy.init_grid_trading(stock_code)
        
        # 执行价格序列的每一步
        log("开始模拟价格变动...")
        price_history = []
        timestamp_history = []
        profit_history = []
        current_time = datetime.now()
        
        # 初始投资金额
        initial_investment = initial_position * initial_price
        
        for i, price in enumerate(prices):
            # 更新当前时间（每8个点代表1天）
            if i % points_per_day == 0:
                current_time += timedelta(days=1)
            else:
                current_time += timedelta(hours=3)  # 假设交易时间为3小时间隔
            
            # 更新数据管理器的当前价格索引
            data_manager.current_index = i
            
            # 执行网格交易
            grid_strategy.execute_grid_trading(stock_code)
            
            # 记录价格和时间
            price_history.append(price)
            timestamp_history.append(current_time)
            
            # 计算当前累计收益
            profit_info = calculate_grid_trading_profit(conn, stock_code, initial_investment)
            profit_history.append(profit_info['total_profit'])
            
            # 每隔一定步数输出当前状态
            if i % 40 == 0:
                log(f"模拟进度: {i+1}/{len(prices)}, 当前价格: {price:.2f}, 当前收益: {profit_info['total_profit']:.2f}")
        
        # 获取最终收益信息
        log("计算最终收益...")
        final_profit_info = calculate_grid_trading_profit(conn, stock_code, initial_investment)
        
        # 获取交易记录
        trade_records = get_trade_records(conn, stock_code)
        
        # 打印收益信息
        log("\n====== 网格交易测试结果 ======")
        log(f"初始价格: {initial_price:.2f}")
        log(f"初始持仓: {initial_position}")
        log(f"初始投资: {initial_investment:.2f}")
        log(f"最终价格: {prices[-1]:.2f}")
        log(f"总买入金额: {final_profit_info['buy_amount']:.2f}")
        log(f"总卖出金额: {final_profit_info['sell_amount']:.2f}")
        log(f"当前持仓价值: {final_profit_info['current_position_value']:.2f}")
        log(f"手续费总额: {final_profit_info['commission']:.2f}")
        log(f"总收益: {final_profit_info['total_profit']:.2f}")
        log(f"收益率: {final_profit_info['profit_ratio']:.2%}")
        log(f"交易次数: {len(trade_records)}")
        log("===========================\n")
        
        # 绘制图表
        log("生成图表...")
        plt.figure(figsize=(16, 10))
        
        # 子图1：价格走势和交易点
        plt.subplot(2, 1, 1)
        plt.plot(timestamp_history, price_history, label='Stock Price', color='blue')
        
        # 标记买入点
        buy_records = trade_records[trade_records['trade_type'] == 'BUY']
        if not buy_records.empty:
            plt.scatter(buy_records['trade_time'], buy_records['price'], color='green', marker='^', s=100, label='Buy Points')
        
        # 标记卖出点
        sell_records = trade_records[trade_records['trade_type'] == 'SELL']
        if not sell_records.empty:
            plt.scatter(sell_records['trade_time'], sell_records['price'], color='red', marker='v', s=100, label='Sell Points')
        
        plt.title('Grid Trading Test - Price Trend and Trade Points', fontsize=14)
        plt.ylabel('Price', fontsize=12)
        plt.grid(True)
        plt.legend()
        
        # 子图2：累计收益
        plt.subplot(2, 1, 2)
        plt.plot(timestamp_history, profit_history, label='Cumulative Profit', color='orange')
        plt.axhline(y=0, color='black', linestyle='--')
        plt.title('Grid Trading Test - Cumulative Profit', fontsize=14)
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Profit', fontsize=12)
        plt.grid(True)
        plt.legend()
        
        plt.tight_layout()
        
        # 保存图表前显示保存的文件名
        save_path = 'grid_trading_test_result.png'
        log(f"保存图表到: {save_path}")
        plt.savefig(save_path, dpi=300)
        log(f"图表已保存到: {save_path}")
        
        plt.show()
        
        # 关闭数据库连接
        log("关闭数据库连接...")
        conn.close()
        
        log("============ 网格交易测试完成 ============")
        
        return {
            'profit_info': final_profit_info,
            'trade_records': trade_records,
            'price_history': price_history,
            'timestamp_history': timestamp_history,
            'profit_history': profit_history
        }
    except Exception as e:
        log(f"测试过程中出现错误: {str(e)}")
        traceback.print_exc()
        return None

# 主函数
if __name__ == "__main__":
    try:
        # 运行网格交易测试
        results = run_grid_trading_test()
        if results:
            log("测试完成!")
        else:
            log("测试失败!")
    except Exception as e:
        log(f"运行测试时出错: {str(e)}")
        traceback.print_exc()