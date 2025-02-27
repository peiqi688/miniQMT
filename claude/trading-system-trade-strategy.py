#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MiniQMT Quantitative Trading System - Trade Strategy
Implements the trading strategy and generates signals
Author: Claude
Date: 2025-02-27
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

class TradeStrategy:
    """Implements trading strategies and generates trade signals"""
    
    def __init__(self, strategy_config, position_monitor):
        """
        Initialize the trade strategy
        
        Args:
            strategy_config (dict): Strategy configuration
            position_monitor (PositionMonitor): Position monitor instance
        """
        self.logger = logging.getLogger('trading_system.trade_strategy')
        self.strategy_config = strategy_config
        self.position_monitor = position_monitor
        
        # Extract configuration parameters
        self.initial_position = strategy_config['position_sizing']['initial_position']
        self.grid_levels = strategy_config['position_sizing']['grid_levels']
        self.first_target = strategy_config['profit_taking']['first_target']
        self.dynamic_targets = strategy_config['profit_taking']['dynamic_targets']
        self.position_stop_loss = strategy_config['stop_loss']['position_stop_loss']
        self.trailing_stop = strategy_config['stop_loss']['trailing_stop']
        self.grid_trading_enabled = strategy_config['grid_trading']['enabled']
        self.grid_size = strategy_config['grid_trading']['grid_size']
        self.grid_quantity = strategy_config['grid_trading']['grid_quantity']
        self.max_position_value = strategy_config['position_sizing']['max_position_value']
    
    def calculate_indicator_score(self, data):
        """
        Calculate a composite score based on various indicators
        
        Args:
            data (pandas.DataFrame): Processed stock data
            
        Returns:
            float: Composite score (-1 to 1)
        """
        # Get the latest data point
        latest = data.iloc[-1]
        
        score = 0.0
        
        # Moving Average signals
        if all(f'ma_{period}' in latest.index for period in [10, 20, 30, 60]):
            # Price above/below moving averages
            price = latest['close']
            ma_10 = latest['ma_10']
            ma_20 = latest['ma_20']
            ma_30 = latest['ma_30']
            ma_60 = latest['ma_60']
            
            # Check for golden/death crosses
            golden_cross = (ma_10 > ma_20) and (ma_20 > ma_30)
            death_cross = (ma_10 < ma_20) and (ma_20 < ma_30)
            
            # Price relative to MAs
            above_all_mas = price > ma_10 and price > ma_20 and price > ma_30 and price > ma_60
            below_all_mas = price < ma_10 and price < ma_20 and price < ma_30 and price < ma_60
            
            if golden_cross and above_all_mas:
                score += 0.3
            elif death_cross and below_all_mas:
                score -= 0.3
            elif price > ma_10:
                score += 0.1
            elif price < ma_10:
                score -= 0.1
        
        # MACD signals
        if all(indicator in latest.index for indicator in ['macd', 'macd_signal', 'macd_hist']):
            macd = latest['macd']
            macd_signal = latest['macd_signal']
            macd_hist = latest['macd_hist']
            
            # MACD crossing above signal line
            if macd > macd_signal and macd_hist > 0:
                score += 0.2
            # MACD crossing below signal line
            elif macd < macd_signal and macd_hist < 0:
                score -= 0.2
            # MACD histogram increasing
            elif macd_hist > 0 and macd_hist > data['macd_hist'].iloc[-2]:
                score += 0.1
            # MACD histogram decreasing
            elif macd_hist < 0 and macd_hist < data['macd_hist'].iloc[-2]:
                score -= 0.1
        
        # RSI signals
        if 'rsi' in latest.index:
            rsi = latest['rsi']
            
            # Oversold
            if rsi < 30:
                score += 0.2
            # Overbought
            elif rsi > 70:
                score -= 0.2
        
        # Volume signals
        if 'volume_ratio' in latest.index:
            volume_ratio = latest['volume_ratio']
            
            # High volume
            if volume_ratio > 2.0:
                # If price is up, positive signal
                if data['close'].iloc[-1] > data['close'].iloc[-2]:
                    score += 0.2
                # If price is down, negative signal
                else:
                    score -= 0.2
        
        # Clamp score between -1 and 1
        score = max(-1.0, min(1.0, score))
        
        return score
    
    def check_entry_signal(self, symbol, data, current_price):
        """
        Check for entry signal
        
        Args:
            symbol (str): Stock symbol
            data (pandas.DataFrame): Processed stock data
            current_price (float): Current price
            
        Returns:
            dict or None: Entry signal if found, None otherwise
        """
        # Calculate indicator score
        score = self.calculate_indicator_score(data)
        
        # Get current position
        position = self.position_monitor.get_position(symbol)
        
        # Check if we're at max position value across all holdings
        total_position_value = self.position_monitor.get_total_position_value()
        if total_position_value >= self.max_position_value:
            self.logger.info(f"Skip entry for {symbol}: Max position value reached ({total_position_value:.2f})")
            return None
        
        # If we don't have a position and score is positive, enter
        if (position is None or position.quantity == 0) and score > 0.3:
            # Calculate quantity based on initial position size
            quantity = int(self.initial_position / current_price / 100) * 100  # Round to nearest 100 shares
            
            # Check if this would exceed max position value
            if (quantity * current_price) + total_position_value > self.max_position_value:
                available_value = self.max_position_value - total_position_value
                quantity = int(available_value / current_price / 100) * 100
            
            if quantity > 0:
                self.logger.info(f"Entry signal for {symbol}: score={score:.2f}, price={current_price}")
                return {
                    'type': 'ENTRY',
                    'symbol': symbol,
                    'direction': 'BUY',
                    'price': current_price,
                    'quantity': quantity,
                    'reason': f"Initial entry based on indicator score {score:.2f}"
                }
        
        # Check for additional entry (scaling in)
        elif position and position.quantity > 0 and self.position_monitor.can_increase_position(symbol):
            # Check for grid level entry
            entry_price = position.avg_price
            
            for level in self.grid_levels:
                level_price = entry_price * level
                
                # If price is at or below grid level
                if current_price <= level_price:
                    # Check if we've already bought at this level
                    level_tag = f"grid_{level:.2f}"
                    already_bought = any(level_tag in trade.get('tags', []) for trade in position.trades)
                    
                    if not already_bought:
                        # Calculate quantity for this grid level
                        quantity = int(self.initial_position / current_price / 100) * 100
                        
                        # Check if this would exceed max position value
                        position_value = self.position_monitor.get_position_value(symbol)
                        new_total = total_position_value + (quantity * current_price)
                        if new_total > self.max_position_value:
                            available_value = self.max_position_value - total_position_value
                            quantity = int(available_value / current_price / 100) * 100
                        
                        if quantity > 0:
                            self.logger.info(f"Grid entry signal for {symbol}: level={level}, price={current_price}")
                            return {
                                'type': 'GRID_ENTRY',
                                'symbol': symbol,
                                'direction': 'BUY',
                                'price': current_price,
                                'quantity': quantity,
                                'reason': f"Grid entry at {level:.0%} of base price {entry_price:.2f}",
                                'tags': [level_tag]
                            }
        
        return None
    
    def check_exit_signal(self, symbol, data, current_price):
        """
        Check for exit signal
        
        Args:
            symbol (str): Stock symbol
            data (pandas.DataFrame): Processed stock data
            current_price (float): Current price
            
        Returns:
            dict or None: Exit signal if found, None otherwise
        """
        # Get current position
        position = self.position_monitor.get_position(symbol)
        
        if position is None or position.quantity == 0:
            return None
        
        # Calculate indicator score
        score = self.calculate_indicator_score(data)
        
        # Check for stop loss
        if position.profit_loss_pct <= self.position_stop_loss:
            self.logger.warning(f"Stop loss exit for {symbol}: P&L={position.profit_loss_pct:.2%}, price={current_price}")
            return {
                'type': 'STOP_LOSS',
                'symbol': symbol,
                'direction': 'SELL',
                'price': current_price,
                'quantity': position.quantity,  # Sell all
                'reason': f"Stop loss triggered at {position.profit_loss_pct:.2%}"
            }
        
        # First target - sell half position
        if position.profit_loss_pct >= self.first_target:
            # Check if we've already taken profit at first target
            first_target_tag = "first_target_profit"
            already_took_profit = any(first_target_tag in trade.get('tags', []) for trade in position.trades)
            
            if not already_took_profit:
                quantity = int(position.quantity / 2 / 100) * 100  # Half position, rounded to nearest 100
                
                if quantity > 0:
                    self.logger.info(f"First target exit for {symbol}: P&L={position.profit_loss_pct:.2%}, price={current_price}")
                    return {
                        'type': 'TAKE_PROFIT',
                        'symbol': symbol,
                        'direction': 'SELL',
                        'price': current_price,
                        'quantity': quantity,
                        'reason': f"First target profit at {position.profit_loss_pct:.2%}",
                        'tags': [first_target_tag]
                    }
        
        # Dynamic trailing stop
        for target, trail in reversed(self.dynamic_targets):
            if position.profit_loss_pct >= target:
                # Calculate trailing stop price
                high_water_mark = position.high_since_entry
                trailing_stop_price = high_water_mark * (1 - trail)
                
                if current_price <= trailing_stop_price:
                    self.logger.info(f"Trailing stop exit for {symbol}: P&L={position.profit_loss_pct:.2%}, " +
                                     f"trail={trail:.2%}, price={current_price}, stop={trailing_stop_price:.2f}")
                    return {
                        'type': 'TRAILING_STOP',
                        'symbol': symbol,
                        'direction': 'SELL',
                        'price': current_price,
                        'quantity': position.quantity,  # Sell all remaining
                        'reason': f"Trailing stop at {trail:.0%} from high of {high_water_mark:.2f}"
                    }
                break  # Only check the highest applicable trailing stop
        
        # Exit based on indicator score if it's strongly negative
        if score < -0.5:
            self.logger.info(f"Indicator exit for {symbol}: score={score:.2f}, price={current_price}")
            return {
                'type': 'INDICATOR_EXIT',
                'symbol': symbol,
                'direction': 'SELL',
                'price': current_price,
                'quantity': position.quantity,  # Sell all
                'reason': f"Exit based on indicator score {score:.2f}"
            }
        
        # Check for grid trading sell signals
        if self.grid_trading_enabled and position.profit_loss_pct > 0:
            # Calculate grid levels above entry price
            entry_price = position.avg_price
            for i in range(1, 10):  # Check up to 10 grid levels
                grid_level = 1 + (i * self.grid_size)
                grid_price = entry_price * grid_level
                grid_tag = f"grid_sell_{grid_level:.2f}"
                
                # If price is at or above grid level
                if current_price >= grid_price:
                    # Check if we've already sold at this level
                    already_sold = any(grid_tag in trade.get('tags', []) for trade in position.trades)
                    
                    if not already_sold:
                        # Calculate quantity for this grid level
                        quantity = max(100, int(position.quantity * self.grid_quantity / 100) * 100)
                        
                        if quantity > 0 and quantity < position.quantity:
                            self.logger.info(f"Grid sell signal for {symbol}: level={grid_level}, price={current_price}")
                            return {
                                'type': 'GRID_SELL',
                                'symbol': symbol,
                                'direction': 'SELL',
                                'price': current_price,
                                'quantity': quantity,
                                'reason': f"Grid sell at {grid_level:.0%} of base price {entry_price:.2f}",
                                'tags': [grid_tag]
                            }
        
        return None
    
    def generate_signals(self, processed_data):
        """
        Generate trading signals for all stocks
        
        Args:
            processed_data (dict): Dictionary of processed data with stock symbols as keys
            
        Returns:
            list: List of trading signals
        """
        signals = []
        
        for symbol, data in processed_data.items():
            if data is not None and not data.empty:
                try:
                    # Get current price
                    current_price = data['close'].iloc[-1]
                    
                    # Check for stop loss first (highest priority)
                    position = self.position_monitor.get_position(symbol)
                    if position and position.quantity > 0:
                        position.update_price(current_price)
                        
                        # Check for stop loss signals
                        if position.profit_loss_pct <= self.position_stop_loss:
                            signals.append({
                                'type': 'STOP_LOSS',
                                'symbol': symbol,
                                'direction': 'SELL',
                                'price': current_price,
                                'quantity': position.quantity,  # Sell all
                                'reason': f"Stop loss triggered at {position.profit_loss_pct:.2%}"
                            })
                            continue  # Skip other checks
                    
                    # Check for exit signals
                    exit_signal = self.check_exit_signal(symbol, data, current_price)
                    if exit_signal:
                        signals.append(exit_signal)
                        continue  # Skip entry check if we're exiting
                    
                    # Check for entry signals
                    entry_signal = self.check_entry_signal(symbol, data, current_price)
                    if entry_signal:
                        signals.append(entry_signal)
                except Exception as e:
                    self.logger.error(f"Error generating signals for {symbol}: {str(e)}")
        
        if signals:
            self.logger.info(f"Generated {len(signals)} signals")
        
        return signals
    
    def handle_manual_signals(self, manual_signals):
        """
        Process manual trading signals
        
        Args:
            manual_signals (list): List of manual trading signals
            
        Returns:
            list: List of processed trading signals
        """
        processed_signals = []
        
        for signal in manual_signals:
            try:
                symbol = signal.get('symbol')
                direction = signal.get('direction')
                quantity = signal.get('quantity')
                price = signal.get('price')
                
                if not all([symbol, direction, quantity, price]):
                    self.logger.error(f"Invalid manual signal: {signal}")
                    continue
                
                # Validate direction
                if direction not in ['BUY', 'SELL']:
                    self.logger.error(f"Invalid direction in manual signal: {direction}")
                    continue
                
                # Get current position
                position = self.position_monitor.get_position(symbol)
                
                # Validate quantity for sells
                if direction == 'SELL' and position and quantity > position.quantity:
                    self.logger.error(f"Invalid quantity in manual sell signal: {quantity} > {position.quantity}")
                    continue
                
                # Check if buy would exceed max position value
                if direction == 'BUY':
                    total_position_value = self.position_monitor.get_total_position_value()
                    if (quantity * price) + total_position_value > self.max_position_value:
                        self.logger.error(f"Manual buy would exceed max position value: {symbol}, {quantity}, {price}")
                        continue
                
                # Add signal type
                signal['type'] = 'MANUAL'
                signal['reason'] = signal.get('reason', 'Manual trading signal')
                
                self.logger.info(f"Processing manual signal: {signal}")
                processed_signals.append(signal)
                
            except Exception as e:
                self.logger.error(f"Error processing manual signal: {str(e)}")
        
        return processed_signals
    
    def clean_old_logs(self, log_dir, days_to_keep=7):
        """
        Clean old log files
        
        Args:
            log_dir (str): Directory containing log files
            days_to_keep (int): Number of days to keep logs for
        """
        if not os.path.exists(log_dir):
            self.logger.warning(f"Log directory does not exist: {log_dir}")
            return
        
        try:
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(days=days_to_keep)
            
            for filename in os.listdir(log_dir):
                file_path = os.path.join(log_dir, filename)
                if os.path.isfile(file_path) and filename.endswith('.log'):
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_mod_time < cutoff_time:
                        os.remove(file_path)
                        self.logger.info(f"Removed old log file: {filename}")
        except Exception as e:
            self.logger.error(f"Error cleaning old logs: {str(e)}")

