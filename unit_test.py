import unittest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime

import config
from position_manager import PositionManager, get_position_manager

class TestPositionManagerCalculateStopLossPrice(unittest.TestCase):
    """测试PositionManager的calculate_stop_loss_price方法"""

    def setUp(self):
        """测试前的准备工作"""
        # 创建一个PositionManager实例
        self.position_manager = get_position_manager()
        # 清空持仓数据
        self.position_manager.conn.execute("DELETE FROM positions")
        self.position_manager.conn.commit()
        # 重置配置参数
        config.STOP_LOSS_RATIO = -0.095
        config.INITIAL_TAKE_PROFIT_RATIO = 0.05
        config.ENABLE_DYNAMIC_STOP_PROFIT = True
        config.DYNAMIC_TAKE_PROFIT = [
            (0.05, 0.96),  # 建仓后最高价涨幅曾大于5%时，止盈位为最高价*96%
            (0.10, 0.93),  # 建仓后最高价涨幅曾大于10%时，止盈位为最高价*93%
            (0.15, 0.90),  # 建仓后最高价涨幅曾大于15%时，止盈位为最高价*90%
            (0.30, 0.87),  # 建仓后最高价涨幅曾大于30%时，止盈位为最高价*87%
            (0.40, 0.85)   # 建仓后最高价涨幅曾大于40%时，止盈位为最高价*85%
        ]

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
            (0.05, 0.96),  # 建仓后最高价涨幅曾大于5%时，止盈位为最高价*96%
            (0.10, 0.93),  # 建仓后最高价涨幅曾大于10%时，止盈位为最高价*93%
            (0.15, 0.90),  # 建仓后最高价涨幅曾大于15%时，止盈位为最高价*90%
            (0.30, 0.87),  # 建仓后最高价涨幅曾大于30%时，止盈位为最高价*87%
            (0.40, 0.85)   # 建仓后最高价涨幅曾大于40%时，止盈位为最高价*85%
        ]

    def test_calculate_stop_loss_price_fixed(self):
        """测试固定止损"""
        config.STOP_LOSS_RATIO = -0.10
        cost_price = 100.0
        highest_price = 100.0
        profit_triggered = False
        
        stop_loss_price = self.position_manager.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
        self.assertAlmostEqual(stop_loss_price, 90.0,places=2)

    def test_calculate_stop_loss_price_dynamic_level1(self):
        """测试动态止损-第一级"""
        cost_price = 100.0
        highest_price = 105.0  # 盈利5%
        profit_triggered = True
        
        stop_loss_price = self.position_manager.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
        self.assertAlmostEqual(stop_loss_price, 100.8,places=2) #105*0.96

    def test_calculate_stop_loss_price_dynamic_level2(self):
        """测试动态止损-第二级"""
        cost_price = 100.0
        highest_price = 110.0  # 盈利10%
        profit_triggered = True
        
        stop_loss_price = self.position_manager.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
        self.assertAlmostEqual(stop_loss_price, 102.3,places=2) #110*0.93
    
    def test_calculate_stop_loss_price_dynamic_level3(self):
        """测试动态止损-第三级"""
        cost_price = 100.0
        highest_price = 115.0  # 盈利15%
        profit_triggered = True
        
        stop_loss_price = self.position_manager.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
        self.assertAlmostEqual(stop_loss_price, 103.5,places=2) #115*0.90

    def test_calculate_stop_loss_price_dynamic_level4(self):
        """测试动态止损-第四级"""
        cost_price = 100.0
        highest_price = 130.0  # 盈利30%
        profit_triggered = True
        
        stop_loss_price = self.position_manager.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
        self.assertAlmostEqual(stop_loss_price, 113.1,places=2) #130*0.87

    def test_calculate_stop_loss_price_dynamic_level5(self):
        """测试动态止损-第五级"""
        cost_price = 100.0
        highest_price = 150.0  # 盈利50%
        profit_triggered = True
        
        stop_loss_price = self.position_manager.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
        self.assertAlmostEqual(stop_loss_price, 127.5,places=2) #150*0.85

    def test_calculate_stop_loss_price_dynamic_no_profit(self):
        """测试动态止损-未盈利"""
        cost_price = 100.0
        highest_price = 90.0
        profit_triggered = True
        
        stop_loss_price = self.position_manager.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
        self.assertAlmostEqual(stop_loss_price, 87.3,places=2) #90*0.97

    def test_calculate_stop_loss_price_dynamic_no_profit_triggered(self):
        """测试动态止损-未触发止盈"""
        config.STOP_LOSS_RATIO = -0.10
        cost_price = 100.0
        highest_price = 110.0
        profit_triggered = False
        
        stop_loss_price = self.position_manager.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
        self.assertAlmostEqual(stop_loss_price, 90.0,places=2)

    def test_calculate_stop_loss_price_zero_cost(self):
        """测试成本为0的情况"""
        cost_price = 0.0
        highest_price = 110.0
        profit_triggered = False
        
        stop_loss_price = self.position_manager.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
        self.assertAlmostEqual(stop_loss_price, 0.0,places=2)

    def test_calculate_stop_loss_price_dynamic_empty_config(self):
        """测试动态止损配置为空的情况"""
        config.DYNAMIC_TAKE_PROFIT = []
        cost_price = 100.0
        highest_price = 110.0
        profit_triggered = True
        
        stop_loss_price = self.position_manager.calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
        self.assertAlmostEqual(stop_loss_price, 106.7,places=2)  #110*0.97

if __name__ == '__main__':
    unittest.main()
