from dataclasses import dataclass

@dataclass
class TelegramConfig:
    api_id: str
    api_hash: str
    phone: str
    channel_username: str

@dataclass
class BitmartConfig:
    api_key: str
    api_secret: str
    memo: str  # Bitmart requires memo for authentication

@dataclass
class Config:
    telegram: TelegramConfig
    bitmart: BitmartConfig 