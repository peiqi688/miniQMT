from xtquant import xtdata
import pandas as pd
import config

def fetch_history_data(stock_list):
    """
    获取历史行情数据
    """
    period = '1d'  # 日线数据
    dividend_type = 'front'  # 前复权
    data = xtdata.get_market_data(
        stock_list=stock_list,
        period=period,
        start_time='',
        end_time='',
        dividend_type=dividend_type,
        count=config.HIST_DATA_DAYS
    )
    return pd.DataFrame(data)

def save_to_csv(data, filename):
    if config.DEBUG_MODE:
        data.to_csv(f"{config.LOG_PATH}{filename}")
        print(f"[DEBUG] 数据已保存至 {filename}")
