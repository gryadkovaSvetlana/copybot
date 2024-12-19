from config import Config, TelegramConfig, BitmartConfig
from signal_monitor import SignalMonitor
from dotenv import load_dotenv
import os
import logging
import asyncio

async def main():
    # Load environment variables
    load_dotenv()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
        # Create config
        config = Config(
            telegram=TelegramConfig(
                api_id=os.getenv("TELEGRAM_API_ID"),
                api_hash=os.getenv("TELEGRAM_API_HASH"),
                phone=os.getenv("TELEGRAM_PHONE"),
                channel_username=os.getenv("TELEGRAM_CHANNEL")
            ),
            bitmart=BitmartConfig(
                api_key=os.getenv("BITMART_API_KEY"),
                api_secret=os.getenv("BITMART_API_SECRET"),
                memo=os.getenv("BITMART_MEMO")
            )
        )
        
        # Create and start monitor
        monitor = SignalMonitor(config)
        logger.info("Connecting to Telegram...")
        await monitor.connect()
        logger.info("Starting channel monitor...")
        await monitor.monitor_channel()
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 