if __name__ == "__main__":
    # Test the trade strategy
    logging.basicConfig(level=logging.DEBUG)
    from config import STRATEGY_CONFIG
    from position_monitor import PositionMonitor
    import tempfile
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        position_file = tmp.name
    
    position_monitor = PositionMonitor(
        position_file, 
        max_position_value=50000, 
        stop_loss_percentage=-0.095
    )
    
    strategy = TradeStrategy(STRATEGY_CONFIG, position_monitor)
    
    # Create some test data
    data = pd.DataFrame({
        'close': [10, 10.2, 10.5, 10.3, 10.8, 11.0, 11.2],
        'ma_10': [9.8, 9.9, 10.0, 10.1, 10.2, 10.3, 10.4],
        'ma_20': [9.7, 9.8, 9.9, 10.0, 10.1, 10.2, 10.3],
        'ma_30': [9.6, 9.7, 9.8, 9.9, 10.0, 10.1, 10.2],
        'ma_60': [9.5, 9.6, 9.7, 9.8, 9.9, 10.0, 10.1],
        'macd': [0.1, 0.12, 0.15, 0.13, 0.18, 0.2, 0.22],
        'macd_signal': [0.08, 0.09, 0.1, 0.11, 0.12, 0.14, 0.16],
        'macd_hist': [0.02, 0.03, 0.05, 0.02, 0.06, 0.06, 0.06],
        'rsi': [55, 60, 65, 58, 68, 72, 75],
        'volume': [100000, 120000, 150000, 130000, 180000, 200000, 220000],
        'volume_ratio': [1.0, 1.2, 1.5, 1.3, 1.8, 2.0, 2.2]
    })
    
    # Test indicator score
    score = strategy.calculate_indicator_score(data)
    print(f"Indicator score: {score:.2f}")
    
    # Test entry signal
    test_symbol = '600000.SH'
    entry_signal = strategy.check_entry_signal(test_symbol, data, 11.2)
    print(f"Entry signal: {entry_signal}")
    
    # Add a position and test exit signal
    position_monitor.add_position(test_symbol, '浦发银行')
    position_monitor.add_trade(test_symbol, {
        'time': datetime.now().isoformat(),
        'direction': 'BUY',
        'price': 10.0,
        'quantity': 2000,
        'amount': 20000,
        'commission': 10.0
    })
    
    # Update position price
    position = position_monitor.get_position(test_symbol)
    position.update_price(11.2)
    
    # Test exit signal
    exit_signal = strategy.check_exit_signal(test_symbol, data, 11.2)
    print(f"Exit signal: {exit_signal}")
    
    # Test generating signals
    processed_data = {test_symbol: data}
    signals = strategy.generate_signals(processed_data)
    print(f"Generated signals: {signals}")
    
    # Test manual signal handling
    manual_signals = [
        {
            'symbol': test_symbol,
            'direction': 'BUY',
            'price': 11.3,
            'quantity': 1000
        }
    ]
    processed_manual_signals = strategy.handle_manual_signals(manual_signals)
    print(f"Processed manual signals: {processed_manual_signals}")
    
    # Clean up temporary file
    if os.path.exists(position_file):
        os.remove(position_file)
    
    # Test log cleaning
    log_dir = tempfile.mkdtemp()
    try:
        # Create some dummy log files
        for i in range(10):
            with open(os.path.join(log_dir, f"test_{i}.log"), 'w') as f:
                f.write("Test log file")
        
        # Test log cleaning
        strategy.clean_old_logs(log_dir, days_to_keep=0)
        
        # Verify logs were cleaned
        remaining_logs = os.listdir(log_dir)
        print(f"Remaining logs after cleaning: {len(remaining_logs)}")
    finally:
        # Clean up temp directory
        for filename in os.listdir(log_dir):
            os.remove(os.path.join(log_dir, filename))
        os.rmdir(log_dir)
    
    print("Tests completed successfully")
