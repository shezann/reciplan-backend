from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log') if os.getenv('FLASK_ENV') == 'production' else logging.NullHandler()
    ]
)

def create_app():
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False

    # Initialize extensions
    CORS(app)
    jwt = JWTManager(app)
    
    # Initialize Firebase
    from config.firebase_config import initialize_firebase
    initialize_firebase()

    # Import routes after app creation
    from routes.auth_routes import auth_bp
    from routes.recipe_routes import recipe_bp
    from controllers.like_controller import like_bp
    from controllers.tiktok_controller import tiktok_bp

    # Register blueprints
    app.register_blueprint(auth_bp)  # Remove url_prefix since it's already in the blueprint
    app.register_blueprint(recipe_bp)  # Remove url_prefix since it's already in the blueprint
    app.register_blueprint(like_bp)  # Register like endpoints
    app.register_blueprint(tiktok_bp)  # Register TikTok endpoints

    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({'status': 'healthy', 'service': 'reciplan-backend'})

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_ENV') != 'production', host='0.0.0.0', port=5000) 