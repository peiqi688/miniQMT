import xtquant.xtdata as xtdata
import time

def test_get_full_tick():
    """
    测试使用xtdata.get_full_tick获取股票实时行情数据。
    """
    stock_code = '159813.SZ'  # 示例股票代码
    print(f"尝试获取股票 {stock_code} 的实时行情数据...")
    try:
        # 获取实时行情数据
        data = xtdata.get_full_tick([stock_code])
        if data and stock_code in data:
            tick_data = data[stock_code]
            print(f"成功获取 {stock_code} 的实时行情数据：")
            for key, value in tick_data.items():
                print(f"  {key}: {value}")
        else:
            print(f"未能获取 {stock_code} 的实时行情数据，返回数据为空或不包含该股票。")
    except Exception as e:
        print(f"获取 {stock_code} 实时行情数据时发生错误: {e}")

if __name__ == '__main__':
    # 确保QMT已连接，否则可能无法获取数据
    # 实际使用中，可能需要在此处添加连接QMT的逻辑
    # 例如：xtdata.connect() 或 xtdata.start_socket_trade() 等
    
    # 运行测试函数
    test_get_full_tick()