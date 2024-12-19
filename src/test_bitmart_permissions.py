from bitmart.api_contract import APIContract
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_permissions():
    api_key = os.getenv("BITMART_API_KEY")
    secret_key = os.getenv("BITMART_API_SECRET")
    memo = os.getenv("BITMART_MEMO")

    contractAPI = APIContract(api_key, secret_key, memo, timeout=(3, 10))

    try:
        # Test 1: Get account details
        logger.info("Testing account access...")
        account = contractAPI.get_account_assets()
        logger.info(f"Account info: {account}")

        # Test 2: Get available contracts
        logger.info("\nTesting contract access...")
        contracts = contractAPI.get_contracts_details()
        logger.info(f"Available contracts: {contracts}")

    except Exception as e:
        logger.error(f"Error checking permissions: {e}")

if __name__ == '__main__':
    test_permissions() 