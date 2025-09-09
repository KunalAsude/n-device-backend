from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class LoginRequest(BaseModel):
    device_id: str
    device_name: str
    full_name: str
    email: str
    phone: str
    force: bool = False

class UserResponse(BaseModel):
    user_id: str
    full_name: str
    email: str
    phone: str
    device_limit: int
    created_at: datetime
    updated_at: datetime

class UserUpdate(BaseModel):
    phone: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None

class Device(BaseModel):
    device_id: str
    device_name: str
    last_active: datetime
    is_current: bool = False

class SessionInfo(BaseModel):
    device_id: str
    device_name: str
    created_at: datetime
    last_active: datetime

class LoginResponse(BaseModel):
    status: str
    user: Optional[UserResponse] = None
    active_sessions: Optional[List[SessionInfo]] = None
    message: Optional[str] = None

class DevicesResponse(BaseModel):
    devices: List[Device]
    total_count: int
