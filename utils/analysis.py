# analysis.py
from stock_data_fetcher import get_overlap_stocks
import adata
import pandas as pd

# 配置参数
COOKIE = 'your_cookie_here'  # 替换为你的实际cookie
QUERY = '人气排行榜前100名'

def analyze_overlap_stocks():
    """分析重叠股票数据"""
    # 调用数据获取函数
    overlap_data, overlap_codes = get_overlap_stocks(
        wencai_query=QUERY,
        adata_func=adata.sentiment.hot.pop_rank_100_east,
        cookie=COOKIE,
        save_csv=True  # 保存结果到CSV
    )
    
    if overlap_data.empty:
        print("未获取到重叠股票数据")
        return
    
    print(f"获取到 {len(overlap_data)} 只重叠股票")
    
    # 示例1: 查看前10只股票
    print("\n重叠股票列表:")
    # 尝试获取合适的显示列
    display_columns = ['股票代码']
    if '股票简称' in overlap_data.columns:
        display_columns.append('股票简称')
    elif 'short_name' in overlap_data.columns:
        display_columns.append('short_name')
    
    print(overlap_data[display_columns].head(10))
    
    # 示例2: 计算平均人气值
    if '人气值' in overlap_data.columns:
        avg_popularity = overlap_data['人气值'].mean()
        print(f"\n重叠股票的平均人气值: {avg_popularity:.2f}")
    
    # 示例3: 行业分布分析
    if '行业' in overlap_data.columns:
        industry_dist = overlap_data['行业'].value_counts()
        print("\n行业分布:")
        print(industry_dist)
    
    # 示例4: 保存处理后的数据
    # 选择关键列保存
    key_columns = ['股票代码', '股票简称', '最新价', '涨跌幅', '人气值', '所属行业']
    # 只保留实际存在的列
    existing_columns = [col for col in key_columns if col in overlap_data.columns]
    
    if existing_columns:
        processed_data = overlap_data[existing_columns]
        processed_data.to_csv('processed_overlap_stocks.csv', index=False, encoding='utf_8_sig')
        print("\n处理后的数据已保存到 processed_overlap_stocks.csv")
    
    return overlap_data

if __name__ == "__main__":
    # 执行分析
    stock_data = analyze_overlap_stocks()
    
    # 在这里可以添加更多分析逻辑
    # 例如:
    # if not stock_data.empty:
    #     # 计算平均市盈率
    #     if '市盈率' in stock_data.columns:
    #         avg_pe = stock_data['市盈率'].mean()
    #         print(f"平均市盈率: {avg_pe:.2f}")
    #
    #     # 筛选高人气股票
    #     high_popularity = stock_data[stock_data['人气值'] > stock_data['人气值'].quantile(0.8)]
    #     print(f"高人气股票数量: {len(high_popularity)}")