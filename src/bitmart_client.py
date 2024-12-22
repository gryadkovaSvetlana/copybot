import hmac
import hashlib
import time
import requests
import json
from dataclasses import dataclass
from typing import Optional
from config import BitmartConfig
import logging

logger = logging.getLogger(__name__)

class BitmartClient:
    BASE_URL = "https://api-cloud-v2.bitmart.com"

    def __init__(self, config: BitmartConfig):
        self.config = config
        self.session = requests.Session()
        self._order_counter = 0  # Add counter for unique order IDs
        self._tick_sizes = {}  # Cache for tick sizes
        
    def _generate_signature(self, timestamp: str, body: dict = None) -> str:
        """Generate signature for BitMart API authentication"""
        body_str = json.dumps(body) if body else ''
        message = f"{timestamp}#{self.config.memo}#{body_str}"
        signature = hmac.new(
            self.config.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _get_headers(self, body: dict = None) -> dict:
        """Generate headers for BitMart API requests"""
        timestamp = str(int(time.time() * 1000))
        return {
            'Content-Type': 'application/json',
            'X-BM-KEY': self.config.api_key,
            'X-BM-TIMESTAMP': timestamp,
            'X-BM-SIGN': self._generate_signature(timestamp, body)
        }

    def _generate_order_id(self) -> str:
        """Generate unique client order ID"""
        self._order_counter += 1
        return f"BOT_{int(time.time())}_{self._order_counter}"

    def get_contract_details(self, symbol: Optional[str] = None) -> dict:
        """Get contract details for a symbol or all symbols"""
        endpoint = "/contract/public/details"
        params = {'symbol': symbol} if symbol else None
        response = self.session.get(f"{self.BASE_URL}{endpoint}", params=params)
        return response.json()

    def submit_order(self, symbol: str, side: int, size: int, 
                    leverage: str, open_type: str,
                    preset_take_profit_price: str = None,
                    preset_stop_loss_price: str = None,
                    preset_take_profit_price_type: int = None,
                    preset_stop_loss_price_type: int = None) -> dict:
        """Submit a futures order"""
        endpoint = "/contract/private/submit-order"
        body = {
            "symbol": symbol,
            "side": side,
            "mode": 1,
            "type": "market",
            "leverage": leverage, 
            "open_type": open_type,
            "size": size,
            "client_order_id": self._generate_order_id()
        }
        
        # Add preset TP/SL if provided
        if preset_take_profit_price:
            body["preset_take_profit_price"] = preset_take_profit_price
            body["preset_take_profit_price_type"] = preset_take_profit_price_type
        if preset_stop_loss_price:
            body["preset_stop_loss_price"] = preset_stop_loss_price
            body["preset_stop_loss_price_type"] = preset_stop_loss_price_type
        
        response = self.session.post(
            f"{self.BASE_URL}{endpoint}",
            headers=self._get_headers(body),
            json=body
        )
        return response.json()

    def get_position(self, symbol: Optional[str] = None) -> dict:
        """Get current position details"""
        endpoint = "/contract/private/position"
        params = {'symbol': symbol} if symbol else None
        response = self.session.get(
            f"{self.BASE_URL}{endpoint}",
            headers=self._get_headers(),
            params=params
        )
        return response.json()

    def get_contract_assets(self) -> dict:
        """Get futures account balance"""
        endpoint = "/contract/private/assets-detail"
        headers = self._get_headers()
        logger.debug(f"Making request to {self.BASE_URL}{endpoint} with headers: {headers}")
        response = self.session.get(
            f"{self.BASE_URL}{endpoint}",
            headers=headers
        )
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response content: {response.text}")
        return response.json()

    def submit_leverage(self, symbol: str, leverage: str, open_type: str) -> dict:
        """Set leverage for a symbol"""
        endpoint = "/contract/private/submit-leverage"
        body = {
            "symbol": symbol,
            "leverage": leverage,
            "open_type": open_type
        }
        response = self.session.post(
            f"{self.BASE_URL}{endpoint}",
            headers=self._get_headers(body),
            json=body
        )
        return response.json() 

    def submit_plan_order(self, symbol: str, side: int, size: int,
                         leverage: str, open_type: str, trigger_price: str,
                         order_type: str = 'limit', execute_price: str = None,
                         price_way: int = 1) -> dict:
        """Submit a plan order
        
        Args:
            symbol: Trading pair
            side: Order side (1=buy_open_long, 2=buy_close_short, 3=sell_close_long, 4=sell_open_short)
            size: Order size
            leverage: Leverage value
            open_type: 'cross' or 'isolated'
            trigger_price: Price at which order triggers
            order_type: 'limit' or 'market'
            execute_price: Required if order_type is 'limit'
            price_way: 1=price_way_long, 2=price_way_short
        """
        endpoint = "/contract/private/submit-plan-order"
        
        # Format prices according to tick size
        formatted_trigger = self._format_price(symbol, trigger_price)
        formatted_exec = self._format_price(symbol, execute_price) if execute_price else formatted_trigger
        
        body = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "leverage": leverage,
            "open_type": open_type,
            "size": size,
            "mode": 1,  # GTC
            "trigger_price": formatted_trigger,
            "executive_price": formatted_exec,  # Always provide execution price
            "price_way": price_way,
            "price_type": 1,  # 1=last_price
            "client_order_id": self._generate_order_id()
        }
            
        logger.info(f"Submitting plan order with body: {json.dumps(body, indent=2)}")
        
        response = self.session.post(
            f"{self.BASE_URL}{endpoint}",
            headers=self._get_headers(body),
            json=body
        )
        return response.json()

    def _get_tick_size(self, symbol: str) -> float:
        """Get tick size for a symbol from contract details"""
        if symbol not in self._tick_sizes:
            details = self.get_contract_details(symbol)
            if details.get('code') != 1000:
                raise ValueError(f"Could not get contract details for {symbol}")
                
            # Find the symbol in the data array
            symbols = details.get('data', {}).get('symbols', [])
            symbol_data = None
            for contract in symbols:
                if contract['symbol'] == symbol:
                    symbol_data = contract
                    break
                    
            if not symbol_data or 'price_precision' not in symbol_data:
                raise ValueError(f"Could not find tick size for {symbol}")
                
            # Convert price precision to tick size (e.g., 0.01 for 2 decimal places)
            price_precision = float(symbol_data['price_precision'])
            self._tick_sizes[symbol] = price_precision
            
        return self._tick_sizes[symbol]

    def _format_price(self, symbol: str, price: str) -> str:
        """Format price according to symbol's tick size"""
        tick_size = self._get_tick_size(symbol)
        logger.debug(f"Tick size for {symbol}: {tick_size}")
        price_float = float(price)
        
        # Round to nearest tick
        ticks = round(price_float / tick_size)
        formatted_price = ticks * tick_size
        
        # Get decimal places from tick size
        decimal_places = len(str(tick_size).split('.')[-1])
        logger.debug(f"Formatting {price} to {decimal_places} decimal places")
        return f"{formatted_price:.{decimal_places}f}"

    def submit_tp_sl_order(self, symbol: str, side: int, type: str, size: int,
                          trigger_price: str, price_type: int = 1,
                          plan_category: int = 1) -> dict:
        """Submit a TP/SL order
        
        Args:
            symbol: Trading pair
            side: Order side (2=buy_close_short, 3=sell_close_long)
            type: 'take_profit' or 'stop_loss'
            size: Order size
            trigger_price: Price at which order triggers
            price_type: 1=last_price, 2=fair_price
            plan_category: 1=TP/SL (default), 2=Position TP/SL
        """
        endpoint = "/contract/private/submit-tp-sl-order"
        
        # Format price according to tick size
        formatted_price = self._format_price(symbol, trigger_price)
        logger.info(f"Formatting price {trigger_price} to {formatted_price} for {symbol}")
        
        body = {
            "symbol": symbol,
            "side": side,
            "type": type,
            "size": size,
            "trigger_price": formatted_price,
            "executive_price": formatted_price,  # Required field
            "price_type": price_type,
            "plan_category": plan_category,
            "client_order_id": self._generate_order_id(),
            "category": "market"  # Always use market for stop loss
        }
            
        logger.info(f"Submitting TP/SL order with body: {json.dumps(body, indent=2)}")
        
        response = self.session.post(
            f"{self.BASE_URL}{endpoint}",
            headers=self._get_headers(body),
            json=body
        )
        return response.json()

    def submit_trail_order(self, symbol: str, side: int, size: int,
                          leverage: str, open_type: str, activation_price: str,
                          callback_rate: str = "2", activation_price_type: int = 1) -> dict:
        """Submit a trailing stop order
        
        Args:
            symbol: Trading pair
            side: Order side (2=buy_close_short, 3=sell_close_long)
            size: Order size
            leverage: Leverage value
            open_type: 'cross' or 'isolated'
            activation_price: Price at which trailing begins
            callback_rate: Rate of trailing (0.1 to 5.0)
            activation_price_type: 1=last_price, 2=fair_price
        """
        endpoint = "/contract/private/submit-trail-order"
        
        # Format price according to tick size
        formatted_price = self._format_price(symbol, activation_price)
        
        body = {
            "symbol": symbol,
            "side": side,
            "leverage": leverage,
            "open_type": open_type,
            "size": size,
            "activation_price": formatted_price,
            "callback_rate": callback_rate,
            "activation_price_type": activation_price_type
        }
            
        logger.info(f"Submitting trail order with body: {json.dumps(body, indent=2)}")
        
        response = self.session.post(
            f"{self.BASE_URL}{endpoint}",
            headers=self._get_headers(body),
            json=body
        )
        return response.json()