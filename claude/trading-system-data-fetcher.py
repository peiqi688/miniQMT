#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MiniQMT Quantitative Trading System - Data Fetcher
Responsible for fetching and storing historical market data
Author: Claude
Date: 2025-02-27
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import traceback

# Import MiniQMT for data fetching
try:
    from MiniQMT import MiniQMT
except ImportError:
    logging.error("MiniQMT library not found. Please install it first.")
    raise

class DataFetcher:
    """Fetches and stores historical stock data using MiniQMT API"""
    
    def __init__(self, data_dir, stock_list, history_days):
        """
        Initialize the data fetcher
        
        Args:
            data_dir (str): Directory to store data
            stock_list (list): List of stock symbols to fetch
            history_days (int): Number of historical days to fetch
        """
        self.logger = logging.getLogger('trading_system.data_fetcher')
        self.data_dir = data_dir
        self.stock_list = stock_list
        self.history_days = history_days
        
        # Create data directory if it doesn't exist
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            self.logger.info(f"Created data directory: {data_dir}")
        
        # Initialize MiniQMT client
        try:
            self.miniqmt = MiniQMT()
            self.logger.info("Successfully initialized MiniQMT client")
        except Exception as e:
            self.logger.error(f"Failed to initialize MiniQMT client: {e}")
            raise
    
    def fetch_stock_data(self, symbol, start_date=None, end_date=None):
        """
        Fetch historical data for a single stock
        
        Args:
            symbol (str): Stock symbol
            start_date (str, optional): Start date in format 'YYYY-MM-DD'
            end_date (str, optional): End date in format 'YYYY-MM-DD'
            
        Returns:
            pandas.DataFrame: Historical data
        """
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=self.history_days)).strftime('%Y-%m-%d')
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        self.logger.info(f"Fetching data for {symbol} from {start_date} to {end_date}")
        
        try:
            # Using MiniQMT to fetch K-line data
            df = self.miniqmt.get_price(
                symbol=symbol,
                start_time=start_date,
                end_time=end_date,
                freq='day'
            )
            
            if df is not None and not df.empty:
                self.logger.info(f"Successfully fetched {len(df)} records for {symbol}")
                return df
            else:
                self.logger.warning(f"No data returned for {symbol}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}: {e}")
            self.logger.debug(traceback.format_exc())
            return None
    
    def save_stock_data(self, symbol, df):
        """
        Save stock data to CSV file
        
        Args:
            symbol (str): Stock symbol
            df (pandas.DataFrame): Data to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        if df is None or df.empty:
            self.logger.warning(f"No data to save for {symbol}")
            return False
        
        try:
            # Create file path
            file_path = os.path.join(self.data_dir, f"{symbol.replace('.', '_')}.csv")
            
            # Save to CSV
            df.to_csv(file_path, index=True)
            self.logger.info(f"Saved data for {symbol} to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving data for {symbol}: {e}")
            return False
    
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
            self.logger.info(f"Loaded {len(df)} records for {symbol} from {file_path}")
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading data for {symbol}: {e}")
            return None
    
    def update_stock_data(self, symbol):
        """
        Update stock data by fetching only new data since last update
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            pandas.DataFrame: Updated data
        """
        # Load existing data
        existing_data = self.load_stock_data(symbol)
        
        if existing_data is not None and not existing_data.empty:
            # Get the last date in the existing data
            last_date = pd.to_datetime(existing_data.index.max())
            start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
            
            # If the last date is today, no need to update
            if last_date.date() >= datetime.now().date():
                self.logger.info(f"Data for {symbol} is already up to date")
                return existing_data
                
            self.logger.info(f"Updating data for {symbol} from {start_date}")
            
            # Fetch new data
            new_data = self.fetch_stock_data(symbol, start_date=start_date)
            
            if new_data is not None and not new_data.empty:
                # Combine old and new data
                updated_data = pd.concat([existing_data, new_data])
                updated_data = updated_data[~updated_data.index.duplicated(keep='last')]
                
                # Save updated data
                self.save_stock_data(symbol, updated_data)
                return updated_data
            else:
                return existing_data
        else:
            # No existing data, fetch all
            self.logger.info(f"No existing data for {symbol}, fetching all")
            data = self.fetch_stock_data(symbol)
            if data is not None:
                self.save_stock_data(symbol, data)
            return data
    
    def update_all_stocks_data(self):
        """
        Update data for all stocks in the list
        
        Returns:
            dict: Dictionary of DataFrames with stock symbols as keys
        """
        self.logger.info(f"Updating data for {len(self.stock_list)} stocks")
        result = {}
        
        for symbol in self.stock_list:
            data = self.update_stock_data(symbol)
            if data is not None:
                result[symbol] = data
        
        self.logger.info(f"Updated data for {len(result)} out of {len(self.stock_list)} stocks")
        return result

if __name__ == "__main__":
    # Test the data fetcher
    logging.basicConfig(level=logging.DEBUG)
    from config import DATA_DIR, STOCK_LIST, HISTORY_DAYS
    
    fetcher = DataFetcher(DATA_DIR, STOCK_LIST, HISTORY_DAYS)
    data = fetcher.update_all_stocks_data()
    
    for symbol, df in data.items():
        print(f"Symbol: {symbol}, Records: {len(df)}")
        print(df.head())
