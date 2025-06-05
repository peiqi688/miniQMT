import time
import pandas as pd
from xtquant import xtdata

def test_subscribe_whole_quote():
    """
    测试订阅全推行情数据
    该函数展示如何使用subscribe_whole_quote接口订阅沪深市场的全推行情数据
    """
    print("=== 测试订阅全推行情数据 ===")
    
    # 确保连接到行情服务器
    if not xtdata.connect():
        print("连接行情服务器失败")
        return
    
    print("连接行情服务器成功")
    
    # 定义回调函数，用于处理接收到的全推行情数据
    def on_whole_quote_data(datas):
        """
        全推行情数据回调函数
        :param datas: {stock1: data1, stock2: data2, ...} 数据字典
        """
        # 获取收到数据的股票代码列表
        stock_codes = list(datas.keys())
        print(f"收到全推行情数据，包含 {len(stock_codes)} 只股票")
        
        # 打印前5只股票的代码（如果有的话）
        if stock_codes:
            display_codes = stock_codes[:5]
            print(f"部分股票代码: {display_codes}")
            
            # 展示第一只股票的详细数据
            first_stock = stock_codes[0]
            stock_data = datas[first_stock]
            print(f"\n股票 {first_stock} 的数据:")
            print(stock_data)
            
            # 如果数据是字典类型，提取一些关键信息
            if isinstance(stock_data, dict):
                # 提取常见字段（根据实际数据结构可能需要调整）
                fields_to_show = ['lastPrice', 'openPrice', 'highPrice', 'lowPrice', 
                                 'preClosePrice', 'volume', 'amount', 'bidPrice', 'askPrice']
                
                print("\n关键数据:")
                for field in fields_to_show:
                    if field in stock_data:
                        print(f"{field}: {stock_data[field]}")
    
    # 订阅沪深市场的全推行情
    # 方式一：订阅特定市场的全部股票
    market_codes = ["SH", "SZ"]  # 沪市和深市
    print(f"订阅市场: {market_codes}")
    
    # 调用subscribe_whole_quote接口进行订阅
    seq = xtdata.subscribe_whole_quote(market_codes, callback=on_whole_quote_data)
    
    if seq > 0:
        print(f"订阅成功，订阅号: {seq}")
        
        # 等待接收数据（保持程序运行一段时间）
        print("等待接收数据，将在30秒后退出...")
        try:
            # 等待30秒接收数据
            for i in range(30):
                time.sleep(1)
                print(f"等待中... {i+1}/30", end="\r")
        except KeyboardInterrupt:
            print("\n用户中断")
        
        # 取消订阅
        if xtdata.unsubscribe_quote(seq):
            print("\n成功取消订阅")
        else:
            print("\n取消订阅失败")
    else:
        print("订阅失败")
    
    # 断开连接
    xtdata.disconnect()
    print("已断开与行情服务器的连接")

# 方式二：也可以订阅特定股票的全推行情
def test_subscribe_specific_stocks():
    """
    测试订阅特定股票的全推行情数据
    """
    print("=== 测试订阅特定股票的全推行情数据 ===")
    
    # 确保连接到行情服务器
    if not xtdata.connect():
        print("连接行情服务器失败")
        return
    
    print("连接行情服务器成功")
    
    # 定义更详细的回调函数
    def on_whole_quote_data(datas):
        stock_codes = list(datas.keys())
        print(f"收到全推行情数据，包含 {len(stock_codes)} 只股票: {stock_codes}")
        
        for stock_code in stock_codes:
            stock_data = datas[stock_code]
            print(f"\n股票 {stock_code} 的数据类型: {type(stock_data)}")
            
            # 打印所有可用的字段
            if isinstance(stock_data, dict):
                print(f"可用字段: {list(stock_data.keys())}")
                
                # 尝试打印更多字段
                for field in stock_data:
                    print(f"{field}: {stock_data[field]}")
            else:
                print(f"数据内容: {stock_data}")
    
    # 订阅特定股票的全推行情 - 增加更多股票以提高收到数据的可能性
    specific_stocks = ["600000.SH", "000001.SZ", "601318.SH", "600519.SH", "000858.SZ"]
    print(f"订阅股票: {specific_stocks}")
    
    seq = xtdata.subscribe_whole_quote(specific_stocks, callback=on_whole_quote_data)
    
    if seq > 0:
        print(f"订阅成功，订阅号: {seq}")
        
        # 等待接收数据（保持程序运行一段时间）
        print("等待接收数据，将在15秒后退出...")
        try:
            # 每秒打印一次等待状态
            for i in range(15):
                time.sleep(1)
                print(f"等待中... {i+1}/15", end="\r")
        except KeyboardInterrupt:
            print("\n用户中断")
        
        # 取消订阅
        if xtdata.unsubscribe_quote(seq):
            print("\n成功取消订阅")
        else:
            print("\n取消订阅失败")
    else:
        print("订阅失败，错误码:", seq)
    
    # 断开连接
    xtdata.disconnect()
    print("已断开与行情服务器的连接")

# 如果直接运行此脚本，则执行测试函数
if __name__ == "__main__":
    #test_subscribe_whole_quote()
    # 如果想测试特定股票的订阅，取消下面的注释
    # test_subscribe_specific_stocks()
    
    data=xtdata.get_stock_list_in_sector('上证A股')
    print(data)