#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 动态止盈止损机制全面测试脚本

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import matplotlib.dates as mdates
from datetime import datetime, timedelta

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

# 模拟配置参数
class TestConfig:
    STOP_LOSS_RATIO = -0.07  # 止损比例(-7%)
    INITIAL_TAKE_PROFIT_RATIO = 0.05  # 首次止盈比例(5%)
    INITIAL_TAKE_PROFIT_RATIO_PERCENTAGE = 0.5  # 首次止盈卖出比例(50%)
    
    # 动态止盈参数
    DYNAMIC_TAKE_PROFIT = [
        (0.05, 0.96),  # 涨幅≥5%，止盈位为最高价*96%
        (0.10, 0.95),  # 涨幅≥10%，止盈位为最高价*95%
        (0.15, 0.93),  # 涨幅≥15%，止盈位为最高价*93%
        (0.30, 0.87),  # 涨幅≥30%，止盈位为最高价*87%
        (0.40, 0.85)   # 涨幅≥40%，止盈位为最高价*85%    
    ]

config = TestConfig()

# 计算止损价格
def calculate_stop_loss_price(cost_price, highest_price, profit_triggered):
    """计算止损价格"""
    if profit_triggered:
        # 动态止损
        highest_profit_ratio = (highest_price - cost_price) / cost_price
        take_profit_coefficient = 0.97  # 默认系数
        
        # 遍历所有止盈级别
        for profit_level, coefficient in config.DYNAMIC_TAKE_PROFIT:
            if highest_profit_ratio >= profit_level:
                take_profit_coefficient = coefficient
                # 不立即break，找到适用的最高级别
        
        return highest_price * take_profit_coefficient
    else:
        # 固定止损
        return cost_price * (1 + config.STOP_LOSS_RATIO)

# 计算动态止盈价格
def calculate_dynamic_take_profit_price(cost_price, highest_price):
    """计算动态止盈价格"""
    highest_profit_ratio = (highest_price - cost_price) / cost_price
    take_profit_coefficient = 0.97  # 默认系数
    
    for profit_level, coefficient in config.DYNAMIC_TAKE_PROFIT:
        if highest_profit_ratio >= profit_level:
            take_profit_coefficient = coefficient
    
    return highest_price * take_profit_coefficient

# 生成各种股价模式
def generate_price_patterns(cost_price=100.0, days=60):
    """生成各种股价模式"""
    patterns = {}
    
    # 1. 直接下跌
    declining = np.linspace(cost_price, cost_price * 0.85, days)
    patterns["直接下跌"] = declining
    
    # 2. 小幅上涨后下跌 (未触发首次止盈)
    small_rise = np.zeros(days)
    small_rise[:10] = np.linspace(cost_price, cost_price * 1.04, 10)  # 上涨4%
    small_rise[10:] = np.linspace(small_rise[9], cost_price * 0.90, days - 10)  # 然后下跌
    patterns["小幅上涨后下跌"] = small_rise
    
    # 3. 各个区间上涨后回落
    levels = {
        "上涨5-10%后回落": (0.08, 0.96),   # 上涨8%，触发首次止盈，使用0.96系数
        "上涨10-15%后回落": (0.12, 0.95),  # 上涨12%，触发首次止盈，使用0.95系数
        "上涨15-30%后回落": (0.20, 0.93),  # 上涨20%，触发首次止盈，使用0.93系数
        "上涨30-40%后回落": (0.35, 0.87),  # 上涨35%，触发首次止盈，使用0.87系数
        "上涨40%以上后回落": (0.45, 0.85)   # 上涨45%，触发首次止盈，使用0.85系数
    }
    
    for name, (peak_gain, _) in levels.items():
        peak_price = cost_price * (1 + peak_gain)
        prices = np.zeros(days)
        
        # 前1/3时间上涨到峰值
        rise_days = days // 3
        prices[:rise_days] = np.linspace(cost_price, peak_price, rise_days)
        
        # 中间1/3时间横盘震荡
        flat_days = days // 3
        fluctuation = peak_price * 0.02  # 2%的波动
        flat_prices = peak_price + np.random.uniform(-fluctuation, fluctuation, flat_days)
        prices[rise_days:rise_days+flat_days] = flat_prices
        
        # 后1/3时间回落
        fall_days = days - rise_days - flat_days
        final_price = cost_price * 0.90  # 最终跌至成本价下方
        prices[rise_days+flat_days:] = np.linspace(prices[rise_days+flat_days-1], final_price, fall_days)
        
        patterns[name] = prices
    
    return patterns

