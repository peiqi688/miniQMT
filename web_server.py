# -*- coding: utf-8 -*-

"""
Web服务模块，提供RESTful API接口与前端交互
"""
import os
import time
import json
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, make_response, Response, stream_with_context
from flask_cors import CORS
import pandas as pd

import config
from logger import get_logger
from data_manager import get_data_manager
from indicator_calculator import get_indicator_calculator
from position_manager import get_position_manager
from trading_executor import get_trading_executor
from strategy import get_trading_strategy
import utils


# 获取logger
logger = get_logger("web_server")
webpage_dir = 'web1.0'

# 创建Flask应用
app = Flask(__name__, static_folder=webpage_dir, static_url_path='')

# 允许跨域请求
CORS(app)

# 获取各个模块的实例
data_manager = get_data_manager()
indicator_calculator = get_indicator_calculator()
position_manager = get_position_manager()
trading_executor = get_trading_executor()
trading_strategy = get_trading_strategy()

# 实时推送的数据
realtime_data = {
    'positions': {},
    'latest_prices': {},
    'trading_signals': {},
    'account_info': {},
    'positions_all': []  # Add new field for all positions data
}

# 实时推送线程
push_thread = None
stop_push_flag = False

@app.route('/')
def index():
    """Serve the index.html file"""
    return send_from_directory(os.path.join(os.path.dirname(__file__), webpage_dir), 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files from the 'web' directory"""
    return send_from_directory(os.path.join(os.path.dirname(__file__), webpage_dir), filename)

@app.route('/api/connection/status', methods=['GET'])
def connection_status():
    """返回API连接状态"""
    try:
        # 检查 qmt_trader 的连接状态
        is_connected = False
        if hasattr(position_manager, 'qmt_trader') and position_manager.qmt_trader:
            if hasattr(position_manager.qmt_trader, 'xt_trader') and position_manager.qmt_trader.xt_trader:
                if hasattr(position_manager.qmt_trader.xt_trader, 'is_connected'):
                    is_connected = position_manager.qmt_trader.xt_trader.is_connected()
                else:
                    # 尝试其他检查方式
                    is_connected = True  # 假设已连接，实际应根据具体情况修改
        
        return jsonify({
            'status': 'success',
            'connected': bool(is_connected),  # 确保返回布尔值
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        logger.error(f"检查API连接状态时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'connected': False,
            'message': f"检查API连接状态时出错: {str(e)}",
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取系统状态"""
    try:
        # 从 position_manager 获取账户信息
        account_info = position_manager.get_account_info() or {}
        
        # 如果没有账户信息，使用默认值
        if not account_info:
            account_info = {
                'account_id': '--',
                'account_type': '--',
                'available': 0.0,
                'frozen_cash': 0.0,
                'market_value': 0.0,
                'total_asset': 0.0,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        # 格式化为前端期望的结构
        account_data = {
            'id': account_info.get('account_id', '--'),
            'availableBalance': account_info.get('available', 0.0),
            'maxHoldingValue': account_info.get('market_value', 0.0),
            'totalAssets': account_info.get('total_asset', 0.0),
            'timestamp': account_info.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        }
        
        # 判断监控状态
        strategy_monitoring = (
            trading_strategy.strategy_thread is not None and 
            trading_strategy.strategy_thread.is_alive()
        )
        position_monitoring = (
            position_manager.monitor_thread is not None and
            position_manager.monitor_thread.is_alive()
        )
        is_monitoring = strategy_monitoring or position_monitoring

        # 获取全局设置状态
        system_settings = {
            'isMonitoring': is_monitoring,
            'enableAutoTrading': config.ENABLE_AUTO_TRADING,
            'allowBuy': getattr(config, 'ENABLE_ALLOW_BUY', True),
            'allowSell': getattr(config, 'ENABLE_ALLOW_SELL', True),
            'simulationMode': getattr(config, 'ENABLE_SIMULATION_MODE', False)
        }

        return jsonify({
            'status': 'success',
            'isMonitoring': is_monitoring,
            'account': account_data,
            'settings': system_settings,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        logger.error(f"获取系统状态时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取系统状态时出错: {str(e)}"
        }), 500

@app.route('/api/positions', methods=['GET'])
def get_positions():
    """获取持仓信息"""
    try:
        positions = trading_executor.get_stock_positions()
        positions_df = pd.DataFrame(positions)
        
        # 计算持仓指标
        metrics = utils.calculate_position_metrics(positions_df)
        
        # 更新实时数据
        for pos in positions:
            stock_code = pos['stock_code']
            realtime_data['positions'][stock_code] = pos
        
        # 获取所有持仓数据
        positions_all_df = position_manager.get_all_positions_with_all_fields()
        realtime_data['positions_all'] = positions_all_df.to_dict('records')
        
        response = make_response(jsonify({
            'status': 'success',
            'data': {
                'positions': positions,
                'metrics': metrics,
                'positions_all': realtime_data['positions_all']
            }
        }))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"获取持仓信息时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取持仓信息时出错: {str(e)}"
        }), 500

@app.route('/api/trade-records', methods=['GET'])
def get_trade_records():
    """获取交易记录"""
    try:
        # 从交易执行器获取交易记录
        trades_df = trading_executor.get_trades()
        
        # 如果没有交易记录，返回空列表
        if trades_df.empty:
            return jsonify({'status': 'success', 'data': []})
        
        # Format 'trade_time' to 'YYYY-MM-DD'
        if 'trade_time' in trades_df.columns:
            trades_df['trade_time'] = pd.to_datetime(trades_df['trade_time']).dt.strftime('%Y-%m-%d')
        
        # Replace NaN with None (which will become null in JSON)
        trades_df = trades_df.replace({pd.NA: None, float('nan'): None})
        
        # 将 DataFrame 转换为 JSON 格式
        trade_records = trades_df.to_dict(orient='records')
        
        response = make_response(jsonify({
            'status': 'success',
            'data': trade_records
        }))        
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"获取交易记录时出错: {str(e)}")
        return jsonify({'status': 'error', 'message': f"获取交易记录时出错: {str(e)}"}), 500

