# stock_filter.py
import pandas as pd
import pywencai
import adata
import xtquant.xtdata as xtdata
import numpy as np
from datetime import datetime, timedelta
import time

def get_overlap_stocks(wencai_query, adata_func, cookie=None):
    """
    获取问财与adata重叠股票数据
    返回：重叠股票DataFrame
    """
    try:
        # 获取问财数据
        res = pywencai.get(
            query=wencai_query, 
            sort_key='', 
            sort_order='',
            page='1', 
            cookie=cookie
        )
        
        # 获取adata数据
        res_df = adata_func()
        
        # 确保两者都是DataFrame
        if not (isinstance(res, pd.DataFrame) and isinstance(res_df, pd.DataFrame)):
            print("错误：输入数据不是DataFrame类型")
            return pd.DataFrame()
        
        # 统一股票代码列名
        if 'stock_code' in res_df.columns and '股票代码' not in res_df.columns:
            res_df = res_df.rename(columns={'stock_code': '股票代码'})
        
        # 预处理股票代码格式
        def clean_stock_code(code):
            if isinstance(code, str):
                return code.split('.')[0]
            return code
        
        # 应用清洗函数
        if '股票代码' in res.columns:
            res['股票代码'] = res['股票代码'].apply(clean_stock_code)
        if '股票代码' in res_df.columns:
            res_df['股票代码'] = res_df['股票代码'].apply(clean_stock_code)
        
        # 合并数据(内连接)
        if '股票代码' in res.columns and '股票代码' in res_df.columns:
            merged_df = pd.merge(
                res, 
                res_df, 
                on='股票代码', 
                how='inner',
                suffixes=('_问财', '_adata')
            )
            return merged_df
        else:
            print("错误：缺少股票代码列")
            return pd.DataFrame()
    
    except Exception as e:
        print(f"获取重叠股票数据时出错: {str(e)}")
        return pd.DataFrame()

def filter_limit_down_stocks(stock_df, days=5, threshold=0.97):
    """
    筛选并排除最近触及跌停的股票
    
    参数:
    stock_df: 包含股票代码的DataFrame
    days: 回溯天数 (默认5天)
    threshold: 跌停阈值 (默认0.97, 即跌幅超过3%视为触及跌停)
    
    返回:
    筛选后的DataFrame
    """
    if stock_df.empty or '股票代码' not in stock_df.columns:
        print("错误：无效的输入数据")
        return stock_df
    
    # 添加交易所后缀
    def add_exchange_suffix(code):
        if str(code).startswith('6'):
            return f"{code}.SH"
        elif str(code).startswith('0') or str(code).startswith('3'):
            return f"{code}.SZ"
        elif str(code).startswith('8'):
            return f"{code}.BJ"
        else:
            return f"{code}.SH"  # 默认
    
    # 准备带交易所后缀的股票列表
    stock_df['带后缀代码'] = stock_df['股票代码'].apply(add_exchange_suffix)
    stock_list = stock_df['带后缀代码'].tolist()
    
    # 获取最近交易日
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days+7)).strftime('%Y%m%d')  # 多取几天缓冲
    
    # 初始化结果列
    stock_df['触及跌停'] = False
    stock_df['最近触及日期'] = None
    
    # 分批处理股票，避免一次性请求过多
    batch_size = 50
    batches = [stock_list[i:i+batch_size] for i in range(0, len(stock_list), batch_size)]
    
    print(f"开始筛选{len(stock_list)}只股票，回溯{days}个交易日...")
    
    for i, batch in enumerate(batches):
        print(f"处理批次 {i+1}/{len(batches)}: {len(batch)}只股票")
        
        try:
            # 获取历史行情数据
            data = xtdata.get_market_data(
                field_list=['close', 'pctChange'],
                stock_list=batch,
                period='1d',
                start_time=start_date,
                end_time=end_date,
                dividend_type='none'
            )
            
            # 处理每只股票
            for stock in batch:
                if stock not in data or 'pctChange' not in data[stock]:
                    continue
                
                # 获取跌幅数据
                pct_changes = data[stock]['pctChange']
                dates = data[stock].index
                
                # 检查最近days个交易日
                recent_dates = sorted(dates, reverse=True)[:days]
                
                for date in recent_dates:
                    pct_change = pct_changes[date]
                    if pct_change is not None and pct_change < 0 and abs(pct_change) > (1 - threshold) * 100:
                        # 找到触及跌停的股票
                        idx = stock_df[stock_df['带后缀代码'] == stock].index
                        if not idx.empty:
                            stock_df.loc[idx, '触及跌停'] = True
                            stock_df.loc[idx, '最近触及日期'] = date.strftime('%Y-%m-%d')
                        break
        
        except Exception as e:
            print(f"处理批次 {i+1} 时出错: {str(e)}")
        time.sleep(1)  # 避免请求过于频繁
    
    # 筛选未触及跌停的股票
    filtered_df = stock_df[~stock_df['触及跌停']].copy()
    filtered_df.drop(columns=['带后缀代码'], inplace=True)
    
    print(f"\n筛选结果: 原始股票 {len(stock_df)} 只")
    #print(f"触及跌停股票: {len(stock_df[stock_df['触及跌停'])} 只")
    print(f"剩余股票: {len(filtered_df)} 只")
    
    return filtered_df

def get_filtered_stocks(query, adata_func, cookie=None, days=5):
    """
    获取并筛选股票的完整流程
    """
    # 1. 获取重叠股票
    overlap_df = get_overlap_stocks(query, adata_func, cookie)
    
    if overlap_df.empty:
        print("未获取到重叠股票数据")
        return pd.DataFrame()
    
    print(f"获取到 {len(overlap_df)} 只重叠股票")
    
    # 2. 筛选排除触及跌停股票
    filtered_df = filter_limit_down_stocks(overlap_df, days=days)
    
    # 3. 保存结果
    if not filtered_df.empty:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"filtered_stocks_{timestamp}.csv"
        filtered_df.to_csv(filename, index=False, encoding='utf_8_sig')
        print(f"筛选结果已保存到: {filename}")
    
    return filtered_df