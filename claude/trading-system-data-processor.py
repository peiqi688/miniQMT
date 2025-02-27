#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MiniQMT Quantitative Trading System - Data Processor
Calculates technical indicators from historical data
Author: Claude
Date: 2025-02-27
"""

import os
import logging
import pandas as pd
import numpy as np
import talib
from datetime import datetime

class DataProcessor:
    """Processes stock data and calculates technical indicators"""
    
    def __init__(self, data_dir, indicators_config):
        """
        Initialize the data processor
        
        Args:
            data_dir (str): Directory containing stock data
            indicators_config (dict): Configuration for indicators calculation
        """
        self.logger = logging.getLogger('trading_system.data_processor')
        self.data_dir = data_dir
        self.indicators_config = indicators_config
    
    def load_stock_data(self, symbol):
        """
        Load stock data from CSV file
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            pandas.DataFrame: Loaded data or None if file doesn't exist
        """
        file_path = os.path.join(self.data_dir, f"{symbol.replace('.', '_')}.csv")
        
        if not os.path.exists(file_path):
            self.logger.warning(f"Data file for {symbol} does not exist")
            return None
        
        try:
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading data for {symbol}: {e}")
            return None
    
    def calculate_moving_averages(self, df, periods):
        """
        Calculate simple moving averages for specified periods
        
        Args:
            df (pandas.DataFrame): Stock data
            periods (list): List of periods to calculate MA for
            
        Returns:
            pandas.DataFrame: DataFrame with added MA columns
        """
        if 'close' not in df.columns:
            self.logger.error("'close' column not found in dataframe")
            return df
            
        result = df.copy()
        
        for period in periods:
            try:
                column_name = f'ma_{period}'
                result[column_name] = talib.SMA(result['close'].values, timeperiod=period)
                self.logger.debug(f"Calculated {column_name}")
            except Exception as e:
                self.logger.error(f"Error calculating MA-{period}: {e}")
        
        return result
    
    def calculate_macd(self, df, fast_period=12, slow_period=26, signal_period=9):
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        Args:
            df (pandas.DataFrame): Stock data
            fast_period (int): Fast period
            slow_period (int): Slow period
            signal_period (int): Signal period
            
        Returns:
            pandas.DataFrame: DataFrame with added MACD columns
        """
        if 'close' not in df.columns:
            self.logger.error("'close' column not found in dataframe")
            return df
            
        result = df.copy()
        
        try:
            macd, macd_signal, macd_hist = talib.MACD(
                result['close'].values,
                fastperiod=fast_period,
                slowperiod=slow_period,
                signalperiod=signal_period
            )
            
            result['macd'] = macd
            result['macd_signal'] = macd_signal
            result['macd_hist'] = macd_hist
            
            self.logger.debug("Calculated MACD")
            
        except Exception as e:
            self.logger.error(f"Error calculating MACD: {e}")
        
        return result
    
    def calculate_volume_indicators(self, df, periods):
        """
        Calculate volume-based indicators
        
        Args:
            df (pandas.DataFrame): Stock data
            periods (list): List of periods for volume averages
            
        Returns:
            pandas.DataFrame: DataFrame with added volume indicators
        """
        if 'volume' not in df.columns:
            self.logger.error("'volume' column not found in dataframe")
            return df
            
        result = df.copy()
        
        for period in periods:
            try:
                column_name = f'volume_ma_{period}'
                result[column_name] = talib.SMA(result['volume'].values, timeperiod=period)
                self.logger.debug(f"Calculated {column_name}")
            except Exception as e:
                self.logger.error(f"Error calculating volume MA-{period}: {e}")
        
        # Volume ratio (current volume / average volume)
        if f'volume_ma_{periods[0]}' in result.columns:
            result['volume_ratio'] = result['volume'] / result[f'volume_ma_{periods[0]}']
            
        return result
    
    def calculate_rsi(self, df, period=14):
        """
        Calculate RSI (Relative Strength Index)
        
        Args:
            df (pandas.DataFrame): Stock data
            period (int): RSI period
            
        Returns:
            pandas.DataFrame: DataFrame with added RSI column
        """
        if 'close' not in df.columns:
            self.logger.error("'close' column not found in dataframe")
            return df
            
        result = df.copy()
        
        try:
            result['rsi'] = talib.RSI(result['close'].values, timeperiod=period)
            self.logger.debug(f"Calculated RSI-{period}")
        except Exception as e:
            self.logger.error(f"Error calculating RSI-{period}: {e}")
        
        return result
    
    def process_stock_data(self, symbol):
        """
        Process stock data and calculate all indicators
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            pandas.DataFrame: Processed data with all indicators
        """
        self.logger.info(f"Processing data for {symbol}")
        
        # Load stock data
        df = self.load_stock_data(symbol)
        
        if df is None or df.empty:
            self.logger.warning(f"No data available for {symbol}")
            return None
        
        # Make sure column names are lowercase
        df.columns = [col.lower() for col in df.columns]
        
        # Calculate indicators based on configuration
        result = df.copy()
        
        # Moving Averages
        if 'ma' in self.indicators_config:
            result = self.calculate_moving_averages(
                result, 
                self.indicators_config['ma']['periods']
            )
        
        # MACD
        if 'macd' in self.indicators_config:
            result = self.calculate_macd(
                result,
                self.indicators_config['macd']['fast_period'],
                self.indicators_config['macd']['slow_period'],
                self.indicators_config['macd']['signal_period']
            )
        
        # Volume indicators
        if 'volume' in self.indicators_config:
            result = self.calculate_volume_indicators(
                result,
                self.indicators_config['volume']['periods']
            )
        
        # RSI
        if 'rsi' in self.indicators_config:
            result = self.calculate_rsi(
                result,
                self.indicators_config['rsi']['period']
            )
        
        # Remove NaN values from the beginning
        result = result.dropna()
        
        self.logger.info(f"Processed {len(result)} records for {symbol}")
        
        return result
    
    def process_all_stocks(self, stock_list=None):
        """
        Process data for all stocks
        
        Args:
            stock_list (list, optional): List of stock symbols to process
            
        Returns:
            dict: Dictionary of processed DataFrames with stock symbols as keys
        """
        if stock_list is None:
            # Get all CSV files in the data directory
            files = [f for f in os.listdir(self.data_dir) if f.endswith('.csv')]
            stock_list = [f.replace('_', '.').replace('.csv', '') for f in files]
        
        self.logger.info(f"Processing data for {len(stock_list)} stocks")
        
        result = {}
        for symbol in stock_list:
            processed_data = self.process_stock_data(symbol)
            if processed_data is not None:
                result[symbol] = processed_data
        
        self.logger.info(f"Processed data for {len(result)} out of {len(stock_list)} stocks")
        
        return result

if __name__ == "__main__":
    # Test the data processor
    logging.basicConfig(level=logging.DEBUG)
    from config import DATA_DIR, INDICATORS_CONFIG
    
    processor = DataProcessor(DATA_DIR, INDICATORS_CONFIG)
    processed_data = processor.process_all_stocks()
    
    for symbol, df in processed_data.items():
        print(f"Symbol: {symbol}, Processed Records: {len(df)}")
        print(df.columns.tolist())
        print(df.tail(1))
