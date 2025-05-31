# realtime_data_manager.py
"""
实时数据管理模块，支持多数据源获取实时行情
"""
import requests
import json
import time
import threading
from datetime import datetime
import config
from logger import get_logger

logger = get_logger("realtime_data_manager")

class DataSource:
    """数据源基类"""
    def __init__(self, name, timeout=5):
        self.name = name
        self.timeout = timeout
        self.error_count = 0
        self.max_errors = 3
        self.last_success_time = None
        self.is_healthy = True
    
    def get_data(self, stock_code):
        """获取数据的抽象方法"""
        raise NotImplementedError
    
    def reset_errors(self):
        """重置错误计数"""
        self.error_count = 0
        self.is_healthy = True
        self.last_success_time = datetime.now()
    
    def record_error(self):
        """记录错误"""
        self.error_count += 1
        if self.error_count >= self.max_errors:
            self.is_healthy = False
            logger.warning(f"数据源 {self.name} 错误次数达到上限，标记为不健康")

class XtQuantSource(DataSource):
    """XtQuant数据源 - 直接实现数据获取"""
    def __init__(self):
        super().__init__("XtQuant", timeout=5)
        self._init_xtquant()
    
    def _init_xtquant(self):
        """初始化xtquant连接"""
        try:
            import xtquant.xtdata as xt
            self.xt = xt
            if not xt.connect():
                logger.error("XtQuant连接失败")
                self.is_healthy = False
            else:
                logger.info("XtQuant连接成功")
        except Exception as e:
            logger.error(f"XtQuant初始化失败: {str(e)}")
            self.xt = None
            self.is_healthy = False
    
    def _adjust_stock_code(self, stock_code):
        """调整股票代码格式"""
        if '.' not in stock_code:
            if stock_code.startswith(('600', '601', '603', '688', '510')):
                return f"{stock_code}.SH"
            else:
                return f"{stock_code}.SZ"
        return stock_code.upper()
    
    def get_data(self, stock_code):
        """直接从xtquant获取数据"""
        try:
            if not self.xt:
                self.record_error()
                return None
                
            formatted_code = self._adjust_stock_code(stock_code)
            
            # 直接调用xtquant接口
            tick_data = self.xt.get_full_tick([formatted_code])
            
            if not tick_data or formatted_code not in tick_data:
                self.record_error()
                return None
            
            tick = tick_data[formatted_code]
            
            result = {
                'stock_code': stock_code,
                'lastPrice': float(getattr(tick, 'lastPrice', 0)),
                'open': float(getattr(tick, 'open', 0)),
                'high': float(getattr(tick, 'high', 0)),
                'low': float(getattr(tick, 'low', 0)),
                'volume': int(getattr(tick, 'volume', 0)),
                'amount': float(getattr(tick, 'amount', 0)),
                'lastClose': float(getattr(tick, 'lastClose', 0)),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': self.name
            }
            
            if result['lastPrice'] > 0:
                self.reset_errors()
                return result
            else:
                self.record_error()
                return None
                
        except Exception as e:
            self.record_error()
            logger.warning(f"XtQuant获取{stock_code}数据失败: {str(e)}")
            return None

class MootdxSource(DataSource):
    """Mootdx数据源"""
    def __init__(self):
        super().__init__("Mootdx", timeout=5)
        try:
            from mootdx.quotes import Quotes
            self.client = Quotes.factory('std')
            logger.info("Mootdx客户端初始化成功")
        except Exception as e:
            logger.error(f"Mootdx客户端初始化失败: {str(e)}")
            self.client = None
    
    def _format_stock_code(self, stock_code):
        """格式化股票代码为mootdx格式"""
        if stock_code.endswith(('.SH', '.SZ', '.sh', '.sz')):
            code = stock_code.split('.')[0]
        else:
            code = stock_code
        return code
    
    def get_data(self, stock_code):
        """从mootdx获取实时数据"""
        try:
            if not self.client:
                self.record_error()
                return None
                
            code = self._format_stock_code(stock_code)
            
            # 使用bars方法获取最新数据
            try:
                data = self.client.bars(symbol=code, frequency=9, offset=1)
                
                if data is not None and len(data) > 0:
                    latest = data.iloc[-1]
                    
                    result = {
                        'stock_code': stock_code,
                        'lastPrice': float(latest.get('close', 0)),
                        'open': float(latest.get('open', 0)),
                        'high': float(latest.get('high', 0)),
                        'low': float(latest.get('low', 0)),
                        'volume': int(latest.get('vol', 0)),
                        'amount': float(latest.get('amount', 0)),
                        'lastClose': float(latest.get('close', 0)),
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'source': self.name
                    }
                    
                    self.reset_errors()
                    logger.debug(f"Mootdx获取{stock_code}数据成功: {result['lastPrice']}")
                    return result
                    
            except Exception as e:
                logger.warning(f"Mootdx bars方法失败，尝试quote方法: {str(e)}")
                
                # 备用方案：使用quote方法
                quotes = self.client.quote(symbol=code)
                
                if quotes and len(quotes) > 0:
                    quote = quotes[0]
                    
                    result = {
                        'stock_code': stock_code,
                        'lastPrice': float(quote.get('price', 0)),
                        'open': float(quote.get('open', 0)),
                        'high': float(quote.get('high', 0)),
                        'low': float(quote.get('low', 0)),
                        'volume': int(quote.get('vol', 0)),
                        'amount': float(quote.get('amount', 0)),
                        'lastClose': float(quote.get('last_close', quote.get('price', 0))),
                        'changePercent': float(quote.get('change_pct', 0)),
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'source': self.name
                    }
                    
                    self.reset_errors()
                    logger.debug(f"Mootdx quote获取{stock_code}数据成功: {result['lastPrice']}")
                    return result
            
            self.record_error()
            logger.warning(f"Mootdx无法获取{stock_code}的有效数据")
            return None
            
        except Exception as e:
            self.record_error()
            logger.error(f"Mootdx获取{stock_code}数据异常: {str(e)}")
            return None

