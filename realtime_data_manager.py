"""
修复Windows兼容性问题的实时数据管理器
"""
import time
import json
import requests
import threading
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import platform

import config
from logger import get_logger

logger = get_logger("realtime_data_manager")

class DataSourceStatus(Enum):
    """数据源状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    FAILED = "failed"
    UNKNOWN = "unknown"

class DataSourcePriority(Enum):
    """数据源优先级"""
    PRIMARY = 1
    SECONDARY = 2
    FALLBACK = 3

class BaseDataSource(ABC):
    """数据源基类"""
    
    def __init__(self, name: str, priority: DataSourcePriority):
        self.name = name
        self.priority = priority
        self.status = DataSourceStatus.UNKNOWN
        self.last_error = None
        self.last_success_time = None
        self.error_count = 0
        self.max_error_count = 3
        self.timeout = 5  # 5秒超时
        self.is_windows = platform.system().lower() == 'windows'
        
    @abstractmethod
    def get_tick_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取tick数据的抽象方法"""
        pass
    
    @abstractmethod
    def format_stock_code(self, stock_code: str) -> str:
        """格式化股票代码的抽象方法"""
        pass
    
    def is_healthy(self) -> bool:
        """检查数据源是否健康"""
        return self.status == DataSourceStatus.HEALTHY
    
    def mark_success(self):
        """标记成功"""
        self.status = DataSourceStatus.HEALTHY
        self.last_success_time = datetime.now()
        self.error_count = 0
        self.last_error = None
        
    def mark_error(self, error: Exception):
        """标记错误"""
        self.error_count += 1
        self.last_error = str(error)
        
        if self.error_count >= self.max_error_count:
            self.status = DataSourceStatus.FAILED
            logger.error(f"数据源 {self.name} 已标记为失败，连续错误次数: {self.error_count}")
        else:
            self.status = DataSourceStatus.DEGRADED
            logger.warning(f"数据源 {self.name} 出现错误 ({self.error_count}/{self.max_error_count}): {error}")

class TimeoutHelper:
    """跨平台超时助手"""
    
    @staticmethod
    def run_with_timeout(func, timeout_seconds, *args, **kwargs):
        """
        跨平台的超时执行函数
        
        参数:
        func: 要执行的函数
        timeout_seconds: 超时时间（秒）
        *args, **kwargs: 函数参数
        
        返回:
        函数执行结果，超时则抛出TimeoutError
        """
        result = [None]
        exception = [None]
        
        def target():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout_seconds)
        
        if thread.is_alive():
            # 线程仍在运行，表示超时
            raise TimeoutError(f"函数执行超时 ({timeout_seconds}秒)")
        
        if exception[0]:
            raise exception[0]
        
        return result[0]

