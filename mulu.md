
mcp依赖 python 版本3.9
pip install uv   
uvx mcp-feedback-enhanced@latest 
项目 依赖库 
pip install xtquant pandas requests baostock flask flask_cors mootdx adata pywencai 

# miniQMT 项目目录结构

## 一、系统架构设计

### 1. 核心模块

| 文件名             | 描述                               |
| :----------------- | :--------------------------------- |
| `config.py`        | **集中管理所有可配置参数**         |
| `data_manager.py`  | 历史数据获取存储（xtdata接口）     |
| `indicator_calculator.py` | 多周期均线/MACD计算（pandas向量化计算） |
| `strategy.py`      | **交易策略逻辑实现**               |
| `trading_executor.py` | 交易指令执行器（xttrader接口）     |
| `position_manager.py` | **持仓管理与止盈止损计算**         |
| `grid_trader.py`   | 网格交易模块                       |
| `risk_mgr.py`      | 风控校验模块                       |

### 2. 其他模块与目录

| 文件/目录名        | 描述                               |
| :----------------- | :--------------------------------- |
| `.conda/`          | Conda 环境相关文件                 |
| `.gitignore`       | Git 忽略文件                       |
| `.trae/`           | Trae IDE 相关配置                  |
| `Methods.py`       | 通用方法或辅助函数                 |
| `MiniQMT.md`       | 项目说明文档                       |
| `MyTT.py`          | 技术指标库                         |
| `README.md`        | 项目自述文件                       |
| `WebBuyTest.py`    | Web 购买测试脚本                   |
| `__pycache__/`     | Python 字节码缓存                  |
| `data/`            | 数据存储目录                       |
| `docs/`            | 项目文档                           |
| `easy_qmt_trader.py` | 简易 QMT 交易器                    |
| `logger.py`        | 日志模块                           |
| `main.py`          | 主程序入口                         |
| `stock_pool.json`  | 股票池配置                         |
| `test/`            | 测试文件目录                       |
| `utils.py`         | 工具函数                           |
| `utils/`           | 更多工具函数和辅助脚本             |
| `web1.0/`          | Web 界面相关文件                   |
| `web_api_test.log` | Web API 测试日志                   |
| `web_server.py`    | Web 服务器                         |
| `xtquant/`         | 迅投 QMT API 库                    |

## 二、关键实现要点 (待实现或优化)

1.  **数据管理 (`data_manager.py`)**
    *   使用 `xtdata.get_market_data` 获取股票历史数据。
    *   采用 HDF5 存储高频数据，SQLite 存储元数据。
    *   实现增量更新机制：`last_update_date` 字段记录最后更新时间。

2.  **指标计算 (`indicator_calculator.py`)**
    *   `calculate_emas(df, periods=[10,20,30,60])`: 带异常值处理的多周期均线计算，使用 pandas 的滚动窗口计算。
    *   `calculate_macd(df, fast=12, slow=26, signal=9)`: MACD 指标计算（兼容空值处理）。

3.  **策略引擎 (`strategy.py`)**
    *   `class TradingStrategy`: 实现 QMT 的事件驱动机制。
    *   `on_tick(self, context)`: 包含分仓补仓逻辑和动态止盈逻辑。

4.  **交易执行 (`trading_executor.py`)**
    *   `class TradeExecutor`:
        *   `smart_order(self, symbol, price, amount)`: 智能下单模块，根据买三/卖三价动态调整委托价格，校验当日剩余交易额度，自动拆分大单（单笔≤1000股）。

5.  **风控管理 (`risk_mgr.py`)**
    *   `check_position_risk(position)`: 实时计算持仓盈亏，整体亏损 > 9.5% 时触发全平仓，个股持仓突破网格阈值触发交易。

## 三、QMT API 特别注意事项

1.  必须实现 `init` 和 `handlebar` 方法。
2.  使用 `ContextInfo` 对象传递策略上下文。
3.  区分模拟交易和实盘交易模式。
4.  使用 `xtdata` 订阅实时行情数据。
5.  采用异步订单查询接口。

## 四、调试建议

1.  在 `config.py` 设置 `DEBUG` 模式：
    ```python
    DEBUG = True  # 启用详细日志输出
    SIMULATION = True # 使用模拟交易模式
    ```
2.  日志管理建议：
    *   使用 `RotatingFileHandler` 实现日志轮换。
    *   保留最近 7 天日志，单个日志 ≤ 10MB。

