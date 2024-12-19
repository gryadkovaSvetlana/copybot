import asyncio
from config import Config, TelegramConfig, BitmartConfig
from bitmart_client import BitmartClient
import json
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_bitmart_connection():
    # Create config with just BitMart credentials
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
        # Verify API credentials are loaded
        logger.info("Loaded API credentials:")
        logger.info(f"API Key: {'*' * (len(os.getenv('BITMART_API_KEY', '')) - 4)}{os.getenv('BITMART_API_KEY', '')[-4:]}")
        logger.info(f"API Secret: {'*' * (len(os.getenv('BITMART_API_SECRET', '')) - 4)}{os.getenv('BITMART_API_SECRET', '')[-4:]}")
        logger.info(f"Memo: {os.getenv('BITMART_MEMO', '')}")

        # Test 1: Get account assets
        logger.info("Testing account assets...")
        assets = bitmart.get_contract_assets()
        logger.info(f"Account assets: {json.dumps(assets, indent=2)}")

        # Test 2: Get contract details for a symbol
        symbol = "BTCUSDT"  # Example symbol
        logger.info(f"\nTesting contract details for {symbol}...")
        details = bitmart.get_contract_details(symbol)
        logger.info(f"Contract details: {json.dumps(details, indent=2)}")

        # Test 3: Get current positions
        logger.info("\nTesting position details...")
        positions = bitmart.get_position()
        logger.info(f"Current positions: {json.dumps(positions, indent=2)}")

    except Exception as e:
        logger.error(f"Error testing BitMart connection: {e}")

if __name__ == "__main__":
    asyncio.run(test_bitmart_connection()) 