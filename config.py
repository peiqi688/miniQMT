class Config:
    # 交易参数
    INIT_CAPITAL = 20000     # 初始分仓金额
    MAX_POSITION = 50000     # 最大持仓金额
    STOP_LOSS = -0.095       # 整体止损线
    TAKE_PROFIT = 0.05       # 首次止盈比例
    
    # 补仓参数
    BUY_LEVELS = [0.93, 0.86]  # 补仓价格比例
    GRID_RATIO = 0.02          # 网格交易幅度
    
    # 数据参数
    HIST_DATA_DAYS = 180      # 历史数据获取天数
    INDICATORS = ['MA10', 'MA20', 'MA30', 'MA60', 'MACD']
    
    # 调试参数
    DEBUG_MODE = True        # 调试开关
    LOG_PATH = './trade_logs/'
    LOG_MAX_DAYS = 30        # 日志保留天数
