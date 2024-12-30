from telethon import TelegramClient, events
from config import Config
from bitmart_client import BitmartClient
from models import Signal, PositionSide, TrailingConfig
import asyncio
import logging
import json
import re
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SignalParsingError(Exception):
    pass

class SignalMonitor:
    def __init__(self, config: Config):
        self.config = config
        self.client = None
        self.channel = None
        self.logger = logging.getLogger(__name__)
        self.bitmart = BitmartClient(config.bitmart)  # Initialize BitMart client
        
    async def connect(self):
        """Connect to Telegram and find the channel"""
        try:
            # Connect to Telegram
            self.client = TelegramClient(
                'signal_monitor_session',
                self.config.telegram.api_id,
                self.config.telegram.api_hash
            )
            await self.client.start(phone=self.config.telegram.phone)
            
            # Get channel by ID
            channel_id = int(self.config.telegram.channel_username)
            self.channel = await self.client.get_entity(channel_id)
            
            if self.channel:
                self.logger.info(f"Connected to channel: {self.channel.title}")
                return True
            else:
                raise ValueError(f"Could not find channel with ID {channel_id}")
            
        except Exception as e:
            self.logger.error(f"Error connecting to channel: {e}")
            raise

    async def monitor_channel(self):
        """Monitor channel for new messages"""
        try:
            @self.client.on(events.NewMessage(chats=self.channel))
            async def handle_new_message(event):
                try:
                    message = event.message.text
                    self.logger.info(f"New message received: {message}")
                    
                    # Check for cancellation message first
                    symbol = self.parse_cancellation(message)
                    if symbol:
                        await self.handle_cancellation(symbol)
                        return
                    
                    # If not a cancellation, try to parse as a signal
                    signal = self.parse_signal(message)
                    if signal:
                        self.logger.info(f"Valid signal detected: {json.dumps(signal, indent=2)}")
                        await self.execute_trade(signal)
                        
                except Exception as e:
                    self.logger.error(f"Error handling message: {e}")
            
            self.logger.info("Starting to monitor channel...")
            await self.client.run_until_disconnected()
            
        except Exception as e:
            self.logger.error(f"Error monitoring channel: {e}")
            raise

    async def execute_trade(self, signal: dict):
        """Execute the trade based on the signal"""
        try:
            symbol = signal['symbol']
            entry_price = float(signal['entry_price'])
            
            # Check for existing position first
            position = self.bitmart.get_position(symbol)
            if position.get('code') == 1000 and position.get('data'):
                for pos in position['data']:
                    if pos['symbol'] == symbol and int(pos['current_amount']) > 0:
                        self.logger.info(f"Found existing position for {symbol}, closing it first...")
                        close_result = self.bitmart.close_position(symbol, pos)
                        self.logger.info(f"Position close result: {json.dumps(close_result, indent=2)}")
                        # Wait a bit for the order to process
                        await asyncio.sleep(1)
            
            # Calculate position size for 15 USDT
            size = self.bitmart.calculate_position_size(symbol, entry_price)
            actual_value = size * entry_price * float(self.bitmart._get_contract_size(symbol))
            
            # Get minimum order size
            min_size = self.bitmart._get_min_volume(symbol)
            size_per_third = size // 3
            size_per_half = size // 2
            
            # Determine position type
            if actual_value > 15.0:
                position_type = "Large (single TP)"
            elif size_per_third < min_size:
                position_type = "Medium (2 TPs)"
            else:
                position_type = "Normal (3 TPs)"
            
            self.logger.info(f"""
Trade Parameters:
Symbol: {symbol}
Side: {signal['side']}
Size: {size} contracts
Actual Value: {actual_value:.2f} USDT
Position Type: {position_type}
Min Order Size: {min_size}
Size per Third: {size_per_third}
Size per Half: {size_per_half}
Leverage: {signal['leverage']}
Take Profits: {signal['take_profits']}
Stop Loss: {signal['stop_loss']}
            """)

            # Set leverage
            leverage_result = self.bitmart.submit_leverage(
                symbol=symbol,
                leverage=signal['leverage'],
                open_type='cross'
            )
            self.logger.info(f"Leverage set result: {json.dumps(leverage_result, indent=2)}")

            # Submit main order with calculated size
            order_result = self.bitmart.submit_order(
                symbol=symbol,
                side=signal['side'],
                size=size,  # Use calculated size
                leverage=signal['leverage'],
                open_type='cross'
            )
            self.logger.info(f"Main order result: {json.dumps(order_result, indent=2)}")

            if order_result.get('code') == 1000:
                # Set trailing stop at first take profit
                first_tp = str(signal['take_profits'][0])
                is_short = signal['side'] == 4
                
                self.logger.info(f"\nSubmitting Trailing Stop at {first_tp}...")
                trailing_result = self.bitmart.submit_trail_order(
                    symbol=symbol,
                    side=2 if is_short else 3,  # 2=buy_close_short, 3=sell_close_long
                    size=size,
                    leverage=signal['leverage'],
                    open_type='cross',
                    activation_price=first_tp,
                    callback_rate="2",  # 2% callback
                    activation_price_type=1  # 1=last_price
                )
                self.logger.info(f"Trailing Stop result: {json.dumps(trailing_result, indent=2)}")

                # Take profit setup based on position type
                if actual_value > 15.0:
                    # For large positions, only use first take profit with full size
                    take_profits = [
                        {"price": str(signal['take_profits'][0]), "size": size}
                    ]
                elif size_per_third < min_size:
                    # For medium positions, use first two take profits with half size each
                    take_profits = [
                        {"price": str(signal['take_profits'][0]), "size": size_per_half},
                        {"price": str(signal['take_profits'][1]), "size": size_per_half}
                    ]
                else:
                    # For normal positions, use all three take profits
                    take_profits = [
                        {"price": str(price), "size": size_per_third} 
                        for price in signal['take_profits']
                    ]

                self.logger.info(f"Formatted take profits: {json.dumps(take_profits, indent=2)}")

                # Submit take profit plan orders
                for i, tp in enumerate(take_profits, 1):
                    await asyncio.sleep(1)
                    is_short = signal['side'] == 4
                    
                    self.logger.info(f"""
Submitting Take Profit {i}:
Price: {tp['price']}
Size: {tp['size']}
Side: {2 if is_short else 3} (2=buy_close_short, 3=sell_close_long)
Price Way: {2 if is_short else 1} (2=price_way_short, 1=price_way_long)
Is Short: {is_short}
                    """)
                    
                    tp_result = self.bitmart.submit_plan_order(
                        symbol=symbol,
                        side=2 if is_short else 3,  # 2=buy_close_short, 3=sell_close_long
                        size=tp['size'],
                        leverage=signal['leverage'],
                        open_type='cross',
                        trigger_price=tp['price'],
                        order_type='market',
                        price_way=2 if is_short else 1  # 2=price_way_short, 1=price_way_long
                    )
                    self.logger.info(f"Take Profit {i} result: {json.dumps(tp_result, indent=2)}")

                # Submit stop loss using TP/SL endpoint
                await asyncio.sleep(1)
                self.logger.info(f"\nSubmitting Stop Loss at {signal['stop_loss']}...")
                sl_result = self.bitmart.submit_tp_sl_order(
                    symbol=symbol,
                    side=2 if is_short else 3,
                    type="stop_loss",
                    size=size,
                    trigger_price=signal['stop_loss'],
                    price_type=1,
                    plan_category=1
                )
                self.logger.info(f"Stop Loss result: {json.dumps(sl_result, indent=2)}")

        except Exception as e:
            self.logger.error(f"Error executing trade: {e}")
            raise

    def parse_signal(self, message: str) -> Optional[dict]:
        """
        Parse trading signal from message
        Returns a dictionary with parsed signal data or None if message format doesn't match
        """
        try:
            # Split message into lines and remove empty lines
            lines = [line.strip() for line in message.split('\n') if line.strip()]
            
            if len(lines) < 6:  # Minimum required lines for a valid signal
                return None

            # Parse first line for symbol and side
            first_line = lines[0].split()
            if len(first_line) != 2:
                return None
                
            symbol = first_line[0]
            side = PositionSide(first_line[1])
            
            # Initialize variables
            leverage = None
            entry = None
            targets = []
            stoploss = None
            trailing_config = None
            
            # Parse remaining lines
            for line in lines[1:]:
                if line.startswith('Leverage:'):
                    # Handle both Cross and Isolated leverage
                    leverage_match = re.search(r'(Cross|Isolated) (\d+)[xX]', line)
                    if leverage_match:
                        leverage = int(leverage_match.group(2))
                elif line.startswith('Entry'):  # Handle both "Entry:" and "Entry zone:"
                    entry_str = line.split(':')[1].strip()
                    # If entry is a range, take the first value
                    if '-' in entry_str:
                        entry = float(entry_str.split('-')[0].strip())
                    else:
                        entry = float(entry_str)
                elif line.startswith('Target'):
                    target = float(line.split(':')[1].strip())
                    targets.append(target)
                elif line.startswith('Stoploss:'):
                    stoploss = float(line.split(':')[1].strip())
                elif line.startswith('Trailing Configuration:'):
                    stop = re.search(r'Stop: ([^-]+)', line).group(1).strip()
                    trigger = re.search(r'Trigger: ([^)]+)', line).group(1).strip()
                    trailing_config = TrailingConfig(stop=stop, trigger=trigger)

            if not all([leverage, entry, targets, stoploss]):
                raise SignalParsingError("Missing required signal components")

            self.logger.info(f"""
Parsed Signal:
Symbol: {symbol}
Side: {side}
Leverage: {leverage}
Entry: {entry}
Targets: {targets}
Stop Loss: {stoploss}
            """)

            return {
                'symbol': symbol,
                'side': 4 if side == PositionSide.SHORT else 1,
                'leverage': str(leverage),
                'size': 1,
                'entry_price': entry,  # Make sure entry price is included
                'take_profits': targets,
                'stop_loss': stoploss,
                'is_short': side == PositionSide.SHORT
            }

        except Exception as e:
            self.logger.error(f"Error parsing signal: {e}")
            return None

    def parse_cancellation(self, message: str) -> Optional[str]:
        """Parse cancellation message to get symbol"""
        try:
            # Match pattern #SYMBOL/USDT Manually Cancelled
            match = re.match(r'#([A-Z]+)/USDT Manually Cancelled', message)
            if match:
                symbol = f"{match.group(1)}USDT"
                self.logger.info(f"Found cancellation request for {symbol}")
                return symbol
            return None
        except Exception as e:
            self.logger.error(f"Error parsing cancellation: {e}")
            return None

    async def handle_cancellation(self, symbol: str):
        """Handle position cancellation for a symbol"""
        try:
            self.logger.info(f"Processing cancellation for {symbol}")
            
            # Get current position
            position = self.bitmart.get_position(symbol)
            if position.get('code') != 1000:
                self.logger.error(f"Error getting position: {position}")
                return
                
            positions = position.get('data', [])
            if not positions:
                self.logger.info(f"No open position found for {symbol}")
                return
                
            # Close each position for the symbol
            for pos in positions:
                if pos['symbol'] == symbol and int(pos['current_amount']) > 0:
                    self.logger.info(f"Found open position: {json.dumps(pos, indent=2)}")
                    result = self.bitmart.close_position(symbol, pos)
                    self.logger.info(f"Position close result: {json.dumps(result, indent=2)}")
                    
        except Exception as e:
            self.logger.error(f"Error handling cancellation: {e}")

    def run(self):
        asyncio.run(self.start()) 