import time
import datetime
from miniqmt import MqApi

class AutoStopStrategy:
    def __init__(self, api, stock_code, stop_loss_pct=0.05, stop_profit_pct=0.1):
        """初始化策略参数"""
        self.api = api
        self.stock_code = stock_code
        self.stop_loss_pct = stop_loss_pct  # 止损百分比
        self.stop_profit_pct = stop_profit_pct  # 止盈百分比
        self.highest_price = 0  # 记录最高价
        self.buy_price = 0  # 买入价格
        self.has_position = False  # 是否持有仓位
        self.order_id = None  # 委托ID
        self.rule_triggered = None  # 触发的规则
        
    def start(self):
        """启动策略"""
        print(f"开始监控股票: {self.stock_code}")
        
        # 订阅行情
        self.api.subscribe_quote(self.stock_code)
        
        # 获取初始持仓信息
        self._update_position()
        
        # 主循环
        while True:
            # 更新行情数据
            quote = self.api.get_quote(self.stock_code)
            if not quote:
                time.sleep(1)
                continue
                
            current_price = quote['last_price']
            
            # 如果没有持仓，检查是否需要买入
            if not self.has_position:
                # 这里可以添加买入逻辑
                time.sleep(1)
                continue
                
            # 更新最高价
            if current_price > self.highest_price:
                self.highest_price = current_price
                
            # 检查是否是开盘
            now = datetime.datetime.now()
            is_open = (now.hour == 9 and now.minute >= 30) or (now.hour > 9 and now.hour < 15)
            
            # 规则1: 高开且最高价超过开盘价1%
            if is_open and now.hour == 9 and now.minute < 35:
                open_price = quote['open_price']
                if open_price > self.buy_price * 1.01 and current_price > open_price * 1.01:
                    self._sell_stock(1)
                    continue
            
            # 规则2: 低开且最高价超过开盘价2%
            if is_open and now.hour == 9 and now.minute < 35:
                open_price = quote['open_price']
                if open_price < self.buy_price * 0.99 and current_price > open_price * 1.02:
                    self._sell_stock(2)
                    continue
            
            # 规则3: 涨幅超过3%后回落1%
            if (self.highest_price >= self.buy_price * 1.03 and 
                current_price <= self.highest_price * 0.99):
                self._sell_stock(3)
                continue
            
            # 规则4: 止损
            if current_price <= self.buy_price * (1 - self.stop_loss_pct):
                self._sell_stock(4)
                continue
            
            # 规则5: 止盈
            if current_price >= self.buy_price * (1 + self.stop_profit_pct):
                self._sell_stock(5)
                continue
            
            # 规则6: 尾盘卖出
            if is_open and now.hour == 14 and now.minute >= 57:
                self._sell_stock(6)
                continue
            
            # 规则7: 涨停炸板前卖出
            if (self.highest_price >= self.buy_price * 1.097 and 
                current_price <= self.highest_price * 0.99):
                self._sell_stock(7)
                continue
            
            # 检查委托状态
            if self.order_id:
                order_status = self.api.get_order_status(self.order_id)
                if order_status == 'FILLED':
                    self.order_id = None
                    self.has_position = False
                    print(f"委托已成交，触发规则: {self.rule_triggered}")
                elif order_status == 'CANCELED':
                    self.order_id = None
                    print("委托已取消")
            
            time.sleep(1)  # 每秒检查一次
    
    def _update_position(self):
        """更新持仓信息"""
        positions = self.api.get_positions()
        for pos in positions:
            if pos['stock_code'] == self.stock_code:
                self.has_position = True
                self.buy_price = pos['cost_price']
                self.highest_price = max(self.highest_price, self.buy_price)
                print(f"当前持有 {self.stock_code}，买入价: {self.buy_price}")
                return
        self.has_position = False
        print(f"当前未持有 {self.stock_code}")
    
    def _sell_stock(self, rule_num):
        """卖出股票"""
        if not self.has_position or self.order_id:
            return
            
        positions = self.api.get_positions()
        for pos in positions:
            if pos['stock_code'] == self.stock_code:
                volume = pos['volume']
                if volume > 0:
                    # 获取最新价格
                    quote = self.api.get_quote(self.stock_code)
                    if not quote:
                        return
                        
                    current_price = quote['last_price']
                    # 以卖一价委托卖出
                    sell_price = quote['ask_price1']
                    
                    self.order_id = self.api.sell(self.stock_code, sell_price, volume)
                    self.rule_triggered = rule_num
                    print(f"触发规则{rule_num}，委托卖出 {self.stock_code}，数量: {volume}，价格: {sell_price}")
                break

# 使用示例
if __name__ == "__main__":
    # 初始化API
    api = MqApi()
    api.login("你的账号", "你的密码")
    
    # 创建策略实例
    strategy = AutoStopStrategy(api, "600000.SH")  # 以上海浦东发展银行为例
    
    # 启动策略
    try:
        strategy.start()
    except KeyboardInterrupt:
        print("策略已停止")
    finally:
        api.logout()
