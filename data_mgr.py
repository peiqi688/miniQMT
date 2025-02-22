# -*- coding:gbk -*-
from xtquant import xtdata
import h5py
import sqlite3
import pandas as pd
from config import Config

class DataManager:
    def __init__(self):
        self.h5_file = 'market_data.h5'
        self.conn = sqlite3.connect('metadata.db')
        self._init_database()
        
    def _init_database(self):
        """创建元数据表"""
        self.conn.execute('''CREATE TABLE IF NOT EXISTS symbol_info
            (symbol TEXT PRIMARY KEY, 
             last_update TEXT)''')
            
    def get_history_data(self, symbol, period):
        """增量获取历史数据"""
        last_update = self._get_last_update(symbol)
        new_data = xtdata.get_market_data(
            field_list=[], 
            stock_list=[symbol],
            period=period,
            start_time=last_update,
            dividend_type='front_ratio',  # 前复权[^4]
            fill_data=True
        )
        
        # HDF5存储
        with h5py.File(self.h5_file, 'a') as f:
            group = f.require_group(symbol)
            dataset = group.require_dataset(
                period,
                shape=(0,),
                maxshape=(None,),
                dtype='f8'
            )
            dataset.resize((dataset.shape[0] + len(new_data),))
            dataset[-len(new_data):] = new_data
        
        # 更新元数据
        self.conn.execute('''REPLACE INTO symbol_info 
            VALUES (?, ?)''', (symbol, new_data[-1]['time']))
        self.conn.commit()
        
        return pd.DataFrame(new_data)
    
    def _get_last_update(self, symbol):
        cursor = self.conn.execute('''SELECT last_update 
            FROM symbol_info WHERE symbol=?''', (symbol,))
        result = cursor.fetchone()
        return result[0] if result else '20000101'
