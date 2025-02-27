#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MiniQMT Quantitative Trading System - Configuration
Author: Claude
Date: 2025-02-27
"""

import os
import logging
from datetime import datetime

# Debug settings
DEBUG = True  # Set to False in production
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO

# Directories and file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
POSITION_DATA_FILE = os.path.join(DATA_DIR, 'positions.json')
TRADE_HISTORY_FILE = os.path.join(DATA_DIR, 'trade_history.json')

# Log management
LOG_RETENTION_DAYS = 7  # Keep logs for 7 days

# Data settings
STOCK_LIST = [
    '600000.SH',  # Example stocks, replace with your list
    '000001.SZ',
    '601318.SH',
    '000333.SZ',
    '600519.SH',
]
HISTORY_DAYS = 120  # Fetch 120 days of historical data

# Trading cycle
CYCLE_INTERVAL = 60  # Check for trading signals every 60 seconds

# Indicator configuration
INDICATORS_CONFIG = {
    'ma': {
        'periods': [10, 20, 30, 60],
        'weight': 0.3
    },
    'macd': {
        'fast_period': 12,
        'slow_period': 26,
        'signal_period': 9,
        'weight': 0.4
    },
    'volume': {
        'periods': [5, 10],
        'weight': 0.1
    },
    'rsi': {
        'period': 14,
        'weight': 0.2
    }
}

# Strategy configuration
STRATEGY_CONFIG = {
    'position_sizing': {
        'initial_position': 20000,  # Initial position size (RMB)
        'grid_levels': [0.93, 0.86, 0.79, 0.72],  # Buy more at these price levels (as % of entry)
    },
    'profit_taking': {
        'first_target': 0.05,  # Take 50% off at 5% profit
        'dynamic_targets': [  # Format: (profit_percentage, trailing_stop_percentage)
            (0.08, 0.03),  # At 8% profit, use 3% trailing stop
            (0.12, 0.04),  # At 12% profit, use 4% trailing stop
            (0.18, 0.06),  # At 18% profit, use 6% trailing stop
            (0.25, 0.08),  # At 25% profit, use 8% trailing stop
        ]
    },
    'stop_loss': {
        'position_stop_loss': -0.095,  # -9.5% stop loss on position cost basis
        'trailing_stop': True
    },
    'grid_trading': {
        'enabled': True,
        'grid_size': 0.02,  # 2% between grid levels
        'grid_quantity': 0.1  # 10% of position size per grid level
    }
}

# Trade execution configuration
TRADE_CONFIG = {
    'max_position_value': 50000,  # Maximum position value per stock (RMB)
    'account_type': 'STOCK',  # STOCK or FUTURE
    'order_type': 'LIMIT',  # LIMIT or MARKET
    'price_tolerance': 0.002,  # Price tolerance for limit orders (0.2%)
    'api_timeout': 10,  # API timeout in seconds
    'retry_count': 3,  # Number of retries for API calls
}

# MiniQMT API configuration
MINIQMT_CONFIG = {
    'account_id': 'YOUR_ACCOUNT_ID',
    'password': 'YOUR_PASSWORD',
    'quote_callback': None,
    'mkt_type': 'stock',
    'mongod_uri': 'mongodb://localhost:27017/',
    'mongod_db': 'miniqmt',
    'quote_type': 'tick',
}

# Position management
MAX_POSITION_VALUE = 50000  # Maximum position value per stock (RMB)
STOP_LOSS_PERCENTAGE = -0.095  # -9.5% stop loss
