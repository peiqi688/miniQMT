#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
卖出策略测试模块
测试各种卖出规则的触发条件和执行逻辑
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from sell_strategy import SellStrategy
from logger import get_logger

logger = get_logger("test_sell_strategy")

class TestSellStrategy(unittest.TestCase):
    """卖出策略测试类"""
    
    def setUp(self):
        """测试前准备"""
        # Mock各个依赖模块
        self.mock_data_manager = Mock()
        self.mock_position_manager = Mock()
        self.mock_trading_executor = Mock()
        
        # 创建卖出策略实例
        with patch('sell_strategy.get_data_manager', return_value=self.mock_data_manager), \
             patch('sell_strategy.get_position_manager', return_value=self.mock_position_manager), \
             patch('sell_strategy.get_trading_executor', return_value=self.mock_trading_executor):
            self.sell_strategy = SellStrategy()
    
    def test_rule1_high_open_drawdown(self):
        """测试规则1：高开后回落卖出"""
        stock_code = "000001.SZ"
        
        # 模拟数据
        yesterday_close = 10.0
        open_price = 10.5  # 高开5%
        high_price = 10.8  # 最高价比开盘价高2.86%
        current_price = 10.6  # 从最高点回落1.85%
        
        position = {'volume': 1000}
        
        # Mock方法
        self.sell_strategy._get_yesterday_close = Mock(return_value=yesterday_close)
        self.sell_strategy._execute_sell = Mock(return_value=True)
        
        # 设置配置
        config.SELL_RULE1_RISE_THRESHOLD = 0.02  # 2%
        config.SELL_RULE1_DRAWDOWN_THRESHOLD = 0.015  # 1.5%
        
        # 执行测试
        result = self.sell_strategy._check_rule1(stock_code, open_price, high_price, current_price, position)
        
        # 验证结果
        self.assertTrue(result)
        self.sell_strategy._execute_sell.assert_called_once()
    
    def test_rule2_low_open_drawdown(self):
        """测试规则2：低开后回落卖出"""
        stock_code = "000001.SZ"
        
        # 模拟数据
        yesterday_close = 10.0
        open_price = 9.8   # 低开2%
        high_price = 10.3  # 最高价比开盘价高5.1%
        current_price = 10.0  # 从最高点回落2.9%
        
        position = {'volume': 1000}
        
        # Mock方法
        self.sell_strategy._get_yesterday_close = Mock(return_value=yesterday_close)
        self.sell_strategy._execute_sell = Mock(return_value=True)
        
        # 设置配置
        config.SELL_RULE2_RISE_THRESHOLD = 0.05  # 5%
        config.SELL_RULE2_DRAWDOWN_THRESHOLD = 0.025  # 2.5%
        
        # 执行测试
        result = self.sell_strategy._check_rule2(stock_code, open_price, high_price, current_price, position)
        
        # 验证结果
        self.assertTrue(result)
        self.sell_strategy._execute_sell.assert_called_once()
    
    def test_rule5_end_of_day_sell(self):
        """测试规则5：尾盘卖出"""
        stock_code = "000001.SZ"
        position = {'volume': 1000}
        
        # Mock方法
        self.mock_data_manager.get_latest_data.return_value = {
            'lastPrice': 10.0,
            'upperLimit': 11.0
        }
        self.sell_strategy._execute_sell = Mock(return_value=True)
        
        # 设置配置
        config.SELL_RULE5_ENABLE = True
        
        # Mock时间为尾盘时间
        with patch('sell_strategy.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 14, 57, 0)  # 14:57
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Mock交易时间检查
            self.sell_strategy._is_trading_time = Mock(return_value=True)
            
            # 执行测试
            result = self.sell_strategy._check_rule5(stock_code, position)
            
            # 验证结果
            self.assertTrue(result)
            self.sell_strategy._execute_sell.assert_called_once()
    
    def test_rule8_max_drawdown(self):
        """测试规则8：最大回撤卖出"""
        stock_code = "000001.SZ"
        position = {'volume': 1000}
        
        # 设置股票状态
        self.sell_strategy.stock_states[stock_code] = {
            'max_drawdown': 0.06  # 6%回撤
        }
        
        # Mock方法
        self.sell_strategy._execute_sell = Mock(return_value=True)
        
        # 设置配置
        config.SELL_RULE8_MAX_DRAWDOWN = 0.05  # 5%
        
        # 执行测试
        result = self.sell_strategy._check_rule8(stock_code, position)
        
        # 验证结果
        self.assertTrue(result)
        self.sell_strategy._execute_sell.assert_called_once()
    
    def test_check_sell_signals_integration(self):
        """测试check_sell_signals集成功能"""
        stock_code = "000001.SZ"
        
        # Mock数据
        self.mock_position_manager.get_position.return_value = {'volume': 1000}
        self.mock_data_manager.get_latest_data.return_value = {
            'lastPrice': 10.5
        }
        
        # Mock今日数据
        self.sell_strategy._get_today_market_data = Mock(return_value={
            'open': 10.0,
            'high': 10.8
        })
        
        # Mock冷却时间检查
        self.sell_strategy._is_in_cooldown = Mock(return_value=False)
        
        # Mock规则检查（让规则1返回True）
        self.sell_strategy._check_rule1 = Mock(return_value=True)
        
        # 执行测试
        result = self.sell_strategy.check_sell_signals(stock_code)
        
        # 验证结果
        self.assertIsNotNone(result)
        self.assertEqual(result['rule'], '规则1-高开回落')
        self.assertEqual(result['stock_code'], stock_code)
    
    def test_cooldown_mechanism(self):
        """测试冷却机制"""
        stock_code = "000001.SZ"
        
        # 设置冷却时间
        self.sell_strategy.trade_cooldown[stock_code] = datetime.now()
        config.SELL_STRATEGY_COOLDOWN_SECONDS = 30
        
        # 测试冷却期内
        result = self.sell_strategy._is_in_cooldown(stock_code)
        self.assertTrue(result)
        
        # 测试冷却期外
        self.sell_strategy.trade_cooldown[stock_code] = datetime.now() - timedelta(seconds=35)
        result = self.sell_strategy._is_in_cooldown(stock_code)
        self.assertFalse(result)
    
    def test_trading_time_check(self):
        """测试交易时间检查"""
        # 测试交易时间内
        trading_time = datetime(2024, 1, 15, 10, 30, 0)  # 周一上午10:30
        result = self.sell_strategy._is_trading_time(trading_time)
        self.assertTrue(result)
        
        # 测试非交易时间
        non_trading_time = datetime(2024, 1, 15, 12, 0, 0)  # 中午12:00
        result = self.sell_strategy._is_trading_time(non_trading_time)
        self.assertFalse(result)
        
        # 测试周末
        weekend_time = datetime(2024, 1, 13, 10, 30, 0)  # 周六
        result = self.sell_strategy._is_trading_time(weekend_time)
        self.assertFalse(result)

if __name__ == '__main__':
    # 设置测试配置
    config.ENABLE_SELL_STRATEGY = True
    config.SELL_STRATEGY_CHECK_INTERVAL = 1
    config.SELL_STRATEGY_COOLDOWN_SECONDS = 30
    
    # 运行测试
    unittest.main(verbosity=2)