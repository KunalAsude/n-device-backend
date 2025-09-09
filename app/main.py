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
    "https://localhost:3000",
    "https://n-device-frontend.vercel.app",
    "https://n-device-frontend-git-main-kunalasudes-projects.vercel.app",
    "https://n-device-frontend-kunalasudes-projects.vercel.app",
    os.getenv("FRONTEND_URL", "https://n-device-frontend.vercel.app"),
    "*"  # Temporary for debugging
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,  # Must be False with wildcard
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600
)

class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        # Allow login endpoints (including URL-encoded user IDs)
        if (path.startswith("/auth/login/") and request.method == "POST"):
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

@app.get("/test-cors")
async def test_cors():
    return {"message": "CORS is working!", "timestamp": "2025-09-09"}
