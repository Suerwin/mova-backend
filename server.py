from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import os
import uuid
import jwt
import bcrypt

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

class UserLogin(BaseModel):
    email: EmailStr
    password: str

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

# ================= REGISTER =================
@api_router.post("/auth/register")
async def register(data: UserCreate):

    try:
        user_exist = await db.users.find_one({"email": data.email})
        if user_exist:
            raise HTTPException(status_code=400, detail="Email sudah terdaftar")

        user_id = str(uuid.uuid4())

        user = {
            "id": user_id,
            "email": data.email,
            "name": data.name,
            "password": hash_password(data.password),
            "created_at": datetime.utcnow()
        }

        await db.users.insert_one(user)

        token = create_token(user_id)

        return {
            "access_token": token,
            "token_type": "bearer"
        }

    except Exception as e:
        import traceback
        print("REGISTER ERROR:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
# ================= LOGIN =================
@api_router.post("/auth/login")
async def login(data: UserLogin):

    user = await db.users.find_one({"email": data.email})

    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Login gagal")

    token = create_token(user["id"])

    return {
        "access_token": token,
        "token_type": "bearer"
    }

# ================= PROFILE =================
@api_router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"]
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
