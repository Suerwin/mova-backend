from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
import os
import uuid
import jwt
import bcrypt
import random
import string

# ================= ENV =================
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "mova")

if not MONGO_URL:
    raise Exception("MONGO_URL belum diset di ENV")

# ================= DB =================
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ================= APP =================
app = FastAPI()
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# ================= CONFIG =================
JWT_SECRET = os.getenv("JWT_SECRET", "mova-secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7

# ================= MODELS =================
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    serial_number: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ================= HELPERS =================
def hash_password(password: str):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str):
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def generate_serial():
    chars = string.ascii_uppercase + string.digits
    parts = [''.join(random.choices(chars, k=4)) for _ in range(3)]
    return f"MOVA-{parts[0]}-{parts[1]}-{parts[2]}"

# ================= AUTH =================
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    user = await db.users.find_one({"id": payload["user_id"]})

    if not user:
        raise HTTPException(status_code=401, detail="User tidak valid")
    return user

# ================= ROUTES =================

@api_router.get("/")
def root():
    return {"status": "MOVA API OK"}

# -------- REGISTER --------
@api_router.post("/auth/register")
async def register(data: UserCreate):
    serial = await db.serial_numbers.find_one({"serial_number": data.serial_number})

    if not serial:
        raise HTTPException(status_code=400, detail="Serial tidak ditemukan")

    if serial.get("is_used"):
        raise HTTPException(status_code=400, detail="Serial sudah dipakai")

    user_id = str(uuid.uuid4())

    user = {
        "id": user_id,
        "email": data.email,
        "name": data.name,
        "password": hash_password(data.password),
        "serial_number": data.serial_number,
        "created_at": datetime.utcnow()
    }

    await db.users.insert_one(user)

    await db.serial_numbers.update_one(
        {"serial_number": data.serial_number},
        {"$set": {
            "is_used": True,
            "used_at": datetime.utcnow(),
            "used_by": data.email
        }}
    )

    token = create_token(user_id)

    return {"access_token": token, "token_type": "bearer"}

# -------- LOGIN --------
@api_router.post("/auth/login")
async def login(data: UserLogin):
    user = await db.users.find_one({"email": data.email})

    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Login gagal")

    token = create_token(user["id"])
    return {"access_token": token, "token_type": "bearer"}

# -------- GENERATE SERIAL (ADMIN SIMPLE VERSION) --------
@api_router.post("/serial/generate")
async def generate_serials(count: int = 1):
    result = []

    for _ in range(min(count, 50)):
        serial = generate_serial()

        while await db.serial_numbers.find_one({"serial_number": serial}):
            serial = generate_serial()

        data = {
            "serial_number": serial,
            "is_used": False,
            "created_at": datetime.utcnow()
        }

        await db.serial_numbers.insert_one(data)
        result.append(data)

    return result

# -------- CHECK SERIAL --------
@api_router.get("/serial/check/{serial}")
async def check_serial(serial: str):
    data = await db.serial_numbers.find_one({"serial_number": serial})

    if not data:
        return {"valid": False}

    return {
        "valid": not data.get("is_used", False)
    }

# ================= APP SETUP =================
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
