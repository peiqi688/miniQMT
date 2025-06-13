# coding=utf-8
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

# Create the 'logs' directory if it doesn't exist
logs_dir = 'logs'
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# Set the log file path within the 'logs' directory
log_file_path = os.path.join(logs_dir, 'xtquant_debug.log')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),  # Use the new path
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

# 在文件开头导入xttrader模块
try:
    import xtquant.xttrader as xtt
    logger.info("成功导入 xtquant.xttrader 模块")
except ImportError as e:
    logger.error(f"导入 xtquant.xttrader 模块失败: {str(e)}")
    logger.info("部分交易测试功能将不可用")

# 交易测试相关常量
DIRECTION_BUY = 48   # 买入方向
DIRECTION_SELL = 49  # 卖出方向

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
        today = datetime.now()
        end_time = today.strftime('%Y%m%d')
        start_time = (today - timedelta(days=60)).strftime('%Y%m%d')  # 获取最近60天数据，确保包含足够的交易日
        
        logger.info(f"下载 {start_time} 至 {end_time} 的日线数据")
        
        # 先获取交易日列表，确保有可用的交易日数据
        trading_dates = xt.get_trading_dates('SH', start_time, end_time)
        if not trading_dates:
            logger.warning("所选日期范围内没有交易日，请选择更大的日期范围")
            trading_dates = xt.get_trading_dates('SH', (today - timedelta(days=365)).strftime('%Y%m%d'), end_time)
            if trading_dates:
                start_time = datetime.fromtimestamp(trading_dates[0]).strftime('%Y%m%d')
                end_time = datetime.fromtimestamp(trading_dates[-1]).strftime('%Y%m%d')
                logger.info(f"调整为有效交易日范围: {start_time} 至 {end_time}")
        
        success_count = 0
        
        # 1. 测试单个股票下载
        test_stock = stocks[0]
        logger.info(f"单个下载: {test_stock}的日线数据")
        # download_history_data不返回数据，只是下载到本地缓存
        xt.download_history_data(
            test_stock,
            period='1d', 
            start_time=start_time,
            end_time=end_time
        )
        
        # 使用get_market_data获取已下载的数据
        data = xt.get_market_data(
            stock_list=[test_stock],
            period='1d',
            start_time=start_time,
            end_time=end_time,
            count=-1
        )
        
        if data and len(data) > 0:
            logger.info(f"成功下载 {test_stock} 的日线数据")
            for field in data:
                df = data[field]
                if isinstance(df, pd.DataFrame) and not df.empty:
                    logger.info(f"字段 {field} 包含 {len(df)} 条记录")
                    if len(df) > 0:
                        logger.info(f"数据示例:\n{df.head(2)}")
        else:
            logger.warning(f"下载 {test_stock} 的数据为空或未能成功获取")
        
        logger.info(f"下载完成: {test_stock}")
        success_count += 1
        
        # 2. 测试批量下载
        logger.info(f"批量下载: {len(stocks)}只股票的日线数据")
        
        def on_progress(data):
            logger.info(f"下载进度: {data['finished']}/{data['total']} - {data['stockcode']}")
        
        # download_history_data2也不返回数据
        xt.download_history_data2(
            stocks,
            period='1d', 
            start_time=start_time,
            end_time=end_time,
            callback=on_progress
        )
        
        # 验证批量下载的数据
        batch_data = xt.get_market_data(
            stock_list=stocks,
            period='1d',
            start_time=start_time,
            end_time=end_time,
            count=-1
        )
        
        if batch_data and len(batch_data) > 0:
            logger.info(f"批量下载数据成功，包含字段: {list(batch_data.keys())}")
            for field in batch_data:
                df = batch_data[field]
                if isinstance(df, pd.DataFrame) and not df.empty:
                    logger.info(f"字段 {field} 包含 {len(df)} 条记录")
                    if len(df) > 0:
                        logger.info(f"数据示例:\n{df.head(2)}")
        else:
            logger.warning(f"批量下载的数据为空或未能成功获取")
        
        logger.info("批量下载完成")
        success_count += 1
        
        # 3. 测试不同周期数据的下载
        test_periods = ['1m', '5m']
        short_start = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
        
        for period in test_periods:
            try:
                logger.info(f"下载 {test_stock} 的 {period} 周期数据")
                xt.download_history_data(
                    test_stock,
                    period=period,
                    start_time=short_start,
                    end_time=end_time
                )
                
                # 验证各周期数据下载情况
                period_data = xt.get_market_data(
                    stock_list=[test_stock],
                    period=period,
                    start_time=short_start,
                    end_time=end_time,
                    count=-1
                )
                
                if period_data and len(period_data) > 0:
                    logger.info(f"成功下载 {period} 周期数据")
                    for field in period_data:
                        df = period_data[field]
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            logger.info(f"{period}周期 {field}字段 包含 {len(df)} 条记录")
                            if len(df) > 0:
                                logger.info(f"数据示例:\n{df.head(2)}")
                else:
                    logger.warning(f"下载 {test_stock} 的 {period} 周期数据为空或未能成功获取")

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
        # 设置日期范围 - 使用更合理的历史日期范围
        today = datetime.now()
        end_time = today.strftime('%Y%m%d')
        start_time = (today - timedelta(days=30)).strftime('%Y%m%d')  # 减少范围到30天
        
        logger.info(f"设置初始日期范围: {start_time} 至 {end_time}")
        
        # 先下载数据确保本地有缓存
        test_stock = stocks[0]
        logger.info(f"确保已下载 {test_stock} 的日线数据")
        try:
            xt.download_history_data(
                test_stock,
                period='1d', 
                start_time=start_time,
                end_time=end_time
            )
            logger.info(f"成功下载 {test_stock} 的历史数据")
        except Exception as e:
            logger.error(f"下载历史数据失败: {str(e)}")
            # 如果下载失败，尝试扩大日期范围
            start_time = (today - timedelta(days=60)).strftime('%Y%m%d')
            logger.info(f"尝试扩大范围: {start_time} 至 {end_time}")
            xt.download_history_data(
                test_stock,
                period='1d', 
                start_time=start_time,
                end_time=end_time
            )
        
        # 使用get_market_data获取数据，增加错误处理和详细日志
        logger.info(f"使用get_market_data获取 {test_stock} 的日线数据")
        logger.info(f"参数: stock_list=[{test_stock}], period=1d, start_time={start_time}, end_time={end_time}")
        
        try:
            # 简化调用，避免使用可能有问题的交易日列表
            data_dict = xt.get_market_data(
                stock_list=[test_stock],
                period='1d', 
                start_time=start_time,
                end_time=end_time,
                count=-1
            )
            
            logger.info(f"API返回数据类型: {type(data_dict)}")
            
            if data_dict is not None:
                logger.info(f"成功获取 {test_stock} 的日线数据")
                
                # 处理并展示数据
                if isinstance(data_dict, dict):
                    logger.info(f"数据格式为字典，包含键: {list(data_dict.keys())}")
                    success_count = 0
                    
                    # 检查是否有数据并打印 - 修正判断逻辑
                    for field, df in data_dict.items():
                        if isinstance(df, pd.DataFrame):
                            if df.empty:
                                logger.info(f"字段 {field} 返回了空DataFrame，形状为 {df.shape}")
                            else:
                                logger.info(f"字段 {field} 包含形状为 {df.shape} 的DataFrame")
                                logger.info(f"数据列: {df.columns.tolist() if hasattr(df, 'columns') else '无列名'}")
                                logger.info(f"数据示例 (前2行):\n{df.head(2)}")
                                success_count += 1
                        else:
                            logger.warning(f"字段 {field} 返回的不是DataFrame类型: {type(df)}")
                else:
                    logger.warning(f"返回的不是字典类型: {type(data_dict)}")
            else:
                logger.warning("API返回了None")
        
        except Exception as e:
            logger.error(f"基本参数调用出错: {str(e)}")
            logger.error(f"错误类型: {type(e).__name__}")
            
            # 尝试更严格的参数设置
            logger.info("尝试使用简化参数...")
            try:
                # 使用当前日期的前一周作为测试
                simple_end = today.strftime('%Y%m%d')
                simple_start = (today - timedelta(days=7)).strftime('%Y%m%d')
                
                data_dict = xt.get_market_data(
                    stock_list=[test_stock],
                    period='1d',
                    start_time=simple_start,
                    end_time=simple_end
                )
                
                if data_dict is not None and isinstance(data_dict, dict):
                    logger.info(f"简化参数成功获取数据，包含键: {list(data_dict.keys())}")
                    return True
            except Exception as e2:
                logger.error(f"简化参数也失败: {str(e2)}")
        
        # 测试更简单的分钟级数据
        try:
            logger.info(f"尝试获取 {test_stock} 的1分钟数据")
            # 使用更短的时间范围
            short_start = (today - timedelta(days=3)).strftime('%Y%m%d')
            short_end = today.strftime('%Y%m%d')
            
            xt.download_history_data(
                test_stock,
                period='1m',
                start_time=short_start,
                end_time=short_end
            )
            
            minute_data = xt.get_market_data(
                stock_list=[test_stock],
                period='1m',
                start_time=short_start,
                end_time=short_end
            )
            
            if minute_data is not None and isinstance(minute_data, dict):
                logger.info(f"成功获取1分钟数据，包含键: {list(minute_data.keys())}")
                # 增加对1分钟数据内容的检查
                empty_count = 0
                data_count = 0
                for field, df in minute_data.items():
                    if isinstance(df, pd.DataFrame):
                        if df.empty:
                            empty_count += 1
                            logger.info(f"1分钟数据字段 {field} 是空DataFrame")
                        else:
                            data_count += 1
                            logger.info(f"1分钟数据字段 {field} 包含 {len(df)} 行数据")
                            if len(df) > 0:
                                logger.info(f"示例数据:\n{df.head(2)}")
                logger.info(f"1分钟数据统计: {data_count} 个字段有数据，{empty_count} 个字段是空DataFrame")
                return data_count > 0
        except Exception as e:
            logger.error(f"获取分钟数据失败: {str(e)}")
        
        return False
    except Exception as e:
        logger.error(f"下载后获取数据时出错: {str(e)}")
        logger.error(f"错误类型: {type(e).__name__}")
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

