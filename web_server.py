"""
Web服务模块，提供RESTful API接口与前端交互
"""
import os
import time
import json
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
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

# 创建Flask应用
app = Flask(__name__)

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
    'account_info': {}
}

# 实时推送线程
push_thread = None
stop_push_flag = False

@app.route('/')
def index():
    """API根路径"""
    return jsonify({
        'status': 'success',
        'message': 'QMT Trading API Server Running',
        'version': '1.0.0',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/system-info', methods=['GET'])
def get_system_info():
    """获取系统信息"""
    try:
        sys_info = utils.system_info()
        memory = utils.memory_usage()
        disk = utils.disk_usage()
        
        return jsonify({
            'status': 'success',
            'data': {
                'system': sys_info,
                'memory': memory,
                'disk': disk,
                'running_time': time.time(),  # 应用运行时间
                'config': {
                    'debug': config.DEBUG,
                    'log_level': config.LOG_LEVEL,
                    'data_dir': config.DATA_DIR,
                    'web_server': {
                        'host': config.WEB_SERVER_HOST,
                        'port': config.WEB_SERVER_PORT
                    }
                }
            }
        })
    except Exception as e:
        logger.error(f"获取系统信息时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取系统信息时出错: {str(e)}"
        }), 500

@app.route('/api/account-info', methods=['GET'])
def get_account_info():
    """获取账户信息"""
    try:
        account_info = trading_executor.get_account_info()
        
        if account_info:
            # 更新实时数据
            realtime_data['account_info'] = account_info
            
            return jsonify({
                'status': 'success',
                'data': account_info
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '获取账户信息失败'
            }), 400
    except Exception as e:
        logger.error(f"获取账户信息时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取账户信息时出错: {str(e)}"
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
        
        return jsonify({
            'status': 'success',
            'data': {
                'positions': positions,
                'metrics': metrics
            }
        })
    except Exception as e:
        logger.error(f"获取持仓信息时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取持仓信息时出错: {str(e)}"
        }), 500

@app.route('/api/orders', methods=['GET'])
def get_orders():
    """获取委托列表"""
    try:
        status = request.args.get('status')
        status = int(status) if status and status.isdigit() else None
        
        orders = trading_executor.get_orders(status)
        
        return jsonify({
            'status': 'success',
            'data': orders
        })
    except Exception as e:
        logger.error(f"获取委托列表时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取委托列表时出错: {str(e)}"
        }), 500

