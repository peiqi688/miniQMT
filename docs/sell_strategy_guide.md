# 卖出策略模块使用指南

## 概述

卖出策略模块是miniQMT量化交易系统的核心组件之一，提供了8种不同的卖出规则，帮助投资者在合适的时机自动卖出股票，实现风险控制和利润保护。

## 功能特性

### 🎯 8种卖出规则

1. **规则1 - 高开回落卖出**
   - 条件：高开 + 最高价高于开盘价N% + 从最高点回落M%
   - 适用场景：捕捉高开后的获利回吐机会

2. **规则2 - 低开反弹回落卖出**
   - 条件：低开 + 最高价高于开盘价N% + 从最高点回落M%
   - 适用场景：低开后反弹乏力的卖出时机

3. **规则3 - 低开涨幅回落卖出**
   - 条件：低开 + 最高价涨幅大于N%（相对昨收）+ 从最高点回落M%
   - 适用场景：低开后强势反弹但后续回落

4. **规则4 - 通用涨幅回落卖出**
   - 条件：不论高低开 + 最高价涨幅大于N%（相对昨收）+ 从最高点回落M%
   - 适用场景：任何开盘情况下的涨幅回落

5. **规则5 - 尾盘定时卖出**
   - 条件：尾盘5分钟（14:55-15:00）若未涨停则卖出
   - 适用场景：避免隔夜风险，锁定当日收益

6. **规则6 - 涨停炸板卖出**
   - 条件：涨停炸板前根据封单金额自动卖出
   - 适用场景：涨停板封单不足时的风险控制

7. **规则7 - 委托超时重下**
   - 条件：卖出委托2秒未成交自动撤单重下
   - 适用场景：提高成交效率，避免挂单过久

8. **规则8 - 最大回撤卖出**
   - 条件：最大回撤达到X%时卖出
   - 适用场景：严格的风险控制，防止大幅亏损

### 🛡️ 安全机制

- **冷却时间**：防止频繁交易，默认30秒冷却期
- **交易时间检查**：只在交易时间内执行卖出操作
- **持仓验证**：确保有足够持仓才执行卖出
- **价格保护**：使用买三价等市场价格进行委托

### 📊 状态跟踪

- **股票状态管理**：跟踪每只股票的今日最高价、最大回撤等
- **待处理订单**：管理未成交的卖出委托
- **卖出触发状态**：防止重复触发同一规则

## 配置参数

### 基础配置

```python
# 卖出策略总开关
ENABLE_SELL_STRATEGY = True

# 检查间隔（秒）
SELL_STRATEGY_CHECK_INTERVAL = 1

# 冷却时间（秒）
SELL_STRATEGY_COOLDOWN_SECONDS = 30
```

### 规则参数配置

```python
# 规则1: 高开回落
SELL_RULE1_RISE_THRESHOLD = 0.03      # 最高价高于开盘价3%
SELL_RULE1_DRAWDOWN_THRESHOLD = 0.02  # 从最高点回落2%

# 规则2: 低开反弹回落
SELL_RULE2_RISE_THRESHOLD = 0.05      # 最高价高于开盘价5%
SELL_RULE2_DRAWDOWN_THRESHOLD = 0.03  # 从最高点回落3%

# 规则3: 低开涨幅回落
SELL_RULE3_GAIN_THRESHOLD = 0.06      # 最高价涨幅大于6%
SELL_RULE3_DRAWDOWN_THRESHOLD = 0.03  # 从最高点回落3%

# 规则4: 通用涨幅回落
SELL_RULE4_GAIN_THRESHOLD = 0.08      # 最高价涨幅大于8%
SELL_RULE4_DRAWDOWN_THRESHOLD = 0.04  # 从最高点回落4%

# 规则5: 尾盘卖出
SELL_RULE5_ENABLE = True

# 规则6: 涨停炸板
SELL_RULE6_SEAL_THRESHOLD = 5000000   # 封单金额阈值（500万元）

# 规则7: 委托超时
SELL_RULE7_CANCEL_TIMEOUT = 2         # 委托超时时间（秒）

# 规则8: 最大回撤
SELL_RULE8_MAX_DRAWDOWN = 0.05        # 最大回撤5%
```

