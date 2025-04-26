"""用来创建公用的方法，方便程序进行调用"""

# from stockquant.quant import *
import pandas as pd
import baostock as bs
import datetime
import time
import requests
import json
from MyTT import *
from mootdx.quotes import Quotes

def backInDays(nday):
    """用来获得n天前的日期，用于从数据接口请求股票数据，避免一次要求过多数据影响程序效率"""
    """建议：30m数据，取值60，即回溯2个月的数据，约40个交易日，320个数据点，最多用于计算MA250"""
    """同理：60m数据，取值120; 日线数据，取值480; 周线数据，取值2400"""
    # 获取当前时间并减去n天
    n_days_back = datetime.datetime.now() - datetime.timedelta(days=float(nday))
    # 将时间转换为字符串格式
    n_days_back_str = n_days_back.strftime("%Y-%m-%d")
    return n_days_back_str


# 对code列进行处理, 在调用baostock接口前添加前缀
def add_bs_prefix(code):
    if code.startswith('6'):
        return 'sh.' + code
    elif code.startswith(('0', '3')):
        return 'sz.' + code
    else:
        return code

# 股票数据请求，用Baostock或者mootdx
# Baostock方式：
#       res = getStockData('600519', fields="date,open,high,low,close,preclose,volume,amount", start_date=Methods.backInDays(500), freq='d', adjustflag='2')
# mootdx方式：
#       res = Methods.getStockData('600519', offset=800, freq=9, adjustflag='qfq') 
#       res['datetime'] = pd.to_datetime(res['datetime']).dt.date
#       res = res.rename(columns={'datetime': 'date'})
#       res = res.reindex(columns=['date', 'open', 'high', 'low', 'close', 'preclose', 'volume', 'amount'])
#       res = res.reset_index(drop=True)
def getStockData(code, 
                 fields="date,code,open,high,low,close,volume,amount,adjustflag", 
                 start_date=None, end_date=None, 
                 offset=100,
                 freq='d', adjustflag='2'):
    
    # 长周期K线数据如日线、周线、月线用Baostock接口，有换手率，PE等数据
    # 日k线；d=日k线、w=周、m=月、5=5分钟、15=15分钟、30=30分钟、60=60分钟k线数据，不区分大小写；
    # 指数没有分钟线数据；周线每周最后一个交易日才可以获取，月线每月最后一个交易日才可以获取
    if freq=='d' or freq=='w' or freq=='m': 
        code = add_bs_prefix(code)

        lg = bs.login()
        result = bs.query_history_k_data_plus(code, fields, start_date, end_date, freq, adjustflag)
        df = pd.DataFrame(result.get_data(), columns=result.fields)
        return df
    # 其它数据用mootdx接口,默认取100根K线数据，，没有换手率，PE等数据
    # frequency -> K线种类 0 => 5分钟K线 => 5m 1 => 15分钟K线 => 15m 2 => 30分钟K线 => 30m 3 => 小时K线 => 1h 
    # 4 => 日K线 (小数点x100) => days 5 => 周K线 => week 6 => 月K线 => mon 
    # 7 => 1分钟K线(好像一样) => 1m 8 => 1分钟K线(好像一样) => 1m 
    # 9 => 日K线 => day 10 => 季K线 => 3mon 11 => 年K线 => year
    elif freq>=0 and freq<=11:
        if code.startswith(("sh.", "sz.")):
            code = code.split('.')[1]
        client = Quotes.factory('std')  # 使用标准版通达信数据
        df = client.bars(symbol=code, frequency=freq, offset=offset, adjust=adjustflag) 
        return df
    else:
        return None


def IsMarketGoingUp():
    # 指数代码
    indices = {
        'sh.000001': '上证指数',   # 上证指数
        'sz.399001': '深证成指',   # 深证成指
        'sz.399005': '中小板指'    # 中小板指
    }

    # 登录到Baostock
    lg = bs.login()

    # 遍历每个指数
    for code, name in indices.items():
        # 获取30天K线数据
        fields = "date,code,open,high,low,close"
        start_date = backInDays(30)
        end_date = datetime.datetime.now().strftime("%Y-%m-%d")  # 当前日期
        res = bs.query_history_k_data_plus(code, fields, start_date, end_date, frequency='d', adjustflag='3')
        df = pd.DataFrame(res.get_data(), columns=res.fields)

        # 计算MA5
        if len(df) >= 5:
            df['close'] = df['close'].astype(float)
            df['MA5'] = df['close'].rolling(window=5).mean()

            # 检查MA5是否呈上升趋势
            if df['MA5'].iloc[-1] > df['MA5'].iloc[-2] and df['MA5'].iloc[-2] > df['MA5'].iloc[-3]:
                print(f"{name} 的MA5呈现上升趋势。")
                return True

    # 如果没有任何一个指数的MA5呈上升趋势
    print("所有检查的指数的MA5都没有呈现上升趋势。")
    return False

