# RecipLan Backend - Firebase Firestore

A Flask-based REST API backend for a recipe planning application using Firebase Cloud Firestore as the database.

## Features

- **Firebase Firestore Integration**: NoSQL document database for scalable data storage
- **RESTful API**: Clean API endpoints for users, recipes, and authentication
- **JWT Authentication**: Secure token-based authentication
- **Data Validation**: Input validation using Marshmallow schemas
- **CORS Support**: Cross-origin resource sharing for frontend integration
- **Flexible Querying**: Support for filtering, searching, and pagination

## Prerequisites

- Python 3.8+
- Firebase project with Firestore enabled
- Service account credentials for Firebase

## Setup Instructions

### 1. Create a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project or select an existing one
3. Enable Firestore Database in the project
4. Go to Project Settings > Service Accounts
5. Generate a new private key (downloads a JSON file)
6. Save the JSON file securely (don't commit to version control)

### 2. Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd reciplan_backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the root directory based on `env_example.txt`:

```bash
# Copy the example file
cp env_example.txt .env
```

Edit the `.env` file with your configuration:

```env
# Firebase Configuration
FIREBASE_SERVICE_ACCOUNT_PATH=path/to/your/firebase-service-account.json

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key-here

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key-here
JWT_ACCESS_TOKEN_EXPIRES=3600

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

### 4. Firebase Security Rules

Set up Firestore security rules in the Firebase Console:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users can read/write their own user document
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    // Recipes can be read by anyone, but only created/modified by authenticated users
    match /recipes/{recipeId} {
      allow read: if resource.data.is_public == true ||
                     (request.auth != null && request.auth.uid == resource.data.user_id);
      allow create: if request.auth != null && request.auth.uid == request.resource.data.user_id;
      allow update, delete: if request.auth != null && request.auth.uid == resource.data.user_id;
    }
  }
}
```

### 5. Run the Application

```bash
# Make sure virtual environment is activated
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate  # On Windows

# Run the application
python app.py
```

The API will be available at `http://localhost:5050`.

## Running the Backend Locally

Follow these steps to run the backend on your local machine:

1. **Clone the repository and navigate to the project directory:**
   ```bash
   git clone <repository-url>
   cd reciplan-backend
   ```

2. **Create and activate a virtual environment:**
   - On **Windows**:
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   - On **macOS/Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   - Copy the example environment file and edit it with your configuration:
     ```bash
     cp env_example.txt .env
     # Edit .env as needed
     ```

5. **Run the backend application:**
   - Make sure your virtual environment is activated.
   - Start the Flask app:
     ```bash
     python app.py
     ```
   - The API will be available at `http://localhost:5050` by default.

## API Endpoints

### Authentication

#### Login

- **POST** `/api/auth/login`
- **Body**: `{"email": "user@example.com", "password": "password123"}`
- **Response**: `{"access_token": "...", "user": {...}}`

#### Get Current User

- **GET** `/api/auth/login`
- **Headers**: `Authorization: Bearer <token>`
- **Response**: `{"user": {...}}`

### Users

#### Create User

- **POST** `/api/users`
- **Body**:
  ```json
  {
    "name": "John Doe",
    "email": "john@example.com",
    "password": "password123",
    "preferences": {},
    "dietary_restrictions": ["vegetarian"]
  }
  ```

#### Get All Users

- **GET** `/api/users`
- **Headers**: `Authorization: Bearer <token>`
- **Query Parameters**: `limit` (optional)

#### Get User by ID

- **GET** `/api/users/<user_id>`
- **Headers**: `Authorization: Bearer <token>`

#### Update User

- **PUT** `/api/users/<user_id>`
- **Headers**: `Authorization: Bearer <token>`
- **Body**: `{"name": "Updated Name", "preferences": {...}}`

#### Delete User

- **DELETE** `/api/users/<user_id>`
- **Headers**: `Authorization: Bearer <token>`

### Recipes

#### Get Recipes

- **GET** `/api/recipes`
- **Query Parameters**:
  - `limit` (optional): Number of recipes to return
  - `tag` (optional): Filter by tag
  - `difficulty` (optional): Filter by difficulty
  - `user_id` (optional): Filter by user

#### Create Recipe

- **POST** `/api/recipes`
- **Headers**: `Authorization: Bearer <token>`
- **Body**:
  ```json
  {
    "title": "Delicious Pasta",
    "description": "A simple pasta recipe",
    "ingredients": [
      { "name": "pasta", "quantity": "500g" },
      { "name": "tomato sauce", "quantity": "400ml" }
    ],
    "instructions": ["Boil water", "Cook pasta", "Add sauce"],
    "prep_time": 10,
    "cook_time": 15,
    "servings": 4,
    "difficulty": "easy",
    "tags": ["pasta", "quick"],
    "nutrition": { "calories": 350 },
    "is_public": true
  }
  ```

#### Get Recipe by ID

- **GET** `/api/recipes/<recipe_id>`

#### Update Recipe

- **PUT** `/api/recipes/<recipe_id>`
- **Headers**: `Authorization: Bearer <token>`
- **Body**: Recipe update data

#### Delete Recipe

- **DELETE** `/api/recipes/<recipe_id>`
- **Headers**: `Authorization: Bearer <token>`

### Health Check

- **GET** `/health`
- **Response**: `{"status": "healthy", "service": "reciplan-backend"}`

## Project Structure

```
reciplan_backend/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── env_example.txt       # Environment variables example
├── config/
│   └── firebase_config.py # Firebase configuration
├── services/
│   └── firestore_service.py # Firestore service layer
├── routes/
│   ├── auth_routes.py    # Authentication routes
│   ├── user_routes.py    # User management routes
│   └── recipe_routes.py  # Recipe management routes
└── README.md             # This file
```

## Firestore Collections

### Users Collection

```json
{
  "id": "user123",
  "name": "John Doe",
  "email": "john@example.com",
  "password": "hashed_password",
  "preferences": {},
  "dietary_restrictions": ["vegetarian"],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Recipes Collection

```json
{
  "id": "recipe123",
  "title": "Delicious Pasta",
  "description": "A simple pasta recipe",
  "ingredients": [
    { "name": "pasta", "quantity": "500g" },
    { "name": "tomato sauce", "quantity": "400ml" }
  ],
  "instructions": ["Step 1", "Step 2"],
  "prep_time": 10,
  "cook_time": 15,
  "servings": 4,
  "difficulty": "easy",
  "tags": ["pasta", "quick"],
  "nutrition": { "calories": 350 },
  "is_public": true,
  "user_id": "user123",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

## Development

### Running in Development Mode

```bash
export FLASK_ENV=development
export FLASK_DEBUG=True
python app.py
```

### Testing with curl

```bash
# Create a user
curl -X POST http://localhost:5050/api/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Test User", "email": "test@example.com", "password": "password123"}'

# Login
curl -X POST http://localhost:5050/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'

# Get recipes (with token)
curl -X GET http://localhost:5050/api/recipes \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Deployment

### Environment Variables for Production

For production deployment, use environment variables instead of the service account file:

```env
FIREBASE_SERVICE_ACCOUNT_KEY={"type": "service_account", "project_id": "your-project-id", ...}
```

### Platform-Specific Deployment

#### Google Cloud Run / App Engine

- The Firebase Admin SDK will automatically use the default service account
- No additional configuration needed for Firebase authentication

#### Other Platforms

- Use the `FIREBASE_SERVICE_ACCOUNT_KEY` environment variable
- Ensure proper security for sensitive credentials

## Security Considerations

1. **Never commit service account keys to version control**
2. **Use environment variables for sensitive data**
3. **Implement proper Firestore security rules**
4. **Use HTTPS in production**
5. **Regularly rotate JWT secret keys**
6. **Implement rate limiting for production**

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.
