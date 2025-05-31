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

class SinaFinanceSource(DataSource):
    """新浪财经数据源"""
    def __init__(self):
        super().__init__("SinaFinance", timeout=3)
        self.base_url = "http://hq.sinajs.cn/list="
    
    def _format_stock_code(self, stock_code):
        """格式化股票代码为新浪财经格式"""
        # 移除已有后缀
        if stock_code.endswith(('.SH', '.SZ', '.sh', '.sz')):
            code = stock_code.split('.')[0]
        else:
            code = stock_code
        
        # 根据代码规则添加前缀
        if code.startswith(('600', '601', '603', '688', '510', '511', '512', '513', '515')):
            return f"sh{code}"
        elif code.startswith(('000', '001', '002', '003', '300')):
            return f"sz{code}"
        else:
            # 默认深圳
            return f"sz{code}"
    
    def get_data(self, stock_code):
        """从新浪财经获取实时数据"""
        try:
            formatted_code = self._format_stock_code(stock_code)
            url = f"{self.base_url}{formatted_code}"
            
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # 解析新浪财经返回的数据
            content = response.text.strip()
            if not content or 'N/A' in content:
                return None
            
            # 新浪财经数据格式：var hq_str_sh600000="股票名称,今开,昨收,现价,最高,最低,买价,卖价,成交量,成交额,..."
            start = content.find('"') + 1
            end = content.rfind('"')
            data_str = content[start:end]
            
            if not data_str:
                return None
            
            parts = data_str.split(',')
            if len(parts) < 32:  # 新浪数据通常有32个字段
                return None
            
            # 解析关键字段
            stock_name = parts[0]
            open_price = float(parts[1]) if parts[1] else 0
            pre_close = float(parts[2]) if parts[2] else 0
            current_price = float(parts[3]) if parts[3] else 0
            high_price = float(parts[4]) if parts[4] else 0
            low_price = float(parts[5]) if parts[5] else 0
            volume = int(parts[8]) if parts[8] else 0
            amount = float(parts[9]) if parts[9] else 0
            
            # 计算涨跌幅
            change_percent = 0
            if pre_close > 0:
                change_percent = ((current_price - pre_close) / pre_close) * 100
            
            result = {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'lastPrice': current_price,
                'lastClose': pre_close,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'volume': volume,
                'amount': amount,
                'change_percent': round(change_percent, 2),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': self.name
            }
            
            self.reset_errors()
            return result
            
        except Exception as e:
            self.record_error()
            logger.warning(f"新浪财经数据源获取 {stock_code} 失败: {str(e)}")
            return None

class XtQuantSource(DataSource):
    """XtQuant数据源"""
    def __init__(self):
        super().__init__("XtQuant", timeout=5)
    
    def get_data(self, stock_code):
        try:
            from data_manager import get_data_manager
            data_manager = get_data_manager()
            result = data_manager.get_latest_xtdata(stock_code)
            
            if result and result.get('lastPrice', 0) > 0:
                result['source'] = self.name
                self.reset_errors()
                return result
            else:
                self.record_error()
                return None
                
        except Exception as e:
            self.record_error()
            logger.warning(f"XtQuant数据源获取 {stock_code} 失败: {str(e)}")
            return None

class MootdxSource(DataSource):
    """Mootdx数据源"""
    def __init__(self):
        super().__init__("Mootdx", timeout=5)
    
    def get_data(self, stock_code):
        try:
            from data_manager import get_data_manager
            data_manager = get_data_manager()
            result = data_manager.get_latest_data(stock_code)
            
            if result and result.get('lastPrice', 0) > 0:
                result['source'] = self.name
                self.reset_errors()
                return result
            else:
                self.record_error()
                return None
                
        except Exception as e:
            self.record_error()
            logger.warning(f"Mootdx数据源获取 {stock_code} 失败: {str(e)}")
            return None

class RealtimeDataManager:
    """实时数据管理器"""
    def __init__(self):
        self.data_sources = [
            XtQuantSource(),
            SinaFinanceSource(),  # 替换Money163
            MootdxSource()
        ]
        self.current_source = self.data_sources[0]
        self.health_check_interval = config.REALTIME_DATA_CONFIG.get('health_check_interval', 30)
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
        """获取实时数据"""
        self._health_check()
        
        # 首先尝试当前数据源
        if self.current_source.is_healthy:
            data = self.current_source.get_data(stock_code)
            if data:
                return data
            else:
                logger.warning(f"当前数据源 {self.current_source.name} 失败，尝试切换备用数据源")
        
        # 尝试其他健康的数据源
        for source in self.data_sources:
            if source != self.current_source and source.is_healthy:
                logger.info(f"尝试使用 {source.name} 获取 {stock_code} 数据")
                data = source.get_data(stock_code)
                if data:
                    logger.info(f"切换到 {source.name} 成功")
                    self.current_source = source
                    return data
        
        # 如果所有健康数据源都失败，尝试不健康的数据源（给一次机会）
        for source in self.data_sources:
            if not source.is_healthy:
                logger.info(f"尝试使用不健康数据源 {source.name} 获取 {stock_code} 数据")
                data = source.get_data(stock_code)
                if data:
                    logger.info(f"不健康数据源 {source.name} 恢复成功")
                    self.current_source = source
                    return data
        
        logger.error(f"所有数据源都失败，无法获取 {stock_code} 的实时数据")
        return None
    
    def get_source_status(self):
        """获取数据源状态"""
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
    
    def switch_to_source(self, source_name: str) -> bool:
        """切换到指定数据源"""
        try:
            target_source = None
            for source in self.data_sources:
                if source.name == source_name:
                    target_source = source
                    break
            
            if not target_source:
                logger.error(f"未找到数据源: {source_name}")
                return False
            
            old_source_name = self.current_source.name
            self.current_source = target_source
            
            # 给状态更新留出时间
            time.sleep(0.5)
            
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
        _instance = RealtimeDataManager()
    return _instance