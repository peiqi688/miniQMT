import time
from xtquant.xttype import StockAccount
from config import Config
from data_fetcher import fetch_history_data
from trade_engine import TradeEngine

def main():
    # 初始化交易引擎
    session_id = 123456
    account = StockAccount('YOUR_ACCOUNT_ID')
    trader = TradeEngine(session_id)
    
    while True:
        # 获取实时数据
        stock_list = ['600000.SH', '000001.SZ']
        hist_data = fetch_history_data(stock_list)
        
        # 执行交易策略
        trader.auto_trade(hist_data)
        
        # 监控持仓风险
        if trader.position_manager.check_risk() == 'FULL_STOP':
            trader.close_all_positions()
            
        time.sleep(60)  # 每分钟轮询一次

if __name__ == "__main__":
    main()