class XtQuantDataSource(BaseDataSource):
    """XtQuant数据源 - Windows兼容版本"""
    
    def __init__(self):
        super().__init__("XtQuant", DataSourcePriority.PRIMARY)
        
    def format_stock_code(self, stock_code: str) -> str:
        """格式化为XtQuant格式"""
        if '.' not in stock_code:
            if stock_code.startswith(('600', '601', '603', '688', '510')):
                return f"{stock_code}.SH"
            else:
                return f"{stock_code}.SZ"
        return stock_code.upper()
    
    def get_tick_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取XtQuant tick数据 - Windows兼容版本"""
        try:
            formatted_code = self.format_stock_code(stock_code)
            
            # 使用跨平台超时机制
            def _get_xtquant_data():
                from xtquant import xtdata as xt
                return xt.get_full_tick([formatted_code])
            
            # 执行带超时的数据获取
            latest_quote = TimeoutHelper.run_with_timeout(
                _get_xtquant_data, 
                self.timeout
            )
            
            if latest_quote and formatted_code in latest_quote:
                tick_data = latest_quote[formatted_code]
                result = self._format_output(tick_data, stock_code)
                self.mark_success()
                return result
            else:
                raise ValueError(f"未获取到 {formatted_code} 的数据")
                
        except TimeoutError as e:
            self.mark_error(e)
            logger.warning(f"XtQuant API调用超时: {e}")
            return None
        except Exception as e:
            self.mark_error(e)
            logger.debug(f"XtQuant获取数据失败: {e}")
            return None
    
    def _format_output(self, tick_data: Any, stock_code: str) -> Dict[str, Any]:
        """格式化输出为统一格式"""
        try:
            return {
                'source': self.name,
                'stock_code': stock_code,
                'lastPrice': getattr(tick_data, 'lastPrice', 0) or 
                           getattr(tick_data, 'last', 0),
                'lastClose': getattr(tick_data, 'lastClose', 0) or 
                           getattr(tick_data, 'preClose', 0),
                'open': getattr(tick_data, 'open', 0),
                'high': getattr(tick_data, 'high', 0),
                'low': getattr(tick_data, 'low', 0),
                'volume': getattr(tick_data, 'volume', 0),
                'amount': getattr(tick_data, 'amount', 0),
                'bidPrice': getattr(tick_data, 'bidPrice', [0])[0] if hasattr(tick_data, 'bidPrice') else 0,
                'askPrice': getattr(tick_data, 'askPrice', [0])[0] if hasattr(tick_data, 'askPrice') else 0,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"XtQuant数据格式化失败: {e}")
            return {}

class MoneyDataSource(BaseDataSource):
    """网易财经数据源"""
    
    def __init__(self):
        super().__init__("Money163", DataSourcePriority.SECONDARY)
        self.base_url = "http://api.money.126.net/data/feed/{},money.api"
        
    def format_stock_code(self, stock_code: str) -> str:
        """格式化为网易财经格式"""
        clean_code = stock_code.split('.')[0]
        
        if clean_code.startswith(('600', '601', '603', '688', '510')):
            return f"0{clean_code}"  # 沪市
        else:
            return f"1{clean_code}"  # 深市
    
    def get_tick_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取网易财经tick数据"""
        try:
            formatted_code = self.format_stock_code(stock_code)
            url = self.base_url.format(formatted_code)
            
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # 解析响应
            text = response.text
            text = text.lstrip("_ntes_quote_callback(").rstrip(");")
            data = json.loads(text)
            
            if formatted_code not in data:
                raise ValueError(f"网易财经未返回 {formatted_code} 的数据")
                
            tick_data = data[formatted_code]
            result = self._format_output(tick_data, stock_code)
            self.mark_success()
            return result
            
        except Exception as e:
            self.mark_error(e)
            logger.debug(f"网易财经获取数据失败: {e}")
            return None
    
    def _format_output(self, tick_data: Dict, stock_code: str) -> Dict[str, Any]:
        """格式化输出为统一格式"""
        try:
            return {
                'source': self.name,
                'stock_code': stock_code,
                'lastPrice': float(tick_data.get('price', 0)),
                'lastClose': float(tick_data.get('yestclose', 0)),
                'open': float(tick_data.get('open', 0)),
                'high': float(tick_data.get('high', 0)),
                'low': float(tick_data.get('low', 0)),
                'volume': int(tick_data.get('volume', 0)),
                'amount': float(tick_data.get('turnover', 0)),
                'bidPrice': float(tick_data.get('bid1', 0)),
                'askPrice': float(tick_data.get('ask1', 0)),
                'percent': float(tick_data.get('percent', 0)),
                'timestamp': tick_data.get('time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            }
        except Exception as e:
            logger.error(f"网易财经数据格式化失败: {e}")
            return {}

class MootdxDataSource(BaseDataSource):
    """Mootdx数据源作为兜底"""
    
    def __init__(self):
        super().__init__("Mootdx", DataSourcePriority.FALLBACK)
        
    def format_stock_code(self, stock_code: str) -> str:
        """格式化为Mootdx格式"""
        return stock_code.split('.')[0]  # 移除后缀
    
    def get_tick_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取Mootdx最新日线数据作为兜底"""
        try:
            import Methods
            formatted_code = self.format_stock_code(stock_code)
            
            # 获取最新1天的数据
            df = Methods.getStockData(
                code=formatted_code,
                offset=1,
                freq=9,  # 日线
                adjustflag='qfq'
            )
            
            if df is None or df.empty:
                raise ValueError(f"Mootdx未返回 {formatted_code} 的数据")
            
            latest_data = df.iloc[-1]
            result = self._format_output(latest_data, stock_code)
            self.mark_success()
            return result
            
        except Exception as e:
            self.mark_error(e)
            logger.debug(f"Mootdx获取数据失败: {e}")
            return None
    
    def _format_output(self, latest_data, stock_code: str) -> Dict[str, Any]:
        """格式化输出为统一格式"""
        try:
            return {
                'source': self.name,
                'stock_code': stock_code,
                'lastPrice': float(latest_data.get('close', 0)),
                'lastClose': float(latest_data.get('close', 0)),
                'open': float(latest_data.get('open', 0)),
                'high': float(latest_data.get('high', 0)),
                'low': float(latest_data.get('low', 0)),
                'volume': int(latest_data.get('volume', 0)),
                'amount': float(latest_data.get('amount', 0)),
                'bidPrice': 0,  # 日线数据无买卖价
                'askPrice': 0,
                'timestamp': str(latest_data.get('datetime', datetime.now().strftime('%Y-%m-%d')))
            }
        except Exception as e:
            logger.error(f"Mootdx数据格式化失败: {e}")
            return {}

class RealtimeDataManager:
    """实时数据管理器 - Windows兼容版本"""
    
    def __init__(self):
        self.data_sources: List[BaseDataSource] = []
        self.current_source: Optional[BaseDataSource] = None
        self.last_health_check = 0
        self.health_check_interval = 30  # 30秒检查一次
        
        # 初始化数据源
        self._init_data_sources()
        
    def _init_data_sources(self):
        """初始化数据源"""
        self.data_sources = [
            XtQuantDataSource(),
            MoneyDataSource(),
            MootdxDataSource()
        ]
        
        # 按优先级排序
        self.data_sources.sort(key=lambda x: x.priority.value)
        self.current_source = self.data_sources[0]  # 默认使用第一个
        
        logger.info(f"初始化实时数据源 (Windows兼容): {[ds.name for ds in self.data_sources]}")
    
    def get_realtime_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取实时数据，支持自动切换"""
        # 定期健康检查
        self._periodic_health_check()
        
        # 尝试当前数据源
        if self.current_source and self.current_source.is_healthy():
            result = self.current_source.get_tick_data(stock_code)
            if result:
                logger.debug(f"使用 {self.current_source.name} 获取 {stock_code} 数据成功")
                return result
        
        # 当前数据源失败，尝试切换
        return self._try_fallback_sources(stock_code)
    
    def _try_fallback_sources(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """尝试备用数据源"""
        current_name = self.current_source.name if self.current_source else "None"
        logger.warning(f"当前数据源 {current_name} 失败，尝试切换备用数据源")
        
        for source in self.data_sources:
            if source == self.current_source:
                continue
                
            logger.info(f"尝试使用 {source.name} 获取 {stock_code} 数据")
            result = source.get_tick_data(stock_code)
            
            if result:
                logger.info(f"切换到 {source.name} 成功")
                self.current_source = source
                return result
        
        logger.error(f"所有数据源都失败，无法获取 {stock_code} 的实时数据")
        return None
    
    def _periodic_health_check(self):
        """定期健康检查"""
        current_time = time.time()
        if current_time - self.last_health_check < self.health_check_interval:
            return
            
        self.last_health_check = current_time
        
        # 检查主数据源是否恢复
        primary_source = self.data_sources[0]
        if (self.current_source != primary_source and 
            primary_source.status != DataSourceStatus.HEALTHY):
            
            # 尝试恢复主数据源
            test_result = primary_source.get_tick_data("000001")  # 测试股票
            if test_result:
                logger.info(f"主数据源 {primary_source.name} 已恢复，切换回主数据源")
                self.current_source = primary_source
    
    def get_source_status(self) -> Dict[str, Any]:
        """获取所有数据源状态"""
        return {
            'current_source': self.current_source.name if self.current_source else None,
            'platform': platform.system(),
            'sources': [{
                'name': source.name,
                'priority': source.priority.name,
                'status': source.status.value,
                'error_count': source.error_count,
                'last_error': source.last_error,
                'last_success_time': source.last_success_time.isoformat() if source.last_success_time else None
            } for source in self.data_sources]
        }

# 全局实例
_realtime_manager_instance = None

def get_realtime_data_manager():
    """获取实时数据管理器单例"""
    global _realtime_manager_instance
    if _realtime_manager_instance is None:
        _realtime_manager_instance = RealtimeDataManager()
    return _realtime_manager_instance