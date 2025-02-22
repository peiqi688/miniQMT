from xtquant.xttrader import XtQuantTrader
import config

class TradeEngine:
    def __init__(self, session_id):
        self.trader = XtQuantTrader(session_id)
        self.positions = {}  # 记录持仓信息
        
    def auto_trade(self, signals):
        """
        根据信号执行自动交易
        """
        for stock, signal in signals.items():
            current_price = self.get_real_price(stock)
            position = self.positions.get(stock, 0)
            
            # 执行补仓逻辑
            if signal == 'BUY' and position < config.MAX_POSITION:
                self.execute_order(stock, 'BUY', config.INIT_CAPITAL/current_price)
                
            # 执行止盈止损
            elif signal == 'SELL' and position > 0:
                self.execute_order(stock, 'SELL', position)

    def manual_trade(self, stock, direction, amount):
        """手动交易接口"""
        return self.execute_order(stock, direction, amount)
    
    # 其他交易相关方法...
