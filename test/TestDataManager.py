import unittest
import pandas as pd
import sqlite3
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta

import config
from data_manager import DataManager, get_data_manager

class TestDataManager(unittest.TestCase):
    """测试DataManager类"""
    data_manager = None

    @classmethod
    def setUpClass(cls):
        """在所有测试开始前执行一次"""
        # 使用内存数据库进行测试，避免影响实际数据库
        config.DB_PATH = ":memory:"
        cls.data_manager = get_data_manager()
        
        # Mock xtquant.xtdata
        cls.mock_xt = patch('data_manager.xt').start()

    @classmethod
    def tearDownClass(cls):
        """在所有测试结束后执行一次"""
        # 关闭数据库连接
        cls.data_manager.close()
        # Stop all patches
        patch.stopall()

    def setUp(self):
        """测试前的准备工作"""
        # 清空数据表
        self.data_manager.conn.execute("DELETE FROM stock_daily_data")
        self.data_manager.conn.execute("DELETE FROM stock_indicators")
        self.data_manager.conn.commit()

    def tearDown(self):
        """测试后的清理工作"""
        pass

    def create_mock_data(self, stock_code, start_date, end_date):
        """创建模拟数据"""
        dates = pd.date_range(start_date, end_date)
        data = {
            'date': dates,
            'open': [10.0] * len(dates),
            'high': [12.0] * len(dates),
            'low': [9.0] * len(dates),
            'close': [11.0] * len(dates),
            'volume': [1000] * len(dates),
            'amount': [100000] * len(dates)
        }
        df = pd.DataFrame(data)
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        df['stock_code'] = stock_code
        return df

    def test_connect_db(self):
        """测试数据库连接"""
        self.assertIsNotNone(self.data_manager.conn)
        self.assertIsInstance(self.data_manager.conn, sqlite3.Connection)

    def test_create_tables(self):
        """测试创建数据表"""
        cursor = self.data_manager.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        self.assertIn('stock_daily_data', tables)
        self.assertIn('stock_indicators', tables)
        self.assertIn('trade_records', tables)
        self.assertIn('positions', tables)
        self.assertIn('grid_trades', tables)

    def test_download_history_data(self):
        """测试下载历史数据"""
        # Mock xt.download_history_data and xt.get_market_data_ex
        mock_data = {
            '600000.SH': {
                'date': ['2023-01-01', '2023-01-02'],
                'open': [10.0, 11.0],
                'high': [12.0, 13.0],
                'low': [9.0, 10.0],
                'close': [11.0, 12.0],
                'volume': [1000, 2000],
                'amount': [100000, 200000]
            }
        }
        self.mock_xt.get_market_data_ex.return_value = mock_data
        self.mock_xt.download_history_data.return_value = None
        
        df = self.data_manager.download_history_data('600000.SH', start_date='20230101', end_date='20230102')
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 2)
        self.assertEqual(df['date'].iloc[0], '2023-01-01')
        self.assertEqual(df['date'].iloc[1], '2023-01-02')
        self.assertEqual(df['open'].iloc[0], 10.0)
        self.assertEqual(df['close'].iloc[1], 12.0)
        self.assertEqual(df['volume'].iloc[0], 1000)
        self.assertEqual(df['amount'].iloc[1], 200000)

    def test_save_history_data(self):
        """测试保存历史数据"""
        df = self.create_mock_data('600000.SH', '2023-01-01', '2023-01-02')
        self.data_manager.save_history_data('600000.SH', df)
        
        # 验证数据是否保存到数据库
        cursor = self.data_manager.conn.cursor()
        cursor.execute("SELECT * FROM stock_daily_data WHERE stock_code='600000.SH'")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], '600000.SH')
        self.assertEqual(rows[0][1], '2023-01-01')
        self.assertEqual(rows[0][2], 10.0)
        self.assertEqual(rows[1][5], 11.0)
        self.assertEqual(rows[1][6], 1000)
        self.assertEqual(rows[1][7], 100000)

    @patch('data_manager.xt.get_full_tick')
    def test_get_latest_data(self, mock_get_full_tick):
        """测试获取最新行情数据"""
        mock_get_full_tick.return_value = {
            '600000.SH': {
                'lastPrice': 15.0,
                'volume': 1000,
                'amount': 100000
            }
        }
        
        latest_data = self.data_manager.get_latest_data('600000.SH')
        self.assertIsNotNone(latest_data)
        self.assertEqual(latest_data['lastPrice'], 15.0)
        self.assertEqual(latest_data['volume'], 1000)
        self.assertEqual(latest_data['amount'], 100000)

    def test_get_history_data_from_db(self):
        """测试从数据库获取历史数据"""
        df = self.create_mock_data('600000.SH', '2023-01-01', '2023-01-02')
        self.data_manager.save_history_data('600000.SH', df)
        
        # 获取所有数据
        df_all = self.data_manager.get_history_data_from_db('600000.SH')
        self.assertEqual(len(df_all), 2)
        
        # 获取指定日期范围内的数据
        df_part = self.data_manager.get_history_data_from_db('600000.SH', start_date='2023-01-02')
        self.assertEqual(len(df_part), 1)
        self.assertEqual(df_part['date'].iloc[0], '2023-01-02')
        
        # 获取不存在的数据
        df_none = self.data_manager.get_history_data_from_db('600001.SH')
        self.assertTrue(df_none.empty)

    def test_update_stock_data(self):
        """测试更新股票数据"""
        # Mock xt.download_history_data and xt.get_market_data_ex
        mock_data = {
            '600000.SH': {
                'date': ['2023-01-03', '2023-01-04'],
                'open': [13.0, 14.0],
                'high': [15.0, 16.0],
                'low': [12.0, 13.0],
                'close': [14.0, 15.0],
                'volume': [3000, 4000],
                'amount': [300000, 400000]
            }
        }
        self.mock_xt.get_market_data_ex.return_value = mock_data
        self.mock_xt.download_history_data.return_value = None
        
        # 先保存一些历史数据
        df = self.create_mock_data('600000.SH', '2023-01-01', '2023-01-02')
        self.data_manager.save_history_data('600000.SH', df)
        
        # 更新数据
        self.data_manager.update_stock_data('600000.SH')
        
        # 验证数据是否更新到数据库
        cursor = self.data_manager.conn.cursor()
        cursor.execute("SELECT * FROM stock_daily_data WHERE stock_code='600000.SH'")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[2][1], '2023-01-03')
        self.assertEqual(rows[3][1], '2023-01-04')
        self.assertEqual(rows[3][5], 15.0)
        self.assertEqual(rows[2][6], 3000)
        self.assertEqual(rows[3][7], 400000)

    def test_update_all_stock_data(self):
        """测试更新所有股票数据"""
        # Mock xt.download_history_data and xt.get_market_data_ex
        mock_data = {
            '600000.SH': {
                'date': ['2023-01-03'],
                'open': [13.0],
                'high': [15.0],
                'low': [12.0],
                'close': [14.0],
                'volume': [3000],
                'amount': [300000]
            },
            '000001.SZ': {
                'date': ['2023-01-03'],
                'open': [13.0],
                'high': [15.0],
                'low': [12.0],
                'close': [14.0],
                'volume': [3000],
                'amount': [300000]
            }
        }
        self.mock_xt.get_market_data_ex.return_value = mock_data
        self.mock_xt.download_history_data.return_value = None
        
        # 设置股票池
        config.STOCK_POOL = ['600000.SH', '000001.SZ']
        
        # 先保存一些历史数据
        df1 = self.create_mock_data('600000.SH', '2023-01-01', '2023-01-02')
        self.data_manager.save_history_data('600000.SH', df1)
        df2 = self.create_mock_data('000001.SZ', '2023-01-01', '2023-01-02')
        self.data_manager.save_history_data('000001.SZ', df2)
        
        # 更新所有股票数据
        self.data_manager.update_all_stock_data()
        
        # 验证数据是否更新到数据库
        cursor = self.data_manager.conn.cursor()
        cursor.execute("SELECT * FROM stock_daily_data WHERE stock_code='600000.SH'")
        rows1 = cursor.fetchall()
        self.assertEqual(len(rows1), 3)
        
        cursor.execute("SELECT * FROM stock_daily_data WHERE stock_code='000001.SZ'")
        rows2 = cursor.fetchall()
        self.assertEqual(len(rows2), 3)

    @patch('data_manager.DataManager._data_update_loop')
    def test_start_stop_data_update_thread(self, mock_data_update_loop):
        """测试启动和停止数据更新线程"""
        # 启动线程
        self.data_manager.start_data_update_thread()
        self.assertTrue(self.data_manager.update_thread.is_alive())
        
        # 停止线程
        self.data_manager.stop_data_update_thread()
        self.assertFalse(self.data_manager.update_thread.is_alive())
        
        # 再次启动线程
        self.data_manager.start_data_update_thread()
        self.assertTrue(self.data_manager.update_thread.is_alive())
        
        # 再次停止线程
        self.data_manager.stop_data_update_thread()
        self.assertFalse(self.data_manager.update_thread.is_alive())

    def test_close(self):
        """测试关闭数据管理器"""
        pass

if __name__ == '__main__':
    unittest.main()
