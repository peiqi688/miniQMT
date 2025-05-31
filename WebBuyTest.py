#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMT交易系统Web API测试脚本
测试实时数据相关接口
"""

import requests
import json
import time
import sys
from datetime import datetime

class QMTAPITester:
    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def test_connection(self):
        """测试API连接状态"""
        print("=" * 60)
        print("1. 测试API连接状态")
        print("-" * 60)
        
        try:
            response = self.session.get(f"{self.base_url}/api/connection/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ API连接成功")
                print(f"   状态: {data.get('status')}")
                print(f"   已连接: {data.get('connected')}")
                print(f"   时间戳: {data.get('timestamp')}")
                return True
            else:
                print(f"❌ API连接失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ API连接异常: {str(e)}")
            return False
    
    def test_data_sources_status(self):
        """测试数据源状态接口"""
        print("\n" + "=" * 60)
        print("2. 测试数据源状态")
        print("-" * 60)
        
        try:
            response = self.session.get(f"{self.base_url}/api/data_sources/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 数据源状态获取成功")
                
                if 'data' in data:
                    for source in data['data']:
                        status_icon = "🟢" if source.get('is_healthy') else "🔴"
                        current_icon = "👈" if source.get('is_current') else ""
                        print(f"   {status_icon} {source.get('name', 'Unknown')} - "
                              f"错误次数: {source.get('error_count', 0)} "
                              f"{current_icon}")
                
                return data
            else:
                print(f"❌ 获取数据源状态失败: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ 数据源状态接口异常: {str(e)}")
            return None
    
    def test_realtime_quote(self, stock_codes=["000001", "600036", "600519"]):
        """测试实时行情接口"""
        print("\n" + "=" * 60)
        print("3. 测试实时行情接口")
        print("-" * 60)
        
        results = {}
        
        for stock_code in stock_codes:
            print(f"\n📈 测试股票: {stock_code}")
            try:
                start_time = time.time()
                response = self.session.get(
                    f"{self.base_url}/api/realtime/quote/{stock_code}", 
                    timeout=10
                )
                end_time = time.time()
                response_time = round((end_time - start_time) * 1000, 2)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        quote_data = data.get('data', {})
                        print(f"   ✅ 获取成功 (响应时间: {response_time}ms)")
                        print(f"      最新价: {quote_data.get('lastPrice', 'N/A')}")
                        print(f"      成交量: {quote_data.get('volume', 'N/A')}")
                        print(f"      数据源: {quote_data.get('source', 'N/A')}")
                        print(f"      时间戳: {quote_data.get('timestamp', 'N/A')}")
                        
                        results[stock_code] = {
                            'success': True,
                            'data': quote_data,
                            'response_time': response_time
                        }
                    else:
                        print(f"   ❌ 数据获取失败: {data.get('message', 'Unknown error')}")
                        results[stock_code] = {'success': False, 'error': data.get('message')}
                else:
                    print(f"   ❌ HTTP错误: {response.status_code}")
                    results[stock_code] = {'success': False, 'error': f"HTTP {response.status_code}"}
                    
            except Exception as e:
                print(f"   ❌ 请求异常: {str(e)}")
                results[stock_code] = {'success': False, 'error': str(e)}
        
        return results
    
    def test_all_sources(self, stock_code="000001"):
        """测试所有数据源接口"""
        print("\n" + "=" * 60)
        print("4. 测试所有数据源")
        print("-" * 60)
        print(f"📊 测试股票: {stock_code}")
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/realtime/test/{stock_code}", 
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    print(f"✅ 所有数据源测试完成")
                    
                    results = data.get('results', {})
                    for source_name, result in results.items():
                        if result.get('success'):
                            print(f"   🟢 {source_name}:")
                            print(f"      响应时间: {result.get('response_time_ms', 'N/A')}ms")
                            print(f"      最新价: {result.get('data', {}).get('lastPrice', 'N/A')}")
                            print(f"      错误次数: {result.get('error_count', 0)}")
                        else:
                            print(f"   🔴 {source_name}:")
                            print(f"      错误: {result.get('error', 'Unknown')}")
                            print(f"      响应时间: {result.get('response_time_ms', 'N/A')}ms")
                    
                    return results
                else:
                    print(f"❌ 测试失败: {data.get('message', 'Unknown error')}")
            else:
                print(f"❌ HTTP错误: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 测试异常: {str(e)}")
        
        return None
    
    def test_switch_data_source(self, target_source="Mootdx"):  # 改为正确的名称
        """测试数据源切换接口"""
        print("\n" + "=" * 60)
        print("5. 测试数据源切换")
        print("-" * 60)
        print(f"🔄 尝试切换到: {target_source}")
        
        try:
            payload = {"source_name": target_source}
            response = self.session.post(
                f"{self.base_url}/api/data_sources/switch",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    print(f"✅ 数据源切换成功")
                    print(f"   当前数据源: {data.get('current_source')}")
                    print(f"   消息: {data.get('message')}")
                    
                    # 等待一下再检查状态
                    time.sleep(1)
                    self.test_data_sources_status()
                    return True
                else:
                    print(f"❌ 切换失败: {data.get('message')}")
            else:
                print(f"❌ HTTP错误: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   错误详情: {error_data.get('message', 'Unknown error')}")
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ 切换异常: {str(e)}")
        
        return False
    
    def test_system_status(self):
        """测试系统状态接口"""
        print("\n" + "=" * 60)
        print("6. 测试系统状态")
        print("-" * 60)
        
        try:
            response = self.session.get(f"{self.base_url}/api/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 系统状态获取成功")
                
                # 显示关键信息
                account = data.get('account', {})
                settings = data.get('settings', {})
                
                print(f"   监控状态: {'🟢 运行中' if data.get('isMonitoring') else '🔴 未运行'}")
                print(f"   账户ID: {account.get('id', 'N/A')}")
                print(f"   可用余额: {account.get('availableBalance', 'N/A')}")
                print(f"   总资产: {account.get('totalAssets', 'N/A')}")
                print(f"   自动交易: {'✅ 启用' if settings.get('enableAutoTrading') else '❌ 禁用'}")
                print(f"   模拟模式: {'✅ 启用' if settings.get('simulationMode') else '❌ 禁用'}")
                
                return data
            else:
                print(f"❌ 获取系统状态失败: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ 系统状态接口异常: {str(e)}")
        
        return None
    
    def performance_test(self, stock_code="000001", iterations=10):
        """性能测试"""
        print("\n" + "=" * 60)
        print("7. 性能测试")
        print("-" * 60)
        print(f"📊 测试股票: {stock_code}, 测试次数: {iterations}")
        
        response_times = []
        success_count = 0
        
        for i in range(iterations):
            try:
                start_time = time.time()
                response = self.session.get(
                    f"{self.base_url}/api/realtime/quote/{stock_code}",
                    timeout=10
                )
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        success_count += 1
                        response_times.append(response_time)
                        print(f"   第{i+1}次: ✅ {response_time:.2f}ms")
                    else:
                        print(f"   第{i+1}次: ❌ 数据获取失败")
                else:
                    print(f"   第{i+1}次: ❌ HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"   第{i+1}次: ❌ 异常: {str(e)}")
            
            # 避免请求过于频繁
            time.sleep(0.5)
        
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
            
            print(f"\n📈 性能统计:")
            print(f"   成功率: {success_count}/{iterations} ({success_count/iterations*100:.1f}%)")
            print(f"   平均响应时间: {avg_time:.2f}ms")
            print(f"   最快响应时间: {min_time:.2f}ms")
            print(f"   最慢响应时间: {max_time:.2f}ms")
        else:
            print("❌ 没有成功的请求用于统计")

    def test_data_consistency(self, stock_codes=["000001", "600036"]):
        """测试数据一致性"""
        print("\n" + "=" * 60)
        print("8. 测试数据一致性")
        print("-" * 60)
        
        for stock_code in stock_codes:
            print(f"\n📊 检查股票: {stock_code}")
            
            try:
                # 获取所有数据源的数据
                response = self.session.get(
                    f"{self.base_url}/api/realtime/test/{stock_code}",
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        results = data.get('results', {})
                        prices = {}
                        
                        for source_name, result in results.items():
                            if result.get('success'):
                                price = result.get('data', {}).get('lastPrice')
                                if price:
                                    prices[source_name] = float(price)
                        
                        if len(prices) > 1:
                            price_values = list(prices.values())
                            max_price = max(price_values)
                            min_price = min(price_values)
                            
                            if max_price > 0:
                                diff_percent = (max_price - min_price) / max_price * 100
                                
                                print(f"   价格对比:")
                                for source, price in prices.items():
                                    print(f"     {source}: {price}")
                                
                                if diff_percent > 5:
                                    print(f"   ⚠️  价格差异: {diff_percent:.2f}% (超过5%阈值)")
                                else:
                                    print(f"   ✅ 价格差异: {diff_percent:.2f}% (正常)")
                        else:
                            print("   ℹ️  只有一个数据源返回数据")
                            
            except Exception as e:
                print(f"   ❌ 检查异常: {str(e)}")

    def run_all_tests(self):
        """运行所有测试"""
        print(f"🚀 QMT交易系统API测试开始")
        print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. 连接测试
        if not self.test_connection():
            print("\n❌ API连接失败，终止测试")
            return
        
        # 2. 数据源状态
        self.test_data_sources_status()
        
        # 3. 实时行情测试
        self.test_realtime_quote()
        
        # 4. 所有数据源测试
        self.test_all_sources()
        
        # 5. 数据源切换测试
        self.test_switch_data_source("MootdxSource")
        
        # 6. 系统状态
        self.test_system_status()
        
        # 7. 性能测试
        self.performance_test()

        # 8. 数据一致性测试
        self.test_data_consistency()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试完成")
        print("=" * 60)




def main():
    """主函数"""
    # 可以通过命令行参数指定服务器地址
    base_url = "http://127.0.0.1:5000"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    print(f"🔧 测试目标: {base_url}")
    
    tester = QMTAPITester(base_url)
    tester.run_all_tests()

if __name__ == "__main__":
    main()