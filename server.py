from pymongo import MongoClient
import os
from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["mova"]
MONGO_URL = os.getenv("MONGO_URL")
import uvicorn
from fastapi import FastAPI
app = FastAPI()
@app.get("/")
def home():
    return {"status": "ok"}
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
import logging
import io
import csv
from pymongo import MongoClient
client = MongoClient(
    MONGO_URL,
    tls=True
)
db = client["mova"]
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import bcrypt
import jwt
import re

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Settings
JWT_SECRET = os.environ.get('JWT_SECRET', 'mova-secret-key-2024')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24 * 7  # 7 days

security = HTTPBearer()

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ==================== Models ====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    serial_number: str  # Required serial number

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    serial_number: str
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class SerialNumberCreate(BaseModel):
    count: int = 1  # How many serial numbers to generate

class SerialNumberResponse(BaseModel):
    serial_number: str
    is_used: bool
    used_by_email: Optional[str] = None
    created_at: datetime
    used_at: Optional[datetime] = None

class FeatureItem(BaseModel):
    icon: str = "star"
    title: str
    description: str
    image: Optional[str] = None  # base64 image
    video: Optional[str] = None  # base64 video or video URL

class LandingPageCreate(BaseModel):
    hero_title: str
    hero_subtitle: str
    hero_image: Optional[str] = None  # base64
    features: List[FeatureItem] = []
    whatsapp_number: str
    cta_text: str = "Hubungi Kami"
    primary_color: str = "#4F46E5"

class LandingPageUpdate(BaseModel):
    hero_title: Optional[str] = None
    hero_subtitle: Optional[str] = None
    hero_image: Optional[str] = None
    features: Optional[List[FeatureItem]] = None
    whatsapp_number: Optional[str] = None
    cta_text: Optional[str] = None
    primary_color: Optional[str] = None

class LandingPageResponse(BaseModel):
    id: str
    slug: str
    user_id: str
    hero_title: str
    hero_subtitle: str
    hero_image: Optional[str] = None
    features: List[FeatureItem] = []
    whatsapp_number: str
    cta_text: str
    primary_color: str
    created_at: datetime
    updated_at: datetime

# ==================== Helper Functions ====================

def generate_slug():
    return str(uuid.uuid4())[:8]

def generate_serial_number():
    """Generate a unique serial number format: MOVA-XXXX-XXXX-XXXX"""
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    parts = [''.join(random.choices(chars, k=4)) for _ in range(3)]
    return f"MOVA-{parts[0]}-{parts[1]}-{parts[2]}"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = await db.users.find_one({"id": user_id})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== Auth Routes ====================

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(data: UserCreate):
    # Validate serial number format
    if not data.serial_number or not data.serial_number.startswith("MOVA-"):
        raise HTTPException(status_code=400, detail="Serial number tidak valid")
    
    # Check if serial number exists and is not used
    serial = await db.serial_numbers.find_one({"serial_number": data.serial_number.upper()})
    if not serial:
        raise HTTPException(status_code=400, detail="Serial number tidak ditemukan")
    
    if serial.get("is_used"):
        raise HTTPException(status_code=400, detail="Serial number sudah digunakan")
    
    # Check if email already registered
    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    
    # Create user
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": data.email.lower(),
        "name": data.name,
        "serial_number": data.serial_number.upper(),
        "password_hash": hash_password(data.password),
        "created_at": datetime.utcnow()
    }
    await db.users.insert_one(user)
    
    # Mark serial number as used
    await db.serial_numbers.update_one(
        {"serial_number": data.serial_number.upper()},
        {"$set": {
            "is_used": True,
            "used_by_email": data.email.lower(),
            "used_by_user_id": user_id,
            "used_at": datetime.utcnow()
        }}
    )
    
    token = create_token(user_id)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=user["email"],
            name=user["name"],
            serial_number=user["serial_number"],
            created_at=user["created_at"]
        )
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(data: UserLogin):
    user = await db.users.find_one({"email": data.email.lower()})
    if not user:
        raise HTTPException(status_code=401, detail="Email atau password salah")
    
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email atau password salah")
    
    token = create_token(user["id"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            serial_number=user.get("serial_number", ""),
            created_at=user["created_at"]
        )
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user = Depends(get_current_user)):
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        serial_number=user.get("serial_number", ""),
        created_at=user["created_at"]
    )

# ==================== Serial Number Routes ====================

@api_router.post("/serial-numbers/generate", response_model=List[SerialNumberResponse])
async def generate_serial_numbers(data: SerialNumberCreate):
    """Generate new serial numbers (Admin only - add proper auth in production)"""
    generated = []
    for _ in range(min(data.count, 100)):  # Max 100 at a time
        serial = generate_serial_number()
        # Ensure unique
        while await db.serial_numbers.find_one({"serial_number": serial}):
            serial = generate_serial_number()
        
        serial_doc = {
            "serial_number": serial,
            "is_used": False,
            "used_by_email": None,
            "used_by_user_id": None,
            "created_at": datetime.utcnow(),
            "used_at": None
        }
        await db.serial_numbers.insert_one(serial_doc)
        generated.append(SerialNumberResponse(**serial_doc))
    
    return generated

