# -*- coding:gbk -*-
from xtquant.xttype import ContextInfo
from xtquant import xtdata
from config import Config
from trade_executor import TradeExecutor
import logging

class RiskManager:
    def __init__(self, context: ContextInfo):
        self.context = context
        self.logger = logging.getLogger('risk')
        self.last_check_time = None
        
    def check_system_risk(self):
        """实时风险扫描"""
        # 获取账户完整信息[^2]
        account = self.context.get_account(Config.TRADE_ACCOUNT)
        
        # 1. 整体账户风控
        if not self._check_account_risk(account):
            return False
            
        # 2. 持仓标的风险
        return self._check_position_risk()
        
    def _check_account_risk(self, account):
        """账户级风控"""
        # 实时风险度控制[^1]
        if account.m_dRealRiskDegree > Config.RISK_DEGREE_LIMIT:
            self.logger.critical(f"实时风险度超标 {account.m_dRealRiskDegree}")
            self._force_liquidation()
            return False
            
        # 维持担保比例[^2]
        if account.m_dPerAssurescaleValue < Config.MARGIN_CALL_RATIO:
            self.logger.error(f"担保比例不足 {account.m_dPerAssurescaleValue}")
            return False
            
        # 单日最大亏损
        if account.m_dDailyLoss > Config.DAILY_LOSS_LIMIT:
            self.logger.error("触发单日最大亏损限制")
            return False
            
        return True
        
    def _check_position_risk(self):
        """持仓级风控"""
        for pos in self.context.positions:
            # 获取实时行情[^1]
            tick = xtdata.get_full_tick([pos.stock_code])[0]
            
            # 动态止盈止损
            self._dynamic_stop(pos, tick)
            
            # 波动率控制
            if tick.last_volume > Config.VOLUME_ALERT:
                self.logger.warning(f"{pos.stock_code}异常成交量")
                self._reduce_position(pos, 0.5)
                
        return True
        
    def _dynamic_stop(self, position, tick_data):
        """动态止盈止损逻辑"""
        current_price = tick_data['price']
        max_price = position.max_price
        cost_price = position.open_price
        
        # 回撤止盈
        if (max_price - current_price)/max_price > Config.PROFIT_RETRACE:
            self.logger.info(f"{position.stock_code}触发回撤止盈")
            TradeExecutor().smart_order(
                position.stock_code,
                current_price,
                -position.enable_amount
            )
            
        # 移动止损
        if current_price < cost_price * (1 - Config.TRAILING_STOP):
            self.logger.info(f"{position.stock_code}触发移动止损")
            TradeExecutor().smart_order(
                position.stock_code,
                current_price,
                -position.enable_amount
            )
    
    def _force_liquidation(self):
        """强制平仓流程"""
        positions = sorted(
            self.context.positions,
            key=lambda x: x.position_pnl,
            reverse=True  # 优先平盈利仓位
        )
        
        for pos in positions[:Config.LIQUIDATION_NUM]:
            TradeExecutor().market_order(
                pos.stock_code,
                -pos.enable_amount
            )
