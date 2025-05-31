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
import Methods
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
        """初始化迅投行情接口"""
        try:
            import xtquant.xtdata as xt

            # 根据文档，首先调用connect连接到行情服务器
            if not xt.connect():
                logger.error("行情服务连接失败")
                return
                
            logger.info("行情服务连接成功")
            
            # 根据测试结果，我们不使用subscribe_quote方法（会失败）
            # 改为验证股票代码是否可以通过get_full_tick获取数据
            valid_stocks = []
            for stock_code in config.STOCK_POOL:
                try:
                    stock_code = self._adjust_stock(stock_code)
                    # 尝试adjust_stock(stock_code)
                    # 尝试获取Tick数据验证股票代码有效性
                    tick_data = xt.get_full_tick([stock_code])
                    if tick_data and stock_code in tick_data:
                        valid_stocks.append(stock_code)
                        logger.info(f"股票 {stock_code} 数据获取成功")
                    else:
                        logger.warning(f"无法获取 {stock_code} 的Tick数据")
                except Exception as e:
                    logger.warning(f"获取 {stock_code} 的Tick数据失败: {str(e)}")
            
            self.subscribed_stocks = valid_stocks
            
            if self.subscribed_stocks:
                logger.info(f"成功验证 {len(self.subscribed_stocks)} 只股票可获取数据")
            else:
                logger.warning("没有有效的股票，请检查股票代码格式")
                
        except Exception as e:
            logger.error(f"初始化迅投行情接口出错: {str(e)}")

    # 股票代码转换
    def _select_data_type(self, stock='600031'):
        '''
        选择数据类型
        '''
        return Methods.select_data_type(stock)
    
    def _adjust_stock(self, stock='600031.SH'):
        '''
        调整代码
        '''
        return Methods.add_xt_suffix(stock)
    
    def get_data(self, stock_code):
        """直接从xtquant获取数据"""
        try:
            if not self.xt:
                self.record_error()
                return None
                
            formatted_code = self._adjust_code(stock_code)
            
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

        # 根据交易模式初始化数据源
        self._init_data_sources_by_mode()
        
        # 健康检查配置
        self.health_check_interval = getattr(config, 'REALTIME_DATA_CONFIG', {}).get('health_check_interval', 30)
        self.last_health_check = 0

    def _init_data_sources_by_mode(self):
        """根据交易模式初始化数据源"""
        # 始终添加XtQuant数据源
        try:
            xtquant_source = XtQuantSource()
            self.data_sources.append(xtquant_source)
            self.current_source = xtquant_source  # 默认使用XtQuant
            logger.info("XtQuant数据源初始化成功")
        except Exception as e:
            logger.error(f"XtQuant数据源初始化失败: {str(e)}")
        
        # 仅在模拟交易模式下添加Mootdx数据源
        if getattr(config, 'ENABLE_SIMULATION_MODE', False):
            try:
                mootdx_source = MootdxSource()
                self.data_sources.append(mootdx_source)
                logger.info("模拟交易模式：Mootdx数据源已添加")
            except Exception as e:
                logger.error(f"Mootdx数据源初始化失败: {str(e)}")
        else:
            logger.info("实盘交易模式：仅使用XtQuant数据源")
        
        if not self.data_sources:
            logger.error("没有可用的数据源！")
    
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
        """获取实时数据 - 根据交易模式优化"""
        try:
            if not self.data_sources:
                logger.error("没有可用的数据源")
                return None
            
            # 实盘模式：仅使用XtQuant，不进行切换
            if not getattr(config, 'ENABLE_SIMULATION_MODE', False):
                return self._get_data_from_xtquant_only(stock_code)
            
            # 模拟模式：使用多数据源和智能切换
            return self._get_data_with_fallback(stock_code)
            
        except Exception as e:
            logger.error(f"获取实时数据时发生异常: {str(e)}")
            return None

    def _get_data_from_xtquant_only(self, stock_code):
        """实盘模式：仅从XtQuant获取数据"""
        xtquant_source = None
        for source in self.data_sources:
            if source.name == "XtQuant":
                xtquant_source = source
                break
        
        if not xtquant_source:
            logger.error("未找到XtQuant数据源")
            return None
        
        try:
            data = xtquant_source.get_data(stock_code)
            if data and data.get('lastPrice', 0) > 0:
                return data
            else:
                logger.warning(f"XtQuant无法获取{stock_code}的有效数据")
                return None
        except Exception as e:
            logger.error(f"XtQuant获取{stock_code}数据失败: {str(e)}")
            return None

    def _get_data_with_fallback(self, stock_code):
        """模拟模式：使用原有的多数据源切换逻辑"""
        # 这里保持原有的智能切换逻辑
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
        
        logger.error(f"所有数据源都失败，无法获取 {stock_code} 的实时数据")
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
        """切换到指定数据源 - 仅在模拟模式下允许"""
        try:
            # 实盘模式下不允许切换
            if not getattr(config, 'ENABLE_SIMULATION_MODE', False):
                logger.warning("实盘交易模式下不允许切换数据源")
                return False
            
            # 原有的切换逻辑
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