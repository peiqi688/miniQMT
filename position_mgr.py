# -*- coding:gbk -*-
from xtquant.xttype import PositionData
from config import Config

class PositionManager:
    def __init__(self):
        self.positions = {}
        
    def update(self, context):
        """更新持仓数据"""
        for pos in context.positions:
            self.positions[pos.stock_code] = {
                'total': pos.amount,
                'available': pos.enable_amount,
                'avg_cost': pos.open_price,
                'profit': pos.position_pnl
            }
            
    @property
    def total_assets(self):
        return sum(p['total']*p['avg_cost'] for p in self.positions.values())
    
    @property
    def max_profit_ratio(self):
        return max([p['profit']/p['avg_cost'] for p in self.positions.values()], default=0)
    
    @property
    def available_cash(self):
        return self.context.cash  # 需从context获取
