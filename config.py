# -*- coding:gbk -*-
class Config:
    # 基础配置
    DEBUG = True                # 调试模式
    SIMULATION = True           # 模拟交易模式[^3]
    TRADE_ACCOUNT = '123456'    # 资金账号
    
    # 风控参数
    MAX_LOSS_RATIO = 0.095      # 最大亏损比例9.5%[^5]
    GRID_INTERVAL = 0.03        # 网格间距3%
    TICKER_LIMIT = 0.1          # 单票仓位限制
    
    # 交易参数
    COMMISSION_RATE = 0.0003    # 佣金率万三
    SLIPPAGE = 0.001            # 滑点
    MAX_ORDER_AMOUNT = 1000     # 单笔最大委托量[^1]
    
    # 数据参数
    HISTORY_PERIODS = ['1d', '60m', '15m']  # 多周期数据
    
    @classmethod
    def logger_config(cls):
        return {
            'version': 1,
            'handlers': {
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': 'qmt_trade.log',
                    'maxBytes': 10*1024*1024,  # 10MB
                    'backupCount': 7
                }
            }
        }
