"""
JWT service for handling authentication tokens with Firebase authentication
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token, 
    jwt_required, get_jwt_identity, get_jwt, verify_jwt_in_request
)


class JWTService:
    """Service for JWT token management"""
    
    def __init__(self, app=None):
        self.jwt_manager = None
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize JWT with Flask app"""
        app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', app.config.get('SECRET_KEY'))
        app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', '24')))
        app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', '30')))
        
        self.jwt_manager = JWTManager(app)
        
        # Set up JWT callbacks
        self._setup_jwt_callbacks()
    
    def _setup_jwt_callbacks(self):
        """Set up JWT callbacks for error handling"""
        
        @self.jwt_manager.expired_token_loader
        def expired_token_callback(jwt_header, jwt_payload):
            return jsonify({
                'error': 'Token has expired',
                'message': 'The token has expired. Please log in again.'
            }), 401
        
        @self.jwt_manager.invalid_token_loader
        def invalid_token_callback(error):
            return jsonify({
                'error': 'Invalid token',
                'message': 'The token is invalid. Please log in again.'
            }), 401
        
        @self.jwt_manager.unauthorized_loader
        def missing_token_callback(error):
            return jsonify({
                'error': 'Authorization token required',
                'message': 'A valid access token is required to access this resource.'
            }), 401
        
        @self.jwt_manager.revoked_token_loader
        def revoked_token_callback(jwt_header, jwt_payload):
            return jsonify({
                'error': 'Token has been revoked',
                'message': 'The token has been revoked. Please log in again.'
            }), 401
    
    def create_tokens(self, user_data: Dict) -> Dict:
        """Create access and refresh tokens with user claims"""
        # Create claims including setup completion status
        additional_claims = {
            'setup_completed': user_data.get('setup_completed', False),
            'username': user_data.get('username', ''),
            'email': user_data.get('email', ''),
            'name': user_data.get('name', ''),
            'user_id': user_data.get('id', ''),
            'firebase_uid': user_data.get('firebase_uid', ''),
            'google_id': user_data.get('google_id'),
            'profile_picture': user_data.get('profile_picture', ''),
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Create tokens
        access_token = create_access_token(
            identity=user_data.get('id'),
            additional_claims=additional_claims
        )
        
        refresh_token = create_refresh_token(
            identity=user_data.get('id'),
            additional_claims=additional_claims
        )
        
        # Handle case where JWT_ACCESS_TOKEN_EXPIRES is False (no expiration)
        expires_in = None
        if current_app.config['JWT_ACCESS_TOKEN_EXPIRES']:
            expires_in = int(current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds())
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': expires_in
        }
    
    def get_current_user_claims(self) -> Optional[Dict]:
        """Get current user claims from JWT token"""
        try:
            verify_jwt_in_request()
            claims = get_jwt()
            return claims
        except Exception:
            return None
    
    def get_current_user_id(self) -> Optional[str]:
        """Get current user ID from JWT token"""
        try:
            verify_jwt_in_request()
            return get_jwt_identity()
        except Exception:
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Dict]:
        """Create new access token from refresh token"""
        try:
            # This would need to be implemented with proper refresh token handling
            # For now, we'll return None as it requires more complex setup
            return None
        except Exception:
            return None


def setup_required(f):
    """Decorator to require user setup completion for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First check if JWT is valid
        try:
            verify_jwt_in_request()
            claims = get_jwt()
            
            # Check if user has completed setup
            if not claims.get('setup_completed', False):
                return jsonify({
                    'error': 'Setup required',
                    'message': 'Please complete your profile setup before accessing this resource.',
                    'setup_completed': False
                }), 403
            
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({
                'error': 'Authentication required',
                'message': 'A valid access token is required to access this resource.'
            }), 401
    
    return decorated_function


def optional_setup_required(f):
    """Decorator that allows access but indicates setup completion status"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            verify_jwt_in_request()
            claims = get_jwt()
            
            # Add setup completion status to request context
            request.setup_completed = claims.get('setup_completed', False)
            request.current_user_id = get_jwt_identity()
            request.current_user_claims = claims
            
            return f(*args, **kwargs)
        except Exception:
            # Allow access without authentication
            request.setup_completed = False
            request.current_user_id = None
            request.current_user_claims = None
            return f(*args, **kwargs)
    
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            verify_jwt_in_request()
            claims = get_jwt()
            
            # Check if user is admin (you can customize this logic)
            if not claims.get('is_admin', False):
                return jsonify({
                    'error': 'Admin privileges required',
                    'message': 'You need administrator privileges to access this resource.'
                }), 403
            
            return f(*args, **kwargs)
        except Exception:
            return jsonify({
                'error': 'Authentication required',
                'message': 'A valid access token is required to access this resource.'
            }), 401
    
    return decorated_function


def get_user_from_token() -> Optional[Dict]:
    """Get user information from current JWT token"""
    try:
        verify_jwt_in_request()
        claims = get_jwt()
        
        return {
            'id': get_jwt_identity(),
            'email': claims.get('email'),
            'username': claims.get('username'),
            'name': claims.get('name'),
            'firebase_uid': claims.get('firebase_uid'),
            'setup_completed': claims.get('setup_completed', False),
            'google_id': claims.get('google_id'),
            'profile_picture': claims.get('profile_picture'),
            'created_at': claims.get('created_at')
        }
    except Exception:
        return None


def check_token_validity() -> Dict:
    """Check if current token is valid and return status"""
    try:
        verify_jwt_in_request()
        claims = get_jwt()
        user_id = get_jwt_identity()
        
        return {
            'valid': True,
            'user_id': user_id,
            'setup_completed': claims.get('setup_completed', False),
            'email': claims.get('email'),
            'username': claims.get('username'),
            'name': claims.get('name'),
            'firebase_uid': claims.get('firebase_uid')
        }
    except Exception as e:
        return {
            'valid': False,
            'error': str(e)
        }


# Service instance
jwt_service = JWTService() 