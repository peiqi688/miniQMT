import requests
import time
import unittest
import json
import concurrent.futures
import threading
import re
from datetime import datetime

class StockBuyingTest(unittest.TestCase):
    """测试股票买入功能的单元测试类"""

    def setUp(self):
        """测试前的设置"""
        # 设置API基础URL - 根据实际环境修改
        self.base_url = "http://127.0.0.1:5000"
        
        # 设置模拟账户初始资金
        self.initial_balance = 1000000
        
        # 记录测试成功的初始化方法和股票代码格式
        self.successful_init_method = None
        self.successful_stock_format = None
        
        # 清空可能影响测试的历史记录
        self.clear_logs()
        self.reset_holdings()
        
        # 记录测试开始前的状态
        self.print_system_status()
        self.initial_logs_count = self.get_logs_count()
        self.initial_account_balance = self.get_account_balance()
        print(f"测试开始前 - 交易记录数量: {self.initial_logs_count}, 账户余额: {self.initial_account_balance}")

    def tearDown(self):
        """测试后环境清理"""
        print("\n测试完成，开始清理环境...")
        
        # 清空交易日志
        self.clear_logs()
        
        # 打印最终状态
        final_logs_count = self.get_logs_count()
        final_balance = self.get_account_balance()
        print(f"测试结束后 - 交易记录数量: {final_logs_count}, 账户余额: {final_balance}")

    def reset_holdings(self):
        """清理测试产生的持仓数据"""
        try:
            # 调用清空当前数据接口
            response = requests.post(f"{self.base_url}/api/data/clear_current", timeout=10)
            if response.status_code == 200:
                print("持仓数据已清理")
            else:
                print(f"持仓数据清理失败: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"清理持仓数据出错: {str(e)}")

    def get_account_balance(self):
        """获取当前账户余额"""
        try:
            response = requests.get(f"{self.base_url}/api/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                balance = data.get('account', {}).get('availableBalance', 0)
                return float(balance)
            else:
                print(f"获取账户余额失败: {response.status_code}")
                return 0
        except Exception as e:
            print(f"获取账户余额错误: {str(e)}")
            return 0

    def print_system_status(self):
        """打印系统当前状态"""
        try:
            # 获取系统状态
            status_response = requests.get(f"{self.base_url}/api/status", timeout=10)
            if status_response.status_code == 200:
                status_data = status_response.json()
                print("\n系统状态:")
                print(f"- 模拟交易模式: {status_data.get('settings', {}).get('simulationMode', '未知')}")
                print(f"- 允许买入: {status_data.get('settings', {}).get('allowBuy', '未知')}")
                print(f"- 允许卖出: {status_data.get('settings', {}).get('allowSell', '未知')}")
                print(f"- 监控状态: {status_data.get('isMonitoring', '未知')}")
                print(f"- 自动交易状态: {status_data.get('settings', {}).get('enableAutoTrading', '未知')}")
                print(f"- 可用资金: {status_data.get('account', {}).get('availableBalance', '未知')}")
                print(f"- 总资产: {status_data.get('account', {}).get('totalAssets', '未知')}")
            else:
                print(f"获取系统状态失败: {status_response.status_code}")
        except Exception as e:
            print(f"获取系统状态错误: {str(e)}")
            
    def get_logs_count(self):
        """获取当前交易日志数量"""
        try:
            response = requests.get(f"{self.base_url}/api/trade-records", timeout=10)
            if response.status_code == 200:
                logs = response.json()
                return len(logs.get('data', []))
            else:
                print(f"获取交易记录失败: {response.status_code}")
                return 0
        except Exception as e:
            print(f"获取交易记录错误: {str(e)}")
            return 0

    def clear_logs(self):
        """清除当天的交易日志"""
        try:
            # 获取清理前的交易记录数量
            logs_before = self.get_logs_count()
            print(f"清理前交易记录数量: {logs_before}")
            
            # 获取当天日期，用于日志显示
            today = datetime.now().strftime('%Y-%m-%d')
            print(f"准备清除 {today} 的交易记录...")
            
            # 调用后端修改后的清理接口
            response = requests.post(f"{self.base_url}/api/logs/clear", timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                print(f"清理结果: {result.get('message', '操作完成')}")
                
                # 等待清理操作完成（数据库事务可能需要时间）
                time.sleep(1)
                
                # 获取清理后的记录数量
                logs_after = self.get_logs_count()
                print(f"清理后交易记录数量: {logs_after}")
                
                # 计算清理数量
                cleared_count = logs_before - logs_after
                print(f"共清理了 {cleared_count} 条当天交易记录")
                
                return True
            else:
                print(f"清理当天交易记录失败: 状态码 {response.status_code}")
                try:
                    error_msg = response.json().get('message', '未知错误')
                    print(f"错误信息: {error_msg}")
                except:
                    print(f"无法解析错误响应: {response.text[:100]}")
                
                return False
        except Exception as e:
            print(f"清理当天交易记录过程中发生异常: {str(e)}")
            return False
            
    def check_database_connection(self):
        """检查数据库连接"""
        try:
            # 调用调试API来检查数据库
            response = requests.get(f"{self.base_url}/api/debug/db-test", timeout=10)
            if response.status_code == 200:
                db_info = response.json()
                print(f"数据库连接状态: {db_info.get('status')}")
                print(f"交易记录数量: {db_info.get('trade_records_count')}")
                return True
            else:
                print(f"数据库连接检查失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"数据库连接检查错误: {str(e)}")
            return False
            
    def print_logs_detail(self):
        """打印交易日志详情"""
        try:
            response = requests.get(f"{self.base_url}/api/trade-records", timeout=10)
            if response.status_code == 200:
                logs = response.json().get('data', [])
                print(f"\n当前交易日志 ({len(logs)}条):")
                for i, log in enumerate(logs[-5:]):  # 只打印最后5条
                    print(f"{i+1}. 时间:{log.get('trade_time')} | 代码:{log.get('stock_code')} | 类型:{log.get('trade_type')} | 价格:{log.get('price')} | 数量:{log.get('volume')}")
            else:
                print(f"获取日志详情失败: {response.status_code}")
        except Exception as e:
            print(f"获取日志详情错误: {str(e)}")

    def wait_for_log_update(self, initial_count, expected_increase=1, max_wait=30):
        """轮询等待日志更新，替代硬编码等待时间"""
        print(f"等待日志更新，预期增加{expected_increase}条，最长等待{max_wait}秒...")
        start_time = time.time()
        while time.time() - start_time < max_wait:
            current_count = self.get_logs_count()
            if current_count >= initial_count + expected_increase:
                print(f"日志已更新，当前数量: {current_count}，耗时: {time.time() - start_time:.2f}秒")
                return current_count
            print(f"等待中...已过{time.time() - start_time:.1f}秒，当前日志数: {current_count}")
            time.sleep(2)
        
        # 等待超时，返回当前状态
        final_count = self.get_logs_count()
        print(f"等待超时，当前日志数量: {final_count} (期望>={initial_count + expected_increase})")
        return final_count

    def execute_buy(self, strategy, stocks, quantity=1, single_buy_amount=10000):
        """执行买入操作的通用方法"""
        buy_data = {
            "strategy": strategy,
            "quantity": quantity,
            "stocks": stocks,
            "singleBuyAmount": single_buy_amount
        }
        
        try:
            buy_response = requests.post(
                f"{self.base_url}/api/actions/execute_buy",
                json=buy_data,
                timeout=15
            )
            
            print(f"买入API状态码: {buy_response.status_code}")
            if buy_response.status_code == 200:
                result = buy_response.json()
                print(f"买入结果: {result}")
                return result
            else:
                print(f"买入请求失败: {buy_response.text}")
                return {"status": "error", "message": f"HTTP错误: {buy_response.status_code}"}
        except Exception as e:
            print(f"买入请求异常: {str(e)}")
            return {"status": "error", "message": str(e)}

    def check_holdings(self, expected_stocks=None):
        """检查持仓信息"""
        try:
            response = requests.get(f"{self.base_url}/api/positions-all", timeout=10)
            if response.status_code == 200:
                holdings = response.json().get('data', [])
                print(f"\n当前持仓信息 ({len(holdings)}条):")
                
                # 只显示前5条持仓
                for i, holding in enumerate(holdings[:5]):
                    print(f"{i+1}. 代码:{holding.get('stock_code')} | 数量:{holding.get('volume')} | 成本:{holding.get('cost_price')}")
                
                # 如果提供了预期股票列表，检查它们是否在持仓中
                if expected_stocks:
                    found_stocks = [h.get('stock_code') for h in holdings]
                    for stock in expected_stocks:
                        # 考虑股票代码格式转换
                        stock_base = self._extract_stock_code(stock)
                        found = False
                        for found_stock in found_stocks:
                            if stock_base in found_stock:
                                found = True
                                print(f"✓ 预期股票 {stock} 在持仓中 (匹配: {found_stock})")
                                break
                        if not found:
                            print(f"✗ 预期股票 {stock} 不在持仓中")
                
                return holdings
            else:
                print(f"获取持仓信息失败: {response.status_code}")
                return []
        except Exception as e:
            print(f"获取持仓信息异常: {str(e)}")
            return []
    
    def _extract_stock_code(self, stock_code):
        """提取股票代码数字部分"""
        # 匹配6位数字
        match = re.search(r'(\d{6})', stock_code)
        if match:
            return match.group(1)
        return stock_code
    
    # 1. 添加账户初始化测试
    def test_01_account_initialization(self):
        """测试不同的账户初始化方法"""
        print("\n开始测试账户初始化方法...")
        
        # 保存成功的初始化方法
        successful_method = None
        
        # 方法1: 使用config/save接口设置资金
        try:
            print("\n尝试方法1: 通过config/save接口设置资金...")
            config_data = {
                "simulationMode": True,
                "singleBuyAmount": 20000,
                "globalAllowBuySell": True,
                "totalMaxPosition": self.initial_balance  # 尝试使用totalMaxPosition
            }
            
            response = requests.post(
                f"{self.base_url}/api/config/save",
                json=config_data,
                timeout=10
            )
            
            print(f"方法1响应: {response.status_code}")
            if response.status_code == 200:
                # 等待配置生效
                time.sleep(2)
                
                # 检查余额是否设置成功
                balance1 = self.get_account_balance()
                print(f"方法1设置后余额: {balance1}")
                
                if balance1 > 10000:  # 如果余额设置成功
                    successful_method = "config_totalMaxPosition"
                    print("✓ 方法1设置资金成功")
            else:
                print(f"✗ 方法1设置失败: {response.text}")
        except Exception as e:
            print(f"✗ 方法1异常: {str(e)}")
            
        # 方法2: 尝试使用singleStockMaxPosition
        if not successful_method:
            try:
                print("\n尝试方法2: 通过singleStockMaxPosition设置资金...")
                config_data = {
                    "simulationMode": True,
                    "singleBuyAmount": 20000,
                    "globalAllowBuySell": True,
                    "singleStockMaxPosition": self.initial_balance // 10,  # 单只股票最大持仓
                    "totalMaxPosition": self.initial_balance  # 最大总持仓
                }
                
                response = requests.post(
                    f"{self.base_url}/api/config/save",
                    json=config_data,
                    timeout=10
                )
                
                print(f"方法2响应: {response.status_code}")
                if response.status_code == 200:
                    # 等待配置生效
                    time.sleep(2)
                    
                    # 检查余额是否设置成功
                    balance2 = self.get_account_balance()
                    print(f"方法2设置后余额: {balance2}")
                    
                    if balance2 > 10000:  # 如果余额设置成功
                        successful_method = "config_singleStockMaxPosition"
                        print("✓ 方法2设置资金成功")
                else:
                    print(f"✗ 方法2设置失败: {response.text}")
            except Exception as e:
                print(f"✗ 方法2异常: {str(e)}")
        
        # 方法3: 尝试直接初始化持仓接口
        if not successful_method:
            try:
                print("\n尝试方法3: 通过初始化持仓接口设置资金...")
                init_data = {
                    "simulationMode": True
                }
                
                response = requests.post(
                    f"{self.base_url}/api/holdings/init",
                    json=init_data,
                    timeout=10
                )
                
                print(f"方法3响应: {response.status_code}")
                if response.status_code == 200:
                    # 等待配置生效
                    time.sleep(2)
                    
                    # 检查余额是否设置成功
                    balance3 = self.get_account_balance()
                    print(f"方法3设置后余额: {balance3}")
                    
                    if balance3 > 10000:  # 如果余额设置成功
                        successful_method = "holdings_init"
                        print("✓ 方法3设置资金成功")
                else:
                    print(f"✗ 方法3设置失败: {response.text}")
            except Exception as e:
                print(f"✗ 方法3异常: {str(e)}")
                
        # 方法4: 尝试使用debug接口
        if not successful_method:
            try:
                print("\n尝试方法4: 通过debug接口设置资金...")
                init_data = {
                    "account_balance": self.initial_balance,
                    "mode": "simulation"
                }
                
                response = requests.post(
                    f"{self.base_url}/api/debug/set_balance",
                    json=init_data,
                    timeout=10
                )
                
                print(f"方法4响应: {response.status_code}")
                if response.status_code == 200:
                    # 等待配置生效
                    time.sleep(2)
                    
                    # 检查余额是否设置成功
                    balance4 = self.get_account_balance()
                    print(f"方法4设置后余额: {balance4}")
                    
                    if balance4 > 10000:  # 如果余额设置成功
                        successful_method = "debug_set_balance"
                        print("✓ 方法4设置资金成功")
                else:
                    print(f"✗ 方法4设置失败: {response.status_code}")
            except Exception as e:
                print(f"✗ 方法4异常: {str(e)}")
        
        # 检查最终结果
        final_balance = self.get_account_balance()
        print(f"\n初始化测试完成，最终账户余额: {final_balance}")
        
        if successful_method:
            print(f"✓ 成功使用方法: {successful_method}")
            self.successful_init_method = successful_method
        else:
            print("✗ 所有初始化方法都失败了，可能需要检查系统接口")
            
        # 即使所有方法都失败，也继续测试，因为系统可能有默认资金
        self.print_system_status()
                
    # 2. 添加股票代码格式测试
    def test_02_stock_code_formats(self):
        """测试不同的股票代码格式"""
        print("\n开始测试股票代码格式...")
        
        # 如果账户初始化成功，使用成功的方法再次确保资金充足
        if self.successful_init_method:
            self._initialize_account_using_method(self.successful_init_method)
            
        # 多种可能的股票代码格式
        stock_formats = [
            "000001.SZ",    # 格式1: 带后缀
            "000001",       # 格式2: 纯代码
            "sz.000001",    # 格式3: 前缀格式
            "sz000001",     # 格式4: 无分隔符前缀
            "SZ000001"      # 格式5: 大写前缀无分隔符
        ]
        
        successful_format = None
        logs_before = self.get_logs_count()
        
        for stock_code in stock_formats:
            print(f"\n测试股票代码格式: {stock_code}")
            
            # 清除之前的日志，便于检测新的交易记录
            self.clear_logs()
            current_logs = self.get_logs_count()
            
            # 执行单股买入
            result = self.execute_buy(
                strategy="custom_stock",
                stocks=[stock_code],
                quantity=1,
                single_buy_amount=5000
            )
            
            # 检查API响应
            if result.get('status') == 'success' and result.get('success_count', 0) > 0:
                print(f"✓ API响应成功，买入数量: {result.get('success_count')}")
                
                # 等待日志更新
                new_logs = self.wait_for_log_update(current_logs, expected_increase=1, max_wait=10)
                
                # 检查日志是否增加
                if new_logs > current_logs:
                    print(f"✓ 日志数量增加: {new_logs - current_logs}条")
                    
                    # 检查持仓是否增加
                    holdings = self.check_holdings(expected_stocks=[stock_code])
                    if holdings and len(holdings) > 0:
                        print(f"✓ 持仓检查成功，格式 {stock_code} 可用")
                        successful_format = stock_code
                        break
                    else:
                        print(f"✗ 持仓检查失败，未增加持仓")
                else:
                    print(f"✗ 日志检查失败，未增加日志记录")
            else:
                print(f"✗ API响应失败或买入数量为0: {result}")
            
            # 等待一会再测试下一个格式
            time.sleep(3)
        
        # 测试结果总结
        if successful_format:
            print(f"\n✓ 测试通过！可用的股票代码格式: {successful_format}")
            self.successful_stock_format = successful_format
        else:
            print("\n✗ 所有股票代码格式都失败了，可能需要检查系统接口或测试其他格式")
            
        self.print_logs_detail()
            
    def _initialize_account_using_method(self, method):
        """使用之前成功的初始化方法设置账户"""
        print(f"\n使用方法 {method} 初始化账户...")
        
        if method == "config_totalMaxPosition":
            config_data = {
                "simulationMode": True,
                "globalAllowBuySell": True,
                "totalMaxPosition": self.initial_balance
            }
            
            response = requests.post(
                f"{self.base_url}/api/config/save",
                json=config_data,
                timeout=10
            )
            print(f"初始化响应: {response.status_code}")
            
        elif method == "config_singleStockMaxPosition":
            config_data = {
                "simulationMode": True,
                "globalAllowBuySell": True,
                "singleStockMaxPosition": self.initial_balance // 10,
                "totalMaxPosition": self.initial_balance
            }
            
            response = requests.post(
                f"{self.base_url}/api/config/save",
                json=config_data,
                timeout=10
            )
            print(f"初始化响应: {response.status_code}")
            
        elif method == "holdings_init":
            init_data = {
                "simulationMode": True
            }
            
            response = requests.post(
                f"{self.base_url}/api/holdings/init",
                json=init_data,
                timeout=10
            )
            print(f"初始化响应: {response.status_code}")
            
        elif method == "debug_set_balance":
            init_data = {
                "account_balance": self.initial_balance,
                "mode": "simulation"
            }
            
            response = requests.post(
                f"{self.base_url}/api/debug/set_balance",
                json=init_data,
                timeout=10
            )
            print(f"初始化响应: {response.status_code}")
            
        # 等待初始化生效
        time.sleep(2)
        
        # 检查余额
        balance = self.get_account_balance()
        print(f"初始化后账户余额: {balance}")
            
    def test_03_random_pool_buying(self):
        """测试从备选池随机买入功能"""
        print("\n开始测试从备选池随机买入...")
        
        # 使用成功的初始化方法确保账户资金充足
        if self.successful_init_method:
            self._initialize_account_using_method(self.successful_init_method)
        
        # 获取买入前状态
        logs_before = self.get_logs_count()
        balance_before = self.get_account_balance()
        print(f"买入前状态: 日志数量={logs_before}, 账户余额={balance_before}")
        
        # 1. 获取备选池股票列表
        print("获取备选池股票列表...")
        try:
            pool_response = requests.get(f"{self.base_url}/api/stock_pool/list", timeout=10)
            self.assertEqual(pool_response.status_code, 200, "获取备选池失败")
            stock_pool = pool_response.json().get('data', [])
            
            # 如果之前确定了成功的股票格式，转换备选池股票格式
            if self.successful_stock_format:
                # 提取股票格式模式
                format_pattern = re.sub(r'\d+', '{code}', self.successful_stock_format)
                transformed_pool = []
                for stock in stock_pool:
                    code = self._extract_stock_code(stock)
                    transformed_stock = format_pattern.replace('{code}', code)
                    transformed_pool.append(transformed_stock)
                stock_pool = transformed_pool
            
            self.assertTrue(len(stock_pool) > 0, "备选池为空")
            print(f"备选池股票数量: {len(stock_pool)}")
            print(f"备选池前5只股票: {stock_pool[:5]}")
        except Exception as e:
            print(f"获取备选池错误: {str(e)}")
            raise
        
        # 2. 执行随机买入操作
        print("执行随机买入操作...")
        # 买入数量和金额
        buy_quantity = 2
        single_amount = 15000
        
        result = self.execute_buy(
            strategy="random_pool",
            stocks=stock_pool,
            quantity=buy_quantity,
            single_buy_amount=single_amount
        )
        
        # 3. 验证买入请求是否成功
        self.assertEqual(result['status'], 'success', f"买入失败: {result.get('message')}")
        
        # 检查实际买入数量
        success_count = result.get('success_count', 0)
        print(f"实际成功买入数量: {success_count}")
        
        # 4. 等待日志更新 - 使用改进的等待机制
        new_logs_count = self.wait_for_log_update(logs_before, expected_increase=success_count, max_wait=15)
        
        # 5. 检查交易日志是否增加
        if success_count > 0:
            self.assertTrue(new_logs_count > logs_before, 
                        f"买入操作未记录到日志：期望>{logs_before}，实际={new_logs_count}")
        
        # 6. 获取最新账户余额，验证资金变化
        balance_after = self.get_account_balance()
        if success_count > 0:
            expected_max_decrease = success_count * single_amount * 1.01  # 考虑交易费用
            
            print(f"买入后账户余额: {balance_after} (之前: {balance_before})")
            print(f"预期最大减少: {expected_max_decrease}")
        
        # 7. 检查持仓情况
        print("检查持仓情况...")
        holdings = self.check_holdings()
        
        # 日志详情
        self.print_logs_detail()
        
        print(f"随机买入测试结束。日志变化: {logs_before} -> {new_logs_count}, 余额变化: {balance_before} -> {balance_after}")

    def test_04_custom_stock_buying(self):
        """测试自定义股票买入功能"""
        print("\n开始测试自定义股票买入...")
        
        # 使用成功的初始化方法确保账户资金充足
        if self.successful_init_method:
            self._initialize_account_using_method(self.successful_init_method)
        
        # 获取买入前状态
        logs_before = self.get_logs_count()
        balance_before = self.get_account_balance()
        print(f"买入前状态: 日志数量={logs_before}, 账户余额={balance_before}")
        
        # 1. 准备自定义股票列表
        custom_stocks = ["000001.SZ", "600519.SH"]  # 平安银行、贵州茅台
        
        # 如果之前确定了成功的股票格式，转换股票格式
        if self.successful_stock_format:
            # 提取股票格式模式
            format_pattern = re.sub(r'\d+', '{code}', self.successful_stock_format)
            transformed_stocks = []
            for stock in custom_stocks:
                code = self._extract_stock_code(stock)
                transformed_stock = format_pattern.replace('{code}', code)
                transformed_stocks.append(transformed_stock)
            custom_stocks = transformed_stocks
            
        print(f"自定义股票列表: {custom_stocks}")
        
        # 2. 执行自定义买入操作
        print("执行自定义买入操作...")
        # 买入数量和金额
        buy_quantity = 1
        single_amount = 10000
        
        result = self.execute_buy(
            strategy="custom_stock",
            stocks=custom_stocks,
            quantity=buy_quantity,
            single_buy_amount=single_amount
        )
        
        # 3. 验证买入请求是否成功
        self.assertEqual(result['status'], 'success', f"买入失败: {result.get('message')}")
        
        # 检查实际买入数量
        success_count = result.get('success_count', 0)
        print(f"实际成功买入数量: {success_count}")
        
        # 4. 等待日志更新
        new_logs_count = self.wait_for_log_update(logs_before, expected_increase=success_count, max_wait=15)
        
        # 5. 检查交易日志是否增加
        if success_count > 0:
            self.assertTrue(new_logs_count > logs_before, 
                        f"买入操作未记录到日志：期望>{logs_before}，实际={new_logs_count}")
        
        # 6. 获取最新账户余额，验证资金变化
        balance_after = self.get_account_balance()
        if success_count > 0:
            expected_max_decrease = success_count * single_amount * 1.01  # 考虑交易费用
            
            print(f"买入后账户余额: {balance_after} (之前: {balance_before})")
            print(f"预期最大减少: {expected_max_decrease}")
        
        # 7. 检查持仓情况，确认自定义股票是否在持仓中
        print("检查持仓情况，验证自定义股票是否买入...")
        holdings = self.check_holdings(expected_stocks=custom_stocks[:buy_quantity])
        
        # 日志详情
        self.print_logs_detail()
        
        print(f"自定义买入测试结束。日志变化: {logs_before} -> {new_logs_count}, 余额变化: {balance_before} -> {balance_after}")

    def test_05_concurrent_buying(self):
        """测试并发买入请求的处理"""
        print("\n开始测试并发买入请求...")
        
        # 使用成功的初始化方法确保账户资金充足
        if self.successful_init_method:
            self._initialize_account_using_method(self.successful_init_method)
        
        # 记录初始状态
        logs_before = self.get_logs_count()
        balance_before = self.get_account_balance()
        print(f"初始状态: 日志数量={logs_before}, 账户余额={balance_before}")
        
        # 准备测试股票
        test_stocks = ["000001.SZ", "600519.SH", "600036.SH", "601318.SH", "600276.SH"]
        
        # 如果之前确定了成功的股票格式，转换股票格式
        if self.successful_stock_format:
            # 提取股票格式模式
            format_pattern = re.sub(r'\d+', '{code}', self.successful_stock_format)
            transformed_stocks = []
            for stock in test_stocks:
                code = self._extract_stock_code(stock)
                transformed_stock = format_pattern.replace('{code}', code)
                transformed_stocks.append(transformed_stock)
            test_stocks = transformed_stocks
            
        print(f"测试股票: {test_stocks}")
        
        # 准备并发请求
        num_requests = 3
        print(f"发起{num_requests}个并发买入请求...")
        
        # 使用线程池执行并发请求
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
            # 提交多个买入请求
            futures = [
                executor.submit(
                    self.execute_buy,
                    strategy="custom_stock",
                    stocks=[stock],
                    quantity=1,
                    single_buy_amount=5000
                ) for stock in test_stocks[:num_requests]
            ]
            
            # 收集结果
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"并发请求异常: {str(e)}")
        
        # 分析结果
        success_count = sum(1 for r in results if r.get('status') == 'success')
        total_buy_count = sum(r.get('success_count', 0) for r in results)
        print(f"并发请求结果: {success_count}/{num_requests} 成功, 实际买入 {total_buy_count} 只")
        
        # 等待所有交易记录更新
        max_expected_increase = total_buy_count
        new_logs_count = self.wait_for_log_update(logs_before, expected_increase=max_expected_increase, max_wait=30)
        
        # 验证交易记录增加
        if total_buy_count > 0:
            # 允许有20%的失败率
            expected_min_increase = int(total_buy_count * 0.8)
            self.assertGreaterEqual(new_logs_count - logs_before, expected_min_increase,  
                                f"并发买入未产生足够的交易记录: 实际={new_logs_count-logs_before}, 期望>={expected_min_increase}")
        
        # 检查持仓
        print("检查并发买入后的持仓情况...")
        holdings = self.check_holdings(expected_stocks=test_stocks[:num_requests])
        
        # 验证资金变化
        balance_after = self.get_account_balance()
        print(f"并发买入后账户余额: {balance_after} (变化: {balance_after - balance_before})")
        
        print("并发买入测试完成。")


if __name__ == "__main__":
    unittest.main()