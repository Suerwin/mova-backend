# Mova Landing Page Builder - Backend

## Requirements
- Python 3.11+
- MongoDB

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file:
```env
MONGO_URL=mongodb+srv://username:password@cluster.mongodb.net/
DB_NAME=mova_db
JWT_SECRET=your-super-secret-key-min-32-characters
```

3. Run server:
```bash
uvicorn server:app --host 0.0.0.0 --port 8001
```

## Deploy to Railway

1. Create account at https://railway.app
2. Create new project
3. Add MongoDB service (or use MongoDB Atlas)
4. Add Web Service from GitHub
5. Set environment variables in Railway dashboard
6. Deploy!

## Deploy to Render

1. Create account at https://render.com
2. Create new Web Service
3. Connect GitHub repository
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
6. Add environment variables
7. Deploy!

## API Endpoints

### Auth
- POST /api/auth/register - Register with serial number
- POST /api/auth/login - Login
- GET /api/auth/me - Get current user

### Landing Pages
- GET /api/landing-pages - Get user's landing pages
- POST /api/landing-pages - Create landing page
- PUT /api/landing-pages/{id} - Update landing page
- DELETE /api/landing-pages/{id} - Delete landing page
- GET /api/p/{slug} - Get public landing page

### Serial Numbers (Admin)
- POST /api/serial-numbers/generate - Generate serial numbers
- GET /api/serial-numbers - List all serial numbers
- GET /api/serial-numbers/download - Download CSV
- GET /api/serial-numbers/check/{serial} - Check serial number
