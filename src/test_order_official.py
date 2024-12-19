from bitmart.api_contract import APIContract
import logging
import os
import time
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_order():
    api_key = os.getenv("BITMART_API_KEY")
    secret_key = os.getenv("BITMART_API_SECRET")
    memo = os.getenv("BITMART_MEMO")

    contractAPI = APIContract(api_key, secret_key, memo, timeout=(3, 10))

    try:
        response = contractAPI.post_submit_order(
            contract_symbol='BCHUSDT',
            client_order_id=f"BOT_{int(time.time())}",
            side=4,  # SHORT
            mode=1,
            type='market',
            leverage='20',
            open_type='cross',
            size=10
        )
        
        logger.info(f"Full API Response: {response}")
        
        if response[0]['code'] == 1000:
            logger.info(f'Order placed successfully: {response[0]}')
        else:
            logger.error(f'Order failed: {response[0]["message"]}')
            
    except Exception as e:
        logger.error(f"Error placing order: {e}")

if __name__ == '__main__':
    test_order() 