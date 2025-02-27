import pandas as pd
import numpy as np
from xtquant import xtdata
import datetime

def get_sector_flow():
    # 同步板块数据[^3]
    xtdata.download_sector_data()
    
    # 获取近10个交易日日期（两周）
    trade_dates = xtdata.get_trading_dates('SH', end_time=datetime.datetime.now().strftime('%Y%m%d'), count=10)[::-1]
    
    result = []
    for date in trade_dates:
        # 获取当日所有板块
        sectors = xtdata.get_sector_list()
        sector_flows = []
        
        for sector in sectors:
            # 获取板块成分股[^3]
            stocks = xtdata.get_stock_list_in_sector(sector)
            
# ... existing code ...
            # 获取当日成交额和市值
            mv_data = xtdata.get_market_data(field_list=['total_mv'], stock_list=stocks, period='1d', end_time=date, count=1)
            amount_data = xtdata.get_market_data(field_list=['amount'], stock_list=stocks, period='1d', end_time=date, count=1)
            
            # 确保获取完整的Series数据
            mv = mv_data['total_mv'].iloc[0] if not mv_data.empty else pd.Series()
            amount = amount_data['amount'].iloc[0] if not amount_data.empty else pd.Series()
# ... existing code ...
       
            # 计算资金市值比[^1]
            valid = (mv > 0) & (amount > 0)
            flow_ratio = (amount[valid] / mv[valid]).sum()
            
            # 记录板块资金流
            sector_flows.append((sector, flow_ratio))
        
        # 取前5板块
        top_sectors = sorted(sector_flows, key=lambda x:x[1], reverse=True)[:5]
        
        date_data = {'日期':date}
        for i, (sector, ratio) in enumerate(top_sectors,1):
            # 获取板块前三个股
            stocks = xtdata.get_stock_list_in_sector(sector)
            df = pd.DataFrame({
                '成交额': xtdata.get_market_data('amount', stocks, '1d', date, 1)['amount'].iloc[0],
                '市值': xtdata.get_market_data('total_mv', stocks, '1d', date, 1)['total_mv'].iloc[0]
            })
            df['占比'] = df['成交额'] / df['市值']
            top_stocks = df.nlargest(3, '占比').index.tolist()
            
            date_data[f'板块{i}'] = sector
            date_data[f'资金占比{i}'] = f"{ratio:.2%}"
            date_data[f'成分股{i}'] = '\n'.join(top_stocks)
        
        result.append(date_data)
    
    return pd.DataFrame(result).set_index('日期')

if __name__ == '__main__':
    df = get_sector_flow()
    print(df)