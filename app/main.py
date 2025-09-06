from fastapi import FastAPI
from app.routes import auth


app = FastAPI(title="N-Device Backend API")

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])


@app.get("/")
async def root():
    return {"message": "Welcome to the N-Device Backend API"}