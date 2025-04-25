import unittest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime

# 假设你的代码文件名为 position_manager.py 和 config.py
# 导入需要测试的类和函数
from position_manager import PositionManager, get_position_manager
from data_manager import DataManager, get_data_manager
import config


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

    def tearDown(self):
        """测试后的清理工作"""
        # 清空持仓数据
        self.position_manager.conn.execute("DELETE FROM positions")
        self.position_manager.conn.commit()

    def create_mock_position(self, stock_code, volume, cost_price, current_price, profit_triggered=False, highest_price=None):
        """创建模拟持仓数据"""
        self.position_manager.update_position(stock_code, volume, cost_price, current_price, profit_triggered, highest_price)

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_stop_loss_triggered(self, mock_get_latest_data):
        """测试触发止损"""
        # 设置止损比例为-10%
        config.STOP_LOSS_RATIO = -0.10

        # 模拟行情数据
        mock_get_latest_data.return_value = {'lastPrice': 90}

        # 创建持仓，成本价100，当前价90，亏损10%
        self.create_mock_position("TEST_STOCK", 100, 100, 90)

        # 检查止损
        result = self.position_manager.check_stop_loss("TEST_STOCK")
        self.assertTrue(result)

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_stop_loss_not_triggered(self, mock_get_latest_data):
        """测试未触发止损"""
        # 设置止损比例为-10%
        config.STOP_LOSS_RATIO = -0.10

        # 模拟行情数据
        mock_get_latest_data.return_value = {'lastPrice': 95}

        # 创建持仓，成本价100，当前价95，亏损5%
        self.create_mock_position("TEST_STOCK", 100, 100, 95)

        # 检查止损
        result = self.position_manager.check_stop_loss("TEST_STOCK")
        self.assertFalse(result)

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_stop_loss_no_position(self, mock_get_latest_data):
        """测试没有持仓时，不触发止损"""
        # 设置止损比例为-10%
        config.STOP_LOSS_RATIO = -0.10

        # 模拟行情数据
        mock_get_latest_data.return_value = {'lastPrice': 90}

        # 不创建持仓
        # 检查止损
        result = self.position_manager.check_stop_loss("TEST_STOCK")
        self.assertFalse(result)

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_initial(self, mock_get_latest_data):
        """测试触发首次止盈（盈利5%）"""
        # 设置首次止盈比例为5%
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True  # 开启动态止盈

        # 模拟行情数据
        mock_get_latest_data.return_value = {'lastPrice': 105}

        # 创建持仓，成本价100，当前价105，盈利5%
        self.create_mock_position("TEST_STOCK", 100, 100, 105)

        # 检查止盈
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'HALF')

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_full(self, mock_get_latest_data):
        """测试触发动态止盈（全仓）"""
        # 设置动态止盈配置
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]

        # 创建持仓，成本价100，当前价110，盈利10%
        self.create_mock_position("TEST_STOCK", 100, 100, 110, profit_triggered=True, highest_price=110)

        # 模拟行情数据
        mock_get_latest_data.return_value = {'lastPrice': 101}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 101, profit_triggered=True, highest_price=110)

        # 检查止盈
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'FULL')

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_not_triggered(self, mock_get_latest_data):
        """测试未触发动态止盈"""
        # 设置动态止盈配置
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]

        # 创建持仓，成本价100，当前价109，盈利9%
        self.create_mock_position("TEST_STOCK", 100, 100, 109, profit_triggered=True, highest_price=109)

        # 检查止盈
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_multi_level(self, mock_get_latest_data):
        """测试多级动态止盈"""
        # 设置动态止盈配置
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]

        # 创建持仓，成本价100，当前价111，盈利11%
        self.create_mock_position("TEST_STOCK", 100, 100, 111, profit_triggered=True, highest_price=111)

        # 检查止盈
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)

        # 模拟行情数据
        mock_get_latest_data.return_value = {'lastPrice': 102}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 102, profit_triggered=True, highest_price=111)

        # 检查止盈
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'FULL')

        # 模拟行情数据
        mock_get_latest_data.return_value = {'lastPrice': 116}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 116, profit_triggered=True, highest_price=116)

        # 检查止盈
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)

        # 模拟行情数据
        mock_get_latest_data.return_value = {'lastPrice': 100}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 100, profit_triggered=True, highest_price=116)

        # 检查止盈
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'FULL')

        # 再次检查，确保不会触发INITIAL_TAKE_PROFIT_RATIO
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)

    @patch('data_manager.DataManager.get_latest_data')
    def test_stop_loss_after_initial_take_profit(self, mock_get_latest_data):
        """测试首次止盈后触发止损"""
        # 设置止损比例为-10%
        config.STOP_LOSS_RATIO = -0.10
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True

        # 1. 模拟触发首次止盈
        mock_get_latest_data.return_value = {'lastPrice': 105}
        self.create_mock_position("TEST_STOCK", 100, 100, 105)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'HALF')

        # 2. 模拟价格下跌，触发止损
        mock_get_latest_data.return_value = {'lastPrice': 89}  # 跌破首次止盈后的止损线
        self.position_manager.update_position("TEST_STOCK", 50, 100, 89, profit_triggered=True, highest_price=105)
        result = self.position_manager.check_stop_loss("TEST_STOCK")
        self.assertTrue(result)

    @patch('data_manager.DataManager.get_latest_data')
    def test_dynamic_take_profit_after_initial_take_profit(self, mock_get_latest_data):
        """测试首次止盈后触发动态止盈"""
        # 设置动态止盈配置
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]

        # 1. 模拟触发首次止盈
        mock_get_latest_data.return_value = {'lastPrice': 105}
        self.create_mock_position("TEST_STOCK", 100, 100, 105)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'HALF')

        # 2. 模拟价格上涨到110，然后下跌到101，触发动态止盈
        mock_get_latest_data.return_value = {'lastPrice': 110}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 110, profit_triggered=True, highest_price=110)
        mock_get_latest_data.return_value = {'lastPrice': 101}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 101, profit_triggered=True, highest_price=110)
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertTrue(result)
        self.assertEqual(take_profit_type, 'FULL')

    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_no_position(self, mock_get_latest_data):
        """测试没有持仓时，不触发动态止盈"""
        # 设置动态止盈配置
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]

        # 不创建持仓
        # 检查止盈
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)
    
    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_disable(self, mock_get_latest_data):
        """测试关闭动态止盈"""
        # 设置动态止盈配置
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = False
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]

        # 创建持仓，成本价100，当前价110，盈利10%
        self.create_mock_position("TEST_STOCK", 100, 100, 110, profit_triggered=False, highest_price=110)

        # 模拟行情数据
        mock_get_latest_data.return_value = {'lastPrice': 101}
        self.position_manager.update_position("TEST_STOCK", 100, 100, 101, profit_triggered=False, highest_price=110)

        # 检查止盈
        result, take_profit_type = self.position_manager.check_dynamic_take_profit("TEST_STOCK")
        self.assertFalse(result)
        self.assertIsNone(take_profit_type)
        
    @patch('data_manager.DataManager.get_latest_data')
    def test_check_dynamic_take_profit_highest_price_update(self, mock_get_latest_data):
        """测试最高价更新"""
        # 设置动态止盈配置
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [(0.10, 0.93), (0.15, 0.90), (0.30, 0.87), (float('inf'), 0.85)]

        # 创建持仓，成本价100，当前价105，盈利5%
        self.create_mock_position("TEST_STOCK", 100, 100, 105, profit_triggered=True, highest_price=105)
        
        # 模拟行情数据
        mock_get_latest_data.return_value = {'lastPrice': 110}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 110, profit_triggered=True, highest_price=110)
        
        position = self.position_manager.get_position("TEST_STOCK")
        self.assertEqual(position['highest_price'], 110)
        
        # 模拟行情数据
        mock_get_latest_data.return_value = {'lastPrice': 100}
        self.position_manager.update_position("TEST_STOCK", 50, 100, 100, profit_triggered=True, highest_price=110)
        
        position = self.position_manager.get_position("TEST_STOCK")
        self.assertEqual(position['highest_price'], 110)

if __name__ == '__main__':
    unittest.main()
