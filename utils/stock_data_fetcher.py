# stock_data_fetcher.py
import pandas as pd
import pywencai
import adata
import os

def get_overlap_stocks(wencai_query, adata_func, cookie=None, save_csv=False):
    """
    获取问财数据与adata数据源中的重叠股票信息
    
    参数:
    wencai_query: 问财查询字符串
    adata_func: adata获取数据的函数
    cookie: 问财查询所需的cookie(可选)
    save_csv: 是否保存结果到CSV文件(默认False)
    
    返回:
    tuple: (merged_df, overlap_codes)
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
            return pd.DataFrame(), set()
        
        # 统一股票代码列名
        # 问财数据通常包含'股票代码'列
        # adata数据通常包含'stock_code'列
        if 'stock_code' in res_df.columns and '股票代码' not in res_df.columns:
            res_df = res_df.rename(columns={'stock_code': '股票代码'})
        
        # 预处理股票代码格式
        def clean_stock_code(code):
            """清洗股票代码格式，移除交易所后缀"""
            if isinstance(code, str):
                # 移除.SZ/.SH等后缀
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
        else:
            print("错误：缺少股票代码列")
            merged_df = pd.DataFrame()
        
        # 备选方法：使用集合查找重叠股票代码
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
        
        # 保存结果到CSV
        if save_csv and not merged_df.empty:
            filename = f"overlap_stocks_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
            merged_df.to_csv(filename, index=False, encoding='utf_8_sig')
            print(f"结果已保存到: {os.path.abspath(filename)}")
        
        return merged_df, overlap_codes
    
    except Exception as e:
        print(f"获取重叠股票数据时出错: {str(e)}")
        return pd.DataFrame(), set()