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
    _shared_connection = None  # 类级别的共享连接
    _connection_lock = threading.Lock()
    
    def __init__(self):
        super().__init__("XtQuant", timeout=5)
        self.max_errors = 10  # 放宽错误限制
        self._init_xtquant()
    
    def _init_xtquant(self):
        """初始化迅投行情接口 - 使用共享连接"""
        try:
            import xtquant.xtdata as xt
            self.xt = xt
            
            with self._connection_lock:
                # 检查是否已有连接
                if XtQuantSource._shared_connection is None:
                    # 只在没有连接时才创建新连接
                    if xt.connect():
                        XtQuantSource._shared_connection = True
                        logger.info("xtquant行情服务连接成功")
                    else:
                        logger.error("xtquant行情服务连接失败")
                        self.xt = None
                        return
                
            # 验证连接状态
            self._verify_connection()
                
        except Exception as e:
            logger.error(f"初始化迅投行情接口出错: {str(e)}")
            self.xt = None
    
    def _verify_connection(self):
        """验证连接状态"""
        try:
            # 使用一个简单的测试来验证连接
            test_codes = ['000001.SZ']  # 测试股票
            test_data = self.xt.get_full_tick(test_codes)
            if test_data:
                logger.debug("xtquant连接状态验证成功")
                return True
            else:
                logger.warning("xtquant连接状态验证失败")
                return False
        except Exception as e:
            logger.warning(f"xtquant连接验证出错: {str(e)}")
            return False

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
        """获取数据 - 增加重试和连接检查"""
        if not self.xt:
            self.record_error()
            return None
        
        # 重试机制
        max_retries = 2
        for attempt in range(max_retries):
            try:
                formatted_code = self._adjust_stock(stock_code)
                
                # 调用接口获取数据
                tick_data = self.xt.get_full_tick([formatted_code])
                
                if not tick_data or formatted_code not in tick_data:
                    if attempt < max_retries - 1:
                        time.sleep(0.1)  # 短暂等待后重试
                        continue
                    else:
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
                    self.reset_errors()  # 成功时重置错误计数
                    return result
                else:
                    if attempt < max_retries - 1:
                        time.sleep(0.1)
                        continue
                    else:
                        self.record_error()
                        return None
                        
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.debug(f"XtQuant获取{stock_code}数据重试 {attempt + 1}: {str(e)}")
                    time.sleep(0.1)
                    continue
                else:
                    self.record_error()
                    logger.warning(f"XtQuant获取{stock_code}数据失败: {str(e)}")
                    return None
        
        return None
    
    def record_error(self):
        """记录错误 - 优化版"""
        self.error_count += 1
        if self.error_count >= self.max_errors:
            self.is_healthy = False
            logger.warning(f"数据源 {self.name} 错误次数达到上限 {self.max_errors}，标记为不健康")
        elif self.error_count > 5:  # 错误较多时给出警告
            logger.warning(f"数据源 {self.name} 错误次数: {self.error_count}")