# 运行完整的测试并生成结果
def run_simulation(patterns, cost_price=100.0):
    """运行所有场景的模拟测试"""
    all_results = {}
    
    for pattern_name, prices in patterns.items():
        print(f"\n模拟场景: {pattern_name}")
        print("=" * 60)
        
        # 初始化变量
        highest_price = cost_price
        profit_triggered = False
        position_size = 1.0  # 初始持仓比例为100%
        first_profit_taken = False
        cash = 0  # 已兑现的现金
        stop_loss_price = calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
        
        # 准备记录数据
        days = len(prices)
        dates = [datetime.now() + timedelta(days=i) for i in range(days)]
        
        results = []
        trades = []
        
        # 模拟每个交易日
        for i, current_price in enumerate(prices):
            # 更新最高价
            if current_price > highest_price:
                highest_price = current_price
            
            # 计算止损价
            stop_loss_price = calculate_stop_loss_price(cost_price, highest_price, profit_triggered)
            
            # 计算盈利率
            profit_ratio = (current_price - cost_price) / cost_price
            
            # 默认动作
            action = "持有"
            trade_type = None
            
            # 检查是否需要操作
            if position_size > 0:  # 仍有持仓
                # 检查是否触发首次止盈
                if not profit_triggered and profit_ratio >= config.INITIAL_TAKE_PROFIT_RATIO:
                    action = f"首次止盈(卖出{config.INITIAL_TAKE_PROFIT_RATIO_PERCENTAGE*100:.0f}%)"
                    trade_type = "FIRST_PROFIT"
                    
                    # 执行首次止盈
                    sell_ratio = config.INITIAL_TAKE_PROFIT_RATIO_PERCENTAGE
                    sell_size = position_size * sell_ratio
                    remaining_size = position_size - sell_size
                    
                    # 更新持仓和现金
                    cash += sell_size * current_price
                    position_size = remaining_size
                    
                    # 标记已触发首次止盈
                    profit_triggered = True
                    first_profit_taken = True
                    
                    # 记录交易
                    trades.append({
                        'date': dates[i],
                        'price': current_price,
                        'type': trade_type,
                        'size': sell_size,
                        'cash': cash
                    })
                    
                # 检查是否触发动态止盈或止损
                elif profit_triggered:
                    # 计算动态止盈价
                    dynamic_tp_price = calculate_dynamic_take_profit_price(cost_price, highest_price)
                    
                    # 检查是否触发动态止盈
                    if current_price < dynamic_tp_price:
                        action = "动态止盈(清仓)"
                        trade_type = "DYNAMIC_PROFIT"
                        
                        # 执行清仓
                        cash += position_size * current_price
                        position_size = 0
                        
                        # 记录交易
                        trades.append({
                            'date': dates[i],
                            'price': current_price,
                            'type': trade_type,
                            'size': position_size,
                            'cash': cash
                        })
                    
                    # 检查是否触发止损
                    elif current_price <= stop_loss_price:
                        action = "止损(清仓)"
                        trade_type = "STOP_LOSS"
                        
                        # 执行清仓
                        cash += position_size * current_price
                        position_size = 0
                        
                        # 记录交易
                        trades.append({
                            'date': dates[i],
                            'price': current_price,
                            'type': trade_type,
                            'size': position_size,
                            'cash': cash
                        })
                
                # 未触发首次止盈前的止损检查
                elif current_price <= stop_loss_price:
                    action = "止损(清仓)"
                    trade_type = "STOP_LOSS"
                    
                    # 执行清仓
                    cash += position_size * current_price
                    position_size = 0
                    
                    # 记录交易
                    trades.append({
                        'date': dates[i],
                        'price': current_price,
                        'type': trade_type,
                        'size': position_size,
                        'cash': cash
                    })
            
            # 计算当前资产价值
            position_value = position_size * current_price
            total_value = position_value + cash
            total_return = (total_value / cost_price - 1) * 100  # 总收益率
            
            # 存储结果
            results.append({
                'date': dates[i],
                'price': current_price,
                'highest_price': highest_price,
                'profit_ratio': profit_ratio * 100,  # 转为百分比
                'stop_loss_price': stop_loss_price,
                'position_size': position_size,
                'cash': cash,
                'total_value': total_value,
                'total_return': total_return,
                'first_profit_taken': first_profit_taken,
                'action': action
            })
            
            # 输出关键信息
            if i % 10 == 0 or trade_type or i == len(prices) - 1:  # 每10天或有交易或最后一天输出
                print(f"Day {i+1}: Price=${current_price:.2f}, Highest=${highest_price:.2f}, " +
                      f"StopLoss=${stop_loss_price:.2f}, Return={total_return:.2f}%, " +
                      f"Position={position_size*100:.0f}%, Action={action}")
        
        # 转换为DataFrame并保存结果
        results_df = pd.DataFrame(results)
        trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
        
        all_results[pattern_name] = {
            'results': results_df,
            'trades': trades_df,
            'final_return': results_df['total_return'].iloc[-1],
            'max_return': results_df['total_return'].max(),
            'max_drawdown': results_df['total_return'].max() - results_df['total_return'].min()
        }
        
        print(f"\n场景 {pattern_name} 最终收益率: {results_df['total_return'].iloc[-1]:.2f}%")
        print(f"最大收益率: {results_df['total_return'].max():.2f}%")
        print(f"最大回撤: {all_results[pattern_name]['max_drawdown']:.2f}%")
        print("-" * 60)
    
    return all_results

