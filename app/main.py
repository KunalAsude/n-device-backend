from app.routes import auth
from fastapi import Request,FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import sessions_collection
from starlette.responses import JSONResponse



app = FastAPI(title="N-Device Backend API")


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request:Request, call_next):
        device_id = request.headers.get("X-Device-ID")
        user_id = request.headers.get("X-User-ID")

        if user_id and device_id:
            session = await sessions_collection.find_one({'user_id':user_id,'device_id':device_id})
            if not session:
                return JSONResponse({"status": "force_logged_out", "message": "You were logged out from another device."}, status_code=403)
            
        response = await call_next(request)
        return response
app.add_middleware(SessionMiddleware)
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])


@app.get("/")
async def root():
    return {"message": "Welcome to the N-Device Backend API"}