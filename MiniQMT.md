量化交易系统，基于迅投QMT交易API，实现了您需要的所有功能。系统有六个主要模块，各自负责不同功能，同时支持React前端界面交互。

## 系统架构

1. **核心模块**：
   - `config.py` - 集中管理所有配置参数
   - `logger.py` - 日志管理，包括日志自动清理
   - `main.py` - 系统主入口，负责初始化和管理各模块
   - `utils.py` - 工具函数集合

2. **数据处理**：
   - `data_manager.py` - 负责历史数据获取与存储
   - `indicator_calculator.py` - 计算各种技术指标（MACD、均线等）

3. **交易策略**：
   - `strategy.py` - 实现核心交易策略
   - `position_manager.py` - 持仓管理和监控
   - `trading_executor.py` - 交易执行和订单管理

4. **Web服务**：
   - `web_server.py` - 提供RESTful API接口供React前端调用

## 交易策略实现

系统严格遵循您提出的交易策略规则：

1. **分仓买入**
   - 每次买入固定金额（默认20000元）
   - 根据建仓成本价格比例（93%、86%等）设置补仓点位
   - 达到仓位上限（默认50000元）后停止买入
   - 总持仓成本损失超过9.5%时全仓止损

2. **动态止盈**
   - 实现浮盈比例与止盈位动态关联
   - 首次盈利达到5%时卖出半仓保证胜率
   - 余下仓位根据动态止盈位置卖出，盈利越多回调空间越大

3. **网格交易**
   - 对持仓个股进行自动网格交易
   - 可调整网格幅度和每格交易量

4. **自动日志管理**
   - 自动清理过期日志文件，不占用存储空间

## 系统特点

1. **模块化设计**：每个功能独立成模块，代码结构清晰
2. **参数可配置**：所有交易参数集中管理，易于调整
3. **RESTful API**：提供完整API供前端调用
4. **丰富的日志**：详细记录系统运行和交易过程
5. **错误处理**：完善的异常处理机制
6. **自动化运行**：支持无人值守的自动交易
7. **手动交易接口**：支持人工干预和操作

## 使用方法

1. 确保安装了必要的Python包：
   ```
   pip install pandas numpy talib flask flask-cors xtquant
   ```

2. 创建账户配置文件 `account_config.json`：
   ```json
   {
     "account_id": "你的交易账号",
     "account_type": "STOCK"
   }
   ```

3. 启动系统：
   ```
   python main.py
   ```

4. 访问Web界面（React前端）：
   ```
   http://localhost:5000
   ```

## 进一步开发

1. 可以增强交易策略，加入更多技术指标
2. 增加回测功能，评估策略效果
3. 优化网格交易算法
4. 添加风控模块，加强交易安全性
5. 增加数据分析和可视化功能

这个系统设计已经考虑了QMT API的特性，并实现了完整的交易生命周期管理，可以有效地支持量化交易策略的执行。


# 详细代码解读
## Position Manager

好的，我来解读一下 position_manager.py 文件中的 PositionManager 类，并尽量用简洁的中文进行说明。

PositionManager 类：持仓管理的核心

这个类主要负责管理股票的持仓信息，包括：

持仓数据的存储和获取：

使用 SQLite 数据库来存储持仓信息，包括股票代码、数量、成本价、当前价格、市值、盈亏比例等。
提供 get_all_positions() 和 get_position() 方法来获取所有持仓或指定股票的持仓信息。
_sync_real_positions_to_db() 方法负责将实盘交易账户的持仓数据同步到数据库中，保持数据一致性。
_update_stock_positions_file() 方法负责更新 stock_positions.json 文件，记录当前持仓的股票代码。
持仓信息的更新：

update_position() 方法用于更新或新增持仓信息。它会自动计算市值、盈亏比例，并记录最后更新时间。
update_all_positions_price() 方法用于批量更新所有持仓的最新价格。
update_all_positions_highest_price() 方法用于批量更新所有持仓的最高价。
remove_position() 方法用于删除持仓记录（例如清仓时）。
止损止盈策略的检查：

check_stop_loss() 方法用于检查是否触发止损条件。
check_dynamic_take_profit() 方法用于检查是否触发动态止盈条件。
calculate_stop_loss_price() 方法用于计算止损价格，支持固定止损和动态止损。
mark_profit_triggered() 方法用于标记股票已触发首次止盈。
网格交易的管理：

get_grid_trades() 方法用于获取指定股票的网格交易记录。
add_grid_trade() 方法用于添加新的网格交易记录。
update_grid_trade_status() 方法用于更新网格交易的状态（例如：PENDING, ACTIVE, COMPLETED）。
check_grid_trade_signals() 方法用于检查网格交易的买入/卖出信号。
监控线程：

start_position_monitor_thread() 方法用于启动一个后台线程，定期监控持仓状态，包括更新价格、检查止损止盈条件、检查网格交易信号等。
stop_position_monitor_thread() 方法用于停止监控线程。
_position_monitor_loop() 方法是监控线程的循环体，负责执行监控任务。
与实盘交易账户的交互

使用了easy_qmt_trader类，通过self.qmt_trader对象与QMT实盘交易账户进行交互，获取实盘持仓数据。
_is_test_environment() 方法用于判断是否在测试环境中，如果在测试环境，则不进行实盘数据同步。
与数据管理模块的交互

使用了data_manager模块，通过self.data_manager对象获取最新行情数据。
核心功能总结：

存储和管理持仓数据。
实时更新持仓信息（价格、市值、盈亏等）。
实现止损止盈策略。
管理网格交易。
后台监控持仓状态。
与实盘交易账户进行交互，同步持仓数据。
与数据管理模块进行交互，获取最新行情。
总而言之，PositionManager 类是整个量化交易系统中负责持仓管理的核心组件，它提供了完善的持仓数据管理、止损止盈策略、网格交易管理和监控功能。