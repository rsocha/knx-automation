import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    knx_gateway_ip: str = os.getenv("KNX_GATEWAY_IP", "192.168.0.66")
    knx_gateway_port: int = int(os.getenv("KNX_GATEWAY_PORT", "3671"))
    knx_use_tunneling: bool = os.getenv("KNX_USE_TUNNELING", "true").lower() == "true"
    knx_use_routing: bool = os.getenv("KNX_USE_ROUTING", "false").lower() == "true"
    database_url: str = "sqlite+aiosqlite:///./data/knx_automation.db"
    
    class Config:
        env_file = ".env"

settings = Settings()
