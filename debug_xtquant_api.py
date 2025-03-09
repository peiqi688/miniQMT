"""
XtQuant API调试脚本

这个脚本用于测试XtQuant API的各种功能，包括连接、订阅、获取数据等，
帮助解决可能的问题。

使用方法: 
1. 将此脚本保存为独立文件，如 debug_xtquant.py
2. 运行: python debug_xtquant.py
"""
import sys
import os
import time
import logging
from datetime import datetime, timedelta
import pandas as pd

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('xtquant_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 导入XtQuant模块
try:
    import xtquant.xtdata as xt
    logger.info("成功导入 xtquant.xtdata 模块")
except ImportError as e:
    logger.error(f"导入 xtquant.xtdata 模块失败: {str(e)}")
    sys.exit(1)

# 测试股票代码
TEST_STOCKS = [
    "600000.SH",  # 浦发银行
    "000001.SZ",  # 平安银行
    "601318.SH"   # 中国平安
]

def test_connection():
    """测试连接到XtQuant行情服务器"""
    logger.info("=== 测试连接XtQuant服务器 ===")
    
    try:
        if not xt.connect():
            logger.error("连接XtQuant服务器失败")
            return False
            
        logger.info("连接XtQuant服务器成功")
        
        # 获取API版本
        version = getattr(xt, 'version', '未知')
        logger.info(f"XtQuant API版本: {version}")
        
        # 获取可用方法
        methods = [method for method in dir(xt) if not method.startswith('_')]
        logger.info(f"XtQuant API可用方法: {', '.join(methods[:10])}... (共{len(methods)}个)")
        
        return True
    except Exception as e:
        logger.error(f"连接XtQuant服务器时出错: {str(e)}")
        return False

def test_download_history_data(stocks):
    """测试下载历史行情数据"""
    logger.info("=== 测试下载历史行情数据 ===")
    
    try:
        # 设置日期范围
        end_time = datetime.now().strftime('%Y%m%d')
        start_time = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')  # 获取最近30天数据
        
        logger.info(f"下载 {start_time} 至 {end_time} 的日线数据")
        
        success_count = 0
        
        # 1. 测试单个股票下载
        test_stock = stocks[0]
        logger.info(f"单个下载: {test_stock}的日线数据")
        data = xt.download_history_data(
            test_stock,
            period='1d', 
            start_time=start_time,
            end_time=end_time
        )
        if data:
            logger.info(f"下载的数据 (前5条): {data[:5]}")
        else:
            logger.warning(f"下载 {test_stock} 的数据为空")
        
        logger.info(f"下载完成: {test_stock}")
        success_count += 1
        
        # 2. 测试批量下载
        logger.info(f"批量下载: {len(stocks)}只股票的日线数据")
        
        def on_progress(data):
            logger.info(f"下载进度: {data['finished']}/{data['total']} - {data['stockcode']}")
        
        data=xt.download_history_data2(
            stocks,
            period='1d', 
            start_time=start_time,
            end_time=end_time,
            callback=on_progress
        )
        if data:
            logger.info(f"下载的数据 (前5条): {data[:5]}")
        else:
            logger.warning(f"下载 {test_stock} 的数据为空")
        logger.info("批量下载完成")
        success_count += 1
        
        # 3. 测试不同周期数据的下载
        test_periods = ['1m', '5m', '15m', '30m', '60m']
        short_start = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
        
        for period in test_periods:
            try:
                logger.info(f"下载 {test_stock} 的 {period} 周期数据")
                data=xt.download_history_data(
                    test_stock,
                    period=period,
                    start_time=short_start,
                    end_time=end_time
                )
                if data:
                    logger.info(f"下载的数据 (前5条): {data[:5]}")
                else:
                    logger.warning(f"下载 {test_stock} 的数据为空")

                logger.info(f"{period}周期数据下载完成")
                success_count += 1
            except Exception as e:
                logger.error(f"下载 {period} 周期数据时出错: {str(e)}")
        
        logger.info(f"历史数据下载成功率: {success_count}/{2 + len(test_periods)}")
        return success_count > 0
    except Exception as e:
        logger.error(f"下载历史数据时出错: {str(e)}")
        return False

def on_quote_data(datas):
    logger.info(f"收到行情回调数据，包含股票: {list(datas.keys())}")
    for stock_code in datas:
        data_count = len(datas[stock_code]) if isinstance(datas[stock_code], list) else 1
        logger.info(f"股票 {stock_code} 收到 {data_count} 条数据")

def test_subscribe_quote(stocks):
    """测试订阅行情数据"""
    logger.info("=== 测试订阅行情数据 ===")
    
    try:
        success_count = 0
        subscribed_seqs = []
        
        # 1. 测试订阅日线数据
        test_stock = stocks[0]
        
        # 设置日期范围
        end_time = datetime.now().strftime('%Y%m%d')
        start_time = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')  # 获取最近30天数据
        
        # 订阅日线行情，包含历史数据
        logger.info(f"订阅 {test_stock} 的日线行情，包含历史数据")
        try:
            seq1 = xt.subscribe_quote(
                test_stock,
                period='1d',
                start_time=start_time,
                end_time=end_time,
                count=-1,  # 获取所有数据
                callback=on_quote_data
            )
        except Exception as e:
            logger.error(f"订阅日线行情时出错: {str(e)}")
            seq1 = -1
        
        if seq1 > 0:
            logger.info(f"成功订阅 {test_stock} 日线行情，订阅号: {seq1}")
            subscribed_seqs.append(seq1)
            success_count += 1
            
            # 等待两秒钟确保订阅生效
            logger.info("等待2秒钟让订阅生效...")
            time.sleep(2)
            
            # 使用get_market_data获取已订阅的数据
            logger.info(f"使用get_market_data获取 {test_stock} 的日线数据")
            try:
                data_dict = xt.get_market_data(
                    stock_list=[test_stock],  # 修正：使用stock_list而非symbol
                    period='1d', 
                    start_time=start_time,
                    end_time=end_time,
                    count=-1,
                    dividend_type='front'
                )
                
                # 检查数据字典是否为None
                if data_dict is None:
                    logger.warning(f"get_market_data返回None，检查参数是否正确")
                # 检查数据字典是否为空
                elif not data_dict:
                    logger.warning(f"get_market_data返回空字典")
                else:
                    logger.info(f"成功获取 {test_stock} 的日线数据")
                    logger.info(f"数据包含字段: {list(data_dict.keys())}")
                    for field in data_dict:
                        df = data_dict[field]
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            logger.info(f"字段 {field} 包含 {len(df)} 条记录")
                            if len(df) > 0:
                                logger.info(f"数据示例:\n{df.head(2)}")
            except Exception as e:
                logger.error(f"使用get_market_data获取数据时出错: {str(e)}")
                logger.error(f"错误类型: {type(e).__name__}")
                # 尝试调用其他API方法获取数据
                try:
                    logger.info("尝试使用其他方法获取数据...")
                    tick_data = xt.get_full_tick([test_stock])
                    logger.info(f"使用get_full_tick获取到的数据: {tick_data}")
                except Exception as e2:
                    logger.error(f"尝试替代方法也失败: {str(e2)}")
        else:
            logger.error(f"订阅 {test_stock} 日线行情失败")
        
        # 2. 测试订阅分钟线行情
        logger.info(f"订阅 {test_stock} 的1分钟行情")
        # 分钟级别数据一般只需要获取最近几天
        short_start = (datetime.now() - timedelta(days=3)).strftime('%Y%m%d')
        try:
            seq2 = xt.subscribe_quote(
                test_stock,
                period='1m',
                start_time=short_start,
                end_time=end_time, 
                count=-1,
                callback=on_quote_data
            )
        except Exception as e:
            logger.error(f"订阅分钟线行情时出错: {str(e)}")
            seq2 = -1
        
        if seq2 > 0:
            logger.info(f"成功订阅 {test_stock} 1分钟线行情，订阅号: {seq2}")
            subscribed_seqs.append(seq2)
            success_count += 1
            
            # 等待两秒钟确保订阅生效
            logger.info("等待2秒钟让订阅生效...")
            time.sleep(2)
            
            # 使用get_market_data获取数据
            logger.info(f"使用get_market_data获取 {test_stock} 的1分钟线数据")
            try:
                data_dict = xt.get_market_data(
                    stock_list=[test_stock],  # 修正：使用stock_list而非symbol
                    period='1m', 
                    start_time=short_start,
                    end_time=end_time,
                    count=-1
                )
                
                if data_dict is not None and len(data_dict) > 0:
                    logger.info(f"成功获取 {test_stock} 的1分钟线数据")
                    logger.info(f"数据包含字段: {list(data_dict.keys())}")
                else:
                    logger.warning(f"未获取到 {test_stock} 的1分钟线数据或数据为空")
            except Exception as e:
                logger.error(f"获取1分钟线数据时出错: {str(e)}")
        
        # 3. 测试订阅Tick行情
        logger.info(f"订阅 {test_stock} 的Tick行情")
        try:
            seq3 = xt.subscribe_quote(
                test_stock,
                period='tick',
                callback=on_quote_data
            )
        except Exception as e:
            logger.error(f"订阅Tick行情时出错: {str(e)}")
            seq3 = -1
        
        if seq3 > 0:
            logger.info(f"成功订阅 {test_stock} Tick行情，订阅号: {seq3}")
            subscribed_seqs.append(seq3)
            success_count += 1
        else:
            logger.error(f"订阅 {test_stock} Tick行情失败")
        
        # 等待几秒钟接收可能的行情推送
        logger.info("等待5秒接收行情推送...")
        time.sleep(5)
        
        # 取消订阅
        for seq in subscribed_seqs:
            logger.info(f"取消订阅号: {seq}")
            xt.unsubscribe_quote(seq)
        
        logger.info(f"行情订阅成功率: {success_count}/3")
        return subscribed_seqs  # 返回订阅序号列表，而不是布尔值
    except Exception as e:
        logger.error(f"订阅行情数据时出错: {str(e)}")
        return []  # 发生错误时返回空列表

def test_get_market_data_after_download(stocks):
    """测试下载历史数据后获取行情数据"""
    logger.info("=== 测试下载后使用get_market_data获取数据 ===")
    
    try:
        # 设置日期范围
        end_time = datetime.now().strftime('%Y%m%d')
        start_time = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        
        success_count = 0
        
        # 确保已下载数据
        test_stock = stocks[0]
        logger.info(f"确保已下载 {test_stock} 的日线数据")
        xt.download_history_data(
            test_stock,
            period='1d', 
            start_time=start_time,
            end_time=end_time
        )
        
        # 使用get_market_data获取数据
        logger.info(f"使用get_market_data获取 {test_stock} 的日线数据")
        data_dict = xt.get_market_data(
            stock_list=[test_stock],  # 修正：使用stock_list而非symbol
            period='1d', 
            start_time=start_time,
            end_time=end_time,
            count=-1,
            dividend_type='front'
        )
        
        if data_dict is not None:
            logger.info(f"成功获取 {test_stock} 的日线数据")
            
            # 处理并展示数据
            if isinstance(data_dict, dict):
                logger.info(f"数据格式为字典，包含键: {list(data_dict.keys())}")
                
                for field in data_dict:
                    df = data_dict[field]
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        logger.info(f"字段 {field} 包含 {len(df)} 条记录")
                        if len(df) > 0:
                            logger.info(f"数据示例:\n{df.head(2)}")
                            success_count += 1
                    else:
                        logger.warning(f"字段 {field} 的数据为空或非DataFrame类型")
            else:
                logger.warning(f"返回的不是字典类型: {type(data_dict)}")
        
        # 测试不同周期
        test_periods = ['1m', '5m']
        short_start = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
        
        for period in test_periods:
            try:
                logger.info(f"确保已下载 {test_stock} 的 {period} 周期数据")
                xt.download_history_data(
                    test_stock,
                    period=period,
                    start_time=short_start,
                    end_time=end_time
                )
                
                logger.info(f"使用get_market_data获取 {test_stock} 的 {period} 周期数据")
                period_data = xt.get_market_data(
                    stock_list=[test_stock],  # 修正：使用stock_list而非symbol
                    period=period,
                    start_time=short_start,
                    end_time=end_time,
                    count=-1,
                    dividend_type='front'
                )
                
                if period_data is not None and isinstance(period_data, dict):
                    has_data = False
                    
                    for field in period_data:
                        df = period_data[field]
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            logger.info(f"{period}周期 {field}字段 包含 {len(df)} 条记录")
                            if len(df) > 0:
                                logger.info(f"数据示例:\n{df.head(2)}")
                                has_data = True
                    
                    if has_data:
                        logger.info(f"成功获取 {period} 周期数据")
                        success_count += 1
                    else:
                        logger.warning(f"获取的 {period} 周期数据为空")
                else:
                    logger.warning(f"获取 {period} 周期数据失败或非字典类型")
            except Exception as e:
                logger.error(f"获取 {period} 周期数据时出错: {str(e)}")
        
        logger.info(f"下载后数据获取成功率: {success_count}/{1+len(test_periods)}")
        return success_count > 0
    except Exception as e:
        logger.error(f"下载后获取数据时出错: {str(e)}")
        return False

def test_get_market_data_after_subscribe(stocks):
    """测试订阅行情后获取数据"""
    logger.info("=== 测试订阅后使用get_market_data获取数据 ===")
    
    try:
        success_count = 0
        subscribed_seqs = []
        
        # 订阅行情
        test_stock = stocks[0]
        
        def on_quote_data(datas):
            logger.info(f"收到行情回调数据: {list(datas.keys())}")
        
        # 订阅日线行情，包含历史数据
        end_time = datetime.now().strftime('%Y%m%d')
        start_time = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
        
        logger.info(f"订阅 {test_stock} 的日线行情，包含历史数据")
        seq = xt.subscribe_quote(
            test_stock,
            period='1d',
            start_time=start_time,
            end_time=end_time,
            count=-1,  # 获取所有数据
            callback=on_quote_data
        )
        
        if seq > 0:
            logger.info(f"成功订阅 {test_stock} 日线行情，订阅号: {seq}")
            subscribed_seqs.append(seq)
            
            # 等待一秒钟确保订阅生效
            time.sleep(1)
            
            # 使用get_market_data获取数据
            logger.info(f"使用get_market_data获取 {test_stock} 的日线数据")
            data_dict = xt.get_market_data(
                stock_list=[test_stock],  # 修正：使用stock_list而非symbol
                period='1d', 
                start_time=start_time,
                end_time=end_time,
                count=-1,
                dividend_type='front'
            )
            
            if data_dict is not None:
                logger.info(f"成功获取 {test_stock} 的日线数据")
                
                # 处理并展示数据
                if isinstance(data_dict, dict):
                    logger.info(f"数据格式为字典，包含键: {list(data_dict.keys())}")
                    
                    for field in data_dict:
                        df = data_dict[field]
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            logger.info(f"字段 {field} 包含 {len(df)} 条记录")
                            if len(df) > 0:
                                logger.info(f"数据示例:\n{df.head(2)}")
                                success_count += 1
        
        # 测试订阅分钟线数据
        logger.info(f"订阅 {test_stock} 的1分钟线行情")
        seq = xt.subscribe_quote(
            test_stock,
            period='1m',
            start_time=start_time,
            end_time=end_time,
            count=-1,
            callback=on_quote_data
        )
        
        if seq > 0:
            logger.info(f"成功订阅 {test_stock} 1分钟线行情，订阅号: {seq}")
            subscribed_seqs.append(seq)
            
            # 等待一秒钟确保订阅生效
            time.sleep(1)
            
            # 使用get_market_data获取数据
            logger.info(f"使用get_market_data获取 {test_stock} 的1分钟线数据")
            data_dict = xt.get_market_data(
                stock_list=[test_stock],  # 修正：使用stock_list而非symbol
                period='1m', 
                start_time=start_time,
                end_time=end_time,
                count=-1
            )
            
            if data_dict is not None and isinstance(data_dict, dict) and len(data_dict) > 0:
                logger.info(f"成功获取 {test_stock} 的1分钟线数据")
                logger.info(f"数据包含字段: {list(data_dict.keys())}")
                success_count += 1
        
        # 测试订阅Tick数据
        logger.info(f"订阅 {test_stock} 的Tick行情")
        seq = xt.subscribe_quote(
            test_stock,
            period='tick',
            count=0,  # 仅订阅实时行情
            callback=on_quote_data
        )
        
        if seq > 0:
            logger.info(f"成功订阅 {test_stock} Tick行情，订阅号: {seq}")
            subscribed_seqs.append(seq)
            
            # 等待两秒钟确保收到一些实时数据
            logger.info("等待2秒钟以接收实时Tick数据...")
            time.sleep(2)
            
            # 使用get_market_data获取数据
            logger.info(f"使用get_market_data获取 {test_stock} 的Tick数据")
            data_dict = xt.get_market_data(
                stock_list=[test_stock],  # 修正：使用stock_list而非symbol
                period='tick',
                count=10  # 获取最近10条
            )
            
            if data_dict is not None and isinstance(data_dict, dict):
                logger.info(f"成功获取 {test_stock} 的Tick数据")
                
                for stock_code in data_dict:
                    tick_data = data_dict[stock_code]
                    if hasattr(tick_data, '__len__') and len(tick_data) > 0:
                        logger.info(f"获取到 {len(tick_data)} 条Tick数据")
                        if len(tick_data) > 0:
                            logger.info(f"数据示例: {tick_data[0]}")
                            success_count += 1
        
        # 取消所有订阅
        for seq in subscribed_seqs:
            logger.info(f"取消订阅 {seq}")
            xt.unsubscribe_quote(seq)
        
        logger.info(f"订阅行情测试完成，成功获取数据: {success_count} 次")
        return success_count > 0
    
    except Exception as e:
        logger.error(f"订阅行情测试出错: {str(e)}")
        
        # 确保取消所有订阅
        try:
            for seq in subscribed_seqs:
                xt.unsubscribe_quote(seq)
        except:
            pass
            
        return False


def test_get_full_tick(stocks):
    """测试获取Tick数据"""
    logger.info("=== 测试获取Tick数据 ===")
    
    try:
        success_count = 0
        
        for stock in stocks:
            try:
                logger.info(f"获取 {stock} 的Tick数据")
                tick_data = xt.get_full_tick([stock])
                
                if tick_data and stock in tick_data:
                    logger.info(f"成功获取 {stock} 的Tick数据")
                    logger.info(f"数据内容: {tick_data[stock]}")
                    success_count += 1
                else:
                    logger.warning(f"未获取到 {stock} 的Tick数据")
                    if tick_data:
                        logger.debug(f"返回的键: {list(tick_data.keys())}")
            except Exception as e:
                logger.error(f"获取 {stock} 的Tick数据时出错: {str(e)}")
        
        logger.info(f"Tick数据获取成功率: {success_count}/{len(stocks)}")
        return success_count > 0
    except Exception as e:
        logger.error(f"获取Tick数据时出错: {str(e)}")
        return False

def test_get_market_data(stocks):
    """测试获取历史行情数据"""
    logger.info("=== 测试获取历史行情数据 ===")
    
    try:
        # 设置日期范围
        end_time = datetime.now().strftime('%Y%m%d')
        start_time = (datetime.now().replace(month=1, day=1)).strftime('%Y%m%d')  # 当年Jan.1
        
        logger.info(f"获取 {start_time} 至 {end_time} 的日线数据")
        
        success_count = 0
        
        for stock in stocks:
            try:
                logger.info(f"获取 {stock} 的历史数据")
                # 修正API调用方式，使用正确的参数名
                df = xt.get_market_data(
                    stock_list=[stock],  # 直接将股票代码列表作为第一个参数
                    period='1d', 
                    start_time=start_time,  # 修改为start_time
                    end_time=end_time,      # 修改为end_time
                    count=-1,  # 获取所有可用数据
                    dividend_type='front'  # 前复权
                )
                
                if df is not None and not (isinstance(df, pd.DataFrame) and df.empty):
                    logger.info(f"成功获取 {stock} 的历史数据")
                    
                    # 改进数据类型和结构判断
                    if isinstance(df, pd.DataFrame):
                        logger.info(f"数据格式为DataFrame，包含 {len(df)} 条记录")
                        logger.info(f"数据列: {df.columns.tolist()}")
                        logger.info(f"数据示例:\n{df.head(2)}")
                    else:
                        logger.warning(f"未知数据格式: {type(df)}")
                        logger.warning(f"数据内容: {df}")
                    
                    success_count += 1
                else:
                    logger.warning(f"未获取到 {stock} 的历史数据")
                    if df is not None:
                        logger.warning(f"返回数据类型: {type(df)}")
            except Exception as e:
                logger.error(f"获取 {stock} 的历史数据时出错: {str(e)}")
        
        # 测试不同周期数据
        if success_count > 0:
            test_periods = ['1m', '5m', '15m', '30m', '60m']
            logger.info("测试获取不同周期的数据")
            for period in test_periods:
                try:
                    logger.info(f"尝试获取 {stocks[0]} 的 {period} 周期数据")
                    # 分钟级别数据一般只需要获取最近几天
                    short_start = (datetime.now() - timedelta(days=3)).strftime('%Y%m%d')
                    
                    minute_df = xt.get_market_data(
                        stock_list=[stocks[0]],  # 直接将股票代码列表作为第一个参数
                        period=period,
                        start_time=short_start,  # 修改为start_time
                        end_time=end_time,       # 修改为end_time
                        count=-1,
                        dividend_type='front'
                    )
                    
                    if minute_df is not None:
                        logger.info(f"成功获取 {period} 周期数据")
                    else:
                        logger.warning(f"未能获取 {period} 周期数据")
                except Exception as e:
                    logger.error(f"获取 {period} 周期数据时出错: {str(e)}")
        
        logger.info(f"历史数据获取成功率: {success_count}/{len(stocks)}")
        return success_count > 0
    except Exception as e:
        logger.error(f"获取历史数据时出错: {str(e)}")
        return False


def test_unsubscribe_and_disconnect(subscribed_stocks):
    """测试取消订阅和断开连接"""
    logger.info("=== 测试取消订阅和断开连接 ===")
    
    try:
        # 检查subscribed_stocks是否为列表类型
        if isinstance(subscribed_stocks, list) and subscribed_stocks:
            logger.info(f"取消订阅 {len(subscribed_stocks)} 个订阅序号")
            for seq in subscribed_stocks:
                result = xt.unsubscribe_quote(seq)
                if result:
                    logger.info(f"取消订阅序号 {seq} 成功")
                else:
                    logger.warning(f"取消订阅序号 {seq} 失败")
        else:
            logger.info("没有需要取消的订阅")
        
        logger.info("断开XtQuant连接")
        xt.disconnect()
        logger.info("断开连接成功")
        
        return True
    except Exception as e:
        logger.error(f"取消订阅和断开连接时出错: {str(e)}")
        return False

def run_all_tests():
    """运行所有测试"""
    logger.info("开始XtQuant API测试...")
    
    # 连接测试
    if not test_connection():
        logger.error("连接测试失败，终止测试")
        return False
    
    # 订阅测试
    subscribed_seqs = test_subscribe_quote(TEST_STOCKS)
    
    # # Tick数据测试
    # test_get_full_tick(TEST_STOCKS)
    
    # # 历史数据测试
    # test_download_history_data(TEST_STOCKS)
    
    # # 下载后获取数据测试
    # test_get_market_data_after_download(TEST_STOCKS)
    
    # # 订阅后获取数据测试
    # test_get_market_data_after_subscribe(TEST_STOCKS)

    # 取消订阅和断开连接测试
    # test_unsubscribe_and_disconnect(subscribed_seqs)
    
    logger.info("XtQuant API测试完成")
    return True

if __name__ == "__main__":
    run_all_tests()