# 绘制结果图表
def plot_results(all_results, cost_price=100.0):
    """绘制所有场景的结果图表"""
    # 设置图表
    n_patterns = len(all_results)
    fig = plt.figure(figsize=(18, 4 * n_patterns))
    
    # 颜色定义
    colors = {
        'price': 'blue',
        'highest_price': 'green',
        'stop_loss': 'red',
        'first_profit': 'orange',
        'dynamic_profit': 'purple',
        'stop_loss_trade': 'darkred'
    }
    
    # 处理每个场景
    for i, (pattern_name, data) in enumerate(all_results.items()):
        results_df = data['results']
        trades_df = data['trades']
        
        # 创建子图
        ax = fig.add_subplot(n_patterns, 1, i+1)
        
        # 绘制价格曲线
        ax.plot(results_df['date'], results_df['price'], 
                color=colors['price'], label='价格', linewidth=2)
        
        # 绘制最高价
        ax.plot(results_df['date'], results_df['highest_price'], 
                color=colors['highest_price'], label='最高价', linestyle='--', alpha=0.7)
        
        # 绘制止损价
        ax.plot(results_df['date'], results_df['stop_loss_price'], 
                color=colors['stop_loss'], label='止损价', linestyle=':', alpha=0.7)
        
        # 绘制成本价参考线
        ax.axhline(y=cost_price, color='grey', linestyle='-', alpha=0.5, label='成本价')
        
        # 绘制首次止盈线
        ax.axhline(y=cost_price * (1 + config.INITIAL_TAKE_PROFIT_RATIO), 
                  color=colors['first_profit'], linestyle='--', alpha=0.5, 
                  label=f'首次止盈线 (+{config.INITIAL_TAKE_PROFIT_RATIO*100}%)')
        
        # 标记交易点
        if not trades_df.empty:
            for _, trade in trades_df.iterrows():
                marker = '^'  # 默认标记
                color = 'black'
                label = None
                
                if trade['type'] == 'FIRST_PROFIT':
                    color = colors['first_profit']
                    label = '首次止盈' if 'first_profit' not in ax.get_legend_handles_labels()[1] else None
                elif trade['type'] == 'DYNAMIC_PROFIT':
                    color = colors['dynamic_profit']
                    label = '动态止盈' if 'dynamic_profit' not in ax.get_legend_handles_labels()[1] else None
                elif trade['type'] == 'STOP_LOSS':
                    color = colors['stop_loss_trade']
                    marker = 'v'
                    label = '止损' if 'stop_loss_trade' not in ax.get_legend_handles_labels()[1] else None
                
                ax.scatter(trade['date'], trade['price'], color=color, marker=marker, 
                          s=100, zorder=5, label=label)
        
        # 设置标题和标签
        ax.set_title(f"场景: {pattern_name} - 最终收益率: {data['final_return']:.2f}%", fontsize=14)
        ax.set_xlabel('日期')
        ax.set_ylabel('价格')
        
        # 格式化x轴日期
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        
        # 添加收益率次坐标轴
        ax2 = ax.twinx()
        ax2.plot(results_df['date'], results_df['total_return'], color='black', 
                linestyle='-', label='总收益率(%)')
        ax2.set_ylabel('收益率(%)')
        
        # 设置图例
        handles1, labels1 = ax.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(handles1 + handles2, labels1 + labels2, loc='upper left')
        
        # 设置网格
        ax.grid(True, alpha=0.3)
        
        # 旋转x轴日期标签
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图表
    plt.savefig('dynamic_stop_loss_test_results.png', dpi=150, bbox_inches='tight')
    
    # 显示图表
    plt.show()

