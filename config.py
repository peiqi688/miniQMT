"""
配置参数管理模块，集中管理所有可配置参数
"""
import os
import json
from datetime import datetime

# ======================= 系统配置 =======================
# 调试开关
DEBUG = False
DEBUG_SIMU_STOCK_DATA= True
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = "qmt_trading.log"
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5  # 保留5个备份文件

# ======================= 数据配置 =======================
# 历史数据存储路径
DATA_DIR = "data"
# 数据库配置（如果使用SQLite）
DB_PATH = os.path.join(DATA_DIR, "trading.db")
# 行情数据周期
PERIODS = ["1d", "1h", "30m", "15m", "5m", "1m"]
# 默认使用的周期
DEFAULT_PERIOD = "1d"
# 历史数据初始获取天数
INITIAL_DAYS = 365
# 定时更新间隔（秒）
UPDATE_INTERVAL = 60

# ======================= 交易配置 =======================
# 交易账号信息（从外部文件读取，避免敏感信息硬编码）
ACCOUNT_CONFIG_FILE = "account_config.json"
QMT_PATH = r'C:/光大证券金阳光QMT实盘/userdata_mini'

def get_account_config():
    """从外部文件读取账号配置"""
    try:
        with open(ACCOUNT_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # 如果配置文件不存在，返回默认空配置
        return {"account_id": "", "account_type": "STOCK"}

# 账号信息
ACCOUNT_CONFIG = get_account_config()

# ======================= 策略配置 =======================
# 仓位管理
POSITION_UNIT = 20000  # 每次买入金额
MAX_POSITION_VALUE = 50000  # 单只股票最大持仓金额
MAX_TOTAL_POSITION_RATIO = 0.95  # 最大总持仓比例（占总资金）

# 买入策略
BUY_GRID_LEVELS = [1.0, 0.93, 0.86]  # 建仓价格网格（第一个是初次建仓价格比例，后面是补仓价格比例）
BUY_AMOUNT_RATIO = [0.4, 0.3, 0.3]  # 每次买入金额占单元的比例

# 卖出和止损策略
STOP_LOSS_RATIO = -0.07  # 止损比例（总成本亏损比例）
INITIAL_TAKE_PROFIT_RATIO = 0.05  # 首次止盈比例（首次盈利5%时卖出半仓）
INITIAL_TAKE_PROFIT_RATIO_PERCENTAGE = 0.5  # 首次止盈卖出比例（半仓）

# 动态止盈参数
DYNAMIC_TAKE_PROFIT = [
    # (盈利比例, 止盈位系数)
    (0.05, 0.96),  # 建仓后最高价涨幅曾大于5%时，止盈位为最高价*96%
    (0.10, 0.95),  # 建仓后最高价涨幅曾大于10%时，止盈位为最高价*93%
    (0.15, 0.93),  # 建仓后最高价涨幅曾大于15%时，止盈位为最高价*90%
    (0.30, 0.87),  # 建仓后最高价涨幅曾大于30%时，止盈位为最高价*87%
    (0.40, 0.85)   # 建仓后最高价涨幅曾大于40%时，止盈位为最高价*83%    
]

# 网格交易参数
GRID_TRADING_ENABLED = True
GRID_STEP_RATIO = 0.05  # 网格步长（价格变动3%创建一个网格）
GRID_POSITION_RATIO = 0.2  # 每个网格交易的仓位比例
GRID_MAX_LEVELS = 6  # 最大网格数量

# ======================= 指标配置 =======================
# MACD参数
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# 均线参数
MA_PERIODS = [10, 20, 30, 60]

# ======================= Web服务配置 =======================
WEB_SERVER_HOST = "localhost"
WEB_SERVER_PORT = 5000
WEB_SERVER_DEBUG = True

# ======================= 功能开关 =======================
ENABLE_AUTO_TRADING = False  # 是否启用自动交易
ENABLE_DATA_SYNC = True  # 是否启用数据同步
ENABLE_POSITION_MONITOR = True  # 是否启用持仓监控
ENABLE_LOG_CLEANUP = True  # 是否启用日志清理
ENABLE_GRID_TRADING = True  # 是否启用网格交易
ENABLE_DYNAMIC_STOP_PROFIT = True  # 是否启用动态止盈

# ======================= 日志清理配置 =======================
LOG_CLEANUP_DAYS = 30  # 保留最近30天的日志
LOG_CLEANUP_TIME = "00:00:00"  # 每天凌晨执行清理

# ======================= 功能配置 =======================
# 交易时间配置
TRADE_TIME = {
    "morning_start": "09:30:00",
    "morning_end": "11:30:00",
    "afternoon_start": "13:00:00",
    "afternoon_end": "15:00:00",
    "trade_days": [1, 2, 3, 4, 5]  # 周一至周五
}

def is_trade_time():
    """判断当前是否为交易时间"""
    if DEBUG_SIMU_STOCK_DATA:
        return True

    now = datetime.now()
    weekday = now.weekday() + 1  # 转换为1-7表示周一至周日
    
    if weekday not in TRADE_TIME["trade_days"]:
        return False
    
    current_time = now.strftime("%H:%M:%S")
    if (TRADE_TIME["morning_start"] <= current_time <= TRADE_TIME["morning_end"]) or \
       (TRADE_TIME["afternoon_start"] <= current_time <= TRADE_TIME["afternoon_end"]):
        return True
    
    return False

# ======================= 预设股票池 =======================
# 可以在这里定义预设的股票池，也可以从外部文件加载
DEFAULT_STOCK_POOL = [
    "000001.SZ",  # 平安银行
    "600036.SH",  # 招商银行
    "000333.SZ",  # 美的集团
    "600519.SH",  # 贵州茅台
    "000858.SZ",  # 五粮液
]

STOCK_POOL_FILE = "stock_pool.json" 

def load_stock_pool(file_path=STOCK_POOL_FILE):
    """从外部文件加载股票池"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return DEFAULT_STOCK_POOL

# 实际使用的股票池
STOCK_POOL = load_stock_pool()
