# -*- coding:gbk -*-
from xtquant import xtdata
from xtquant.xttype import ContextInfo
from strategy_engine import TradingStrategy
from data_mgr import DataManager
from risk_mgr import RiskManager
from config import Config
import logging
import time

def init(context: ContextInfo):
    """策略初始化入口[^3]"""
    try:
        # 初始化日志
        logging.basicConfig(
            level=logging.DEBUG if Config.DEBUG else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.handlers.RotatingFileHandler(
                    'qmt_strategy.log',
                    maxBytes=10*1024*1024,
                    backupCount=7
                )
            ]
        )
        
        # 数据订阅[^1]
        xtdata.subscribe_quote(
            Config.TARGET_SYMBOLS,
            Config.HISTORY_PERIODS,
            callback=handlebar
        )
        
        # 预加载历史数据
        DataManager().load_history_data(Config.TARGET_SYMBOLS)
        
        # 初始化核心模块
        context.strategy = TradingStrategy(context)
        context.risk_mgr = RiskManager(context)
        context.last_tick_time = 0
        
        logging.info("策略初始化完成")
        
    except Exception as e:
        logging.error(f"初始化异常: {str(e)}")
        raise

def handlebar(context: ContextInfo):
    """行情驱动主逻辑[^6]"""
    try:
        # 节流控制（每秒最多处理10次）
        current_time = time.time()
        if current_time - context.last_tick_time < 0.1:
            return
        context.last_tick_time = current_time
        
        # 前置风控检查
        if not context.risk_mgr.check_system_risk():
            logging.warning("风控检查未通过，停止交易")
            return
            
        # 执行交易策略
        context.strategy.on_tick()
        
        # 更新持仓数据
        context.portfolio.refresh()
        
    except Exception as e:
        logging.error(f"主逻辑异常: {str(e)}", exc_info=True)
        if Config.DEBUG:
            raise