@api_router.get("/serial-numbers", response_model=List[SerialNumberResponse])
async def get_all_serial_numbers():
    """Get all serial numbers (Admin only - add proper auth in production)"""
    serials = await db.serial_numbers.find().sort("created_at", -1).to_list(1000)
    return [SerialNumberResponse(**s) for s in serials]

@api_router.get("/serial-numbers/check/{serial_number}")
async def check_serial_number(serial_number: str):
    """Check if a serial number is valid and available"""
    serial = await db.serial_numbers.find_one({"serial_number": serial_number.upper()})
    if not serial:
        return {"valid": False, "message": "Serial number tidak ditemukan"}
    if serial.get("is_used"):
        return {"valid": False, "message": "Serial number sudah digunakan"}
    return {"valid": True, "message": "Serial number tersedia"}

@api_router.get("/serial-numbers/download")
async def download_serial_numbers_csv():
    """Download all serial numbers as CSV file"""
    serials = await db.serial_numbers.find().sort("created_at", -1).to_list(10000)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['No', 'Serial Number', 'Status', 'Used By Email', 'Created At', 'Used At'])
    
    for i, s in enumerate(serials, 1):
        created_at = s['created_at'].strftime('%Y-%m-%d %H:%M:%S') if s.get('created_at') else '-'
        used_at = s['used_at'].strftime('%Y-%m-%d %H:%M:%S') if s.get('used_at') else '-'
        writer.writerow([
            i,
            s['serial_number'],
            'Sudah Digunakan' if s.get('is_used') else 'Tersedia',
            s.get('used_by_email') or '-',
            created_at,
            used_at
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mova_serial_numbers.csv"}
    )

# ==================== Landing Page Routes ====================

@api_router.post("/landing-pages", response_model=LandingPageResponse)
async def create_landing_page(data: LandingPageCreate, user = Depends(get_current_user)):
    page_id = str(uuid.uuid4())
    slug = generate_slug()
    
    # Ensure unique slug
    while await db.landing_pages.find_one({"slug": slug}):
        slug = generate_slug()
    
    now = datetime.utcnow()
    page = {
        "id": page_id,
        "slug": slug,
        "user_id": user["id"],
        "hero_title": data.hero_title,
        "hero_subtitle": data.hero_subtitle,
        "hero_image": data.hero_image,
        "features": [f.dict() for f in data.features],
        "whatsapp_number": data.whatsapp_number,
        "cta_text": data.cta_text,
        "primary_color": data.primary_color,
        "created_at": now,
        "updated_at": now
    }
    await db.landing_pages.insert_one(page)
    
    return LandingPageResponse(**page)

@api_router.get("/landing-pages", response_model=List[LandingPageResponse])
async def get_my_landing_pages(user = Depends(get_current_user)):
    pages = await db.landing_pages.find({"user_id": user["id"]}).sort("created_at", -1).to_list(100)
    return [LandingPageResponse(**page) for page in pages]

@api_router.get("/landing-pages/{page_id}", response_model=LandingPageResponse)
async def get_landing_page(page_id: str, user = Depends(get_current_user)):
    page = await db.landing_pages.find_one({"id": page_id, "user_id": user["id"]})
    if not page:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    return LandingPageResponse(**page)

@api_router.put("/landing-pages/{page_id}", response_model=LandingPageResponse)
async def update_landing_page(page_id: str, data: LandingPageUpdate, user = Depends(get_current_user)):
    page = await db.landing_pages.find_one({"id": page_id, "user_id": user["id"]})
    if not page:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if "features" in update_data:
        update_data["features"] = [f if isinstance(f, dict) else f.dict() for f in update_data["features"]]
    update_data["updated_at"] = datetime.utcnow()
    
    await db.landing_pages.update_one({"id": page_id}, {"$set": update_data})
    
    updated_page = await db.landing_pages.find_one({"id": page_id})
    return LandingPageResponse(**updated_page)

@api_router.delete("/landing-pages/{page_id}")
async def delete_landing_page(page_id: str, user = Depends(get_current_user)):
    page = await db.landing_pages.find_one({"id": page_id, "user_id": user["id"]})
    if not page:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    
    await db.landing_pages.delete_one({"id": page_id})
    return {"message": "Landing page berhasil dihapus"}

# ==================== Public Landing Page Route ====================

@api_router.get("/p/{slug}", response_model=LandingPageResponse)
async def get_public_landing_page(slug: str):
    page = await db.landing_pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
    return LandingPageResponse(**page)

# ==================== Root Route ====================

@api_router.get("/")
async def root():
    return {"message": "Mova Landing Page API"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
