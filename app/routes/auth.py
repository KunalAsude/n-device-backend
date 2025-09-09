from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
from urllib.parse import unquote
from app.models import UserResponse, LoginRequest, Device, SessionInfo, LoginResponse, DevicesResponse, UserUpdate
from app.database import sessions_collection, users_collection
from bson import ObjectId

router = APIRouter()

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

async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    return await users_collection.find_one({"user_id": user_id})

async def create_or_update_user(user_id: str, full_name: str, email: str, phone: str) -> Dict[str, Any]:
    existing_user = await get_user_by_id(user_id)
    
    if existing_user:
        update_data = {
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "updated_at": datetime.utcnow()
        }
        await users_collection.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
        existing_user.update(update_data)
        return existing_user
    else:
        user_doc = {
            "user_id": user_id,
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "device_limit": 3,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await users_collection.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        return user_doc

async def get_active_sessions(user_id: str) -> List[Dict[str, Any]]:
    active_sessions = await sessions_collection.find({
        "user_id": user_id,
        "is_active": True
    }).sort("created_at", -1).to_list(None)
    
    if not active_sessions:
        legacy_sessions = await sessions_collection.find({
            "user_id": user_id,
            "is_active": {"$exists": False}
        }).sort("created_at", -1).to_list(None)
        return legacy_sessions
    
    return active_sessions

async def create_session(user_id: str, device_id: str, device_name: str) -> Dict[str, Any]:
    session_doc = {
        "session_id": str(uuid.uuid4()),
        "user_id": user_id,
        "device_id": device_id,
        "device_name": device_name,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "last_active": datetime.utcnow()
    }
    
    result = await sessions_collection.insert_one(session_doc)
    session_doc["_id"] = result.inserted_id
    return session_doc

async def logout_device(device_id: str) -> bool:
    result = await sessions_collection.update_one(
        {"device_id": device_id, "is_active": True},
        {"$set": {"is_active": False, "logged_out_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        existing_session = await sessions_collection.find_one({"device_id": device_id})
        if existing_session:
            result = await sessions_collection.update_one(
                {"device_id": device_id},
                {"$set": {"is_active": False, "logged_out_at": datetime.utcnow()}}
            )
            return result.modified_count > 0
        else:
            return False
    
    return result.modified_count > 0

async def cleanup_old_sessions(user_id: str, device_id: str):
    await sessions_collection.delete_many({
        "user_id": user_id,
        "device_id": device_id,
        "is_active": False
    })

async def update_session_activity(device_id: str):
    await sessions_collection.update_one(
        {"device_id": device_id, "is_active": True},
        {"$set": {"last_active": datetime.utcnow()}}
    )

@router.post("/login/{user_id}", response_model=LoginResponse)
async def login_device(user_id: str, login_data: LoginRequest):
    # Decode URL-encoded user_id
    user_id = unquote(user_id)
    
    user = await create_or_update_user(
        user_id=user_id,
        full_name=login_data.full_name,
        email=login_data.email,
        phone=login_data.phone
    )
    
    existing_session = await sessions_collection.find_one({
        "user_id": user_id,
        "device_id": login_data.device_id
    })
    
    if existing_session:
        await sessions_collection.update_one(
            {"_id": existing_session["_id"]},
            {"$set": {
                "is_active": True,
                "device_name": login_data.device_name,
                "last_active": datetime.utcnow(),
                "logged_out_at": None
            }}
        )
        return LoginResponse(
            status="already_logged_in",
            user=UserResponse(**user),
            message="Device session reactivated"
        )
    
    active_sessions = await get_active_sessions(user_id)
    
    if len(active_sessions) >= user["device_limit"] and not login_data.force:
        return LoginResponse(
            status="limit_reached",
            active_sessions=[
                SessionInfo(
                    device_id=session["device_id"],
                    device_name=session["device_name"],
                    created_at=session["created_at"],
                    last_active=session["last_active"]
                ) for session in active_sessions
            ],
            message=f"Device limit of {user['device_limit']} reached"
        )
    
    if login_data.force and len(active_sessions) >= user["device_limit"]:
        oldest_session = min(active_sessions, key=lambda x: x["last_active"])
        await logout_device(oldest_session["device_id"])
    
    await create_session(user_id, login_data.device_id, login_data.device_name)
    
    return LoginResponse(
        status="logged_in",
        user=UserResponse(**user),
        message="Successfully logged in"
    )

@router.get("/me/{user_id}", response_model=UserResponse)
async def get_user_info(user_id: str):
    # Decode URL-encoded user_id
    user_id = unquote(user_id)
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(**user)

@router.put("/user/{user_id}", response_model=UserResponse)
async def update_user_info(user_id: str, user_update: UserUpdate):
    # Decode URL-encoded user_id
    user_id = unquote(user_id)
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = {}
    if user_update.phone is not None:
        update_data["phone"] = user_update.phone
    if user_update.full_name is not None:
        update_data["full_name"] = user_update.full_name
    if user_update.email is not None:
        update_data["email"] = user_update.email
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields provided for update")
    
    update_data["updated_at"] = datetime.utcnow()
    
    await users_collection.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    
    updated_user = await get_user_by_id(user_id)
    return UserResponse(**updated_user)

@router.get("/devices/{user_id}", response_model=DevicesResponse)
async def get_user_devices(user_id: str):
    try:
        # Decode URL-encoded user_id
        user_id = unquote(user_id)
        user = await get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        active_sessions = await get_active_sessions(user_id)
        
        if not active_sessions:
            return DevicesResponse(devices=[], total_count=0)
        
        devices = []
        for session in active_sessions:
            try:
                device = Device(
                    device_id=session["device_id"],
                    device_name=session.get("device_name", "Unknown Device"),
                    last_active=session.get("last_active", session.get("created_at", datetime.utcnow())),
                    is_current=False
                )
                devices.append(device)
            except Exception:
                continue
        
        return DevicesResponse(devices=devices, total_count=len(devices))
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch devices: {str(e)}")

@router.post("/logout/{device_id}")
async def logout_device_endpoint(device_id: str):
    try:
        session = await sessions_collection.find_one({"device_id": device_id})
        success = await logout_device(device_id)
        
        if not success:
            any_session = await sessions_collection.find_one({"device_id": device_id})
            if any_session:
                return {"message": "Device already logged out", "device_id": device_id}
            else:
                raise HTTPException(status_code=404, detail="Device not found")
        
        if session:
            await cleanup_old_sessions(session["user_id"], device_id)
        
        return {"message": "Device logged out successfully", "device_id": device_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to logout device: {str(e)}")