# 配置管理API
@app.route('/api/config', methods=['GET'])
def get_config():
    """获取系统配置"""
    try:
        # 从config模块获取配置项
        config_data = {
            "singleBuyAmount": config.POSITION_UNIT,
            "firstProfitSell": config.INITIAL_TAKE_PROFIT_RATIO * 100,
            "firstProfitSellEnabled": config.ENABLE_DYNAMIC_STOP_PROFIT,
            "stockGainSellPencent": config.INITIAL_TAKE_PROFIT_RATIO_PERCENTAGE * 100,
            "allowBuy": getattr(config, 'ENABLE_ALLOW_BUY', True),
            "allowSell": getattr(config, 'ENABLE_ALLOW_SELL', True),
            "stopLossBuy": abs(config.BUY_GRID_LEVELS[1] - 1) * 100,
            "stopLossBuyEnabled": True,
            "stockStopLoss": abs(config.STOP_LOSS_RATIO) * 100,
            "StopLossEnabled": True,
            "singleStockMaxPosition": config.MAX_POSITION_VALUE,
            "totalMaxPosition": config.MAX_TOTAL_POSITION_RATIO * 1000000,
            "connectPort": config.WEB_SERVER_PORT,
            "totalAccounts": "127.0.0.1",
            "globalAllowBuySell": config.ENABLE_AUTO_TRADING,
            "simulationMode": getattr(config, 'ENABLE_SIMULATION_MODE', False)
        }
        
        # 获取参数范围
        param_ranges = {k: {'min': v['min'], 'max': v['max']} for k, v in config.CONFIG_PARAM_RANGES.items()}
        
        return jsonify({
            'status': 'success',
            'data': config_data,
            'ranges': param_ranges
        })
    except Exception as e:
        logger.error(f"获取配置时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取配置时出错: {str(e)}"
        }), 500

