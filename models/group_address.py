from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class GroupAddressBase(BaseModel):
    address: str
    name: str
    dpt: Optional[str] = None
    description: Optional[str] = None
    room: Optional[str] = None
    function: Optional[str] = None
    enabled: bool = True
    is_internal: bool = False  # Internal address (not on KNX bus)

class GroupAddressCreate(GroupAddressBase):
    pass

class GroupAddressUpdate(BaseModel):
    name: Optional[str] = None
    dpt: Optional[str] = None
    description: Optional[str] = None
    room: Optional[str] = None
    function: Optional[str] = None
    enabled: Optional[bool] = None
    is_internal: Optional[bool] = None

class GroupAddressResponse(GroupAddressBase):
    id: int
    last_value: Optional[str] = None
    last_updated: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