class MootdxSource(DataSource):
    """Mootdx数据源"""
    """Mootdx数据源 - 修改版：支持锁定模式"""
    def __init__(self):
        super().__init__("Mootdx", timeout=5)
        self._is_locked = False  # 🔥 新增锁定标志
        try:
            from mootdx.quotes import Quotes
            self.client = Quotes.factory('std')
            logger.info("Mootdx客户端初始化成功")
        except Exception as e:
            logger.error(f"Mootdx客户端初始化失败: {str(e)}")
            self.client = None

    def set_locked(self, locked=True):
        """设置锁定状态"""
        self._is_locked = locked
        if locked:
            logger.info(f"Mootdx数据源已设置为锁定模式")
        else:
            logger.info(f"Mootdx数据源已解除锁定模式")

    def record_error(self):
        """记录错误 - 修改版：锁定状态下不记录错误"""
        if self._is_locked:
            logger.debug("Mootdx数据源处于锁定状态，跳过错误记录")
            return
        
        # 调用父类的错误记录方法
        super().record_error()
    
    def _format_stock_code(self, stock_code):
        """格式化股票代码为mootdx格式"""
        if stock_code.endswith(('.SH', '.SZ', '.sh', '.sz')):
            code = stock_code.split('.')[0]
        else:
            code = stock_code
        return code
    
    def get_data(self, stock_code):
        """从mootdx获取实时数据 - 修改版：锁定状态下的特殊处理"""
        try:
            if not self.client:
                if not self._is_locked:
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
                    
                    # 🔥 锁定状态下总是重置错误
                    if self._is_locked:
                        self.error_count = 0  # 强制重置错误计数
                        self.is_healthy = True
                    else:
                        self.reset_errors()
                        
                    logger.debug(f"Mootdx获取{stock_code}数据成功: {result['lastPrice']}")
                    return result
                    
            except Exception as e:
                logger.warning(f"Mootdx bars方法失败，尝试quote方法: {str(e)}")
                
                # 备用方案：使用quote方法
                quotes_df = self.client.quotes(symbol=[code])
                
                if quotes_df is not None and not quotes_df.empty:
                    # 从DataFrame中筛选对应股票代码的数据
                    quote_data_series = quotes_df[quotes_df['code'] == code]
                    if not quote_data_series.empty:
                        quote = quote_data_series.iloc[0].to_dict()

                        result = {
                            'stock_code': stock_code,
                            'lastPrice': float(quote.get('price', 0)),
                            'open': float(quote.get('open', 0)),
                            'high': float(quote.get('high', 0)),
                            'low': float(quote.get('low', 0)),
                            'volume': int(quote.get('vol', 0)),  # mootdx 返回的成交量字段是 vol
                            'amount': float(quote.get('amount', 0)),
                            'lastClose': float(quote.get('last_close', quote.get('price', 0))), # mootdx 返回的昨收是 last_close
                            'changePercent': float(quote.get('change_pct', 0)), # mootdx 返回的涨跌幅是 change_pct
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'source': self.name
                        }

                    # 🔥 锁定状态下总是重置错误
                    if self._is_locked:
                        self.error_count = 0
                        self.is_healthy = True
                    else:
                        self.reset_errors()
                        
                    logger.debug(f"Mootdx quote获取{stock_code}数据成功: {result['lastPrice']}")
                    return result
            
            # 🔥 锁定状态下不记录错误
            if not self._is_locked:
                self.record_error()
            
            logger.warning(f"Mootdx无法获取{stock_code}的有效数据")
            return None
            
        except Exception as e:
            # 🔥 锁定状态下不记录错误
            if not self._is_locked:
                self.record_error()
            logger.error(f"Mootdx获取{stock_code}数据异常: {str(e)}")
            return None