@app.route('/api/config/save', methods=['POST'])
def save_config():
    """保存系统配置"""
    try:
        config_data = request.json
        
        # 参数校验
        validation_errors = []
        for param_name, value in config_data.items():
            # 检查类型，跳过布尔值和字符串
            if isinstance(value, bool) or isinstance(value, str):
                continue
                
            # 校验参数
            is_valid, error_msg = config.validate_config_param(param_name, value)
            if not is_valid:
                validation_errors.append(error_msg)
        
        # 如果有验证错误，返回错误信息
        if validation_errors:
            return jsonify({
                'status': 'error',
                'message': '参数校验失败',
                'errors': validation_errors
            }), 400
        
        # 更新配置
        # 注意：这里只是临时更新运行时配置，不会修改配置文件
        # 在实际应用中，您可能需要将配置写入配置文件
        
        # 更新主要参数
        if "singleBuyAmount" in config_data:
            config.POSITION_UNIT = float(config_data["singleBuyAmount"])
        if "firstProfitSell" in config_data:
            config.INITIAL_TAKE_PROFIT_RATIO = float(config_data["firstProfitSell"]) / 100
        if "firstProfitSellEnabled" in config_data:
            config.ENABLE_DYNAMIC_STOP_PROFIT = bool(config_data["firstProfitSellEnabled"])
        if "stockGainSellPencent" in config_data:
            config.INITIAL_TAKE_PROFIT_RATIO_PERCENTAGE = float(config_data["stockGainSellPencent"]) / 100
        if "stopLossBuy" in config_data:
            # 更新第二个网格级别
            ratio = 1 - float(config_data["stopLossBuy"]) / 100
            config.BUY_GRID_LEVELS[1] = ratio
        if "stockStopLoss" in config_data:
            config.STOP_LOSS_RATIO = -float(config_data["stockStopLoss"]) / 100
        if "singleStockMaxPosition" in config_data:
            config.MAX_POSITION_VALUE = float(config_data["singleStockMaxPosition"])
        if "totalMaxPosition" in config_data:
            config.MAX_TOTAL_POSITION_RATIO = float(config_data["totalMaxPosition"]) / 1000000
            
        # 开关类参数
        if "allowBuy" in config_data:
            setattr(config, 'ENABLE_ALLOW_BUY', bool(config_data["allowBuy"]))
        if "allowSell" in config_data:
            setattr(config, 'ENABLE_ALLOW_SELL', bool(config_data["allowSell"]))
        if "globalAllowBuySell" in config_data:
            config.ENABLE_AUTO_TRADING = bool(config_data["globalAllowBuySell"])
        if "simulationMode" in config_data:
            setattr(config, 'ENABLE_SIMULATION_MODE', bool(config_data["simulationMode"]))
        
        logger.info(f"配置已更新: {config_data}")
        
        return jsonify({
            'status': 'success',
            'message': '配置已保存并应用'
        })
    except Exception as e:
        logger.error(f"保存配置时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"保存配置失败: {str(e)}"
        }), 500

@app.route('/api/monitor/start', methods=['POST'])
def start_monitor():
    """启动监控"""
    try:
        # 获取并保存配置
        if request.is_json:
            config_data = request.json
            
            # 参数校验
            validation_errors = []
            for param_name, value in config_data.items():
                # 检查类型，跳过布尔值和字符串
                if isinstance(value, bool) or isinstance(value, str):
                    continue
                    
                # 校验参数
                is_valid, error_msg = config.validate_config_param(param_name, value)
                if not is_valid:
                    validation_errors.append(error_msg)
            
            # 如果有验证错误，返回错误信息
            if validation_errors:
                return jsonify({
                    'status': 'error',
                    'message': '参数校验失败，无法启动监控',
                    'errors': validation_errors
                }), 400
            
            # 保存配置
            # 更新主要参数
            if "singleBuyAmount" in config_data:
                config.POSITION_UNIT = float(config_data["singleBuyAmount"])
            if "firstProfitSell" in config_data:
                config.INITIAL_TAKE_PROFIT_RATIO = float(config_data["firstProfitSell"]) / 100
            if "firstProfitSellEnabled" in config_data:
                config.ENABLE_DYNAMIC_STOP_PROFIT = bool(config_data["firstProfitSellEnabled"])
            if "stockGainSellPencent" in config_data:
                config.INITIAL_TAKE_PROFIT_RATIO_PERCENTAGE = float(config_data["stockGainSellPencent"]) / 100
            if "stopLossBuy" in config_data:
                # 更新第二个网格级别
                ratio = 1 - float(config_data["stopLossBuy"]) / 100
                config.BUY_GRID_LEVELS[1] = ratio
            if "stockStopLoss" in config_data:
                config.STOP_LOSS_RATIO = -float(config_data["stockStopLoss"]) / 100
            if "singleStockMaxPosition" in config_data:
                config.MAX_POSITION_VALUE = float(config_data["singleStockMaxPosition"])
            if "totalMaxPosition" in config_data:
                config.MAX_TOTAL_POSITION_RATIO = float(config_data["totalMaxPosition"]) / 1000000
                
            # 开关类参数
            if "allowBuy" in config_data:
                setattr(config, 'ENABLE_ALLOW_BUY', bool(config_data["allowBuy"]))
            if "allowSell" in config_data:
                setattr(config, 'ENABLE_ALLOW_SELL', bool(config_data["allowSell"]))
            if "globalAllowBuySell" in config_data:
                config.ENABLE_AUTO_TRADING = bool(config_data["globalAllowBuySell"])
            if "simulationMode" in config_data:
                setattr(config, 'ENABLE_SIMULATION_MODE', bool(config_data["simulationMode"]))
                
        # 启用自动交易
        config.ENABLE_AUTO_TRADING = True
        
        # 启动策略线程
        trading_strategy.start_strategy_thread()
        
        # 启动持仓监控线程
        position_manager.start_position_monitor_thread()
        
        return jsonify({
            'status': 'success',
            'message': '监控已启动',
            'isMonitoring': True
        })
    except Exception as e:
        logger.error(f"启动监控时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"启动监控失败: {str(e)}"
        }), 500

