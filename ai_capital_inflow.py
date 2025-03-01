import pandas as pd
import numpy as np
from xtquant import xtdata
import datetime

def get_sector_flow():
    # 同步板块数据
    xtdata.download_sector_data()
    
    # 获取近10个交易日日期（两周）
    trade_dates = xtdata.get_trading_dates('SH', end_time=datetime.datetime.now().strftime('%Y%m%d'), count=10)[::-1]
    
    result = []
    for date in trade_dates:

       # 日期预处理：确保日期格式正确 - 转换为'YYYY-MM-DD'格式
        if isinstance(date, datetime.datetime) or isinstance(date, datetime.date):
            date_str = date.strftime('%Y-%m-%d')
        else:
            # 将日期转为字符串
            date_str = str(date)
            
            # 处理毫秒级时间戳（如1740326400000）
            if date_str.isdigit() and len(date_str) > 10:
                # 毫秒级时间戳转为datetime
                timestamp_seconds = int(date_str) / 1000
                date_time = datetime.datetime.fromtimestamp(timestamp_seconds)
                date_str = date_time.strftime('%Y-%m-%d')

        # 获取当日所有板块
        sectors = xtdata.get_sector_list()
        sector_flows = []
        
        for sector in sectors:
            # 获取板块成分股
            stocks = xtdata.get_stock_list_in_sector(sector)
            
            if not stocks:
                sector_flows.append((sector, 0))
                continue
                
            # 获取成交额和收盘价数据（而不是直接获取total_mv）
            market_data = xtdata.get_market_data(field_list=['close', 'amount'], 
                                                 stock_list=stocks, 
                                                 start_time=date_str, 
                                                 end_time=date_str, 
                                                 period='1d', 
                                                 count=1)
            
            if not market_data or 'close' not in market_data or 'amount' not in market_data:
                sector_flows.append((sector, 0))
                continue
                
            close_prices = market_data['close'].iloc[0]
            amount = market_data['amount'].iloc[0]
            
            # 获取每只股票的总股本信息用于计算市值
            total_mv = {}
            for stock in stocks:
                try:
                    # 获取股票详细信息，包括总股本
                    stock_detail = xtdata.get_instrument_detail(stock, iscomplete=True)
                    if stock_detail and 'TotalVolume' in stock_detail:
                        # 如果有收盘价，计算该股票市值 = 总股本 × 收盘价
                        if stock in close_prices.index and close_prices[stock] > 0:
                            total_mv[stock] = stock_detail['TotalVolume'] * close_prices[stock]
                except Exception as e:
                    print(f"获取{stock}基础信息出错: {e}")
            
            # 计算板块总市值和总成交额
            sector_total_mv = 0
            sector_total_amount = 0
            
            for stock in total_mv:
                if stock in amount.index and amount[stock] > 0 and total_mv[stock] > 0:
                    sector_total_mv += total_mv[stock]
                    sector_total_amount += amount[stock]
            
            # 计算资金流比例 = 总成交额 / 总市值
            flow_ratio = sector_total_amount / sector_total_mv if sector_total_mv > 0 else 0
            
            # 记录板块资金流
            sector_flows.append((sector, flow_ratio))
        
        # 取前5板块
        top_sectors = sorted(sector_flows, key=lambda x:x[1], reverse=True)[:5]
        
        date_data = {'日期':date}
        for i, (sector, ratio) in enumerate(top_sectors,1):
            # 获取板块成分股
            stocks = xtdata.get_stock_list_in_sector(sector)
            
            # 获取成交额数据
            price_data = xtdata.get_market_data(field_list=['close', 'amount'], 
                                              stock_list=stocks, 
                                              start_time=date_str, 
                                              end_time=date_str, 
                                              period='1d', 
                                              count=1)
            
            if price_data and 'close' in price_data and 'amount' in price_data:
                # 获取股票基础信息（包含总股本）
                stocks_info = {}
                for stock in stocks:
                    try:
                        # 获取股票详细信息，包括总股本
                        stock_detail = xtdata.get_instrument_detail(stock, iscomplete=True)
                        if stock_detail and 'TotalVolume' in stock_detail:
                            # TotalVolume是总股本字段
                            stocks_info[stock] = stock_detail['TotalVolume']
                    except Exception as e:
                        print(f"获取{stock}基础信息出错: {e}")
                
                # 计算市值并与成交额比较
                close_prices = price_data['close'].iloc[0]
                amounts = price_data['amount'].iloc[0]
                
                market_caps = {}
                ratios = {}
                for stock in stocks:
                    if stock in stocks_info and stock in close_prices.index and stock in amounts.index:
                        # 计算市值 = 总股本 × 收盘价
                        market_cap = stocks_info[stock] * close_prices[stock]
                        market_caps[stock] = market_cap
                        # 计算成交额与市值比
                        if market_cap > 0:
                            ratios[stock] = amounts[stock] / market_cap
                
                # 找出比例最高的三只股票
                top_stocks = sorted(ratios.items(), key=lambda x: x[1], reverse=True)[:3]
                top_stocks = [stock for stock, _ in top_stocks]
            else:
                top_stocks = []
            
            date_data[f'板块{i}'] = sector
            date_data[f'资金占比{i}'] = f"{ratio:.2%}"
            date_data[f'成分股{i}'] = '\n'.join(top_stocks)
        
        result.append(date_data)
    
    return pd.DataFrame(result).set_index('日期')

if __name__ == '__main__':
    df = get_sector_flow()
    print(df)