# 性能比较图表
def plot_performance_comparison(all_results):
    """绘制所有场景的性能比较图表"""
    # 提取性能数据
    patterns = list(all_results.keys())
    final_returns = [data['final_return'] for data in all_results.values()]
    max_returns = [data['max_return'] for data in all_results.values()]
    max_drawdowns = [data['max_drawdown'] for data in all_results.values()]
    
    # 设置图表
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # 绘制收益率对比
    x = np.arange(len(patterns))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, final_returns, width, label='最终收益率(%)', color='darkblue')
    bars2 = ax1.bar(x + width/2, max_returns, width, label='最大收益率(%)', color='green')
    
    ax1.set_title('各场景收益率对比', fontsize=14)
    ax1.set_xticks(x)
    ax1.set_xticklabels(patterns, rotation=45, ha='right')
    ax1.legend()
    
    # 为柱状图添加标签
    def add_labels(bars):
        for bar in bars:
            height = bar.get_height()
            ax1.annotate(f'{height:.1f}%',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  # 3点垂直偏移
                        textcoords="offset points",
                        ha='center', va='bottom')
    
    add_labels(bars1)
    add_labels(bars2)
    
    # 绘制最大回撤
    ax2.bar(patterns, max_drawdowns, color='red', alpha=0.7)
    ax2.set_title('各场景最大回撤(%)', fontsize=14)
    ax2.set_xticklabels(patterns, rotation=45, ha='right')
    
    # 为回撤柱状图添加标签
    for i, v in enumerate(max_drawdowns):
        ax2.text(i, v + 0.5, f'{v:.1f}%', ha='center')
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图表
    plt.savefig('dynamic_stop_loss_performance_comparison.png', dpi=150, bbox_inches='tight')
    
    # 显示图表
    plt.show()

if __name__ == "__main__":
    # 初始参数
    cost_price = 100.0
    
    # 1. 生成各种股价模式
    price_patterns = generate_price_patterns(cost_price=cost_price, days=60)
    
    # 2. 运行模拟
    results = run_simulation(price_patterns, cost_price=cost_price)
    
    # 3. 绘制结果图表
    plot_results(results, cost_price=cost_price)
    
    # 4. 绘制性能比较图表
    plot_performance_comparison(results)
    
    print("模拟测试完成，图表已生成。")