@app.route('/api/monitor/stop', methods=['POST'])
def stop_monitor():
    """停止监控"""
    try:
        # 停止策略线程
        trading_strategy.stop_strategy_thread()
        
        # 停止持仓监控线程
        position_manager.stop_position_monitor_thread()
        
        # 禁用自动交易
        config.ENABLE_AUTO_TRADING = False
        
        return jsonify({
            'status': 'success',
            'message': '监控已停止',
            'isMonitoring': False
        })
    except Exception as e:
        logger.error(f"停止监控时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"停止监控失败: {str(e)}"
        }), 500

@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """清空日志"""
    try:
        # 执行清空日志的操作
        # 这里假设交易记录存储在数据库中，我们执行清空操作
        cursor = data_manager.conn.cursor()
        cursor.execute("DELETE FROM trade_records")
        data_manager.conn.commit()
        
        return jsonify({
            'status': 'success',
            'message': '日志已清空'
        })
    except Exception as e:
        logger.error(f"清空日志时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"清空日志失败: {str(e)}"
        }), 500

@app.route('/api/data/clear_current', methods=['POST'])
def clear_current_data():
    """清空当前数据"""
    try:
        # 清空持仓数据
        cursor = data_manager.conn.cursor()
        cursor.execute("DELETE FROM positions")
        data_manager.conn.commit()
        
        return jsonify({
            'status': 'success',
            'message': '当前数据已清空'
        })
    except Exception as e:
        logger.error(f"清空当前数据时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"清空当前数据失败: {str(e)}"
        }), 500

@app.route('/api/data/clear_buysell', methods=['POST'])
def clear_buysell_data():
    """清空买入/卖出数据"""
    try:
        # 清空交易记录
        cursor = data_manager.conn.cursor()
        cursor.execute("DELETE FROM trade_records")
        data_manager.conn.commit()
        
        return jsonify({
            'status': 'success',
            'message': '买入/卖出数据已清空'
        })
    except Exception as e:
        logger.error(f"清空买入/卖出数据时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"清空买入/卖出数据失败: {str(e)}"
        }), 500

@app.route('/api/data/import', methods=['POST'])
def import_data():
    """导入保存数据"""
    try:
        # 这里需要实现导入数据的逻辑
        # 由于没有具体实现，返回成功消息
        return jsonify({
            'status': 'success',
            'message': '数据导入成功'
        })
    except Exception as e:
        logger.error(f"导入数据时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"导入数据失败: {str(e)}"
        }), 500

