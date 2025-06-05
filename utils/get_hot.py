import pandas as pd
import pywencai
import adata

def find_overlap_stocks(wencai_query, adata_func, cookie=None):
    """
    获取问财数据与adata数据源中的重叠股票信息
    
    参数:
    wencai_query: 问财查询字符串
    adata_func: adata获取数据的函数
    cookie: 问财查询所需的cookie(可选)
    
    返回:
    merged_df: 合并后的重叠股票DataFrame
    overlap_codes: 重叠的股票代码集合
    """
    # 1. 获取问财数据
    res = pywencai.get(
        query=wencai_query, 
        sort_key='', 
        sort_order='',
        page='1', 
        cookie=cookie
    )
    
    # 2. 获取adata数据
    res_df = adata_func()
    
    # 3. 确保两者都是DataFrame
    if not (isinstance(res, pd.DataFrame) and isinstance(res_df, pd.DataFrame)):
        print("错误：输入数据不是DataFrame类型")
        return pd.DataFrame(), set()
    
    # 4. 统一股票代码列名
    # 问财数据通常包含'股票代码'列
    # adata数据通常包含'stock_code'列
    if 'stock_code' in res_df.columns and '股票代码' not in res_df.columns:
        res_df = res_df.rename(columns={'stock_code': '股票代码'})
    
    # 5. 预处理股票代码格式
    def clean_stock_code(code):
        """清洗股票代码格式，移除交易所后缀"""
        if isinstance(code, str):
            # 移除.SZ/.SH等后缀
            return code.split('.')[0]
        return code
    
    # 6. 应用清洗函数
    if '股票代码' in res.columns:
        res['股票代码'] = res['股票代码'].apply(clean_stock_code)
    if '股票代码' in res_df.columns:
        res_df['股票代码'] = res_df['股票代码'].apply(clean_stock_code)
    
    # 7. 合并数据(内连接)
    if '股票代码' in res.columns and '股票代码' in res_df.columns:
        merged_df = pd.merge(
            res, 
            res_df, 
            on='股票代码', 
            how='inner',
            suffixes=('_问财', '_adata')
        )
        
        # 打印合并结果
        print("\n=== 重叠股票信息 ===")
        if not merged_df.empty:
            print(f"找到 {len(merged_df)} 个重叠的股票")
            # 尝试打印关键列
            display_columns = ['股票代码']
            if '股票简称' in merged_df.columns:
                display_columns.append('股票简称')
            if 'short_name' in merged_df.columns:
                display_columns.append('short_name')
            
            print(merged_df[display_columns].head())
        else:
            print("没有找到重叠的股票")
    else:
        print("错误：缺少股票代码列")
        merged_df = pd.DataFrame()
    
    # 8. 备选方法：使用集合查找重叠股票代码
    def extract_stock_codes(data):
        """从不同格式的数据中提取股票代码集合"""
        if isinstance(data, pd.DataFrame):
            # 尝试常见列名
            for col in ['股票代码', 'code', 'symbol', '代码']:
                if col in data.columns:
                    return set(data[col].astype(str))
        return set()
    
    res_codes = extract_stock_codes(res)
    res_df_codes = extract_stock_codes(res_df)
    overlap_codes = res_codes & res_df_codes
    
    print(f"\n备选方法找到重叠股票: {len(overlap_codes)}个")
    return merged_df, overlap_codes


# 使用示例
if __name__ == "__main__":
    # 配置参数
    query = '人气排行榜前100名'
    cookie = 'xxx'  # 替换为实际cookie
    
    # 执行函数
    merged_data, overlap_codes = find_overlap_stocks(
        wencai_query=query,
        adata_func=adata.sentiment.hot.pop_rank_100_east,
        cookie=cookie
    )
    
    # 保存结果到CSV
    # if not merged_data.empty:
    #     merged_data.to_csv('重叠股票数据.csv', index=False, encoding='utf_8_sig')
    #     print("结果已保存到: 重叠股票数据.csv")