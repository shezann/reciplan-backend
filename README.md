# Reciplan Backend — AI Recipe Extraction API

A Flask-based REST API that powers the Reciplan Android app. Accepts TikTok video URLs and runs them through a 6-stage AI extraction pipeline to produce structured recipes, stored in Firebase Firestore.

Containerized with **Docker**, async processing via **Celery + Redis**, and secured with **JWT authentication**.

---

## Pipeline Overview

```
POST /api/extract  →  TikTok URL
        │
        ▼
Celery Task Queue (Redis broker)
        │
        ├── Stage 1: Video download (yt-dlp)
        ├── Stage 2: Audio extraction (FFmpeg)
        ├── Stage 3: Transcription (OpenAI Whisper)
        ├── Stage 4: Recipe structuring (GPT-4)
        ├── Stage 5: On-screen text extraction (PaddleOCR)
        └── Stage 6: Storage (Firebase Firestore)
        │
        ▼
GET /api/extract/{task_id}/status  →  pipeline progress (polled by app)
```

Achieved **95% extraction accuracy** across **50+ test videos**.

---

## Tech Stack

| Layer | Tech |
|---|---|
| API Framework | Flask (Python) |
| Task Queue | Celery |
| Message Broker | Redis |
| Transcription | OpenAI Whisper |
| Recipe Structuring | GPT-4 |
| OCR | PaddleOCR |
| Database | Firebase Firestore |
| Auth | Firebase Authentication + JWT |
| Containerization | Docker + Docker Compose |
| Schema Validation | Marshmallow |

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Firebase project with Firestore enabled and a service account key
- OpenAI API key

### 1. Clone and Configure

```bash
git clone https://github.com/shezann/reciplan-backend.git
cd reciplan-backend
cp env_example.txt .env
```

Edit `.env`:

```env
# OpenAI
OPENAI_API_KEY=your-openai-key

# Firebase
FIREBASE_SERVICE_ACCOUNT_PATH=path/to/service-account.json

# Flask
FLASK_ENV=development
SECRET_KEY=your-secret-key

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ACCESS_TOKEN_EXPIRES=3600

# CORS
CORS_ORIGINS=http://localhost:3000
```

### 2. Run with Docker

```bash
docker-compose up --build
```

This starts three services:
- `web` — Flask API on port `5050`
- `worker` — Celery worker processing pipeline tasks
- `redis` — Redis broker

### 3. Run Locally (without Docker)

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Terminal 1 — Flask API
python app.py

# Terminal 2 — Celery worker
celery -A app.celery worker --loglevel=info
```

---

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | Login with email/password, returns JWT |
| GET | `/api/auth/login` | Get current authenticated user |

### Recipe Extraction

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/extract` | Submit a TikTok URL, returns `task_id` |
| GET | `/api/extract/{task_id}/status` | Poll pipeline progress (stages 1–6) |

### Recipes

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/recipes` | List recipes (filter by tag, difficulty, user) |
| POST | `/api/recipes` | Create a recipe manually |
| GET | `/api/recipes/{id}` | Get recipe by ID |
| PUT | `/api/recipes/{id}` | Update recipe |
| DELETE | `/api/recipes/{id}` | Delete recipe |

### Users

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/users` | Create user |
| GET | `/api/users` | List users (auth required) |
| GET | `/api/users/{id}` | Get user by ID |
| PUT | `/api/users/{id}` | Update user |
| DELETE | `/api/users/{id}` | Delete user |

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check — returns `{"status": "healthy"}` |

---

## Project Structure

```
reciplan-backend/
├── app.py                    # Flask app + Celery init
├── run.py                    # Entry point
├── errors.py                 # Global error handlers
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── config/
│   └── firebase_config.py    # Firebase Admin SDK setup
├── routes/
│   ├── auth_routes.py
│   ├── user_routes.py
│   └── recipe_routes.py
├── controllers/              # Request handling logic
├── services/
│   └── firestore_service.py  # Firestore read/write layer
├── tasks/                    # Celery pipeline task definitions
├── schemas/                  # Marshmallow validation schemas
├── prompts/                  # GPT-4 prompt templates
├── utils/
├── scripts/
├── tests/
└── docs/
```

---

## Firestore Collections

### `users`
```json
{
  "id": "user123",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "preferences": {},
  "dietary_restrictions": ["vegetarian"],
  "created_at": "2024-01-01T00:00:00Z"
}
```

### `recipes`
```json
{
  "id": "recipe123",
  "title": "Spicy Ramen",
  "ingredients": [
    { "name": "ramen noodles", "quantity": "100g" },
    { "name": "chili paste", "quantity": "1 tbsp" }
  ],
  "instructions": ["Boil noodles", "Add broth", "Stir in chili paste"],
  "prep_time": 5,
  "cook_time": 10,
  "servings": 1,
  "source_url": "https://tiktok.com/...",
  "is_public": true,
  "user_id": "user123",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## Security

- All sensitive keys loaded from environment variables — never committed
- Firestore security rules enforce per-user read/write access
- JWT tokens expire after 1 hour with automatic refresh on the client
- HTTPS enforced in production
- Rate limiting recommended for production deployment

---

## Frontend Repo

See [reciplan](https://github.com/shezann/reciplan) for the Android app built with Kotlin, Jetpack Compose, and MVVM architecture.

---

## License

MIT
