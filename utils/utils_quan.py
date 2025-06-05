from xtquant import xtdata
from xtquant.xttrader import XtQuantTrader
from xtquant.xttype import StockAccount
from xtquant import xtconstant
import time
from datetime import datetime, timedelta

class SmallCapStrategy:
    def __init__(self, account):
        """
        初始化策略
        :param account: 交易账户
        """
        self.account = account
        self.xt_trader = XtQuantTrader(account)
        
        # 策略参数
        self.benchmark = '000300.SH'  # 基准指数
        self.stock_num = 3            # 持仓数量
        self.holding_days = 5         # 持有天数
        self.market_cap_min = 20      # 最小市值(亿)
        self.market_cap_max = 30      # 最大市值(亿)
        
        # 状态变量
        self.trade_days = 0           # 交易日计数器
        self.current_positions = {}   # 当前持仓 {股票代码: {'amount': 数量, 'buy_price': 价格, 'buy_date': 日期}}
        self.last_trade_date = None   # 上次交易日期
        
        # 初始化数据订阅
        self.subscribe_data()
        
    def subscribe_data(self):
        """订阅所需数据"""
        xtdata.subscribe_quote(self.benchmark)
        xtdata.subscribe_full([], ['lastPrice'])
        xtdata.subscribe_fundamental([], 'market_cap')
    
    def run(self):
        """运行策略"""
        print("小市值股票轮动策略开始运行...")
        while True:
            current_date = datetime.now().strftime('%Y%m%d')
            
            # 只在交易日执行
            if self.is_trading_day(current_date):
                if current_date != self.last_trade_date:
                    self.last_trade_date = current_date
                    self.trade_days += 1
                    print(f"\n交易日: {current_date}, 运行第 {self.trade_days} 天")
                    
                    # 执行交易逻辑
                    self.handle_data()
            
            # 每分钟检查一次
            time.sleep(60)
    
    def is_trading_day(self, date_str):
        """检查是否为交易日"""
        # 这里简化为只检查工作日，实际应使用交易所日历
        date = datetime.strptime(date_str, '%Y%m%d')
        return date.weekday() < 5  # 周一到周五
    
    def handle_data(self):
        """每日交易逻辑"""
        # 检查是否需要调仓(每5个交易日调仓一次)
        if self.trade_days % self.holding_days == 0:
            print("执行调仓操作...")
            
            # 获取符合条件的股票列表
            target_stocks = self.select_stocks()
            print(f"目标股票: {target_stocks}")
            
            # 执行调仓
            self.rebalance_portfolio(target_stocks)
        
        # 打印当前持仓
        self.print_positions()
    
    def select_stocks(self):
        """筛选市值介于20-30亿且市值最小的三只股票"""
        print("开始筛选股票...")
        
        # 获取全市场股票
        all_stocks = xtdata.get_stock_list_in_sector('沪深A股')
        stock_data = []
        
        for stock in all_stocks:
            try:
                # 获取市值数据(单位:亿)
                market_cap = xtdata.get_fundamental_data(stock, 'market_cap')
                
                if market_cap and self.market_cap_min <= market_cap <= self.market_cap_max:
                    # 获取当前价格检查是否停牌
                    price_data = xtdata.get_full_tick([stock])
                    if stock in price_data and price_data[stock]['lastPrice'] > 0:
                        stock_data.append((stock, market_cap))
            except Exception as e:
                print(f"获取股票 {stock} 数据时出错: {e}")
                continue
        
        # 按市值升序排序
        stock_data.sort(key=lambda x: x[1])
        
        # 取市值最小的三只股票
        selected_stocks = [stock[0] for stock in stock_data[:self.stock_num]]
        
        return selected_stocks
    
    def rebalance_portfolio(self, target_stocks):
        """调整持仓到目标股票"""
        if not target_stocks:
            print("没有符合条件的股票，清空持仓")
            self.clear_positions()
            return
        
        print("开始调整持仓...")
        
        # 1. 卖出不在目标列表中的持仓
        stocks_to_sell = [stock for stock in self.current_positions if stock not in target_stocks]
        for stock in stocks_to_sell:
            self.order_target(stock, 0)
            if stock in self.current_positions:
                del self.current_positions[stock]
        
        # 2. 计算可用资金
        account_info = self.xt_trader.query_stock_asset(self.account)
        available_cash = account_info.cash
        
        # 如果有持仓需要调整，先等卖出资金到账
        if stocks_to_sell:
            print("等待卖出资金结算...")
            time.sleep(3)  # 简单等待，实际应检查订单状态
            account_info = self.xt_trader.query_stock_asset(self.account)
            available_cash = account_info.cash
        
        # 3. 买入目标股票
        cash_per_stock = available_cash / len(target_stocks)
        
        for stock in target_stocks:
            if stock in self.current_positions:
                continue  # 已经持有该股票
                
            # 获取当前价格
            price_data = xtdata.get_full_tick([stock])
            if stock not in price_data or price_data[stock]['lastPrice'] <= 0:
                print(f"股票 {stock} 价格数据无效，跳过")
                continue
                
            price = price_data[stock]['lastPrice']
            amount = int(cash_per_stock / price / 100) * 100  # 按手数取整
            
            if amount > 0:
                success = self.order_value(stock, cash_per_stock)
                if success:
                    self.current_positions[stock] = {
                        'amount': amount,
                        'buy_price': price,
                        'buy_date': self.last_trade_date
                    }
    
    def clear_positions(self):
        """清空所有持仓"""
        for stock in list(self.current_positions.keys()):
            self.order_target(stock, 0)
            del self.current_positions[stock]
    
    def order_target(self, stock, target_amount):
        """
        调整股票到目标数量
        :return: 是否下单成功
        """
        current_amount = self.current_positions.get(stock, {}).get('amount', 0)
        delta = target_amount - current_amount
        
        if delta == 0:
            return True
            
        print(f"调整 {stock} 持仓: 当前 {current_amount}, 目标 {target_amount}")
        
        try:
            if delta > 0:
                # 买入
                order_type = xtconstant.STOCK_BUY
                action = "买入"
            else:
                # 卖出
                order_type = xtconstant.STOCK_SELL
                action = "卖出"
                delta = -delta
            
            # 获取当前价格
            price_data = xtdata.get_full_tick([stock])
            if stock not in price_data or price_data[stock]['lastPrice'] <= 0:
                print(f"股票 {stock} 价格数据无效，无法下单")
                return False
                
            price = price_data[stock]['lastPrice']
            
            # 下单
            order_id = self.xt_trader.order_stock(
                self.account,
                stock_code=stock,
                order_type=order_type,
                order_volume=delta,
                price_type=xtconstant.LATEST_PRICE,
                price=price,
                strategy_name='小市值策略',
                order_comment=f'调仓{action}'
            )
            
            if order_id:
                print(f"{action} {stock} 下单成功, 数量 {delta}, 价格 {price}, 订单ID {order_id}")
                return True
            else:
                print(f"{action} {stock} 下单失败")
                return False
                
        except Exception as e:
            print(f"{action} {stock} 时发生错误: {e}")
            return False
    
    def order_value(self, stock, value):
        """
        按价值下单
        :return: 是否下单成功
        """
        try:
            # 获取当前价格
            price_data = xtdata.get_full_tick([stock])
            if stock not in price_data or price_data[stock]['lastPrice'] <= 0:
                print(f"股票 {stock} 价格数据无效，无法下单")
                return False
                
            price = price_data[stock]['lastPrice']
            amount = int(value / price / 100) * 100  # 按手数取整
            
            if amount <= 0:
                print(f"股票 {stock} 计算数量为0，跳过")
                return False
                
            # 下单
            order_id = self.xt_trader.order_stock(
                self.account,
                stock_code=stock,
                order_type=xtconstant.STOCK_BUY,
                order_volume=amount,
                price_type=xtconstant.LATEST_PRICE,
                price=price,
                strategy_name='小市值策略',
                order_comment='价值买入'
            )
            
            if order_id:
                print(f"买入 {stock} 下单成功, 数量 {amount}, 价格 {price}, 订单ID {order_id}")
                return True
            else:
                print(f"买入 {stock} 下单失败")
                return False
                
        except Exception as e:
            print(f"买入 {stock} 时发生错误: {e}")
            return False
    
    def print_positions(self):
        """打印当前持仓"""
        if not self.current_positions:
            print("当前无持仓")
            return
            
        print("\n当前持仓:")
        total_value = 0
        account_info = self.xt_trader.query_stock_asset(self.account)
        
        for stock, pos in self.current_positions.items():
            # 获取当前价格
            price_data = xtdata.get_full_tick([stock])
            current_price = price_data[stock]['lastPrice'] if stock in price_data else pos['buy_price']
            market_value = current_price * pos['amount']
            total_value += market_value
            
            profit = (current_price - pos['buy_price']) / pos['buy_price'] * 100
            
            print(f"{stock}: 数量 {pos['amount']}, 成本价 {pos['buy_price']:.2f}, "
                  f"现价 {current_price:.2f}, 市值 {market_value:.2f}, "
                  f"盈亏 {profit:.2f}%")
        
        print(f"\n总持仓市值: {total_value:.2f}")
        print(f"可用资金: {account_info.cash:.2f}")
        print(f"总资产: {account_info.total_asset:.2f}")

if __name__ == '__main__':
    # 替换为你的MiniQMT账号
    # account = StockAccount('你的客户号', 'STOCK')
    
    # # 创建并运行策略
    # strategy = SmallCapStrategy(account)
    # strategy.run()
    select_stocks(self)