class RealtimeDataManager:
    """实时数据管理器"""
    def __init__(self):
        self.data_sources = []
        self.current_source = None

        # 🔥 新增：数据源切换锁定机制
        self._locked_source = None  # 被锁定使用的数据源
        self._current_trading_mode = None  # 当前交易模式
        self._is_source_locked = False  # 数据源是否已锁定

        # 根据交易模式初始化数据源
        self._init_data_sources_by_mode()
        
        # 健康检查配置
        self.health_check_interval = getattr(config, 'REALTIME_DATA_CONFIG', {}).get('health_check_interval', 30)
        self.last_health_check = 0

        # 增加调用频率控制
        self._call_frequency_control = {}
        self._min_call_interval = 0.5  # 最小调用间隔500ms

    def _init_data_sources_by_mode(self):
        """根据交易模式初始化数据源"""
        # 获取当前交易模式
        current_mode = 'simulation' if getattr(config, 'ENABLE_SIMULATION_MODE', False) else 'real'
        
        # 🔥 检查交易模式是否发生变化
        if self._current_trading_mode != current_mode:
            logger.info(f"交易模式变化: {self._current_trading_mode} -> {current_mode}")
            self._current_trading_mode = current_mode
            
            # 🔥 重置数据源锁定状态
            if self._is_source_locked:
                logger.info(f"交易模式切换，解除数据源锁定: {self._locked_source.name if self._locked_source else 'None'}")
                self._locked_source = None
                self._is_source_locked = False
        
        # 清空现有数据源
        self.data_sources = []
        
        # 始终添加XtQuant数据源
        try:
            xtquant_source = XtQuantSource()
            self.data_sources.append(xtquant_source)
            self.current_source = xtquant_source  # 默认使用XtQuant
            logger.info("XtQuant数据源初始化成功")
        except Exception as e:
            logger.error(f"XtQuant数据源初始化失败: {str(e)}")
        
        # 仅在模拟交易模式下添加Mootdx数据源
        if current_mode == 'simulation':
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
        """健康检查 - 修改版：不重置已锁定数据源的错误状态"""
        current_time = time.time()
        if current_time - self.last_health_check < self.health_check_interval:
            return
        
        self.last_health_check = current_time
        
        # 🔥 修改：在模拟模式下，如果已经锁定了数据源，不重置其他数据源的错误计数
        if self._current_trading_mode == 'simulation' and self._is_source_locked:
            logger.debug(f"模拟模式下已锁定数据源 {self._locked_source.name}，跳过其他数据源的健康检查重置")
            return
        
        # 重置长时间未使用的数据源错误计数（仅在未锁定状态下）
        for source in self.data_sources:
            if source.last_success_time:
                time_since_success = current_time - source.last_success_time.timestamp()
                if time_since_success > 300:  # 5分钟未成功，重置错误计数
                    source.error_count = max(0, source.error_count - 1)
                    if source.error_count == 0:
                        source.is_healthy = True
    
    def get_realtime_data(self, stock_code):
        """获取实时数据 - 修改版：检查交易模式变化"""
        try:
            # 频率控制
            current_time = time.time()
            last_call_time = self._call_frequency_control.get(stock_code, 0)
            
            if current_time - last_call_time < self._min_call_interval:
                logger.debug(f"{stock_code} 调用过于频繁，跳过本次请求")
                return None
            
            self._call_frequency_control[stock_code] = current_time
            
            # 原有逻辑
            if not self.data_sources:
                logger.error("没有可用的数据源")
                return None            
            
            # 🔥 检查交易模式是否发生变化
            current_mode = 'simulation' if getattr(config, 'ENABLE_SIMULATION_MODE', False) else 'real'
            if self._current_trading_mode != current_mode:
                logger.info(f"检测到交易模式变化，重新初始化数据源")
                self._init_data_sources_by_mode()
            
            # 实盘模式：仅使用XtQuant，不进行切换
            if current_mode == 'real':
                return self._get_data_from_xtquant_only(stock_code)
            
            # 模拟模式：使用修改后的多数据源和锁定切换逻辑
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
        """模拟模式：使用锁定数据源或fallback逻辑"""
        
        # 🔥 如果数据源已锁定，直接使用锁定的数据源，不做任何检查
        if self._is_source_locked and self._locked_source:
            try:
                logger.debug(f"使用锁定的数据源 {self._locked_source.name} 获取 {stock_code} 数据")
                data = self._locked_source.get_data(stock_code)
                
                # 🔥 即使获取失败也返回结果，不进行fallback
                if data and data.get('lastPrice', 0) > 0:
                    logger.debug(f"锁定数据源获取数据成功: {self._locked_source.name}")
                    return data
                else:
                    logger.warning(f"锁定数据源 {self._locked_source.name} 获取数据失败，但继续使用")
                    # 🔥 返回None但不切换数据源
                    return None
                    
            except Exception as e:
                logger.error(f"锁定数据源 {self._locked_source.name} 异常: {str(e)}，但继续使用")
                # 🔥 即使异常也不切换数据源
                return None
        
        # 🔥 未锁定状态下的正常fallback逻辑
        self._health_check()
        
        # 首先尝试当前数据源
        if self.current_source and self.current_source.is_healthy:
            try:
                data = self.current_source.get_data(stock_code)
                if data and data.get('lastPrice', 0) > 0:
                    return data
            except Exception as e:
                logger.warning(f"当前数据源 {self.current_source.name} 获取数据失败: {str(e)}")
        
        # 尝试其他健康的数据源，并在切换成功后锁定
        for source in self.data_sources:
            if source != self.current_source and source.is_healthy:
                try:
                    logger.info(f"尝试使用 {source.name} 获取 {stock_code} 数据")
                    data = source.get_data(stock_code)
                    if data and data.get('lastPrice', 0) > 0:
                        logger.info(f"切换到 {source.name} 成功")
                        self.current_source = source
                        
                        # 🔥 在模拟模式下，如果切换到mootdx，立即锁定
                        if self._current_trading_mode == 'simulation' and source.name == 'Mootdx':
                            self._locked_source = source
                            self._is_source_locked = True
                            logger.warning(f"模拟模式：数据源已锁定为 {source.name},不再进行健康检查和切换")
                        
                        return data
                except Exception as e:
                    logger.warning(f"数据源 {source.name} 获取数据失败: {str(e)}")
        
        logger.error(f"所有数据源都失败，无法获取 {stock_code} 的实时数据")
        return None
    
    def get_source_status(self):
        """获取数据源状态 - 增加锁定状态信息"""
        try:
            status = []
            for source in self.data_sources:
                status.append({
                    'name': source.name,
                    'is_healthy': source.is_healthy,
                    'error_count': source.error_count,
                    'is_current': source == self.current_source,
                    'is_locked': self._is_source_locked and source == self._locked_source,  # 🔥 锁定状态
                    'last_success': source.last_success_time.isoformat() if source.last_success_time else None
                })
            
            # 🔥 添加全局锁定状态信息
            status.append({
                'global_lock_status': {
                    'is_locked': self._is_source_locked,
                    'locked_source': self._locked_source.name if self._locked_source else None,
                    'trading_mode': self._current_trading_mode
                }
            })
            
            return status
        except Exception as e:
            logger.error(f"获取数据源状态失败: {str(e)}")
            return []
    
    def switch_to_source(self, source_name: str) -> bool:
        """手动切换数据源 - 修改版：支持锁定解除"""
        try:
            # 实盘模式下不允许切换
            if self._current_trading_mode == 'real':
                logger.warning("实盘交易模式下不允许切换数据源")
                return False
            
            # 查找目标数据源
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
            
            # 🔥 手动切换时解除锁定
            if self._is_source_locked:
                logger.info(f"手动切换解除数据源锁定: {self._locked_source.name}")
                self._locked_source = None
                self._is_source_locked = False
            
            # 执行切换
            self.current_source = target_source
            target_source.reset_errors()
            
            # 🔥 如果手动切换到mootdx，立即锁定
            if self._current_trading_mode == 'simulation' and source_name == 'Mootdx':
                self._locked_source = target_source
                self._is_source_locked = True
                logger.warning(f"手动切换到Mootdx，立即锁定数据源")
            
            logger.info(f"数据源已从 {old_source_name} 切换到 {source_name}")
            return True
            
        except Exception as e:
            logger.error(f"切换数据源失败: {str(e)}")
            return False

    def force_unlock_source(self):
        """强制解除数据源锁定 - 新增调试方法"""
        if self._is_source_locked:
            logger.info(f"强制解除数据源锁定: {self._locked_source.name}")
            self._locked_source = None
            self._is_source_locked = False
            return True
        else:
            logger.info("当前没有锁定的数据源")
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