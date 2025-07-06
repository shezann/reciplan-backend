from flask import Flask
from flask_cors import CORS
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Basic configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    # CORS configuration
    cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',')
    CORS(app, origins=cors_origins, supports_credentials=True)
    
    # Initialize services
    from config.firebase_config import initialize_firebase
    from services.jwt_service import jwt_service
    
    # Initialize Firebase
    if not initialize_firebase():
        print("❌ Warning: Firebase initialization failed. Some features may not work.")
    
    # Initialize JWT
    jwt_service.init_app(app)
    
    # Register blueprints
    from routes.auth_routes import auth_bp
    app.register_blueprint(auth_bp)
    
    # Basic routes
    @app.route('/')
    def hello_world():
        return {'message': 'RecipLan Backend API', 'version': '1.0.0'}, 200
    
    @app.route('/health')
    def health_check():
        return {
            'status': 'healthy', 
            'service': 'reciplan-backend',
            'version': '1.0.0',
            'features': [
                'Firebase Authentication',
                'Email Link Sign-In',
                'Google Sign-In',
                'JWT Tokens',
                'User Setup Flow',
                'Recipe Management'
            ]
        }, 200
    
    @app.route('/api/status')
    def api_status():
        """API status endpoint with service information"""
        return {
            'api_version': '1.0.0',
            'service': 'reciplan-backend',
            'status': 'operational',
            'endpoints': {
                'auth': '/api/auth',
                'health': '/health',
                'status': '/api/status'
            },
            'features': {
                'firebase_auth': True,
                'email_link_signin': True,
                'google_signin': bool(os.getenv('GOOGLE_CLIENT_ID')),
                'user_setup_flow': True,
                'firebase_ready': True  # We'll assume it's ready if we get here
            }
        }, 200
    
    # Basic error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {
            'error': 'Resource not found',
            'message': 'The requested resource was not found.',
            'status_code': 404
        }, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return {
            'error': 'Internal server error',
            'message': 'An unexpected error occurred. Please try again later.',
            'status_code': 500
        }, 500
    
    @app.errorhandler(401)
    def unauthorized(error):
        return {
            'error': 'Unauthorized',
            'message': 'Authentication is required to access this resource.',
            'status_code': 401
        }, 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return {
            'error': 'Forbidden',
            'message': 'You do not have permission to access this resource.',
            'status_code': 403
        }, 403
    
    return app

if __name__ == '__main__':
    app = create_app()
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5050))
    host = os.getenv('HOST', '0.0.0.0')
    
    print(f"🚀 Starting RecipLan Backend API")
    print(f"📍 Server: {host}:{port}")
    print(f"🔧 Debug Mode: {debug_mode}")
    print(f"🔐 Google Auth: {'✅ Configured' if os.getenv('GOOGLE_CLIENT_ID') else '❌ Not configured'}")
    print(f"🔥 Firebase: {'✅ Configured' if os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH') or os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY') else '❌ Not configured'}")
    print(f"🔑 JWT Secret: {'✅ Configured' if os.getenv('JWT_SECRET_KEY') else '❌ Using default (not secure)'}")
    print(f"📚 API Documentation: http://{host}:{port}/api/status")
    print(f"🔗 Available Endpoints:")
    print(f"   - POST /api/auth/firebase-login")
    print(f"   - POST /api/auth/google")
    print(f"   - POST /api/auth/setup")
    print(f"   - POST /api/auth/check-username")
    print(f"   - GET  /api/auth/me")
    print(f"   - PUT  /api/auth/update-profile")
    
    app.run(host=host, port=port, debug=debug_mode) 