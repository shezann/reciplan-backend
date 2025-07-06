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
    CORS(app, origins=['http://localhost:3000'], supports_credentials=True)
    
    # Basic routes
    @app.route('/')
    def hello_world():
        return {'message': 'Hello World'}, 200
    
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'reciplan-backend'}, 200
    
    # Basic error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Resource not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'error': 'Internal server error'}, 500
    
    return app

if __name__ == '__main__':
    app = create_app()
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5050, debug=debug_mode) 