#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MiniQMT Quantitative Trading System - Position Monitor
Tracks and manages positions, calculates profit/loss
Author: Claude
Date: 2025-02-27
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime

class Position:
    """Represents a stock position with associated trades and metrics"""
    
    def __init__(self, symbol, name=None):
        """
        Initialize a position
        
        Args:
            symbol (str): Stock symbol
            name (str, optional): Stock name
        """
        self.symbol = symbol
        self.name = name if name else symbol
        self.quantity = 0  # Total quantity
        self.cost = 0.0  # Total cost
        self.trades = []  # List of trade dictionaries
        self.avg_price = 0.0  # Average price
        self.current_price = 0.0  # Current market price
        self.profit_loss = 0.0  # Unrealized P&L
        self.profit_loss_pct = 0.0  # Unrealized P&L as percentage
        self.high_since_entry = 0.0  # Highest price since entry
        self.low_since_entry = float('inf')  # Lowest price since entry
        
    def add_trade(self, trade):
        """
        Add a trade to the position
        
        Args:
            trade (dict): Trade information
        """
        self.trades.append(trade)
        self.recalculate()
    
    def recalculate(self):
        """Recalculate position metrics based on trades"""
        total_quantity = 0
        total_cost = 0.0
        
        for trade in self.trades:
            # Buy increases position, sell decreases
            if trade['direction'] == 'BUY':
                total_cost += trade['price'] * trade['quantity']
                total_quantity += trade['quantity']
            else:  # SELL
                # Proportionally reduce cost
                if self.quantity > 0:
                    cost_per_share = self.cost / self.quantity
                    total_cost -= cost_per_share * trade['quantity']
                total_quantity -= trade['quantity']
        
        self.quantity = total_quantity
        self.cost = total_cost
        
        if self.quantity > 0:
            self.avg_price = self.cost / self.quantity
        else:
            self.avg_price = 0.0
            
        # Recalculate profit/loss if we have a current price
        if self.current_price > 0 and self.quantity > 0:
            self.profit_loss = (self.current_price - self.avg_price) * self.quantity
            self.profit_loss_pct = (self.current_price - self.avg_price) / self.avg_price
            
        # Update high/low since entry
        if self.current_price > self.high_since_entry:
            self.high_since_entry = self.current_price
        if self.current_price < self.low_since_entry and self.current_price > 0:
            self.low_since_entry = self.current_price
    
    def update_price(self, price):
        """
        Update the current price and recalculate metrics
        
        Args:
            price (float): Current price
        """
        self.current_price = price
        self.recalculate()
    
    def to_dict(self):
        """
        Convert position to dictionary for storage
        
        Returns:
            dict: Position as dictionary
        """
        return {
            'symbol': self.symbol,
            'name': self.name,
            'quantity': self.quantity,
            'cost': self.cost,
            'avg_price': self.avg_price,
            'current_price': self.current_price,
            'profit_loss': self.profit_loss,
            'profit_loss_pct': self.profit_loss_pct,
            'high_since_entry': self.high_since_entry,
            'low_since_entry': self.low_since_entry,
            'trades': self.trades
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Create position from dictionary
        
        Args:
            data (dict): Position data
            
        Returns:
            Position: Position object
        """
        position = cls(data['symbol'], data['name'])
        position.quantity = data['quantity']
        position.cost = data['cost']
        position.avg_price = data['avg_price']
        position.current_price = data['current_price']
        position.profit_loss = data['profit_loss']
        position.profit_loss_pct = data['profit_loss_pct']
        position.high_since_entry = data['high_since_entry']
        position.low_since_entry = data['low_since_entry']
        position.trades = data['trades']
        return position

class PositionMonitor:
    """Monitors and manages stock positions"""
    
    def __init__(self, position_file, max_position_value, stop_loss_percentage):
        """
        Initialize the position monitor
        
        Args:
            position_file (str): File to store position data
            max_position_value (float): Maximum position value per stock
            stop_loss_percentage (float): Stop loss percentage (negative)
        """
        self.logger = logging.getLogger('trading_system.position_monitor')
        self.position_file = position_file
        self.max_position_value = max_position_value
        self.stop_loss_percentage = stop_loss_percentage
        self.positions = {}  # Dictionary of Position objects
        
        # Create directory if it doesn't exist
        position_dir = os.path.dirname(position_file)
        if not os.path.exists(position_dir):
            os.makedirs(position_dir)
            self.logger.info(f"Created position directory: {position_dir}")
        
        # Load existing positions
        self.load_positions()
    
    def load_positions(self):
        """Load positions from file"""
        if os.path.exists(self.position_file):
            try:
                with open(self.position_file, 'r') as f:
                    positions_data = json.load(f)
                
                for symbol, position_data in positions_data.items():
                    self.positions[symbol] = Position.from_dict(position_data)
                
                self.logger.info(f"Loaded {len(self.positions)} positions from {self.position_file}")
            except Exception as e:
                self.logger.error(f"Error loading positions: {e}")
        else:
            self.logger.info(f"Position file {self.position_file} does not exist, starting with empty positions")
    
    def save_positions(self):
        """Save positions to file"""
        try:
            positions_data = {symbol: position.to_dict() for symbol, position in self.positions.items()}
            
            with open(self.position_file, 'w') as f:
                json.dump(positions_data, f, indent=4)
            
            self.logger.info(f"Saved {len(self.positions)} positions to {self.position_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving positions: {e}")
            return False
    
    def add_position(self, symbol, name=None):
        """
        Add a new position
        
        Args:
            symbol (str): Stock symbol
            name (str, optional): Stock name
            
        Returns:
            Position: The new position
        """
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol, name)
            self.logger.info(f"Added new position for {symbol}")
        return self.positions[symbol]
    
    def get_position(self, symbol):
        """
        Get position for a symbol
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            Position: Position object or None if not found
        """
        return self.positions.get(symbol)
    
    def add_trade(self, symbol, trade):
        """
        Add a trade to a position
        
        Args:
            symbol (str): Stock symbol
            trade (dict): Trade information
            
        Returns:
            Position: Updated position
        """
        position = self.get_position(symbol)
        if position is None:
            position = self.add_position(symbol)
        
        position.add_trade(trade)
        self.logger.info(f"Added trade for {symbol}: {trade}")
        
        # Save positions after adding trade
        self.save_positions()
        
        return position
    
    def update_prices(self, prices_dict):
        """
        Update prices for all positions
        
        Args:
            prices_dict (dict): Dictionary of current prices with symbols as keys
        """
        for symbol, price in prices_dict.items():
            if symbol in self.positions:
                self.positions[symbol].update_price(price)
                self.logger.debug(f"Updated price for {symbol}: {price}")
        
        # Save positions after updating prices
        self.save_positions()
    
    def get_stop_loss_signals(self):
        """
        Check for stop loss signals
        
        Returns:
            list: List of symbols that triggered stop loss
        """
        signals = []
        
        for symbol, position in self.positions.items():
            # Check if position is underwater more than stop loss percentage
            if position.quantity > 0 and position.profit_loss_pct <= self.stop_loss_percentage:
                signals.append(symbol)
                self.logger.warning(f"Stop loss triggered for {symbol}: {position.profit_loss_pct:.2%}")
        
        return signals
    
    def get_position_value(self, symbol):
        """
        Get current position value
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            float: Current position value
        """
        position = self.get_position(symbol)
        if position and position.quantity > 0:
            return position.current_price * position.quantity
        return 0.0
    
    def can_increase_position(self, symbol):
        """
        Check if position can be increased (under max value)
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            bool: True if position can be increased
        """
        current_value = self.get_position_value(symbol)
        return current_value < self.max_position_value
    
    def get_all_positions(self):
        """
        Get all positions
        
        Returns:
            dict: Dictionary of Position objects
        """
        return self.positions
    
    def get_position_summary(self):
        """
        Get summary of all positions
        
        Returns:
            pd.DataFrame: DataFrame with position summary
        """
        summary = []
        
        for symbol, position in self.positions.items():
            if position.quantity > 0:
                summary.append({
                    'symbol': symbol,
                    'name': position.name,
                    'quantity': position.quantity,
                    'avg_price': position.avg_price,
                    'current_price': position.current_price,
                    'value': position.current_price * position.quantity,
                    'profit_loss': position.profit_loss,
                    'profit_loss_pct': position.profit_loss_pct,
                })
        
        if not summary:
            return pd.DataFrame()
        
        return pd.DataFrame(summary)
    
    def update_positions(self):
        """
        Update positions with latest market data
        This should be called periodically to keep positions up to date
        """
        try:
            # In a real implementation, fetch latest prices for all positions
            # For now, we'll just save the current state
            self.save_positions()
            self.logger.info("Updated positions")
            
        except Exception as e:
            self.logger.error(f"Error updating positions: {e}")

if __name__ == "__main__":
    # Test the position monitor
    logging.basicConfig(level=logging.DEBUG)
    import tempfile
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        position_file = tmp.name
    
    monitor = PositionMonitor(position_file, 50000, -0.095)
    
    # Add a position with some trades
    monitor.add_position('600000.SH', '浦发银行')
    
    # Add some trades
    monitor.add_trade('600000.SH', {
        'time': datetime.now().isoformat(),
        'direction': 'BUY',
        'price': 10.5,
        'quantity': 1000,
        'amount': 10500,
        'commission': 5.25
    })
    
    monitor.add_trade('600000.SH', {
        'time': datetime.now().isoformat(),
        'direction': 'BUY',
        'price': 10.2,
        'quantity': 1000,
        'amount': 10200,
        'commission': 5.10
    })
    
    # Update price
    monitor.update_prices({'600000.SH': 10.8})
    
    # Print position summary
    print(monitor.get_position_summary())
    
    # Clean up
    os.unlink(position_file)
