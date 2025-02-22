import pandas as pd
import config

class PositionManager:
    def __init__(self):
        self.positions = pd.DataFrame(
            columns=['cost_price', 'quantity', 'floating_pnl']
        )
        
    def update_positions(self, trades):
        for trade in trades:
            stock = trade['stock_code']
            if trade['direction'] == 'BUY':
                new_cost = (self.positions.loc[stock, 'cost_price'] * self.positions.loc[stock, 'quantity'] 
                           + trade['price'] * trade['quantity']) / (self.positions.loc[stock, 'quantity'] + trade['quantity'])
                self.positions.loc[stock, 'quantity'] += trade['quantity']
                self.positions.loc[stock, 'cost_price'] = new_cost
            else:
                self.positions.loc[stock, 'quantity'] -= trade['quantity']
                
    def check_risk(self):
        total_loss = (self.positions['floating_pnl'] / 
                     (self.positions['cost_price'] * self.positions['quantity'])).sum()
        if total_loss <= config.STOP_LOSS:
            return 'FULL_STOP'
        return 'NORMAL'
