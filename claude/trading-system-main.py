#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MiniQMT Quantitative Trading System - Main Application
Author: Claude
Date: 2025-02-27
"""

import os
import time
import logging
from datetime import datetime
import config
from data_fetcher import DataFetcher
from data_processor import DataProcessor
from trade_strategy import TradeStrategy
from trade_executor import TradeExecutor
from log_manager import LogManager
from position_monitor import PositionMonitor

def setup_logging():
    """Set up logging configuration"""
    log_dir = config.LOG_DIR
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f'trading_{datetime.now().strftime("%Y%m%d")}.log')
    
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('trading_system')

def main():
    """Main entry point of the trading system"""
    logger = setup_logging()
    logger.info("Starting MiniQMT Trading System")
    
    # Initialize log manager and perform cleanup if needed
    log_manager = LogManager(config.LOG_DIR, config.LOG_RETENTION_DAYS)
    log_manager.cleanup_old_logs()
    
    try:
        # Initialize components
        data_fetcher = DataFetcher(
            config.DATA_DIR,
            config.STOCK_LIST,
            config.HISTORY_DAYS
        )
        
        data_processor = DataProcessor(
            config.DATA_DIR,
            config.INDICATORS_CONFIG
        )
        
        position_monitor = PositionMonitor(
            config.POSITION_DATA_FILE,
            config.MAX_POSITION_VALUE,
            config.STOP_LOSS_PERCENTAGE
        )
        
        strategy = TradeStrategy(
            config.STRATEGY_CONFIG,
            position_monitor
        )
        
        executor = TradeExecutor(
            config.TRADE_CONFIG,
            position_monitor
        )
        
        # Main loop
        while True:
            if config.DEBUG:
                logger.debug("Starting trading cycle")
            
            # Step 1: Fetch latest market data
            data_fetcher.update_all_stocks_data()
            
            # Step 2: Process data and calculate indicators
            processed_data = data_processor.process_all_stocks()
            
            # Step 3: Generate trading signals
            signals = strategy.generate_signals(processed_data)
            
            # Step 4: Execute trades based on signals
            if signals:
                for signal in signals:
                    executor.execute_trade(signal)
            
            # Step 5: Update position information
            position_monitor.update_positions()
            
            # Check for manual operations through the API interface
            executor.check_manual_operations()
            
            # Sleep until next cycle
            if config.DEBUG:
                logger.debug(f"Cycle completed, sleeping for {config.CYCLE_INTERVAL} seconds")
            
            time.sleep(config.CYCLE_INTERVAL)
            
    except KeyboardInterrupt:
        logger.info("Trading system stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Shutting down trading system")

if __name__ == "__main__":
    main()