@app.route('/api/trades', methods=['GET'])
def get_trades():
    """获取成交记录"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        trades_df = trading_executor.get_trades(start_date, end_date)
        
        # 转换为JSON可序列化的格式
        trades = trades_df.to_dict('records')
        
        # 计算交易指标
        metrics = utils.calculate_trade_metrics(trades_df)
        
        return jsonify({
            'status': 'success',
            'data': {
                'trades': trades,
                'metrics': metrics
            }
        })
    except Exception as e:
        logger.error(f"获取成交记录时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取成交记录时出错: {str(e)}"
        }), 500

@app.route('/api/stock-data', methods=['GET'])
def get_stock_data():
    """获取股票历史数据"""
    try:
        stock_code = request.args.get('stock_code')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not stock_code:
            return jsonify({
                'status': 'error',
                'message': '股票代码不能为空'
            }), 400
        
        # 获取历史数据
        data_df = data_manager.get_history_data_from_db(stock_code, start_date, end_date)
        
        if data_df.empty:
            return jsonify({
                'status': 'error',
                'message': f'未找到 {stock_code} 的历史数据'
            }), 404
        
        # 转换为JSON可序列化的格式
        data = data_df.to_dict('records')
        
        return jsonify({
            'status': 'success',
            'data': data
        })
    except Exception as e:
        logger.error(f"获取股票历史数据时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取股票历史数据时出错: {str(e)}"
        }), 500

@app.route('/api/indicators', methods=['GET'])
def get_indicators():
    """获取股票指标数据"""
    try:
        stock_code = request.args.get('stock_code')
        days = request.args.get('days', 60)
        
        if not stock_code:
            return jsonify({
                'status': 'error',
                'message': '股票代码不能为空'
            }), 400
        
        try:
            days = int(days)
        except ValueError:
            days = 60
        
        # 获取指标数据
        indicators_df = indicator_calculator.get_indicators_history(stock_code, days)
        
        if indicators_df.empty:
            return jsonify({
                'status': 'error',
                'message': f'未找到 {stock_code} 的指标数据'
            }), 404
        
        # 转换为JSON可序列化的格式
        indicators = indicators_df.to_dict('records')
        
        return jsonify({
            'status': 'success',
            'data': indicators
        })
    except Exception as e:
        logger.error(f"获取股票指标数据时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取股票指标数据时出错: {str(e)}"
        }), 500

@app.route('/api/latest-price', methods=['GET'])
def get_latest_price():
    """获取最新行情"""
    try:
        stock_code = request.args.get('stock_code')
        
        if not stock_code:
            return jsonify({
                'status': 'error',
                'message': '股票代码不能为空'
            }), 400
        
        # 获取最新行情
        latest_quote = data_manager.get_latest_data(stock_code)
        
        if not latest_quote:
            return jsonify({
                'status': 'error',
                'message': f'未找到 {stock_code} 的最新行情'
            }), 404
        
        # 更新实时数据
        realtime_data['latest_prices'][stock_code] = latest_quote
        
        return jsonify({
            'status': 'success',
            'data': latest_quote
        })
    except Exception as e:
        logger.error(f"获取最新行情时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取最新行情时出错: {str(e)}"
        }), 500

@app.route('/api/stock-pool', methods=['GET', 'POST'])
def stock_pool():
    """获取或更新股票池"""
    if request.method == 'GET':
        try:
            return jsonify({
                'status': 'success',
                'data': config.STOCK_POOL
            })
        except Exception as e:
            logger.error(f"获取股票池时出错: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f"获取股票池时出错: {str(e)}"
            }), 500
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            if not data or 'stock_codes' not in data:
                return jsonify({
                    'status': 'error',
                    'message': '请求数据格式错误'
                }), 400
            
            stock_codes = data['stock_codes']
            
            # 验证股票代码
            valid_codes = []
            for code in stock_codes:
                if utils.is_valid_stock_code(code):
                    valid_codes.append(code)
                else:
                    logger.warning(f"无效的股票代码: {code}")
            
            if not valid_codes:
                return jsonify({
                    'status': 'error',
                    'message': '没有有效的股票代码'
                }), 400
            
            # 更新股票池
            config.STOCK_POOL = valid_codes
            
            # 保存到文件
            utils.save_stock_pool_to_json(valid_codes)
            
            return jsonify({
                'status': 'success',
                'message': f'股票池已更新，共 {len(valid_codes)} 只股票',
                'data': valid_codes
            })
        except Exception as e:
            logger.error(f"更新股票池时出错: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f"更新股票池时出错: {str(e)}"
            }), 500

@app.route('/api/grid-trades', methods=['GET'])
def get_grid_trades():
    """获取网格交易记录"""
    try:
        stock_code = request.args.get('stock_code')
        status = request.args.get('status')
        
        if not stock_code:
            return jsonify({
                'status': 'error',
                'message': '股票代码不能为空'
            }), 400
        
        # 获取网格交易记录
        grid_trades_df = position_manager.get_grid_trades(stock_code, status)
        
        if grid_trades_df.empty:
            return jsonify({
                'status': 'success',
                'data': []
            })
        
        # 转换为JSON可序列化的格式
        grid_trades = grid_trades_df.to_dict('records')
        
        return jsonify({
            'status': 'success',
            'data': grid_trades
        })
    except Exception as e:
        logger.error(f"获取网格交易记录时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取网格交易记录时出错: {str(e)}"
        }), 500

@app.route('/api/init-grid', methods=['POST'])
def init_grid():
    """初始化网格交易"""
    try:
        data = request.get_json()
        
        if not data or 'stock_code' not in data:
            return jsonify({
                'status': 'error',
                'message': '请求数据格式错误'
            }), 400
        
        stock_code = data['stock_code']
        
        # 初始化网格交易
        success = trading_strategy.init_grid_trading(stock_code)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'{stock_code} 网格交易初始化成功'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'{stock_code} 网格交易初始化失败'
            }), 400
    except Exception as e:
        logger.error(f"初始化网格交易时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"初始化网格交易时出错: {str(e)}"
        }), 500

@app.route('/api/buy', methods=['POST'])
def buy_stock():
    """买入股票"""
    try:
        data = request.get_json()
        
        if not data or 'stock_code' not in data:
            return jsonify({
                'status': 'error',
                'message': '请求数据格式错误'
            }), 400
        
        stock_code = data['stock_code']
        volume = data.get('volume')
        price = data.get('price')
        amount = data.get('amount')
        
        # 检查交易时间
        if not config.is_trade_time():
            return jsonify({
                'status': 'error',
                'message': '当前不是交易时间'
            }), 400
        
        # 执行买入
        order_id = trading_strategy.manual_buy(stock_code, volume, price, amount)
        
        if order_id:
            return jsonify({
                'status': 'success',
                'message': f'{stock_code} 买入委托已提交，委托号: {order_id}',
                'data': {'order_id': order_id}
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'{stock_code} 买入委托提交失败'
            }), 400
    except Exception as e:
        logger.error(f"买入股票时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"买入股票时出错: {str(e)}"
        }), 500

@app.route('/api/sell', methods=['POST'])
def sell_stock():
    """卖出股票"""
    try:
        data = request.get_json()
        
        if not data or 'stock_code' not in data:
            return jsonify({
                'status': 'error',
                'message': '请求数据格式错误'
            }), 400
        
        stock_code = data['stock_code']
        volume = data.get('volume')
        price = data.get('price')
        ratio = data.get('ratio')
        
        # 检查交易时间
        if not config.is_trade_time():
            return jsonify({
                'status': 'error',
                'message': '当前不是交易时间'
            }), 400
        
        # 执行卖出
        order_id = trading_strategy.manual_sell(stock_code, volume, price, ratio)
        
        if order_id:
            return jsonify({
                'status': 'success',
                'message': f'{stock_code} 卖出委托已提交，委托号: {order_id}',
                'data': {'order_id': order_id}
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'{stock_code} 卖出委托提交失败'
            }), 400
    except Exception as e:
        logger.error(f"卖出股票时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"卖出股票时出错: {str(e)}"
        }), 500

@app.route('/api/cancel', methods=['POST'])
def cancel_order():
    """撤销委托"""
    try:
        data = request.get_json()
        
        if not data or 'order_id' not in data:
            return jsonify({
                'status': 'error',
                'message': '请求数据格式错误'
            }), 400
        
        order_id = data['order_id']
        
        # 检查交易时间
        if not config.is_trade_time():
            return jsonify({
                'status': 'error',
                'message': '当前不是交易时间'
            }), 400
        
        # 执行撤单
        success = trading_executor.cancel_order(order_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'委托 {order_id} 撤单请求已提交'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'委托 {order_id} 撤单请求提交失败'
            }), 400
    except Exception as e:
        logger.error(f"撤销委托时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"撤销委托时出错: {str(e)}"
        }), 500

@app.route('/api/export-trades', methods=['GET'])
def export_trades():
    """导出交易记录"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 获取成交记录
        trades_df = trading_executor.get_trades(start_date, end_date)
        
        if trades_df.empty:
            return jsonify({
                'status': 'error',
                'message': '没有可导出的交易记录'
            }), 404
        
        # 导出到CSV
        file_path = utils.export_trades_to_csv(trades_df)
        
        if file_path:
            return jsonify({
                'status': 'success',
                'message': f'交易记录已导出到 {file_path}',
                'data': {'file_path': file_path}
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '导出交易记录失败'
            }), 500
    except Exception as e:
        logger.error(f"导出交易记录时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"导出交易记录时出错: {str(e)}"
        }), 500

