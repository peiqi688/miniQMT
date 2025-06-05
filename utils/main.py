# main.py
from stock_filter import get_filtered_stocks
import adata
import config

def main():
    print("="*50)
    print("开始执行股票筛选流程")
    print("="*50)
    
    # 获取并筛选股票
    filtered_stocks = get_filtered_stocks(
        query=config.WENCAI_QUERY,
        adata_func=adata.sentiment.hot.pop_rank_100_east,
        cookie=config.WENCAI_COOKIE,
        days=config.LOOKBACK_DAYS
    )
    
    if not filtered_stocks.empty:
        print("\n最终筛选结果:")
        # 显示关键信息 - 根据实际列名调整
        display_cols = ['股票代码', '股票简称', '最新价', '涨跌幅', '人气值']
        # 只保留实际存在的列
        display_cols = [col for col in display_cols if col in filtered_stocks.columns]
        print(filtered_stocks[display_cols].head(10))
        
        # 这里可以添加交易信号生成逻辑
        generate_trading_signals(filtered_stocks)
    else:
        print("没有符合条件的股票")

def generate_trading_signals(stock_df):
    """
    生成交易信号 (示例)
    """
    print("\n生成交易信号...")
    
    # 示例信号逻辑：高人气+低波动
    if '人气值' in stock_df.columns and '涨跌幅' in stock_df.columns:
        # 标准化人气值 (0-100)
        stock_df['人气值标准分'] = (stock_df['人气值'] - stock_df['人气值'].min()) / (stock_df['人气值'].max() - stock_df['人气值'].min()) * 100
        
        # 生成信号
        stock_df['交易信号'] = '观望'
        
        # 条件1: 人气值高于80分且当日涨幅<5%
        condition1 = (stock_df['人气值标准分'] > 80) & (stock_df['涨跌幅'] < 5)
        stock_df.loc[condition1, '交易信号'] = '关注'
        
        # 条件2: 人气值高于90分且当日涨幅<3%
        condition2 = (stock_df['人气值标准分'] > 90) & (stock_df['涨跌幅'] < 3)
        stock_df.loc[condition2, '交易信号'] = '强烈关注'
        
        # 保存信号结果
        signal_cols = ['股票代码', '股票简称', '最新价', '涨跌幅', '人气值标准分', '交易信号']
        signal_cols = [col for col in signal_cols if col in stock_df.columns]
        
        signal_df = stock_df[signal_cols].sort_values(by='人气值标准分', ascending=False)
        print(signal_df.head(10))
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        signal_df.to_csv(f'trading_signals_{timestamp}.csv', index=False, encoding='utf_8_sig')
        print(f"交易信号已保存到 trading_signals_{timestamp}.csv")
    else:
        print("缺少必要的列，无法生成交易信号")

if __name__ == "__main__":
    main()