## 使用方法

### 1. 自动模式（推荐）

卖出策略已集成到主策略模块中，会自动运行：

```python
# 在strategy.py中自动调用
from sell_strategy import get_sell_strategy

# 获取卖出策略实例
sell_strategy = get_sell_strategy()

# 检查卖出信号
sell_signal = sell_strategy.check_sell_signals(stock_code)
if sell_signal:
    logger.info(f"触发卖出信号: {sell_signal}")
```

### 2. 手动触发

```python
from sell_strategy import get_sell_strategy

# 获取卖出策略实例
sell_strategy = get_sell_strategy()

# 手动触发卖出
result = sell_strategy.manual_trigger_sell("000001.SZ", "手动卖出")
if result:
    print("手动卖出成功")
```

### 3. 监控模式

```python
from sell_strategy import get_sell_strategy

# 获取卖出策略实例
sell_strategy = get_sell_strategy()

# 启动监控线程
sell_strategy.start_monitoring()

# 停止监控
sell_strategy.stop_monitoring()
```

## Web界面配置

卖出策略支持通过Web界面进行实时配置：

1. 访问 `http://localhost:5000`
2. 进入"配置管理"页面
3. 找到"卖出策略配置"部分
4. 调整各项参数
5. 点击"保存配置"应用更改

### 可配置项目

- ✅ 卖出策略总开关
- ✅ 各规则的阈值参数
- ✅ 规则5的启用/禁用
- ✅ 超时和回撤参数

## 日志和监控

### 日志输出

卖出策略会输出详细的日志信息：

```
2024-01-15 10:30:15 - sell_strategy - INFO - [规则1] 000001.SZ 触发卖出: 高开后涨3.2%，回落2.1%
2024-01-15 14:57:30 - sell_strategy - INFO - [规则5] 600036.SH 尾盘卖出: 未涨停
2024-01-15 11:25:45 - sell_strategy - INFO - [规则8] 000333.SZ 触发卖出: 最大回撤5.2%
```

### 状态查询

```python
# 获取股票状态
state = sell_strategy.get_stock_state("000001.SZ")
print(f"今日最高价: {state.get('today_high', 0)}")
print(f"最大回撤: {state.get('max_drawdown', 0):.2%}")

# 重置股票状态
sell_strategy.reset_stock_state("000001.SZ")
```

## 测试验证

运行测试用例验证功能：

```bash
# 运行卖出策略测试
python test/test_sell_strategy.py
```

测试覆盖：
- ✅ 各种卖出规则的触发条件
- ✅ 冷却机制
- ✅ 交易时间检查
- ✅ 集成功能测试

## 注意事项

### ⚠️ 风险提示

1. **参数设置**：请根据市场情况和个人风险承受能力合理设置参数
2. **回测验证**：建议先在模拟环境中测试参数效果
3. **市场适应**：不同市场环境可能需要调整参数
4. **资金管理**：卖出策略应与整体资金管理策略配合使用

### 💡 最佳实践

1. **渐进调整**：初次使用时建议保守设置参数，逐步优化
2. **组合使用**：多个规则可以同时启用，形成多层保护
3. **定期回顾**：定期检查卖出记录，优化参数设置
4. **风险分散**：不要过度依赖单一卖出规则

## 技术支持

如有问题或建议，请：

1. 查看日志文件获取详细错误信息
2. 运行测试用例验证功能状态
3. 检查配置参数是否在有效范围内
4. 确认交易时间和市场状态

---

**版本**: v1.0  
**更新日期**: 2024-01-15  
**兼容性**: miniQMT v1.0+