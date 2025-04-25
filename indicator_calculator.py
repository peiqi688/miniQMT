"""
指标计算模块，负责计算各种技术指标
"""
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime
from MyTT import *

import config
from logger import get_logger
from data_manager import get_data_manager

# 获取logger
logger = get_logger("indicator_calculator")

class IndicatorCalculator:
    """指标计算类"""
    
    def __init__(self):
        """初始化指标计算器"""
        self.data_manager = get_data_manager()
        self.conn = self.data_manager.conn
    
    def calculate_all_indicators(self, stock_code, force_update=False):
        """
        计算所有技术指标
        
        参数:
        stock_code (str): 股票代码
        force_update (bool): 是否强制更新所有数据的指标
        
        返回:
        bool: 是否计算成功
        """
        try:
            # 获取历史数据
            df = self.data_manager.get_history_data_from_db(stock_code)
            if df.empty:
                logger.warning(f"没有 {stock_code} 的历史数据，无法计算指标")
                return False
            
            # 按日期排序
            df = df.sort_values('date')
            
            # 如果不是强制更新，检查是否有新数据需要计算
            if not force_update:
                # 获取指标表中的最新日期
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT MAX(date) FROM stock_indicators WHERE stock_code=?", 
                    (stock_code,)
                )
                result = cursor.fetchone()
                latest_indicator_date = result[0] if result and result[0] else None
                
                # 如果没有新数据，不需要计算
                if latest_indicator_date:
                    latest_df_date = df['date'].max()
                    if latest_indicator_date >= latest_df_date:
                        logger.debug(f"{stock_code} 的指标已是最新，不需要更新")
                        return True
                    
                    # 只获取新数据部分
                    df = df[df['date'] > latest_indicator_date]
                    if df.empty:
                        logger.debug(f"{stock_code} 没有新的数据需要计算指标")
                        return True
            
            # 计算各种指标
            result_df = pd.DataFrame()
            result_df['stock_code'] = df['stock_code']
            result_df['date'] = df['date']
            
            # 计算均线指标
            for period in config.MA_PERIODS:
                ma_col = f'ma{period}'
                result_df[ma_col] = self._calculate_ma(df, period)
            
            # 计算MACD指标
            macd_df = self._calculate_macd(df)
            for col in macd_df.columns:
                result_df[col] = macd_df[col]
            
            # 保存指标结果到数据库
            self._save_indicators(result_df)
            
            logger.info(f"成功计算 {stock_code} 的技术指标，共 {len(result_df)} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"计算 {stock_code} 的技术指标时出错: {str(e)}")
            return False
    
    def _calculate_ma(self, df, period):
        """
        计算移动平均线
        
        参数:
        df (pandas.DataFrame): 历史数据
        period (int): 周期
        
        返回:
        pandas.Series: 移动平均线数据
        """
        try:
            # 使用talib计算MA
            ma = SMA(df['close'].values, timeperiod=period)
            return ma
        except Exception as e:
            logger.error(f"计算MA{period}指标时出错: {str(e)}")
            return pd.Series([None] * len(df))
    
    def _calculate_macd(self, df):
        """
        计算MACD指标
        
        参数:
        df (pandas.DataFrame): 历史数据
        
        返回:
        pandas.DataFrame: MACD指标数据
        """
        try:
            # 使用talib计算MACD
            macd, signal, hist = MACD(
                df['close'].values,
                fastperiod=config.MACD_FAST,
                slowperiod=config.MACD_SLOW,
                signalperiod=config.MACD_SIGNAL
            )
            
            # 创建结果DataFrame
            result = pd.DataFrame({
                'macd': macd,
                'macd_signal': signal,
                'macd_hist': hist
            })
            
            return result
        except Exception as e:
            logger.error(f"计算MACD指标时出错: {str(e)}")
            # 返回空的DataFrame
            return pd.DataFrame({
                'macd': [None] * len(df),
                'macd_signal': [None] * len(df),
                'macd_hist': [None] * len(df)
            })
    
    def _save_indicators(self, df):
        """
        保存指标到数据库
        
        参数:
        df (pandas.DataFrame): 指标数据
        """
        try:
            # 处理NaN值
            df = df.replace({np.nan: None})
            
            # 保存到数据库
            df.to_sql('stock_indicators', self.conn, if_exists='append', index=False, method='multi')
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"保存指标数据时出错: {str(e)}")
            self.conn.rollback()
    
    def get_latest_indicators(self, stock_code):
        """
        获取最新的指标数据
        
        参数:
        stock_code (str): 股票代码
        
        返回:
        dict: 最新指标数据
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM stock_indicators 
                WHERE stock_code=? 
                ORDER BY date DESC 
                LIMIT 1
            """, (stock_code,))
            
            row = cursor.fetchone()
            if not row:
                logger.warning(f"未找到 {stock_code} 的指标数据")
                return None
            
            # 获取列名
            columns = [description[0] for description in cursor.description]
            
            # 转换为字典
            indicators = dict(zip(columns, row))
            return indicators
            
        except Exception as e:
            logger.error(f"获取 {stock_code} 的最新指标数据时出错: {str(e)}")
            return None
    
    def get_indicators_history(self, stock_code, days=60):
        """
        获取历史指标数据
        
        参数:
        stock_code (str): 股票代码
        days (int): 获取最近的天数
        
        返回:
        pandas.DataFrame: 历史指标数据
        """
        try:
            query = f"""
                SELECT * FROM stock_indicators 
                WHERE stock_code=? 
                ORDER BY date DESC 
                LIMIT {days}
            """
            
            df = pd.read_sql_query(query, self.conn, params=(stock_code,))
            
            # 按日期排序（从早到晚）
            df = df.sort_values('date')
            
            return df
            
        except Exception as e:
            logger.error(f"获取 {stock_code} 的历史指标数据时出错: {str(e)}")
            return pd.DataFrame()
    
    def check_buy_signal(self, stock_code):
        """
        检查买入信号
        
        参数:
        stock_code (str): 股票代码
        
        返回:
        bool: 是否有买入信号
        """
        try:
            # 获取最近的指标数据
            indicators_df = self.get_indicators_history(stock_code, days=10)
            if indicators_df.empty:
                logger.warning(f"没有足够的 {stock_code} 指标数据来检查买入信号")
                return False
            
            # 计算MACD金叉信号
            if len(indicators_df) >= 2:
                # 检查前一天MACD柱为负，当天MACD柱为正（MACD金叉）
                prev_hist = indicators_df.iloc[-2]['macd_hist']
                curr_hist = indicators_df.iloc[-1]['macd_hist']
                
                macd_cross = prev_hist < 0 and curr_hist > 0
                
                # 检查均线多头排列（MA10 > MA20 > MA30 > MA60）
                latest = indicators_df.iloc[-1]
                ma_alignment = (
                    latest['ma10'] > latest['ma20'] > 
                    latest['ma30'] > latest['ma60']
                )
                
                # 检查是否满足买入条件
                if macd_cross and ma_alignment:
                    logger.info(f"{stock_code} 满足买入条件: MACD金叉 + 均线多头排列")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"检查 {stock_code} 的买入信号时出错: {str(e)}")
            return False
    
    def check_sell_signal(self, stock_code):
        """
        检查卖出信号
        
        参数:
        stock_code (str): 股票代码
        
        返回:
        bool: 是否有卖出信号
        """
        try:
            # 获取最近的指标数据
            indicators_df = self.get_indicators_history(stock_code, days=10)
            if indicators_df.empty:
                logger.warning(f"没有足够的 {stock_code} 指标数据来检查卖出信号")
                return False
            
            # 计算MACD死叉信号
            if len(indicators_df) >= 2:
                # 检查前一天MACD柱为正，当天MACD柱为负（MACD死叉）
                prev_hist = indicators_df.iloc[-2]['macd_hist']
                curr_hist = indicators_df.iloc[-1]['macd_hist']
                
                macd_cross = prev_hist > 0 and curr_hist < 0
                
                # 检查均线空头排列（MA10 < MA20 < MA30 < MA60）
                latest = indicators_df.iloc[-1]
                ma_alignment = (
                    latest['ma10'] < latest['ma20'] < 
                    latest['ma30'] < latest['ma60']
                )
                
                # 检查是否满足卖出条件
                if macd_cross and ma_alignment:
                    logger.info(f"{stock_code} 满足卖出条件: MACD死叉 + 均线空头排列")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"检查 {stock_code} 的卖出信号时出错: {str(e)}")
            return False
    
    def update_all_stock_indicators(self, force_update=False):
        """
        更新所有股票的技术指标
        
        参数:
        force_update (bool): 是否强制更新所有数据的指标
        """
        for stock_code in config.STOCK_POOL:
            self.calculate_all_indicators(stock_code, force_update)


# 单例模式
_instance = None

def get_indicator_calculator():
    """获取IndicatorCalculator单例"""
    global _instance
    if _instance is None:
        _instance = IndicatorCalculator()
    return _instance
