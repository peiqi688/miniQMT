# -*- coding:gbk -*-
from xtquant import xttrader
from config import Config
import logging

class TradeExecutor:
    def __init__(self):
        self.trader = xttrader.XtQuantTrader(Config.TRADE_ACCOUNT)
        self.logger = logging.getLogger('trade')
        
    def smart_order(self, symbol, price, amount):
        """智能下单"""
        # 价格调整
        bid3 = xtdata.get_order_book(symbol)['BidPrice3']
        ask3 = xtdata.get_order_book(symbol) ['AskPrice3']
        final_price = bid3 if amount >0 else ask3  # 对手价[^5]
        
        # 大单拆分
        while abs(amount) > Config.MAX_ORDER_AMOUNT:
            chunk = Config.MAX_ORDER_AMOUNT if amount>0 else -Config.MAX_ORDER_AMOUNT
            self._submit_order(symbol, final_price, chunk)
            amount -= chunk
            
        if amount !=0:
            self._submit_order(symbol, final_price, amount)
            
    def _submit_order(self, symbol, price, amount):
        order_id = self.trader.order(
            stock_code=symbol,
            price=price,
            volume=abs(amount),
            direction=1 if amount>0 else 2,
            order_volume_condition=1  # 立即成交剩余转限价[^1]
        )
        self.logger.info(f"委托提交 {symbol} {amount}@{price} ID:{order_id}")
