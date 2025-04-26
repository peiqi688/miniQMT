import unittest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime

# 导入需要测试的类和函数
from position_manager import PositionManager, get_position_manager
from data_manager import DataManager, get_data_manager
import config
import sqlite3

class TestPositionManagerStopLossTakeProfit(unittest.TestCase):
    """测试PositionManager的止损止盈逻辑，确保100%覆盖率"""

    def setUp(self):
        """测试前的准备工作"""
        # 创建一个PositionManager实例
        self.position_manager = get_position_manager()
        # 清空持仓数据
        self.position_manager.conn.execute("DELETE FROM positions")
        self.position_manager.conn.commit()
        self.data_manager = get_data_manager()

        # Mock easy_qmt_trader.position()
        self.mock_qmt_position = patch.object(self.position_manager.qmt_trader, 'position').start()
        self.addCleanup(patch.stopall)  # Stop all patches after the test

    def tearDown(self):
        """测试后的清理工作"""
        # 清空持仓数据
        self.position_manager.conn.execute("DELETE FROM positions")
        self.position_manager.conn.commit()
        # 重置配置参数
        config.STOP_LOSS_RATIO = -0.095
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [
            (0.10, 0.93),
            (0.15, 0.90),
            (0.30, 0.87),
            (float('inf'), 0.85)
        ]
        # Stop all patches
        patch.stopall()

    def create_mock_position(self, stock_code, volume, cost_price, current_price, profit_triggered=False, highest_price=None):
        """创建模拟持仓数据"""
        self.position_manager.update_position(stock_code, volume, cost_price, current_price, profit_triggered, highest_price)

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_stop_loss_triggered(self, mock_get_latest_data):
        """测试触发止损"""
        config.STOP_LOSS_RATIO = -0.10
        self.mock_qmt_position.return_value = pd.DataFrame()
        mock_get_latest_data.return_value = {'lastPrice': 90}
        self.create_mock_position("TEST_STOCK", 100, 100, 90)
        result = self.position_manager.check_stop_loss("TEST_STOCK")
        print(f"\n[test_check_stop_loss_triggered] 止损触发: {result}")
        self.assertTrue(result)

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_stop_loss_not_triggered(self, mock_get_latest_data):
        """测试未触发止损"""
        config.STOP_LOSS_RATIO = -0.10
        self.mock_qmt_position.return_value = pd.DataFrame()
        mock_get_latest_data.return_value = {'lastPrice': 95}
        self.create_mock_position("TEST_STOCK", 100, 100, 95)
        result = self.position_manager.check_stop_loss("TEST_STOCK")
        print(f"\n[test_check_stop_loss_not_triggered] 止损触发: {result}")
        self.assertFalse(result)

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_stop_loss_no_position(self, mock_get_latest_data):
        """测试没有持仓时，不触发止损"""
        config.STOP_LOSS_RATIO = -0.10
        self.mock_qmt_position.return_value = pd.DataFrame()
        mock_get_latest_data.return_value = {'lastPrice': 90}
        result = self.position_manager.check_stop_loss("TEST_STOCK")
        print(f"\n[test_check_stop_loss_no_position] 止损触发: {result}")
        self.assertFalse(result)

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_initial(self, mock_get_latest_data):
        """测试触发首次止盈（盈利5%）"""
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        self.mock_qmt_position.return_value = pd.DataFrame()
        mock_get_latest_data.return_value = {'lastPrice': 105}
        self.create_mock_position("TEST_STOCK", 100, 100, 105)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_initial] 首次止盈触发: {result}, 止盈类型: {take_profit_type}")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'HALF')

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_full(self, mock_get_latest_data):
        """测试触发动态止盈（全仓）"""
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]
        self.mock_qmt_position.return_value = pd.DataFrame()
        self.create_mock_position("TEST_STOCK", 100, 100, 110, profit_triggered=True, highest_price=110)
        mock_get_latest_data.return_value = {'lastPrice': 101}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 101, profit_triggered=True, highest_price=110)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_full] 动态止盈触发: {result}, 止盈类型: {take_profit_type}")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'FULL')

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_not_triggered(self, mock_get_latest_data):
        """测试未触发动态止盈"""
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]
        self.mock_qmt_position.return_value = pd.DataFrame()
        self.create_mock_position("TEST_STOCK", 100, 100, 109, profit_triggered=True, highest_price=109)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_not_triggered] 动态止盈触发: {result}, 止盈类型: {take_profit_type}")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_multi_level(self, mock_get_latest_data):
        """测试多级动态止盈"""
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]
        self.mock_qmt_position.return_value = pd.DataFrame()
        self.create_mock_position("TEST_STOCK", 100, 100, 111, profit_triggered=True, highest_price=111)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_multi_level] 动态止盈触发: {result}, 止盈类型: {take_profit_type}")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)

        mock_get_latest_data.return_value = {'lastPrice': 102}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 102, profit_triggered=True, highest_price=111)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_multi_level] 动态止盈触发: {result}, 止盈类型: {take_profit_type}")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'FULL')

        mock_get_latest_data.return_value = {'lastPrice': 116}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 116, profit_triggered=True, highest_price=116)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_multi_level] 动态止盈触发: {result}, 止盈类型: {take_profit_type}")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)

        mock_get_latest_data.return_value = {'lastPrice': 100}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 100, profit_triggered=True, highest_price=116)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_multi_level] 动态止盈触发: {result}, 止盈类型: {take_profit_type}")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'FULL')

        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_multi_level] 动态止盈触发: {result}, 止盈类型: {take_profit_type}")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)

    @patch('data_manager.DataManager.get_latest_data')
    def test_stop_loss_after_initial_take_profit(self, mock_get_latest_data):
        """测试首次止盈后触发止损"""
        config.STOP_LOSS_RATIO = -0.10
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        self.mock_qmt_position.return_value = pd.DataFrame()
        mock_get_latest_data.return_value = {'lastPrice': 105}
        self.create_mock_position("TEST_STOCK", 100, 100, 105)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'HALF')
        mock_get_latest_data.return_value = {'lastPrice': 89}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 89, profit_triggered=True, highest_price=105)
        result = self.position_manager.check_stop_loss("TEST_STOCK")
        print(f"\n[test_stop_loss_after_initial_take_profit] 止损触发: {result}")
        self.assertTrue(result)

    @patch('data_manager.DataManager.get_latest_data')
    def test_dynamic_take_profit_after_initial_take_profit(self, mock_get_latest_data):
        """测试首次止盈后触发动态止盈"""
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]
        self.mock_qmt_position.return_value = pd.DataFrame()
        mock_get_latest_data.return_value = {'lastPrice': 105}
        self.create_mock_position("TEST_STOCK", 100, 100, 105)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'HALF')
        mock_get_latest_data.return_value = {'lastPrice': 110}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 110, profit_triggered=True, highest_price=110)
        mock_get_latest_data.return_value = {'lastPrice': 101}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 101, profit_triggered=True, highest_price=110)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        print(f"\n[test_dynamic_take_profit_after_initial_take_profit] 动态止盈触发: {result}, 止盈类型: {take_profit_type}")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'FULL')

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_no_position(self, mock_get_latest_data):
        """测试没有持仓时，不触发动态止盈"""
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]
        self.mock_qmt_position.return_value = pd.DataFrame()
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_no_position] 动态止盈触发: {result}, 止盈类型: {take_profit_type}")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)
    
    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_disable(self, mock_get_latest_data):
        """测试关闭动态止盈"""
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = False
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]
        self.mock_qmt_position.return_value = pd.DataFrame()
        self.create_mock_position("TEST_STOCK", 100, 100, 110, profit_triggered=False, highest_price=110)
        mock_get_latest_data.return_value = {'lastPrice': 101}
        self.position_manager.update_position("TEST_STOCK", 100, 100, 101, profit_triggered=False, highest_price=110)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_disable] 动态止盈触发: {result}, 止盈类型: {take_profit_type}")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)
        
    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_highest_price_update(self, mock_get_latest_data):
        """测试最高价更新"""
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]
        self.mock_qmt_position.return_value = pd.DataFrame()
        self.create_mock_position("TEST_STOCK", 100, 100, 105, profit_triggered=True, highest_price=105)
        mock_get_latest_data.return_value = {'lastPrice': 110}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 110, profit_triggered=True, highest_price=110)
        position = self.position_manager.get_position("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_highest_price_update] 最高价更新: {position['highest_price']}")
        self.assertEqual(position['highest_price'], 110)
        mock_get_latest_data.return_value = {'lastPrice': 100}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 100, profit_triggered=True, highest_price=110)
        position = self.position_manager.get_position("TEST_STOCK")
        print(f"\n[test_check_dynamic_take_profit_highest_price_update] 最高价更新: {position['highest_price']}")
        self.assertEqual(position['highest_price'], 110)
    
    @patch('data_manager.DataManager.get_latest_data')
    def test_stop_loss_after_dynamic_take_profit(self, mock_get_latest_data):
        """测试动态止盈后触发止损"""
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]
        config.STOP_LOSS_RATIO = -0.10
        self.mock_qmt_position.return_value = pd.DataFrame()
        mock_get_latest_data.return_value = {'lastPrice': 105}
        self.create_mock_position("TEST_STOCK", 100, 100, 105)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'HALF')
        mock_get_latest_data.return_value = {'lastPrice': 110}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 110, profit_triggered=True, highest_price=110)
        mock_get_latest_data.return_value = {'lastPrice': 101}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 101, profit_triggered=True, highest_price=110)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'FULL')
        mock_get_latest_data.return_value = {'lastPrice': 89}
        self.position_manager.update_position("TEST_STOCK", 0, 100, 89, profit_triggered=True, highest_price=110)
        result = self.position_manager.check_stop_loss("TEST_STOCK")
        print(f"\n[test_stop_loss_after_dynamic_take_profit] 止损触发: {result}")
        self.assertFalse(result)

    @patch('data_manager.DataManager.get_latest_data')
    def test_dynamic_take_profit_multi_level_and_stop_loss(self, mock_get_latest_data):
        """测试多级动态止盈和止损"""
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]
        config.STOP_LOSS_RATIO = -0.10
        self.mock_qmt_position.return_value = pd.DataFrame()
        mock_get_latest_data.return_value = {'lastPrice': 105}
        self.create_mock_position("TEST_STOCK", 100, 100, 105)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'HALF')
        mock_get_latest_data.return_value = {'lastPrice': 120}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 120, profit_triggered=True, highest_price=120)
        mock_get_latest_data.return_value = {'lastPrice': 100}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 100, profit_triggered=True, highest_price=120)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)
        mock_get_latest_data.return_value = {'lastPrice': 89}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 89, profit_triggered=True, highest_price=120)
        result = self.position_manager.check_stop_loss("TEST_STOCK")
        print(f"\n[test_dynamic_take_profit_multi_level_and_stop_loss] 止损触发: {result}")
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