@app.route('/api/export-positions', methods=['GET'])
def export_positions():
    """导出持仓记录"""
    try:
        # 获取持仓记录
        positions = trading_executor.get_stock_positions()
        positions_df = pd.DataFrame(positions)
        
        if positions_df.empty:
            return jsonify({
                'status': 'error',
                'message': '没有可导出的持仓记录'
            }), 404
        
        # 导出到CSV
        file_path = utils.export_positions_to_csv(positions_df)
        
        if file_path:
            return jsonify({
                'status': 'success',
                'message': f'持仓记录已导出到 {file_path}',
                'data': {'file_path': file_path}
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '导出持仓记录失败'
            }), 500
    except Exception as e:
        logger.error(f"导出持仓记录时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"导出持仓记录时出错: {str(e)}"
        }), 500

@app.route('/api/download/<path:filename>', methods=['GET'])
def download_file(filename):
    """下载文件"""
    try:
        export_dir = os.path.join(config.DATA_DIR, 'exports')
        return send_from_directory(export_dir, filename, as_attachment=True)
    except Exception as e:
        logger.error(f"下载文件时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"下载文件时出错: {str(e)}"
        }), 500

@app.route('/api/auto-trading', methods=['GET', 'POST'])
def auto_trading():
    """获取或设置自动交易状态"""
    if request.method == 'GET':
        try:
            return jsonify({
                'status': 'success',
                'data': {
                    'enabled': config.ENABLE_AUTO_TRADING,
                    'running': trading_strategy.strategy_thread is not None and trading_strategy.strategy_thread.is_alive()
                }
            })
        except Exception as e:
            logger.error(f"获取自动交易状态时出错: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f"获取自动交易状态时出错: {str(e)}"
            }), 500
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            if not isinstance(data, dict) or 'enabled' not in data:
                return jsonify({
                    'status': 'error',
                    'message': '请求数据格式错误'
                }), 400
            
            enabled = data['enabled']
            
            if enabled:
                # 启用自动交易
                config.ENABLE_AUTO_TRADING = True
                trading_strategy.start_strategy_thread()
                
                return jsonify({
                    'status': 'success',
                    'message': '自动交易已启用'
                })
            else:
                # 禁用自动交易
                config.ENABLE_AUTO_TRADING = False
                trading_strategy.stop_strategy_thread()
                
                return jsonify({
                    'status': 'success',
                    'message': '自动交易已禁用'
                })
        except Exception as e:
            logger.error(f"设置自动交易状态时出错: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f"设置自动交易状态时出错: {str(e)}"
            }), 500

