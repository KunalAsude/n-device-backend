from fastapi import APIRouter, HTTPException
from app.database import sessions_collection, users_collection
import datetime
import os
from dotenv import load_dotenv

load_dotenv()
max_devices = int(os.getenv("MAX_DEVICES", 3))

router = APIRouter()

@router.post("/login/{user_id}")
async def login(user_id: str, device_id: str,force_logout_device_id:str=None):
    from app.models import UserModel
    user = await users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = await sessions_collection.find_one({"user_id": user_id, "device_id": device_id})
    if existing:
        user["_id"] = str(user["_id"]) if "_id" in user else None
        return {"status": "already_logged_in", "device_id": device_id, "user": UserModel(**user)}

    if force_logout_device_id:
        await sessions_collection.delete_one({'user_id':user_id,'device_id':force_logout_device_id})

    active_sessions = await sessions_collection.find({"user_id": user_id}).to_list(None)
    for session in active_sessions:
        if "_id" in session:
            session["_id"] = str(session["_id"])
    if len(active_sessions) >= max_devices:
        return {
            "status": "limit_reached",
            "message": f"Already {max_devices} devices logged in!",
            "active_sessions": active_sessions
        }

    session = {
        "user_id": user_id,
        "device_id": device_id,
        "created_at": datetime.datetime.utcnow()
    }
    await sessions_collection.insert_one(session)

    user["_id"] = str(user["_id"]) if "_id" in user else None
    return {"status": "logged_in", "device_id": device_id, "user": UserModel(**user)}


@router.post('/logout/{device_id}')
async def logout(device_id:str):
    result = await sessions_collection.delete_one({'device_id':device_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404,detail='session not found')
    return {'status':'logged_out','device_id':device_id}


@router.get("/me/{user_id}")
async def get_user_info(user_id: str):
    from app.models import UserModel
    user = await users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["_id"] = str(user["_id"]) if "_id" in user else None
    return UserModel(**user)


# only for testing
from fastapi import Body
from fastapi.encoders import jsonable_encoder
import uuid
@router.post("/create_user")
async def create_user(full_name: str = Body(...), phone: str = Body(...)):

    user_id = str(uuid.uuid4())
    
    existing = await users_collection.find_one({"phone": phone})
    if existing:
        return {"status": "error", "message": "Phone number already registered", "user_id": existing["user_id"]}
    
    user = {
        "user_id": user_id,
        "full_name": full_name,
        "phone": phone
    }
    
    await users_collection.insert_one(user)
    return {"status": "created", "user_id": user_id, "full_name": full_name, "phone": phone}