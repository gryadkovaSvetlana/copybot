import asyncio
from config import Config, TelegramConfig, BitmartConfig
from bitmart_client import BitmartClient
import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_order():
    config = Config(
        telegram=TelegramConfig(
            api_id="12345",
            api_hash="test",
            phone="test",
            channel_username="test"
        ),
        bitmart=BitmartConfig(
            api_key=os.getenv("BITMART_API_KEY"),
            api_secret=os.getenv("BITMART_API_SECRET"),
            memo=os.getenv("BITMART_MEMO")
        )
    )

    bitmart = BitmartClient(config.bitmart)
    
    try:
        symbol = "BCHUSDT"
        side = 1  # 1 for LONG
        leverage = "20"
        size = 10
        
        # Take profit levels
        take_profits = [
            {"price": "557.40", "size": size // 3},
            {"price": "567.75", "size": size // 3},
            {"price": "576.50", "size": size // 3}
        ]
        stop_loss = "400.85"

        logger.info(f"Opening position:")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Side: {'LONG' if side == 1 else 'SHORT'}")
        logger.info(f"Size: {size}")
        logger.info(f"Leverage: {leverage}x")
        logger.info(f"Take Profits: {take_profits}")
        logger.info(f"Stop Loss: {stop_loss}")

        # Set leverage
        logger.info("\nSetting leverage...")
        leverage_result = bitmart.submit_leverage(
            symbol=symbol,
            leverage=leverage,
            open_type='cross'
        )
        logger.info(f"Leverage result: {json.dumps(leverage_result, indent=2)}")

        # Submit main position
        order_result = bitmart.submit_order(
            symbol=symbol,
            side=side,
            size=size,
            leverage=leverage,
            open_type='cross'
        )
        logger.info(f"Main order result: {json.dumps(order_result, indent=2)}")

        if order_result.get('code') == 1000:
            # Submit take profit plan orders
            for i, tp in enumerate(take_profits, 1):
                await asyncio.sleep(1)
                logger.info(f"\nSubmitting Take Profit Plan {i} at {tp['price']} for {tp['size']} contracts...")
                tp_result = bitmart.submit_plan_order(
                    symbol=symbol,
                    side=3,  # 3 for sell_close_long
                    size=tp['size'],
                    leverage=leverage,
                    open_type='cross',
                    trigger_price=tp['price'],
                    order_type='limit',
                    execute_price=tp['price']
                )
                logger.info(f"Take Profit Plan {i} result: {json.dumps(tp_result, indent=2)}")

            # Submit stop loss using TP/SL endpoint
            await asyncio.sleep(1)
            logger.info(f"\nSubmitting Stop Loss at {stop_loss}...")
            sl_result = bitmart.submit_tp_sl_order(
                symbol=symbol,
                side=3,  # 3 for sell_close_long
                type="stop_loss",
                size=size,  # Full position size
                trigger_price=stop_loss,
                price_type=1,  # -1=last_price
                plan_category=1  # 1=TP/SL (not position-level)
            )
            logger.info(f"Stop Loss result: {json.dumps(sl_result, indent=2)}")

    except Exception as e:
        logger.error(f"Error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_order()) 