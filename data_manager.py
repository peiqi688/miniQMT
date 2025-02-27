"""
数据管理模块，负责历史数据的获取与存储
"""
import os
import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta
import threading
import xtquant.xtdata as xt
from xtquant.xttype import StockData

import config
from logger import get_logger

# 获取logger
logger = get_logger("data_manager")

class DataManager:
    """数据管理类，处理历史行情数据的获取与存储"""
    
    def __init__(self):
        """初始化数据管理器"""
        # 创建数据目录
        if not os.path.exists(config.DATA_DIR):
            os.makedirs(config.DATA_DIR)
            
        # 连接数据库
        self.conn = self._connect_db()
        
        # 创建表结构
        self._create_tables()
        
        # 初始化行情接口
        self._init_xtquant()
        
        # 数据更新线程
        self.update_thread = None
        self.stop_flag = False
    
    def _connect_db(self):
        """连接SQLite数据库"""
        try:
            conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
            logger.info(f"已连接数据库: {config.DB_PATH}")
            return conn
        except Exception as e:
            logger.error(f"连接数据库失败: {str(e)}")
            raise
    
    def _create_tables(self):
        """创建数据表结构"""
        cursor = self.conn.cursor()
        
        # 创建股票历史数据表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_daily_data (
            stock_code TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            PRIMARY KEY (stock_code, date)
        )
        ''')
        
        # 创建指标数据表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_indicators (
            stock_code TEXT,
            date TEXT,
            ma10 REAL,
            ma20 REAL,
            ma30 REAL,
            ma60 REAL,
            macd REAL,
            macd_signal REAL,
            macd_hist REAL,
            PRIMARY KEY (stock_code, date)
        )
        ''')
        
        # 创建交易记录表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            trade_time TIMESTAMP,
            trade_type TEXT,  -- BUY, SELL
            price REAL,
            volume INTEGER,
            amount REAL,
            trade_id TEXT,
            commission REAL,
            strategy TEXT
        )
        ''')
        
        # 创建持仓表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            stock_code TEXT PRIMARY KEY,
            volume INTEGER,
            cost_price REAL,
            current_price REAL,
            market_value REAL,
            profit_ratio REAL,
            last_update TIMESTAMP
        )
        ''')
        
        # 创建网格交易表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grid_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            grid_level INTEGER,
            buy_price REAL,
            sell_price REAL,
            volume INTEGER,
            status TEXT,  -- PENDING, ACTIVE, COMPLETED
            create_time TIMESTAMP,
            update_time TIMESTAMP
        )
        ''')
        
        self.conn.commit()
        logger.info("数据表结构已创建")
    
    def _init_xtquant(self):
        """初始化迅投行情接口"""
        try:
            # 登录迅投行情API
            result = xt.subscribe_quote(config.STOCK_POOL, 'sse')
            if result:
                logger.info("迅投行情接口初始化成功")
            else:
                logger.error("迅投行情接口初始化失败")
        except Exception as e:
            logger.error(f"初始化迅投行情接口出错: {str(e)}")
    
    def download_history_data(self, stock_code, period=None, start_date=None, end_date=None):
        """
        下载历史行情数据
        
        参数:
        stock_code (str): 股票代码，如 '000001.SZ'
        period (str): 周期，如 '1d', '1h', '30m', '15m', '5m', '1m'
        start_date (str): 开始日期，如 '20210101'
        end_date (str): 结束日期，如 '20210331'
        
        返回:
        pandas.DataFrame: 历史数据
        """
        if period is None:
            period = config.DEFAULT_PERIOD
            
        if start_date is None:
            # 默认获取一年的数据
            start_date = (datetime.now() - timedelta(days=config.INITIAL_DAYS)).strftime('%Y%m%d')
            
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        
        logger.info(f"开始下载 {stock_code} 的历史数据，周期: {period}, 日期范围: {start_date} - {end_date}")
        
        try:
            # 调用迅投API获取历史数据
            df = xt.get_market_data(
                fields=['open', 'high', 'low', 'close', 'volume', 'amount'],
                stock_list=[stock_code],
                period=period,
                start_time=start_date,
                end_time=end_date
            )
            
            if df is None or df.empty:
                logger.warning(f"未获取到 {stock_code} 的历史数据")
                return None
            
            # 重塑数据结构
            if isinstance(df, pd.Panel):
                # Panel格式转为DataFrame
                df = df.loc[stock_code].reset_index()
            elif isinstance(df, pd.DataFrame):
                # 如果已经是DataFrame，检查是否需要处理
                if 'time' not in df.columns and 'date' not in df.columns:
                    # 假设索引是时间
                    df = df.reset_index()
            
            # 统一列名
            df = df.rename(columns={
                'time': 'date',
                'index': 'date'
            })
            
            # 确保date列是字符串格式的日期
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            logger.info(f"成功下载 {stock_code} 的历史数据, 共 {len(df)} 条记录")
            return df
        
        except Exception as e:
            logger.error(f"下载 {stock_code} 的历史数据时出错: {str(e)}")
            return None
    
    def save_history_data(self, stock_code, data_df):
        """
        保存历史数据到数据库
        
        参数:
        stock_code (str): 股票代码
        data_df (pandas.DataFrame): 历史数据
        """
        if data_df is None or data_df.empty:
            logger.warning(f"没有 {stock_code} 的数据可保存")
            return
        
        try:
            # 检查必要的列是否存在
            required_columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
            for col in required_columns:
                if col not in data_df.columns:
                    logger.error(f"{stock_code} 的数据缺少必要的列: {col}")
                    return
            
            # 准备数据
            data_df['stock_code'] = stock_code
            
            # 保存到数据库
            data_df[['stock_code', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']].to_sql(
                'stock_daily_data', 
                self.conn, 
                if_exists='append', 
                index=False,
                method='multi'  # 使用批量插入提高性能
            )
            
            self.conn.commit()
            logger.info(f"已保存 {stock_code} 的历史数据到数据库, 共 {len(data_df)} 条记录")
            
        except Exception as e:
            logger.error(f"保存 {stock_code} 的历史数据时出错: {str(e)}")
            self.conn.rollback()
    
    def get_latest_data(self, stock_code):
        """
        获取最新行情数据
        
        参数:
        stock_code (str): 股票代码
        
        返回:
        dict: 最新行情数据
        """
        try:
            # 调用迅投API获取最新行情
            latest_quote = xt.get_full_tick([stock_code])
            
            if not latest_quote or stock_code not in latest_quote:
                logger.warning(f"未获取到 {stock_code} 的最新行情")
                return None
            
            return latest_quote[stock_code]
            
        except Exception as e:
            logger.error(f"获取 {stock_code} 的最新行情时出错: {str(e)}")
            return None
    
    def get_history_data_from_db(self, stock_code, start_date=None, end_date=None):
        """
        从数据库获取历史数据
        
        参数:
        stock_code (str): 股票代码
        start_date (str): 开始日期，如 '2021-01-01'
        end_date (str): 结束日期，如 '2021-03-31'
        
        返回:
        pandas.DataFrame: 历史数据
        """
        query = "SELECT * FROM stock_daily_data WHERE stock_code=?"
        params = [stock_code]
        
        if start_date:
            query += " AND date>=?"
            params.append(start_date)
            
        if end_date:
            query += " AND date<=?"
            params.append(end_date)
            
        query += " ORDER BY date"
        
        try:
            df = pd.read_sql_query(query, self.conn, params=params)
            logger.debug(f"从数据库获取 {stock_code} 的历史数据, 共 {len(df)} 条记录")
            return df
        except Exception as e:
            logger.error(f"从数据库获取 {stock_code} 的历史数据时出错: {str(e)}")
            return pd.DataFrame()
    
    def update_all_stock_data(self):
        """更新所有股票的历史数据"""
        for stock_code in config.STOCK_POOL:
            self.update_stock_data(stock_code)
            # 避免请求过于频繁
            time.sleep(1)
    
    def update_stock_data(self, stock_code):
        """
        更新单只股票的数据
        
        参数:
        stock_code (str): 股票代码
        """
        # 从数据库获取最新的数据日期
        latest_date_query = "SELECT MAX(date) FROM stock_daily_data WHERE stock_code=?"
        cursor = self.conn.cursor()
        cursor.execute(latest_date_query, (stock_code,))
        result = cursor.fetchone()
        
        if result and result[0]:
            latest_date = result[0]
            # 从最新日期的下一天开始获取
            start_date = (datetime.strptime(latest_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y%m%d')
            logger.info(f"更新 {stock_code} 的数据，从 {start_date} 开始")
        else:
            # 如果没有历史数据，获取完整的历史数据
            start_date = None
            logger.info(f"获取 {stock_code} 的完整历史数据")
        
        # 下载并保存数据
        data_df = self.download_history_data(stock_code, start_date=start_date)
        if data_df is not None and not data_df.empty:
            self.save_history_data(stock_code, data_df)
    
    def start_data_update_thread(self):
        """启动数据更新线程"""
        if not config.ENABLE_DATA_SYNC:
            logger.info("数据同步功能已关闭，不启动更新线程")
            return
            
        if self.update_thread and self.update_thread.is_alive():
            logger.warning("数据更新线程已在运行")
            return
            
        self.stop_flag = False
        self.update_thread = threading.Thread(target=self._data_update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        logger.info("数据更新线程已启动")
    
    def stop_data_update_thread(self):
        """停止数据更新线程"""
        if self.update_thread and self.update_thread.is_alive():
            self.stop_flag = True
            self.update_thread.join(timeout=5)
            logger.info("数据更新线程已停止")
    
    def _data_update_loop(self):
        """数据更新循环"""
        while not self.stop_flag:
            try:
                # 判断是否在交易时间
                if config.is_trade_time():
                    logger.info("开始更新所有股票数据")
                    self.update_all_stock_data()
                    logger.info("股票数据更新完成")
                
                # 等待下一次更新
                for _ in range(config.UPDATE_INTERVAL):
                    if self.stop_flag:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"数据更新循环出错: {str(e)}")
                time.sleep(60)  # 出错后等待一分钟再继续
    
    def close(self):
        """关闭数据管理器"""
        self.stop_data_update_thread()
        
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")
            
        # 取消行情订阅
        xt.unsubscribe_quote(config.STOCK_POOL)
        logger.info("已取消行情订阅")


# 单例模式
_instance = None

def get_data_manager():
    """获取DataManager单例"""
    global _instance
    if _instance is None:
        _instance = DataManager()
    return _instance
