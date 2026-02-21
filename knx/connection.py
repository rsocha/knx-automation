import asyncio
import logging
import re
from typing import Optional, Callable, List
from datetime import datetime

from xknx import XKNX
from xknx.io import ConnectionConfig, ConnectionType
from xknx.core import XknxConnectionState
from xknx.telegram import Telegram
from xknx.telegram.address import GroupAddress
from xknx.dpt import DPTArray, DPTBinary

from config import settings
from utils import db_manager

logger = logging.getLogger(__name__)


class KNXConnectionManager:
    def __init__(self):
        self.xknx: Optional[XKNX] = None
        self.telegram_callbacks: List[Callable] = []
        self.is_connected = False
        self._last_telegrams = []
        self._max_telegram_history = 100
        self._gateway_ip = None
        self._gateway_port = None
        self._connection_type = None
    
    async def connect(self):
        try:
            if settings.knx_use_routing:
                connection_type = ConnectionType.ROUTING
                self._connection_type = "ROUTING"
            elif settings.knx_use_tunneling:
                connection_type = ConnectionType.TUNNELING
                self._connection_type = "TUNNELING"
            else:
                logger.error("No connection type specified!")
                return False
            
            self._gateway_ip = settings.knx_gateway_ip
            self._gateway_port = settings.knx_gateway_port
            
            connection_config = ConnectionConfig(
                connection_type=connection_type,
                gateway_ip=settings.knx_gateway_ip,
                gateway_port=settings.knx_gateway_port,
            )
            
            self.xknx = XKNX(
                connection_config=connection_config,
                connection_state_changed_cb=self._connection_state_changed,
                telegram_received_cb=self._telegram_received_callback
            )
            
            await self.xknx.start()
            logger.info(f"Connected to KNX gateway at {settings.knx_gateway_ip}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to KNX gateway: {e}")
            self.is_connected = False
            return False
    
    async def _connection_state_changed(self, state: XknxConnectionState):
        if state == XknxConnectionState.CONNECTED:
            self.is_connected = True
            logger.info(f"KNX connection established to {self._gateway_ip}")
        elif state == XknxConnectionState.DISCONNECTED:
            self.is_connected = False
            logger.warning("KNX connection lost")
        else:
            logger.info(f"KNX connection state: {state}")
    
    async def disconnect(self):
        if self.xknx:
            await self.xknx.stop()
            self.is_connected = False
            logger.info("Disconnected from KNX gateway")
    
    async def _telegram_received_callback(self, telegram: Telegram):
        try:
            from xknx.telegram.apci import GroupValueWrite, GroupValueResponse, GroupValueRead
            
            source = str(telegram.source_address) if telegram.source_address else "unknown"
            destination = str(telegram.destination_address) if telegram.destination_address else "unknown"
            
            # Determine telegram type
            is_read_request = isinstance(telegram.payload, GroupValueRead)
            is_write_or_response = isinstance(telegram.payload, (GroupValueWrite, GroupValueResponse))
            
            payload_value = None
            raw_bytes = None
            
            if is_read_request:
                # Don't store read requests as values, just log them
                telegram_data = {
                    "timestamp": datetime.now(),
                    "source": source,
                    "destination": destination,
                    "payload": "READ",
                    "direction": "incoming"
                }
                self._last_telegrams.append(telegram_data)
                if len(self._last_telegrams) > self._max_telegram_history:
                    self._last_telegrams.pop(0)
                return  # Don't update DB with read requests
            
            # Extract raw bytes for Write/Response telegrams
            if is_write_or_response and hasattr(telegram.payload, 'value'):
                inner_payload = telegram.payload.value
                if isinstance(inner_payload, DPTBinary):
                    raw_bytes = bytes([inner_payload.value])
                    payload_value = str(inner_payload.value)
                elif isinstance(inner_payload, DPTArray):
                    if inner_payload.value:
                        # xknx 2.12.0: value can be tuple or bytes
                        raw = inner_payload.value
                        if isinstance(raw, tuple):
                            raw_bytes = bytes(raw)
                        elif isinstance(raw, (bytes, bytearray)):
                            raw_bytes = bytes(raw)
                        else:
                            raw_bytes = bytes([raw]) if isinstance(raw, int) else None
                    else:
                        raw_bytes = bytes([0])
                elif inner_payload is not None:
                    payload_value = str(inner_payload)
            
            # Try to decode based on DPT if we have raw bytes
            if raw_bytes is not None:
                # Try to get DPT from database
                dpt = await self._get_address_dpt(destination)
                decoded = self._decode_dpt(raw_bytes, dpt)
                if decoded is not None:
                    payload_value = str(decoded)
                else:
                    # Fallback to hex
                    payload_value = raw_bytes.hex()
            
            # Fallback extraction if above didn't work
            if payload_value is None:
                if hasattr(telegram.payload, 'value'):
                    inner = telegram.payload.value
                    if isinstance(inner, DPTBinary):
                        payload_value = str(inner.value)
                    elif isinstance(inner, DPTArray):
                        raw = inner.value
                        if raw:
                            if isinstance(raw, tuple):
                                payload_value = ''.join(f'{b:02x}' for b in raw)
                            elif isinstance(raw, (bytes, bytearray)):
                                payload_value = raw.hex()
                            else:
                                payload_value = str(raw)
                        else:
                            payload_value = "00"
                    elif isinstance(inner, tuple):
                        payload_value = ''.join(f'{b:02x}' for b in inner)
                    elif isinstance(inner, (bytes, bytearray)):
                        payload_value = inner.hex()
                    elif inner is not None:
                        payload_value = str(inner)
            
            # Last resort: try to parse from string representation
            if payload_value is None:
                payload_str = str(telegram.payload)
                # Skip if it's a read request string
                if 'GroupValueRead' in payload_str:
                    return
                match = re.search(r'value="?([0-9a-fA-F]+)"?', payload_str)
                if match:
                    payload_value = match.group(1)
            
            # Skip if we still have no valid value or if it contains Read-related strings
            if payload_value is None:
                return
            if 'Read' in str(payload_value) or 'GroupValue' in str(payload_value) or '<' in str(payload_value):
                logger.debug(f"Skipping invalid payload: {payload_value}")
                return
            
            telegram_data = {
                "timestamp": datetime.now(),
                "source": source,
                "destination": destination,
                "payload": payload_value,
                "direction": "incoming"
            }
            
            self._last_telegrams.append(telegram_data)
            if len(self._last_telegrams) > self._max_telegram_history:
                self._last_telegrams.pop(0)
            
            # Only update DB with actual values, not read requests
            if telegram.destination_address and payload_value:
                try:
                    await db_manager.update_group_address_value(destination, payload_value)
                    logger.debug(f"Updated {destination} = {payload_value}")
                except Exception as e:
                    logger.debug(f"Could not update address value: {e}")
            
            for callback in self.telegram_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(telegram_data)
                    else:
                        callback(telegram_data)
                except Exception as e:
                    logger.error(f"Error in telegram callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing telegram: {e}")
    
    def register_telegram_callback(self, callback: Callable):
        if callback not in self.telegram_callbacks:
            self.telegram_callbacks.append(callback)
    
    def unregister_telegram_callback(self, callback: Callable):
        if callback in self.telegram_callbacks:
            self.telegram_callbacks.remove(callback)
    
    async def send_telegram(self, group_address: str, value):
        if not self.xknx or not self.is_connected:
            logger.error("Cannot send telegram: not connected")
            return False
        
        try:
            ga = GroupAddress(group_address)
            
            if isinstance(value, bool):
                payload = DPTBinary(1 if value else 0)
            elif isinstance(value, int):
                if value in [0, 1]:
                    payload = DPTBinary(value)
                else:
                    payload = DPTArray(value.to_bytes(2, 'big'))
            else:
                payload = DPTBinary(1 if value else 0)
            
            from xknx.telegram.apci import GroupValueWrite
            
            telegram = Telegram(
                destination_address=ga,
                payload=GroupValueWrite(payload)
            )
            
            await self.xknx.telegrams.put(telegram)
            logger.info(f"Sent telegram to {group_address}: {value}")
            
            telegram_data = {
                "timestamp": datetime.now(),
                "source": "local",
                "destination": group_address,
                "payload": str(value),
                "direction": "outgoing"
            }
            self._last_telegrams.append(telegram_data)
            if len(self._last_telegrams) > self._max_telegram_history:
                self._last_telegrams.pop(0)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send telegram: {e}")
            return False
    
    def get_recent_telegrams(self, count: int = 50):
        return self._last_telegrams[-count:]
    
    async def _get_address_dpt(self, address: str) -> str:
        """Get DPT for an address from the database"""
        try:
            addr = await db_manager.get_group_address(address)
            if addr and addr.dpt:
                return addr.dpt
        except Exception as e:
            logger.debug(f"Could not get DPT for {address}: {e}")
        return None
    
    def _decode_dpt(self, raw_bytes: bytes, dpt: str) -> any:
        """Decode raw bytes based on DPT"""
        if not raw_bytes or not dpt:
            return None
        
        try:
            dpt_main = dpt.split('.')[0] if '.' in dpt else dpt
            
            # DPT 1 - Boolean (1 bit)
            if dpt_main == '1':
                return bool(raw_bytes[0] & 0x01)
            
            # DPT 5 - Unsigned 8-bit (0-255 or 0-100%)
            elif dpt_main == '5':
                if len(raw_bytes) >= 1:
                    val = raw_bytes[0]
                    if dpt == '5.001':  # Percentage
                        return round(val * 100 / 255, 1)
                    return val
            
            # DPT 6 - Signed 8-bit
            elif dpt_main == '6':
                if len(raw_bytes) >= 1:
                    val = raw_bytes[0]
                    if val > 127:
                        val -= 256
                    return val
            
            # DPT 7 - Unsigned 16-bit
            elif dpt_main == '7':
                if len(raw_bytes) >= 2:
                    return (raw_bytes[0] << 8) | raw_bytes[1]
            
            # DPT 8 - Signed 16-bit
            elif dpt_main == '8':
                if len(raw_bytes) >= 2:
                    val = (raw_bytes[0] << 8) | raw_bytes[1]
                    if val > 32767:
                        val -= 65536
                    return val
            
            # DPT 9 - 2-byte float (temperature, humidity, etc.)
            elif dpt_main == '9':
                if len(raw_bytes) >= 2:
                    # KNX 2-byte float encoding
                    sign = (raw_bytes[0] >> 7) & 0x01
                    exp = (raw_bytes[0] >> 3) & 0x0F
                    mant = ((raw_bytes[0] & 0x07) << 8) | raw_bytes[1]
                    
                    if sign:
                        mant = mant - 2048
                    
                    value = (0.01 * mant) * (2 ** exp)
                    return round(value, 2)
            
            # DPT 12 - Unsigned 32-bit
            elif dpt_main == '12':
                if len(raw_bytes) >= 4:
                    return (raw_bytes[0] << 24) | (raw_bytes[1] << 16) | (raw_bytes[2] << 8) | raw_bytes[3]
            
            # DPT 13 - Signed 32-bit
            elif dpt_main == '13':
                if len(raw_bytes) >= 4:
                    val = (raw_bytes[0] << 24) | (raw_bytes[1] << 16) | (raw_bytes[2] << 8) | raw_bytes[3]
                    if val > 2147483647:
                        val -= 4294967296
                    return val
            
            # DPT 14 - 4-byte float
            elif dpt_main == '14':
                if len(raw_bytes) >= 4:
                    import struct
                    return round(struct.unpack('>f', raw_bytes[:4])[0], 4)
            
        except Exception as e:
            logger.debug(f"DPT decode error for {dpt}: {e}")
        
        return None


knx_manager = KNXConnectionManager()
