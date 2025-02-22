import pandas as pd
from MyTT import MACD, MA

def calculate_ma(data, window):
    """MyTT均线计算"""
    close = data['close'].values  # 转换为numpy数组
    return MA(close, window) 

def calculate_macd(data):
    """MyTT版MACD计算"""
    close = data['close'].values
    return MACD(close)  # 返回(DIF, DEA, MACD柱)

def generate_signals(data):
    signals = pd.DataFrame(index=data.index)
    
    # 计算均线指标
    signals['MA10'] = calculate_ma(data, 10)
    signals['MA20'] = calculate_ma(data, 20)
    signals['MA30'] = calculate_ma(data, 30)
    signals['MA60'] = calculate_ma(data, 60)
    
    # 计算MACD指标
    dif, dea, hist = calculate_macd(data)
    signals['MACD_DIF'] = dif
    signals['MACD_DEA'] = dea
    signals['MACD_HIST'] = hist
    
    return signals
