from app.routes import auth
from fastapi import Request, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import sessions_collection
from starlette.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="N-Device Backend API")

origins = [
    "http://localhost:3000",
    os.getenv("FRONTEND_URL", "http://localhost:3000")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if (path == "/auth/login" and request.method == "POST"):
            return await call_next(request)

        user_id = request.headers.get("X-User-ID")
        device_id = request.headers.get("X-Device-ID")

        if user_id and device_id:
            session = await sessions_collection.find_one({"user_id": user_id, "device_id": device_id})
            if not session:
                return JSONResponse(
                    {"status": "force_logged_out", "message": "You were logged out from another device."},
                    status_code=403
                )

        return await call_next(request)

app.add_middleware(SessionMiddleware)
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

@app.get("/")
async def root():
    return {"message": "Welcome to the N-Device Backend API"}
