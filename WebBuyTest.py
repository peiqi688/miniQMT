#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web API 实时数据源完整性测试脚本
通过调用系统Web API接口测试各数据源的数据质量和完整性
"""

import requests
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('web_api_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WebAPIDataSourceTester:
    """Web API数据源测试器"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:5000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 10
        
        # 测试股票池
        self.test_stocks = [
            "000001.SZ",  # 平安银行
            "000002.SZ",  # 万科A
            "600000.SH",  # 浦发银行
            "600036.SH",  # 招商银行
            "600519.SH",  # 贵州茅台
            "000858.SZ",  # 五粮液
            "002415.SZ",  # 海康威视
            "000166.SZ",  # 申万宏源
        ]
        
        # 数据完整性检查规则
        self.data_integrity_rules = {
            'required_fields': [
                'lastPrice', 'volume', 'amount', 'high', 'low', 'open'
            ],
            'optional_fields': [
                'lastClose', 'change', 'changePercent', 'bidPrice', 'askPrice',
                'bidVol', 'askVol', 'timestamp', 'source'
            ],
            'price_range_check': True,
            'volume_check': True,
            'logical_check': True
        }
        
        self.test_results = {}
    
    def make_request(self, endpoint: str, method: str = 'GET', data: Dict = None) -> Tuple[bool, Dict]:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            response.raise_for_status()
            return True, response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败 {url}: {str(e)}")
            return False, {'error': str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败 {url}: {str(e)}")
            return False, {'error': f'JSON解析失败: {str(e)}'}

    def check_system_status(self) -> Dict:
        """检查系统状态"""
        logger.info("🔍 检查系统状态...")
        
        status_checks = {
            'api_connection': {'endpoint': '/api/connection/status', 'required': True},
            'system_status': {'endpoint': '/api/status', 'required': True},
            'data_sources_status': {'endpoint': '/api/data_sources/status', 'required': False}
        }
        
        results = {}
        
        for check_name, check_config in status_checks.items():
            success, response = self.make_request(check_config['endpoint'])
            
            results[check_name] = {
                'success': success,
                'response': response,
                'critical': check_config['required'],
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if success:
                logger.info(f"✅ {check_name}: 正常")
            else:
                level = logger.error if check_config['required'] else logger.warning
                level(f"❌ {check_name}: 失败 - {response.get('error', '未知错误')}")
        
        return results

    def test_single_stock_all_sources(self, stock_code: str) -> Dict:
        """测试单只股票的所有数据源"""
        logger.info(f"📊 测试股票 {stock_code} 的所有数据源...")
        
        # 调用API测试所有数据源
        success, response = self.make_request(f'/api/realtime/test/{stock_code}')
        
        if not success:
            logger.error(f"❌ 无法获取 {stock_code} 的测试结果")
            return {
                'stock_code': stock_code,
                'success': False,
                'error': response.get('error', '未知错误'),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        # 处理测试结果
        test_result = {
            'stock_code': stock_code,
            'success': True,
            'test_time': response.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            'sources': {},
            'data_quality_summary': {}
        }
        
        # 分析每个数据源的结果
        source_results = response.get('results', {})
        
        for source_name, source_data in source_results.items():
            # 数据完整性检查
            integrity_score = self._check_data_integrity(source_data.get('data', {}))
            
            # 数据一致性检查
            consistency_score = self._check_data_consistency(source_data.get('data', {}))
            
            # 综合评分
            overall_score = self._calculate_overall_score(source_data, integrity_score, consistency_score)
            
            test_result['sources'][source_name] = {
                'success': source_data.get('success', False),
                'response_time_ms': source_data.get('response_time_ms', 0),
                'error_count': source_data.get('error_count', 0),
                'is_healthy': source_data.get('is_healthy', False),
                'data': source_data.get('data', {}),
                'error': source_data.get('error', ''),
                'integrity_score': integrity_score,
                'consistency_score': consistency_score,
                'overall_score': overall_score
            }
        
        # 生成数据质量汇总
        test_result['data_quality_summary'] = self._generate_quality_summary(test_result['sources'])
        
        return test_result

    def _check_data_integrity(self, data: Dict) -> Dict:
        """检查数据完整性"""
        if not data:
            return {
                'score': 0,
                'details': {'error': '无数据'},
                'issues': ['无数据']
            }
        
        score = 0
        max_score = 100
        issues = []
        details = {}
        
        # 1. 必需字段检查 (40分)
        required_fields = self.data_integrity_rules['required_fields']
        field_score = 0
        missing_fields = []
        
        for field in required_fields:
            if field in data and data[field] is not None:
                try:
                    value = float(data[field])
                    if value >= 0:  # 价格、成交量等应该非负
                        field_score += 40 / len(required_fields)
                    else:
                        issues.append(f"{field}值为负数: {value}")
                except (ValueError, TypeError):
                    issues.append(f"{field}不是有效数值: {data[field]}")
            else:
                missing_fields.append(field)
        
        if missing_fields:
            issues.append(f"缺少必需字段: {missing_fields}")
        
        details['required_fields_score'] = field_score
        score += field_score
        
        # 2. 价格逻辑检查 (30分)
        price_logic_score = 0
        try:
            last_price = float(data.get('lastPrice', 0))
            high = float(data.get('high', 0))
            low = float(data.get('low', 0))
            open_price = float(data.get('open', 0))
            
            if last_price > 0 and high > 0 and low > 0:
                if low <= last_price <= high:
                    price_logic_score += 15
                else:
                    issues.append(f"价格逻辑错误: low({low}) <= lastPrice({last_price}) <= high({high})")
                
                if low <= open_price <= high:
                    price_logic_score += 15
                else:
                    issues.append(f"开盘价逻辑错误: low({low}) <= open({open_price}) <= high({high})")
        except (ValueError, TypeError) as e:
            issues.append(f"价格数据类型错误: {str(e)}")
        
        details['price_logic_score'] = price_logic_score
        score += price_logic_score
        
        # 3. 成交量检查 (15分)
        volume_score = 0
        try:
            volume = float(data.get('volume', 0))
            amount = float(data.get('amount', 0))
            
            if volume >= 0:
                volume_score += 7.5
            else:
                issues.append(f"成交量为负: {volume}")
            
            if amount >= 0:
                volume_score += 7.5
            else:
                issues.append(f"成交额为负: {amount}")
        except (ValueError, TypeError) as e:
            issues.append(f"成交量数据类型错误: {str(e)}")
        
        details['volume_score'] = volume_score
        score += volume_score
        
        # 4. 时间戳检查 (15分)
        timestamp_score = 0
        if 'timestamp' in data and data['timestamp']:
            try:
                # 检查时间戳格式
                if isinstance(data['timestamp'], str):
                    datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S')
                    timestamp_score = 15
                elif isinstance(data['timestamp'], (int, float)):
                    # Unix时间戳
                    timestamp_score = 15
            except ValueError:
                issues.append(f"时间戳格式错误: {data['timestamp']}")
        else:
            issues.append("缺少时间戳")
        
        details['timestamp_score'] = timestamp_score
        score += timestamp_score
        
        return {
            'score': min(score, max_score),
            'details': details,
            'issues': issues
        }

    def _check_data_consistency(self, data: Dict) -> Dict:
        """检查数据一致性"""
        if not data:
            return {
                'score': 0,
                'details': {'error': '无数据'},
                'issues': ['无数据']
            }
        
        score = 0
        max_score = 100
        issues = []
        details = {}
        
        try:
            # 1. 价格变化合理性 (40分)
            last_price = float(data.get('lastPrice', 0))
            last_close = float(data.get('lastClose', 0))
            change = data.get('change', 0)
            change_percent = data.get('changePercent', 0)
            
            if last_close > 0 and last_price > 0:
                # 计算理论涨跌额和涨跌幅
                expected_change = last_price - last_close
                expected_change_percent = (expected_change / last_close) * 100
                
                # 检查涨跌额一致性
                if change is not None:
                    change_diff = abs(float(change) - expected_change)
                    if change_diff < 0.01:  # 容忍0.01的误差
                        score += 20
                    else:
                        issues.append(f"涨跌额不一致: 给定{change}, 计算{expected_change:.2f}")
                
                # 检查涨跌幅一致性
                if change_percent is not None:
                    percent_diff = abs(float(change_percent) - expected_change_percent)
                    if percent_diff < 0.01:  # 容忍0.01%的误差
                        score += 20
                    else:
                        issues.append(f"涨跌幅不一致: 给定{change_percent}%, 计算{expected_change_percent:.2f}%")
            
            # 2. 买卖价格合理性 (30分)
            bid_prices = data.get('bidPrice', [])
            ask_prices = data.get('askPrice', [])
            
            if bid_prices and ask_prices:
                try:
                    max_bid = max([float(p) for p in bid_prices if p > 0])
                    min_ask = min([float(p) for p in ask_prices if p > 0])
                    
                    if max_bid <= min_ask:
                        score += 15
                    else:
                        issues.append(f"买卖价格倒挂: 最高买价{max_bid} > 最低卖价{min_ask}")
                    
                    # 检查价格是否在合理范围内
                    if last_price > 0:
                        if max_bid <= last_price <= min_ask or abs(last_price - max_bid) / last_price < 0.1:
                            score += 15
                        else:
                            issues.append(f"最新价格偏离买卖价过远: lastPrice={last_price}, bid={max_bid}, ask={min_ask}")
                except (ValueError, TypeError) as e:
                    issues.append(f"买卖价格数据错误: {str(e)}")
            
            # 3. 成交量与成交额一致性 (30分)
            volume = float(data.get('volume', 0))
            amount = float(data.get('amount', 0))
            
            if volume > 0 and amount > 0 and last_price > 0:
                # 估算平均成交价
                avg_price = amount / volume
                price_deviation = abs(avg_price - last_price) / last_price
                
                if price_deviation < 0.1:  # 10%以内的偏差认为合理
                    score += 30
                else:
                    issues.append(f"成交均价偏离过大: 均价{avg_price:.2f}, 最新价{last_price:.2f}")
            
        except (ValueError, TypeError, ZeroDivisionError) as e:
            issues.append(f"数据一致性检查错误: {str(e)}")
        
        details['final_score'] = score
        
        return {
            'score': min(score, max_score),
            'details': details,
            'issues': issues
        }

    def _calculate_overall_score(self, source_data: Dict, integrity_result: Dict, consistency_result: Dict) -> Dict:
        """计算综合评分"""
        # 权重设置
        weights = {
            'success': 0.3,       # 接口成功率
            'performance': 0.2,   # 响应性能
            'integrity': 0.3,     # 数据完整性
            'consistency': 0.2    # 数据一致性
        }
        
        # 成功率评分
        success_score = 100 if source_data.get('success', False) else 0
        
        # 性能评分 (响应时间)
        response_time = source_data.get('response_time_ms', 999999)
        if response_time < 100:
            performance_score = 100
        elif response_time < 500:
            performance_score = 90
        elif response_time < 1000:
            performance_score = 80
        elif response_time < 2000:
            performance_score = 60
        elif response_time < 5000:
            performance_score = 40
        else:
            performance_score = 20
        
        # 完整性和一致性评分
        integrity_score = integrity_result.get('score', 0)
        consistency_score = consistency_result.get('score', 0)
        
        # 计算加权总分
        overall_score = (
            success_score * weights['success'] +
            performance_score * weights['performance'] +
            integrity_score * weights['integrity'] +
            consistency_score * weights['consistency']
        )
        
        # 等级评定
        if overall_score >= 90:
            grade = 'A'
            description = '优秀'
        elif overall_score >= 80:
            grade = 'B'
            description = '良好'
        elif overall_score >= 70:
            grade = 'C'
            description = '一般'
        elif overall_score >= 60:
            grade = 'D'
            description = '较差'
        else:
            grade = 'F'
            description = '失败'
        
        return {
            'overall_score': round(overall_score, 2),
            'grade': grade,
            'description': description,
            'component_scores': {
                'success': success_score,
                'performance': performance_score,
                'integrity': integrity_score,
                'consistency': consistency_score
            },
            'weights': weights
        }

    def _generate_quality_summary(self, sources_results: Dict) -> Dict:
        """生成数据质量汇总"""
        summary = {
            'total_sources': len(sources_results),
            'successful_sources': 0,
            'average_response_time': 0,
            'best_source': None,
            'worst_source': None,
            'source_rankings': []
        }
        
        if not sources_results:
            return summary
        
        response_times = []
        source_scores = []
        
        for source_name, result in sources_results.items():
            if result.get('success', False):
                summary['successful_sources'] += 1
                response_times.append(result.get('response_time_ms', 0))
            
            overall_score = result.get('overall_score', {}).get('overall_score', 0)
            source_scores.append({
                'source': source_name,
                'score': overall_score,
                'grade': result.get('overall_score', {}).get('grade', 'F')
            })
        
        # 计算平均响应时间
        if response_times:
            summary['average_response_time'] = round(statistics.mean(response_times), 2)
        
        # 排序并找出最佳和最差数据源
        source_scores.sort(key=lambda x: x['score'], reverse=True)
        summary['source_rankings'] = source_scores
        
        if source_scores:
            summary['best_source'] = source_scores[0]
            summary['worst_source'] = source_scores[-1]
        
        return summary

    def test_data_source_switching(self) -> Dict:
        """测试数据源切换功能"""
        logger.info("🔄 测试数据源切换功能...")
        
        # 获取当前数据源状态
        success, status_response = self.make_request('/api/data_sources/status')
        if not success:
            return {
                'success': False,
                'error': '无法获取数据源状态',
                'details': status_response
            }
        
        switch_results = {
            'success': True,
            'original_status': status_response,
            'switch_tests': [],
            'restoration_success': False
        }
        
        # 获取可用的数据源列表
        available_sources = []
        current_source = None
        
        if 'data' in status_response:
            for source_name, source_info in status_response['data'].items():
                available_sources.append(source_name)
                if source_info.get('is_current', False):
                    current_source = source_name
        
        # 测试切换到每个数据源
        for source_name in available_sources:
            if source_name == current_source:
                continue  # 跳过当前数据源
            
            logger.info(f"切换到数据源: {source_name}")
            
            switch_success, switch_response = self.make_request(
                '/api/data_sources/switch',
                'POST',
                {'source_name': source_name}
            )
            
            switch_test = {
                'target_source': source_name,
                'switch_success': switch_success,
                'switch_response': switch_response,
                'verification_success': False,
                'test_data_quality': {}
            }
            
            if switch_success:
                # 验证切换是否成功
                time.sleep(1)  # 等待切换生效
                
                # 测试数据获取
                test_stock = self.test_stocks[0]
                quote_success, quote_response = self.make_request(f'/api/realtime/quote/{test_stock}')
                
                if quote_success and quote_response.get('status') == 'success':
                    switch_test['verification_success'] = True
                    switch_test['test_data_quality'] = self._check_data_integrity(
                        quote_response.get('data', {})
                    )
                else:
                    switch_test['verification_error'] = quote_response.get('message', '数据获取失败')
            
            switch_results['switch_tests'].append(switch_test)
        
        # 恢复到原始数据源
        if current_source:
            restore_success, restore_response = self.make_request(
                '/api/data_sources/switch',
                'POST',
                {'source_name': current_source}
            )
            switch_results['restoration_success'] = restore_success
            switch_results['restore_response'] = restore_response
        
        return switch_results

    def run_comprehensive_test(self) -> Dict:
        """运行综合测试"""
        logger.info("=" * 80)
        logger.info("🚀 开始Web API实时数据源完整性测试")
        logger.info("=" * 80)
        
        test_start_time = datetime.now()
        
        comprehensive_results = {
            'test_info': {
                'start_time': test_start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'base_url': self.base_url,
                'test_stocks': self.test_stocks,
                'test_type': 'Web API Integration Test'
            },
            'system_status': {},
            'stock_tests': {},
            'switch_test': {},
            'summary': {},
            'recommendations': []
        }
        
        # 1. 系统状态检查
        comprehensive_results['system_status'] = self.check_system_status()
        
        # 检查关键系统是否可用
        critical_failures = [
            check for check, result in comprehensive_results['system_status'].items()
            if result['critical'] and not result['success']
        ]
        
        if critical_failures:
            logger.error(f"❌ 关键系统检查失败: {critical_failures}")
            comprehensive_results['summary'] = {
                'overall_success': False,
                'critical_failures': critical_failures,
                'message': '系统状态检查失败，无法继续测试'
            }
            return comprehensive_results
        
        # 2. 股票数据测试
        logger.info(f"📈 开始测试 {len(self.test_stocks)} 只股票...")
        
        # 并行测试多只股票
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_stock = {
                executor.submit(self.test_single_stock_all_sources, stock): stock 
                for stock in self.test_stocks
            }
            
            for future in as_completed(future_to_stock):
                stock_code = future_to_stock[future]
                try:
                    result = future.result()
                    comprehensive_results['stock_tests'][stock_code] = result
                except Exception as e:
                    logger.error(f"❌ 测试股票 {stock_code} 时发生异常: {str(e)}")
                    comprehensive_results['stock_tests'][stock_code] = {
                        'success': False,
                        'error': str(e)
                    }
        
        # 3. 数据源切换测试
        comprehensive_results['switch_test'] = self.test_data_source_switching()
        
        # 4. 生成综合分析
        comprehensive_results['summary'] = self._generate_comprehensive_summary(comprehensive_results)
        
        # 5. 生成改进建议
        comprehensive_results['recommendations'] = self._generate_recommendations(comprehensive_results)
        
        test_end_time = datetime.now()
        comprehensive_results['test_info']['end_time'] = test_end_time.strftime('%Y-%m-%d %H:%M:%S')
        comprehensive_results['test_info']['duration_seconds'] = (test_end_time - test_start_time).total_seconds()
        
        logger.info("✅ 综合测试完成！")
        
        return comprehensive_results

    def _generate_comprehensive_summary(self, results: Dict) -> Dict:
        """生成综合测试汇总"""
        summary = {
            'overall_success': True,
            'system_health': {},
            'data_source_performance': {},
            'data_quality_overview': {},
            'key_findings': []
        }
        
        # 系统健康状况
        system_checks = results.get('system_status', {})
        system_health = {
            'total_checks': len(system_checks),
            'passed_checks': sum(1 for check in system_checks.values() if check['success']),
            'critical_failures': [
                name for name, check in system_checks.items()
                if check['critical'] and not check['success']
            ]
        }
        system_health['health_score'] = (system_health['passed_checks'] / system_health['total_checks']) * 100 if system_health['total_checks'] > 0 else 0
        summary['system_health'] = system_health
        
        # 数据源性能统计
        source_stats = {}
        all_sources = set()
        
        for stock_code, stock_result in results.get('stock_tests', {}).items():
            if not stock_result.get('success', False):
                continue
                
            for source_name, source_result in stock_result.get('sources', {}).items():
                all_sources.add(source_name)
                
                if source_name not in source_stats:
                    source_stats[source_name] = {
                        'total_tests': 0,
                        'successful_tests': 0,
                        'response_times': [],
                        'integrity_scores': [],
                        'consistency_scores': [],
                        'overall_scores': []
                    }
                
                stats = source_stats[source_name]
                stats['total_tests'] += 1
                
                if source_result.get('success', False):
                    stats['successful_tests'] += 1
                    stats['response_times'].append(source_result.get('response_time_ms', 0))
                    stats['integrity_scores'].append(source_result.get('integrity_score', {}).get('score', 0))
                    stats['consistency_scores'].append(source_result.get('consistency_score', {}).get('score', 0))
                    stats['overall_scores'].append(source_result.get('overall_score', {}).get('overall_score', 0))
        
        # 计算各数据源的综合指标
        performance_summary = {}
        for source_name, stats in source_stats.items():
            perf = {
                'success_rate': (stats['successful_tests'] / stats['total_tests']) * 100 if stats['total_tests'] > 0 else 0,
                'avg_response_time': statistics.mean(stats['response_times']) if stats['response_times'] else 0,
                'avg_integrity_score': statistics.mean(stats['integrity_scores']) if stats['integrity_scores'] else 0,
                'avg_consistency_score': statistics.mean(stats['consistency_scores']) if stats['consistency_scores'] else 0,
                'avg_overall_score': statistics.mean(stats['overall_scores']) if stats['overall_scores'] else 0
            }
            performance_summary[source_name] = perf
        
        summary['data_source_performance'] = performance_summary
        
        # 数据质量概览
        quality_overview = {
            'total_stock_tests': len(results.get('stock_tests', {})),
            'successful_stock_tests': sum(1 for test in results.get('stock_tests', {}).values() if test.get('success', False)),
            'average_data_quality': 0,
            'quality_distribution': {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        }
        
        all_quality_scores = []
        for stock_result in results.get('stock_tests', {}).values():
            if not stock_result.get('success', False):
                continue
            for source_result in stock_result.get('sources', {}).values():
                if source_result.get('success', False):
                    score = source_result.get('overall_score', {}).get('overall_score', 0)
                    grade = source_result.get('overall_score', {}).get('grade', 'F')
                    all_quality_scores.append(score)
                    quality_overview['quality_distribution'][grade] += 1
        
        if all_quality_scores:
            quality_overview['average_data_quality'] = statistics.mean(all_quality_scores)
        
        summary['data_quality_overview'] = quality_overview
        
        # 关键发现
        findings = []
        
        # 找出最佳和最差数据源
        if performance_summary:
            best_source = max(performance_summary.items(), key=lambda x: x[1]['avg_overall_score'])
            worst_source = min(performance_summary.items(), key=lambda x: x[1]['avg_overall_score'])
            
            findings.append(f"最佳数据源: {best_source[0]} (综合得分: {best_source[1]['avg_overall_score']:.1f})")
            findings.append(f"最差数据源: {worst_source[0]} (综合得分: {worst_source[1]['avg_overall_score']:.1f})")
        
        # 性能警告
        for source_name, perf in performance_summary.items():
            if perf['success_rate'] < 80:
                findings.append(f"⚠️ {source_name} 成功率偏低: {perf['success_rate']:.1f}%")
            if perf['avg_response_time'] > 2000:
                findings.append(f"⚠️ {source_name} 响应时间较慢: {perf['avg_response_time']:.1f}ms")
        
        summary['key_findings'] = findings
        
        # 判断总体成功
        if system_health['critical_failures'] or quality_overview['average_data_quality'] < 60:
            summary['overall_success'] = False
        
        return summary

    def _generate_recommendations(self, results: Dict) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        summary = results.get('summary', {})
        performance = summary.get('data_source_performance', {})
        
        # 基于性能数据生成建议
        for source_name, perf in performance.items():
            if perf['success_rate'] < 50:
                recommendations.append(f"🔧 建议检查 {source_name} 数据源配置，成功率过低 ({perf['success_rate']:.1f}%)")
            
            if perf['avg_response_time'] > 5000:
                recommendations.append(f"⚡ 建议优化 {source_name} 网络连接，响应时间过慢 ({perf['avg_response_time']:.1f}ms)")
            
            if perf['avg_integrity_score'] < 70:
                recommendations.append(f"📊 建议修复 {source_name} 数据完整性问题，完整性得分过低 ({perf['avg_integrity_score']:.1f})")
        
        # 系统级建议
        switch_test = results.get('switch_test', {})
        if not switch_test.get('success', True):
            recommendations.append("🔄 建议检查数据源切换功能，切换测试失败")
        
        # 数据质量建议
        quality = summary.get('data_quality_overview', {})
        if quality.get('average_data_quality', 0) < 80:
            recommendations.append("📈 建议提升整体数据质量，当前平均质量得分偏低")
        
        # 如果没有发现问题，给出优化建议
        if not recommendations:
            recommendations.append("✅ 系统整体运行良好，建议定期监控数据质量")
            recommendations.append("📊 建议增加更多股票样本进行测试")
            recommendations.append("⏰ 建议设置自动化定时测试")
        
        return recommendations

    def print_detailed_report(self, results: Dict):
        """打印详细测试报告"""
        print("\n" + "=" * 100)
        print("📋 WEB API 实时数据源完整性测试报告")
        print("=" * 100)
        
        # 基本信息
        test_info = results.get('test_info', {})
        print(f"🕐 测试时间: {test_info.get('start_time')} - {test_info.get('end_time')}")
        print(f"⏱️ 测试耗时: {test_info.get('duration_seconds', 0):.2f} 秒")
        print(f"🌐 测试URL: {test_info.get('base_url')}")
        print(f"📈 测试股票: {len(test_info.get('test_stocks', []))} 只")
        
        # 系统健康状况
        print(f"\n🏥 系统健康状况:")
        system_health = results.get('summary', {}).get('system_health', {})
        health_score = system_health.get('health_score', 0)
        print(f"   健康得分: {health_score:.1f}% ({system_health.get('passed_checks', 0)}/{system_health.get('total_checks', 0)} 检查通过)")
        
        if system_health.get('critical_failures'):
            print(f"   ❌ 关键失败: {', '.join(system_health['critical_failures'])}")
        else:
            print(f"   ✅ 所有关键检查通过")
        
        # 数据源性能对比
        print(f"\n📊 数据源性能对比:")
        performance = results.get('summary', {}).get('data_source_performance', {})
        
        if performance:
            print(f"{'数据源':<15} {'成功率':<8} {'响应时间':<10} {'完整性':<8} {'一致性':<8} {'综合得分':<8} {'等级'}")
            print("-" * 85)
            
            for source_name, perf in performance.items():
                print(f"{source_name:<15} "
                      f"{perf['success_rate']:<7.1f}% "
                      f"{perf['avg_response_time']:<9.0f}ms "
                      f"{perf['avg_integrity_score']:<7.1f} "
                      f"{perf['avg_consistency_score']:<7.1f} "
                      f"{perf['avg_overall_score']:<7.1f} "
                      f"{'A' if perf['avg_overall_score'] >= 90 else 'B' if perf['avg_overall_score'] >= 80 else 'C' if perf['avg_overall_score'] >= 70 else 'D' if perf['avg_overall_score'] >= 60 else 'F'}")
        
        # 数据质量分布
        print(f"\n📈 数据质量分布:")
        quality = results.get('summary', {}).get('data_quality_overview', {})
        dist = quality.get('quality_distribution', {})
        total_tests = sum(dist.values())
        
        if total_tests > 0:
            for grade in ['A', 'B', 'C', 'D', 'F']:
                count = dist.get(grade, 0)
                percentage = (count / total_tests) * 100
                bar = "█" * int(percentage / 2)
                print(f"   {grade}级: {count:>3} ({percentage:>5.1f}%) {bar}")
        
        print(f"   平均质量得分: {quality.get('average_data_quality', 0):.1f}")
        
        # 关键发现
        print(f"\n🔍 关键发现:")
        findings = results.get('summary', {}).get('key_findings', [])
        for finding in findings:
            print(f"   • {finding}")
        
        # 改进建议
        print(f"\n💡 改进建议:")
        recommendations = results.get('recommendations', [])
        for rec in recommendations:
            print(f"   • {rec}")
        
        # 总体结论
        overall_success = results.get('summary', {}).get('overall_success', False)
        print(f"\n🎯 总体结论: {'✅ 测试通过' if overall_success else '❌ 需要改进'}")

    def save_results(self, results: Dict, filename: str = None):
        """保存测试结果"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"web_api_data_source_test_results_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"📁 测试结果已保存到: {filename}")
        except Exception as e:
            logger.error(f"❌ 保存结果失败: {str(e)}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Web API 实时数据源完整性测试')
    parser.add_argument('--url', default='http://127.0.0.1:5000', help='API服务器地址')
    parser.add_argument('--stocks', nargs='+', help='指定测试股票代码')
    parser.add_argument('--output', help='结果输出文件名')
    
    args = parser.parse_args()
    
    print("🚀 启动Web API实时数据源完整性测试...")
    
    # 创建测试器
    tester = WebAPIDataSourceTester(base_url=args.url)
    
    # 如果指定了股票代码，使用指定的
    if args.stocks:
        tester.test_stocks = args.stocks
    
    # 运行测试
    try:
        results = tester.run_comprehensive_test()
        
        # 显示报告
        tester.print_detailed_report(results)
        
        # 保存结果
        tester.save_results(results, args.output)
        
        print("\n✅ 测试完成！")
        
        # 根据测试结果返回适当的退出码
        overall_success = results.get('summary', {}).get('overall_success', False)
        exit(0 if overall_success else 1)
        
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
        exit(1)
    except Exception as e:
        logger.error(f"❌ 测试过程中发生异常: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()