def test_trader_connection(account_id=None, account_type="STOCK"):
    """测试连接到XtQuant交易服务器"""
    logger.info("=== 测试连接XtQuant交易服务器 ===")
    
    try:
        # 如果未提供账户ID，尝试从配置或环境变量获取
        if account_id is None:
            try:
                import config
                account_config = config.get_account_config()
                account_id = account_config.get('account_id', '')
                account_type = account_config.get('account_type', 'STOCK')
            except:
                logger.warning("未找到账户配置，请手动指定账户ID和类型")
                return False
        
        if not account_id:
            logger.error("未指定交易账户ID，无法连接交易服务器")
            return False
            
        logger.info(f"尝试连接交易账户: {account_id}, 类型: {account_type}")
        
        # 获取API版本
        version = getattr(xtt, 'version', '未知')
        logger.info(f"XtQuant交易API版本: {version}")
        
        # 获取可用方法
        methods = [method for method in dir(xtt) if not method.startswith('_')]
        logger.info(f"XtQuant交易API可用方法: {', '.join(methods[:10])}... (共{len(methods)}个)")
        
        # 尝试创建交易API客户端
        trader = None
        try:
            if hasattr(xtt, 'create_trader'):
                trader = xtt.create_trader()
                logger.info("使用create_trader()创建交易API客户端")
            elif hasattr(xtt, 'XtQuantTrader'):
                trader = xtt.XtQuantTrader(account_id)
                logger.info("使用XtQuantTrader类创建交易API客户端")
            else:
                logger.error("找不到合适的交易API创建方法")
                return False
                
            # 登录账户
            login_result = False
            if hasattr(trader, 'login'):
                login_result = trader.login(account_id, account_type)
                logger.info(f"登录账户结果: {login_result}")
            else:
                logger.error("交易API客户端没有login方法")
                return False
                
            # 等待账户连接
            is_connected = False
            for _ in range(5):
                if hasattr(trader, 'is_connected') and trader.is_connected():
                    is_connected = True
                    logger.info(f"交易账户 {account_id} 连接成功")
                    break
                time.sleep(1)
                
            if not is_connected:
                logger.warning(f"交易账户 {account_id} 连接状态未确认")
                
            return trader
        except Exception as e:
            logger.error(f"创建交易API客户端时出错: {str(e)}")
            return None
    except Exception as e:
        logger.error(f"连接XtQuant交易服务器时出错: {str(e)}")
        return None