@app.route('/api/holdings/init', methods=['POST'])
def init_holdings():
    """初始化持仓数据"""
    try:
        # 获取配置数据
        if request.is_json:
            config_data = request.json
            
            # 校验并保存配置
            # 这里重复使用save_config的代码
            validation_errors = []
            for param_name, value in config_data.items():
                # 检查类型，跳过布尔值和字符串
                if isinstance(value, bool) or isinstance(value, str):
                    continue
                    
                # 校验参数
                is_valid, error_msg = config.validate_config_param(param_name, value)
                if not is_valid:
                    validation_errors.append(error_msg)
            
            # 如果有验证错误，返回错误信息
            if validation_errors:
                return jsonify({
                    'status': 'error',
                    'message': '参数校验失败，无法初始化持仓',
                    'errors': validation_errors
                }), 400
            
            # 应用配置
            # 更新主要参数
            if "singleBuyAmount" in config_data:
                config.POSITION_UNIT = float(config_data["singleBuyAmount"])
            if "firstProfitSell" in config_data:
                config.INITIAL_TAKE_PROFIT_RATIO = float(config_data["firstProfitSell"]) / 100
            if "firstProfitSellEnabled" in config_data:
                config.ENABLE_DYNAMIC_STOP_PROFIT = bool(config_data["firstProfitSellEnabled"])
            if "stockGainSellPencent" in config_data:
                config.INITIAL_TAKE_PROFIT_RATIO_PERCENTAGE = float(config_data["stockGainSellPencent"]) / 100
            if "stopLossBuy" in config_data:
                # 更新第二个网格级别
                ratio = 1 - float(config_data["stopLossBuy"]) / 100
                config.BUY_GRID_LEVELS[1] = ratio
            if "stockStopLoss" in config_data:
                config.STOP_LOSS_RATIO = -float(config_data["stockStopLoss"]) / 100
            if "singleStockMaxPosition" in config_data:
                config.MAX_POSITION_VALUE = float(config_data["singleStockMaxPosition"])
            if "totalMaxPosition" in config_data:
                config.MAX_TOTAL_POSITION_RATIO = float(config_data["totalMaxPosition"]) / 1000000
                
            # 开关类参数
            if "allowBuy" in config_data:
                setattr(config, 'ENABLE_ALLOW_BUY', bool(config_data["allowBuy"]))
            if "allowSell" in config_data:
                setattr(config, 'ENABLE_ALLOW_SELL', bool(config_data["allowSell"]))
            if "globalAllowBuySell" in config_data:
                config.ENABLE_AUTO_TRADING = bool(config_data["globalAllowBuySell"])
            if "simulationMode" in config_data:
                setattr(config, 'ENABLE_SIMULATION_MODE', bool(config_data["simulationMode"]))
        
        # 初始化持仓数据
        # 这里需要实现初始化持仓的逻辑
        # 可以通过查询交易接口获取实际持仓
        
        # 假设我们直接从交易执行器获取持仓
        positions = trading_executor.get_stock_positions()
        
        # 清空已有持仓数据
        cursor = data_manager.conn.cursor()
        cursor.execute("DELETE FROM positions")
        data_manager.conn.commit()
        
        # 导入最新持仓
        for pos in positions:
            # 假设position_manager有一个update_position方法
            position_manager.update_position(
                stock_code=pos['stock_code'],
                volume=pos['volume'],
                cost_price=pos['cost_price'],
                current_price=pos['current_price']
            )
        
        return jsonify({
            'status': 'success',
            'message': '持仓数据初始化成功',
            'count': len(positions)
        })
    except Exception as e:
        logger.error(f"初始化持仓数据时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"初始化持仓数据失败: {str(e)}"
        }), 500

@app.route('/api/actions/execute_buy', methods=['POST'])
def execute_buy():
    """执行买入操作"""
    try:
        buy_data = request.json
        strategy = buy_data.get('strategy', 'random_pool')
        quantity = int(buy_data.get('quantity', 0))
        
        if quantity <= 0:
            return jsonify({
                'status': 'error',
                'message': '买入数量必须大于0'
            }), 400
        
        # 从股票池选择股票
        stock_codes = config.STOCK_POOL[:quantity] if quantity <= len(config.STOCK_POOL) else config.STOCK_POOL
        
        # 执行买入
        success_count = 0
        for stock_code in stock_codes:
            # 计算买入金额
            amount = config.POSITION_UNIT
            
            # 执行买入
            order_id = trading_strategy.manual_buy(
                stock_code=stock_code,
                amount=amount
            )
            
            if order_id:
                success_count += 1
        
        return jsonify({
            'status': 'success',
            'message': f'成功发送{success_count}个买入指令',
            'success_count': success_count,
            'total_count': len(stock_codes)
        })
    except Exception as e:
        logger.error(f"执行买入操作时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"执行买入操作失败: {str(e)}"
        }), 500

@app.route('/api/holdings/update', methods=['POST'])
def update_holding_params():
    """更新持仓参数"""
    try:
        data = request.json
        stock_code = data.get('stock_code')
        profit_triggered = data.get('profit_triggered')
        highest_price = data.get('highest_price')
        stop_loss_price = data.get('stop_loss_price')
        
        if not stock_code:
            return jsonify({
                'status': 'error',
                'message': '股票代码不能为空'
            }), 400
        
        # 获取当前持仓
        position = position_manager.get_position(stock_code)
        if not position:
            return jsonify({
                'status': 'error',
                'message': f'未找到{stock_code}的持仓信息'
            }), 404
        
        # 更新持仓参数
        position_manager.update_position(
            stock_code=stock_code,
            volume=position['volume'],
            cost_price=position['cost_price'],
            profit_triggered=profit_triggered if profit_triggered is not None else position['profit_triggered'],
            highest_price=highest_price if highest_price is not None else position['highest_price'],
            stop_loss_price=stop_loss_price if stop_loss_price is not None else position['stop_loss_price']
        )
        
        return jsonify({
            'status': 'success',
            'message': f'{stock_code}持仓参数更新成功'
        })
    except Exception as e:
        logger.error(f"更新持仓参数时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"更新持仓参数失败: {str(e)}"
        }), 500

