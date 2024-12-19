import asyncio
from config import Config, TelegramConfig, BitmartConfig
from signal_monitor import SignalMonitor
import json

# Test signals
TEST_SIGNALS = [
    """SOLUSDT SHORT
Leverage: Cross 20x
Entry: 219.59
Target 1: 214.98
Target 2: 210.81
Target 3: 206.20
Stoploss: 225.74
Trailing Configuration: Stop: Breakeven - Trigger: Target (1)""",

    """BCHUSDT LONG
Leverage: Cross 20x
Entry: 545.39
Target 1: 557.39
Target 2: 567.75
Target 3: 576.48
Stoploss: 526.85""",
]

async def test_parser():
    # Create test config
    config = Config(
        telegram=TelegramConfig(
            api_id="12345",
            api_hash="test",
            phone="test",
            channel_username="test"
        ),
        bitmart=BitmartConfig(
            api_key="test",
            api_secret="test",
            memo="test"
        )
    )

    monitor = SignalMonitor(config)

    # Test each signal
    for signal_text in TEST_SIGNALS:
        print("\nTesting signal:")
        print("-" * 50)
        print(signal_text)
        print("-" * 50)
        
        result = monitor.parse_signal(signal_text)
        print("\nParsed result:")
        print("-" * 50)
        print(result)
        print("-" * 50)

    signal = """BCHUSDT SHORT
Leverage: Cross 20x
Entry: 528.13
Target 1: 460.00
Target 2: 470.00
Target 3: 480.00
Stoploss: 549.26"""

    # Parse and print the result
    parsed = monitor.parse_signal(signal)
    print(json.dumps(parsed, indent=2))

if __name__ == "__main__":
    asyncio.run(test_parser()) 