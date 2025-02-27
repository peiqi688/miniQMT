# -*- coding:gbk -*-
from xtquant.xttype import ContextInfo
from xtquant import xtdata
from config import Config
from trade_executor import TradeExecutor
from position_mgr import PositionManager
import logging

class TradingStrategy:
    def __init__(self, context):
        self.context = context
        self.position = PositionManager()
        self.logger = logging.getLogger('strategy')
        
    def on_tick(self):
        """事件驱动主逻辑[^6]"""
        # 获取最新行情
        tick_data = xtdata.get_full_tick([self.context.stock_code])[0]
        current_price = tick_data['price']
        
        # 执行网格交易
        if current_price < self.position.avg_cost * (1-Config.GRID_INTERVAL):
            self._grid_add_position(current_price)
            
        # 动态止盈
        if self.position.max_profit_ratio > 0.15:
            self._dynamic_profit_control(current_price)
            
    def _grid_add_position(self, price):
        """网格补仓逻辑"""
        order_amount = min(
            Config.MAX_ORDER_AMOUNT,
            self.position.available_cash // (price * 1.01)  # 考虑手续费
        )
        if order_amount > 0:
            TradeExecutor().smart_order(
                symbol=self.context.stock_code,
                price=round(price * 0.995, 2),  # 挂低0.5%[^1]
                amount=order_amount
            )
            self.logger.info(f"网格补仓 {order_amount}股 @{price}")
            
    def _dynamic_profit_control(self, current_price):
        """动态止盈"""
        if current_price > self.position.high_price * 0.97:
            close_amount = int(self.position.total_amount * 0.3)
            TradeExecutor().smart_order(
                symbol=self.context.stock_code,
                price=current_price,
                amount=-close_amount
            )
            self.logger.info(f"止盈平仓 {close_amount}股")