def test_get_account_info(trader):
    """测试获取账户信息"""
    logger.info("=== 测试获取账户信息 ===")
    
    try:
        if trader is None:
            logger.error("交易API客户端未初始化")
            return False
            
        try:
            # 尝试获取账户信息
            if hasattr(trader, 'query_account'):
                accounts = trader.query_account()
                logger.info(f"获取到 {len(accounts) if accounts else 0} 个账户信息")
                
                if accounts:
                    for acc in accounts:
                        logger.info(f"账户信息: {acc}")
                        logger.info(f"可用资金: {getattr(acc, 'm_dAvailable', '未知')}")
                        logger.info(f"总资产: {getattr(acc, 'm_dBalance', '未知')}")
                        logger.info(f"持仓市值: {getattr(acc, 'm_dMarket', '未知')}")
                
                return True
            else:
                logger.error("交易API客户端没有query_account方法")
                
                # 尝试其他可能的方法名
                for method_name in ['get_account_info', 'get_accounts', 'query_accounts']:
                    if hasattr(trader, method_name):
                        logger.info(f"尝试使用 {method_name} 方法获取账户信息")
                        method = getattr(trader, method_name)
                        result = method()
                        logger.info(f"获取结果: {result}")
                        return True
                
                return False
        except Exception as e:
            logger.error(f"获取账户信息时出错: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"测试获取账户信息时出错: {str(e)}")
        return False

def test_get_positions(trader):
    """测试获取持仓信息"""
    logger.info("=== 测试获取持仓信息 ===")
    
    try:
        if trader is None:
            logger.error("交易API客户端未初始化")
            return False
            
        try:
            # 尝试获取持仓信息
            if hasattr(trader, 'query_position'):
                positions = trader.query_position()
                logger.info(f"获取到 {len(positions) if positions else 0} 个持仓信息")
                
                if positions:
                    for pos in positions:
                        logger.info(f"持仓信息: {pos}")
                        logger.info(f"股票代码: {getattr(pos, 'm_strInstrumentID', '未知')}")
                        logger.info(f"股票名称: {getattr(pos, 'm_strInstrumentName', '未知')}")
                        logger.info(f"持仓数量: {getattr(pos, 'm_nVolume', '未知')}")
                        logger.info(f"可用数量: {getattr(pos, 'm_nCanUseVolume', '未知')}")
                        logger.info(f"持仓成本: {getattr(pos, 'm_dCostPrice', '未知')}")
                        logger.info(f"最新价格: {getattr(pos, 'm_dLastPrice', '未知')}")
                
                return True
            else:
                logger.error("交易API客户端没有query_position方法")
                
                # 尝试其他可能的方法名
                for method_name in ['get_positions', 'query_positions', 'get_position']:
                    if hasattr(trader, method_name):
                        logger.info(f"尝试使用 {method_name} 方法获取持仓信息")
                        method = getattr(trader, method_name)
                        result = method()
                        logger.info(f"获取结果: {result}")
                        return True
                
                return False
        except Exception as e:
            logger.error(f"获取持仓信息时出错: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"测试获取持仓信息时出错: {str(e)}")
        return False

def test_order_operations(trader, account_id=None, account_type="STOCK"):
    """测试下单和撤单操作"""
    logger.info("=== 测试下单和撤单操作 ===")
    
    if trader is None:
        logger.error("交易API客户端未初始化")
        return False
        
    # 使用上证ETF进行测试
    test_stock = "510050.SH"  # 上证50ETF，流动性好，价格低
    
    try:
        # 1. 获取最新行情
        logger.info(f"获取 {test_stock} 最新行情")
        latest_quote = None
        try:
            if hasattr(xt, 'get_last_ticks'):
                ticks = xt.get_last_ticks([test_stock])
                if ticks and test_stock in ticks:
                    latest_quote = ticks[test_stock]
            elif hasattr(xt, 'get_quote'):
                latest_quote = xt.get_quote(test_stock)
        except Exception as e:
            logger.error(f"获取行情时出错: {str(e)}")
        
        if not latest_quote:
            logger.warning("无法获取最新行情，使用模拟价格测试")
            bid_price = 2.5  # 模拟买一价
            ask_price = 2.51  # 模拟卖一价
            last_price = 2.505  # 模拟最新价
        else:
            logger.info(f"行情数据: {latest_quote}")
            bid_price = getattr(latest_quote, 'bid', None) or getattr(latest_quote, 'bidPrice1', None) or 2.5
            ask_price = getattr(latest_quote, 'ask', None) or getattr(latest_quote, 'askPrice1', None) or 2.51
            last_price = getattr(latest_quote, 'lastPrice', None) or 2.505
            
        logger.info(f"最新价: {last_price}, 买一价: {bid_price}, 卖一价: {ask_price}")
        
        # 2. 测试限价买入
        buy_price = float(bid_price) * 0.99  # 略低于买一价，避免实际成交
        buy_volume = 100  # 买入数量，最小为100股
        
        logger.info(f"测试限价买入 {test_stock}, 价格: {buy_price}, 数量: {buy_volume}")
        buy_order_id = None
        
        try:
            if hasattr(trader, 'limit_order'):
                buy_order_id = trader.limit_order(test_stock, DIRECTION_BUY, buy_price, buy_volume)
            elif hasattr(trader, 'order'):
                buy_order_id = trader.order(test_stock, buy_price, buy_volume, direction=1, order_type=0)
            else:
                logger.error("没有找到可用的买入方法")
        except Exception as e:
            logger.error(f"买入下单时出错: {str(e)}")
            
        if buy_order_id:
            logger.info(f"买入下单成功，委托号: {buy_order_id}")
            
            # 等待一秒查询委托状态
            time.sleep(1)
            
            # 查询委托状态
            try:
                if hasattr(trader, 'query_order'):
                    orders = trader.query_order()
                    if orders:
                        for order in orders:
                            if order.m_strOrderSysID == buy_order_id:
                                logger.info(f"买入委托状态: {order.m_nOrderStatus}")
                                break
            except Exception as e:
                logger.error(f"查询委托时出错: {str(e)}")
            
            # 撤单测试
            logger.info(f"测试撤单，委托号: {buy_order_id}")
            try:
                if hasattr(trader, 'cancel_order'):
                    result = trader.cancel_order(buy_order_id)
                    logger.info(f"撤单结果: {result}")
                else:
                    logger.error("没有找到可用的撤单方法")
            except Exception as e:
                logger.error(f"撤单时出错: {str(e)}")
                
            # 等待撤单处理
            time.sleep(1)
            
            # 再次查询委托状态
            try:
                if hasattr(trader, 'query_order'):
                    orders = trader.query_order()
                    if orders:
                        for order in orders:
                            if order.m_strOrderSysID == buy_order_id:
                                logger.info(f"撤单后委托状态: {order.m_nOrderStatus}")
                                break
            except Exception as e:
                logger.error(f"查询委托时出错: {str(e)}")
        else:
            logger.warning("买入下单失败，跳过撤单测试")
            
        # 3. 测试市价单 (如果API支持)
        logger.info(f"测试市价买入 {test_stock}, 数量: {buy_volume}")
        market_order_id = None
        
        try:
            if hasattr(trader, 'market_order'):
                market_order_id = trader.market_order(test_stock, DIRECTION_BUY, buy_volume)
                logger.info(f"市价买入下单成功，委托号: {market_order_id}")
            else:
                logger.warning("交易API不支持市价单方法，跳过市价单测试")
        except Exception as e:
            logger.error(f"市价买入下单时出错: {str(e)}")
            
        # 总结测试结果
        if buy_order_id or market_order_id:
            logger.info("下单和撤单测试部分成功")
            return True
        else:
            logger.warning("下单和撤单测试失败")
            return False
            
    except Exception as e:
        logger.error(f"测试下单和撤单操作时出错: {str(e)}")
        return False
        
def test_trader_disconnect(trader):
    """测试断开交易连接"""
    logger.info("=== 测试断开交易连接 ===")
    
    try:
        if trader is None:
            logger.warning("交易API客户端未初始化，无需断开连接")
            return True
            
        if hasattr(trader, 'logout'):
            trader.logout()
            logger.info("已登出交易账户")
            
        if hasattr(trader, 'disconnect') or hasattr(trader, 'close'):
            disconnect_method = getattr(trader, 'disconnect', None) or getattr(trader, 'close')
            disconnect_method()
            logger.info("已断开交易连接")
            
        return True
    except Exception as e:
        logger.error(f"断开交易连接时出错: {str(e)}")
        return False

def run_trader_tests(account_id=None, account_type="STOCK"):
    """运行所有交易测试"""
    logger.info("开始XtQuant交易API测试...")
    
    # 连接测试
    trader = test_trader_connection(account_id, account_type)
    if trader is None:
        logger.error("交易API连接测试失败，终止交易测试")
        return False
    
    # 获取账户信息
    test_get_account_info(trader)
    
    # 获取持仓信息
    test_get_positions(trader)
    
    # 下单和撤单测试（可选，默认注释掉以避免实际提交委托）
    # test_order_operations(trader, account_id, account_type)
    
    # 断开连接
    test_trader_disconnect(trader)
    
    logger.info("XtQuant交易API测试完成")
    return True

def run_all_tests(run_trader_tests_flag=False, account_id=None, account_type="STOCK"):
    """运行所有测试"""
    logger.info("开始XtQuant API测试...")
    
    # 检查是否为交易日
    today = datetime.now()
    end_time = today.strftime('%Y%m%d')
    start_time = today.strftime('%Y%m%d')
    trading_dates = xt.get_trading_dates('SH', start_time, end_time)
    
    if not trading_dates:
        logger.warning("今天是非交易日，部分测试可能会返回空数据")
    
    # 连接测试
    if not test_connection():
        logger.error("连接测试失败，终止测试")
        return False
    
    # 订阅测试
    # subscribed_seqs = test_subscribe_quote(TEST_STOCKS)
    
    # Tick数据测试
    test_get_full_tick(TEST_STOCKS)
    
    # # 历史数据测试
    # test_download_history_data(TEST_STOCKS)
    
    # # 下载后获取数据测试
    # test_get_market_data_after_download(TEST_STOCKS)
    
    # # 订阅后获取数据测试
    # test_get_market_data_after_subscribe(TEST_STOCKS)
    
    # 取消订阅和断开连接测试
    # test_unsubscribe_and_disconnect(subscribed_seqs)
    
    # 交易接口测试
    if run_trader_tests_flag:
        run_trader_tests(account_id, account_type)
    
    logger.info("XtQuant API测试完成")
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='XtQuant API测试工具')
    parser.add_argument('--trade', action='store_true', help='运行交易API测试')
    parser.add_argument('--account', type=str, help='交易账户ID')
    parser.add_argument('--type', type=str, default='STOCK', help='账户类型 (默认: STOCK)')
    
    args = parser.parse_args()
    
    if args.trade:
        run_all_tests(True, args.account, args.type)
    else:
        run_all_tests()