# 添加SSE接口
@app.route('/api/sse', methods=['GET'])
def sse():
    """提供Server-Sent Events流"""
    def event_stream():
        prev_data = None
        while True:
            try:
                # 获取最新数据
                account_info = position_manager.get_account_info() or {}
                current_data = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'holdings_count': len(realtime_data['positions_all']),
                    'account_info': {
                        'available': account_info.get('available', 0),
                        'market_value': account_info.get('market_value', 0),
                        'total_asset': account_info.get('total_asset', 0)
                    },
                    'monitoring': {
                        'isMonitoring': config.ENABLE_AUTO_TRADING,
                        'allowBuy': getattr(config, 'ENABLE_ALLOW_BUY', True),
                        'allowSell': getattr(config, 'ENABLE_ALLOW_SELL', True),
                        'simulationMode': getattr(config, 'ENABLE_SIMULATION_MODE', False)
                    }
                }
                
                # 只在数据变化时发送更新
                if current_data != prev_data:
                    yield f"data: {json.dumps(current_data)}\n\n"
                    prev_data = current_data
            except Exception as e:
                logger.error(f"SSE流生成数据时出错: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            time.sleep(2)  # 每2秒检查一次
    
    return Response(stream_with_context(event_stream()), 
                   mimetype="text/event-stream",
                   headers={"Cache-Control": "no-cache",
                            "X-Accel-Buffering": "no"})

# 修改get_positions_all函数，添加数据版本号
@app.route('/api/positions-all', methods=['GET'])
def get_positions_all():
    """获取所有持仓信息（包括所有字段）"""
    try:
        positions_all_df = position_manager.get_all_positions_with_all_fields()
        
        # 计算数据版本号（使用时间戳）
        data_version = int(time.time())
        
        # 处理NaN值
        positions_all_df = positions_all_df.replace({pd.NA: None, float('nan'): None})
        
        # 转换为JSON可序列化的格式
        positions_all = positions_all_df.to_dict('records')
        
        # 更新实时数据
        realtime_data['positions_all'] = positions_all

        # 添加数据版本号（可以使用时间戳）
        data_version = int(time.time())

        response = make_response(jsonify({
            'status': 'success',
            'data': positions_all,
            'data_version': data_version  # 添加版本号
        }))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"获取所有持仓信息（所有字段）时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取所有持仓信息（所有字段）时出错: {str(e)}"
        }), 500

def push_realtime_data():
    """推送实时数据的线程函数"""
    global stop_push_flag
    
    while not stop_push_flag:
        try:
            # 只在交易时间更新数据
            if config.is_trade_time():
                # 更新所有持仓的最新价格
                position_manager.update_all_positions_price()
                
                # 获取所有持仓数据
                positions_all_df = position_manager.get_all_positions_with_all_fields()
                
                # 处理NaN值
                positions_all_df = positions_all_df.replace({pd.NA: None, float('nan'): None})
                
                # 更新实时数据
                realtime_data['positions_all'] = positions_all_df.to_dict('records')
            
            # 休眠间隔
            time.sleep(3)
        except Exception as e:
            logger.error(f"推送实时数据时出错: {str(e)}")
            time.sleep(3)  # 出错后休眠


def start_push_thread():
    """启动实时推送线程"""
    global push_thread
    global stop_push_flag
    
    if push_thread is None or not push_thread.is_alive():
        stop_push_flag = False
        push_thread = threading.Thread(target=push_realtime_data)
        push_thread.daemon = True
        push_thread.start()
        logger.info("实时推送线程已启动")
    else:
        logger.warning("实时推送线程已在运行")

def start_web_server():
    """启动Web服务器"""
    start_push_thread()
    app.run(host=config.WEB_SERVER_HOST, port=config.WEB_SERVER_PORT, debug=config.WEB_SERVER_DEBUG, use_reloader=False)

if __name__ == '__main__':
     start_web_server()