class RealtimeDataManager:
    """实时数据管理器"""
    def __init__(self):
        self.data_sources = []
        self.current_source = None
        
        # 初始化数据源
        try:
            xtquant_source = XtQuantSource()
            self.data_sources.append(xtquant_source)
            logger.info("XtQuant数据源初始化成功")
        except Exception as e:
            logger.error(f"XtQuant数据源初始化失败: {str(e)}")
        
        try:
            mootdx_source = MootdxSource()
            self.data_sources.append(mootdx_source)
            logger.info("Mootdx数据源初始化成功")
        except Exception as e:
            logger.error(f"Mootdx数据源初始化失败: {str(e)}")
        
        # 设置默认数据源
        if self.data_sources:
            self.current_source = self.data_sources[0]
            logger.info(f"默认数据源设置为: {self.current_source.name}")
        else:
            logger.error("没有可用的数据源！")
        
        # 健康检查配置
        self.health_check_interval = getattr(config, 'REALTIME_DATA_CONFIG', {}).get('health_check_interval', 30)
        self.last_health_check = 0
    
    def _health_check(self):
        """健康检查"""
        current_time = time.time()
        if current_time - self.last_health_check < self.health_check_interval:
            return
        
        self.last_health_check = current_time
        
        # 重置长时间未使用的数据源错误计数
        for source in self.data_sources:
            if source.last_success_time:
                time_since_success = current_time - source.last_success_time.timestamp()
                if time_since_success > 300:  # 5分钟未成功，重置错误计数
                    source.error_count = max(0, source.error_count - 1)
                    if source.error_count == 0:
                        source.is_healthy = True
    
    def get_realtime_data(self, stock_code):
        """获取实时数据 - 核心方法"""
        try:
            # 检查是否有可用数据源
            if not self.data_sources:
                logger.error("没有可用的数据源")
                return None
            
            # 如果当前数据源为空，设置默认数据源
            if not self.current_source:
                self.current_source = self.data_sources[0]
                logger.info(f"设置默认数据源: {self.current_source.name}")
            
            self._health_check()
            
            # 首先尝试当前数据源
            if self.current_source and self.current_source.is_healthy:
                try:
                    data = self.current_source.get_data(stock_code)
                    if data and data.get('lastPrice', 0) > 0:
                        return data
                except Exception as e:
                    logger.warning(f"当前数据源 {self.current_source.name} 获取数据失败: {str(e)}")
            
            # 尝试其他健康的数据源
            for source in self.data_sources:
                if source != self.current_source and source.is_healthy:
                    try:
                        logger.info(f"尝试使用 {source.name} 获取 {stock_code} 数据")
                        data = source.get_data(stock_code)
                        if data and data.get('lastPrice', 0) > 0:
                            logger.info(f"切换到 {source.name} 成功")
                            self.current_source = source
                            return data
                    except Exception as e:
                        logger.warning(f"数据源 {source.name} 获取数据失败: {str(e)}")
            
            # 如果所有健康数据源都失败，尝试不健康的数据源（给一次机会）
            for source in self.data_sources:
                if not source.is_healthy:
                    try:
                        logger.info(f"尝试使用不健康数据源 {source.name} 获取 {stock_code} 数据")
                        data = source.get_data(stock_code)
                        if data and data.get('lastPrice', 0) > 0:
                            logger.info(f"不健康数据源 {source.name} 恢复成功")
                            self.current_source = source
                            return data
                    except Exception as e:
                        logger.warning(f"不健康数据源 {source.name} 仍然失败: {str(e)}")
            
            logger.error(f"所有数据源都失败，无法获取 {stock_code} 的实时数据")
            return None
            
        except Exception as e:
            logger.error(f"获取实时数据时发生异常: {str(e)}")
            return None
    
    def get_source_status(self):
        """获取数据源状态"""
        try:
            status = []
            for source in self.data_sources:
                status.append({
                    'name': source.name,
                    'is_healthy': source.is_healthy,
                    'error_count': source.error_count,
                    'is_current': source == self.current_source,
                    'last_success': source.last_success_time.isoformat() if source.last_success_time else None
                })
            return status
        except Exception as e:
            logger.error(f"获取数据源状态失败: {str(e)}")
            return []
    
    def switch_to_source(self, source_name: str) -> bool:
        """切换到指定数据源"""
        try:
            target_source = None
            for source in self.data_sources:
                if source.name == source_name:
                    target_source = source
                    break
            
            if not target_source:
                available_sources = [s.name for s in self.data_sources]
                logger.error(f"未找到数据源: {source_name}，可用数据源: {available_sources}")
                return False
            
            old_source_name = self.current_source.name if self.current_source else "None"
            self.current_source = target_source
            
            # 重置目标数据源的错误计数
            target_source.reset_errors()
            
            logger.info(f"数据源已从 {old_source_name} 切换到 {source_name}")
            return True
            
        except Exception as e:
            logger.error(f"切换数据源失败: {str(e)}")
            return False

# 单例模式
_instance = None

def get_realtime_data_manager():
    """获取RealtimeDataManager单例"""
    global _instance
    if _instance is None:
        try:
            _instance = RealtimeDataManager()
            logger.info("RealtimeDataManager单例创建成功")
        except Exception as e:
            logger.error(f"RealtimeDataManager单例创建失败: {str(e)}")
            _instance = None
    return _instance