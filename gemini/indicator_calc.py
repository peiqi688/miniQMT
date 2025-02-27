# -*- coding:gbk -*-
import pandas as pd
import numpy as np
from config import Config

class IndicatorCalculator:
    @staticmethod
    def calculate_emas(df, periods=Config.HISTORY_PERIODS):
        """多周期EMA计算"""
        for period in periods:
            if isinstance(period, str): continue  # 跳过周期字符串
            col_name = f'EMA_{period}'
            try:
                df[col_name] = df['close'].ewm(
                    span=period, 
                    adjust=False
                ).mean().round(2)
            except Exception as e:
                print(f"EMA计算错误 {period}: {str(e)}")
                df[col_name] = np.nan
        return df
    
    @staticmethod 
    def calculate_macd(df, fast=12, slow=26, signal=9):
        """MACD指标计算"""
        try:
            ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
            ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
            df['DIF'] = ema_fast - ema_slow
            df['DEA'] = df['DIF'].ewm(span=signal, adjust=False).mean()
            df['MACD'] = 2 * (df['DIF'] - df['DEA'])
        except Exception as e:
            print(f"MACD计算错误: {str(e)}")
            df[['DIF','DEA','MACD']] = np.nan
        return df