def m_v_vol(code, dfd):
    
    tick = Market.tick(code.replace('.', ''))

    VOLUME= dfd['volume'].values.astype(float) 

    # 计算虚拟成交量
    now = datetime.datetime.now()
    morning_start = datetime.datetime(now.year, now.month, now.day, 9, 30)
    morning_end = datetime.datetime(now.year, now.month, now.day, 11, 30)
    afternoon_start = datetime.datetime(now.year, now.month, now.day, 13, 0)
    afternoon_end = datetime.datetime(now.year, now.month, now.day, 15, 0)

    time0930 = datetime.datetime(now.year, now.month, now.day,  9, 30)
    time0945 = datetime.datetime(now.year, now.month, now.day,  9, 45)
    time1000 = datetime.datetime(now.year, now.month, now.day, 10,  0)
    time1030 = datetime.datetime(now.year, now.month, now.day, 10, 30)
    time1100 = datetime.datetime(now.year, now.month, now.day, 11,  0)
    time1130 = datetime.datetime(now.year, now.month, now.day, 11, 30)
    time1300 = datetime.datetime(now.year, now.month, now.day, 13,  0)
    time1330 = datetime.datetime(now.year, now.month, now.day, 13, 30)
    time1400 = datetime.datetime(now.year, now.month, now.day, 14,  0)
    time1430 = datetime.datetime(now.year, now.month, now.day, 14, 30)
    time1500 = datetime.datetime(now.year, now.month, now.day, 15,  0)	

    if morning_start <= now <= morning_end:
        minutes = int((now - morning_start).total_seconds() / 60)
    elif afternoon_start <= now <= afternoon_end:
        minutes = int((now - afternoon_start).total_seconds() / 60) + 120  # 加上上午的交易时间
    elif now < morning_start:
        minutes = 0  # 如果当前时间早于9:30，返回0
    elif morning_end < now < afternoon_start:
        minutes = 120  # 如果当前时间在中午休市期间，返回上午的交易时间
    else:  # now > afternoon_end
        minutes = 240  # 如果当前时间晚于15:00，返回全天的交易时间

    if(minutes!=0):
        VVOL = tick.transactions / (minutes / 240.0) 
    else:
        VVOL = VOLUME[-1]

    if time0930 <= now < time0945:
        V_FORECAST =  VVOL/7.0   # 3.5
    elif time0945 <= now < time1000:
        V_FORECAST =  VVOL/4.5   # 3.2
    elif time1000 <= now < time1030:
        V_FORECAST =  VVOL/4.0   # 3.2
    elif time1030 <= now < time1100:
        V_FORECAST =  VVOL/3.5   # 2.5
    elif time1100 <= now <= time1130:
        V_FORECAST =  VVOL/2.5   # 2.1
    elif time1300 <= now < time1330:
        V_FORECAST =  VVOL/1.7
    elif time1330 <= now < time1400:
        V_FORECAST =  VVOL/1.4
    elif time1400 <= now < time1430:
        V_FORECAST =  VVOL/1.3
    elif time1430 <= now <= time1500:
        V_FORECAST =  VVOL/1.2
    else:
        V_FORECAST = VVOL

    return V_FORECAST    

def calmacd(df):
    df2 = df
    if len(df2) > 33:
        dif, dea, hist = MACD(df2['close'].astype(float).values, fastperiod=12, slowperiod=26, signalperiod=9)
        df3 = pd.DataFrame({'dif': dif[33:], 'dea': dea[33:], 'hist': hist[33:]}, index=df2['date'][33:], columns=['dif', 'dea', 'hist'])
        return df3


def WX_send(msg):
    token = "65a7ae6c776c4881899e36aace47d491"
    title = "Stockquant"
    # 在pushplus推送加微信公众号-功能-个人中心-渠道配置-新增-webhook编码为“stockquant”， 请求地址为企微机器人的webhook地址 
    # webhook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxxxxxxxxxxxxxxx"

    url = "http://www.pushplus.plus/send"
    headers = {"Content-Type": "application/json"}
    data = {
        "token": token,
        "title": title,
        "content": msg,
        "channel": "webhook",
        "webhook": "stockquant"
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        return response.json()
    else:
        return None


def sendTradeMsg(msg):
    try:
        DingTalk.markdown("python交易提醒："+msg)
    except Exception as e:
        print(e)
        
    try:
        WX_send("Stockquant："+msg)
    except Exception as e:
        print(e)

# 满足建仓条件的股票列表
def stockListGoodToLong():
    # 60m出买点， 常规建仓为一类， 下有长中枢为另一类
    db = getDB()
    cursor = db.cursor()
    cursor.execute("SELECT code,filter_box from stg_m60 where  isDel is NULL and  lastUpdatetime > '%s' and isKdayVolUp = 'y' and isKdayMA34GoUp = 'y' and priceOfHighPct >= 0.72" % backInDays(2))
    return cursor.fetchall()


if __name__ == '__main__':

    IsMarketGoingUp()