@app.route('/api/trading-config', methods=['GET', 'POST'])
def trading_config():
    """获取或更新交易配置"""
    if request.method == 'GET':
        try:
            # 返回交易相关配置
            config_data = {
                'POSITION_UNIT': config.POSITION_UNIT,
                'MAX_POSITION_VALUE': config.MAX_POSITION_VALUE,
                'MAX_TOTAL_POSITION_RATIO': config.MAX_TOTAL_POSITION_RATIO,
                'BUY_GRID_LEVELS': config.BUY_GRID_LEVELS,
                'BUY_AMOUNT_RATIO': config.BUY_AMOUNT_RATIO,
                'STOP_LOSS_RATIO': config.STOP_LOSS_RATIO,
                'INITIAL_TAKE_PROFIT_RATIO': config.INITIAL_TAKE_PROFIT_RATIO,
                'INITIAL_TAKE_PROFIT_RATIO_PERCENTAGE': config.INITIAL_TAKE_PROFIT_RATIO_PERCENTAGE,
                'DYNAMIC_TAKE_PROFIT': config.DYNAMIC_TAKE_PROFIT,
                'GRID_TRADING_ENABLED': config.GRID_TRADING_ENABLED,
                'GRID_STEP_RATIO': config.GRID_STEP_RATIO,
                'GRID_POSITION_RATIO': config.GRID_POSITION_RATIO,
                'GRID_MAX_LEVELS': config.GRID_MAX_LEVELS
            }
            
            return jsonify({
                'status': 'success',
                'data': config_data
            })
        except Exception as e:
            logger.error(f"获取交易配置时出错: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f"获取交易配置时出错: {str(e)}"
            }), 500
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            if not isinstance(data, dict):
                return jsonify({
                    'status': 'error',
                    'message': '请求数据格式错误'
                }), 400
            
            # 更新配置
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                    logger.info(f"更新配置 {key}: {value}")
                else:
                    logger.warning(f"未知配置项: {key}")
            
            return jsonify({
                'status': 'success',
                'message': '交易配置已更新'
            })
        except Exception as e:
            logger.error(f"更新交易配置时出错: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f"更新交易配置时出错: {str(e)}"
            }), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """获取日志"""
    try:
        lines = request.args.get('lines', 100)
        try:
            lines = int(lines)
        except ValueError:
            lines = 100
        
        log_file = os.path.join('logs', config.LOG_FILE)
        
        if not os.path.exists(log_file):
            return jsonify({
                'status': 'error',
                'message': '日志文件不存在'
            }), 404
        
        # 读取日志文件的最后几行
        logs = []
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = f.readlines()[-lines:]
        
        return jsonify({
            'status': 'success',
            'data': logs
        })
    except Exception as e:
        logger.error(f"获取日志时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取日志时出错: {str(e)}"
        }), 500

def push_realtime_data():
    """推送实时数据的线程函数"""
    global stop_push_flag
    
    while not stop_push_flag:
        try:
            # 更新所有持仓的最新价格
            if config.is_trade_time():
                position_manager.update_all_positions_price()
            
            # 休眠一段时间
            time.sleep(5)
        except Exception as e:
            logger.error(f"推送实时数据时出错: {str(e)}")
            time.sleep(5)

def start_push_thread():
    """启动推送实时数据的线程"""
    global push_thread, stop_push_flag
    
    if push_thread and push_thread.is_alive():
        logger.warning("推送线程已在运行")
        return
    
    stop_push_flag = False
    push_thread = threading.Thread(target=push_realtime_data)
    push_thread.daemon = True
    push_thread.start()
    logger.info("推送线程已启动")

def stop_push_thread():
    """停止推送实时数据的线程"""
    global push_thread, stop_push_flag
    
    if push_thread and push_thread.is_alive():
        stop_push_flag = True
        push_thread.join(timeout=5)
        logger.info("推送线程已停止")

def start_web_server():
    """启动Web服务器"""
    try:
        # 启动推送线程
        start_push_thread()
        
        # 启动Web服务器
        app.run(
            host=config.WEB_SERVER_HOST,
            port=config.WEB_SERVER_PORT,
            debug=config.WEB_SERVER_DEBUG
        )
    except Exception as e:
        logger.error(f"启动Web服务器时出错: {str(e)}")
    finally:
        # 停止推送线程
        stop_push_thread()

if __name__ == '__main__':
    start_web_server()
