"""
Authentication routes for Firebase email link authentication and Google Sign-In
"""
import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, ValidationError
from google.oauth2 import id_token
from google.auth.transport import requests
from firebase_admin import auth as firebase_auth
from services.firestore_service import user_service
from services.jwt_service import jwt_service, get_user_from_token, check_token_validity


# Create blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


# Validation schemas
class FirebaseAuthSchema(Schema):
    """Schema for Firebase authentication"""
    firebase_token = fields.Str(required=True)


class GoogleLoginSchema(Schema):
    """Schema for Google login"""
    google_token = fields.Str(required=True)


class UserSetupSchema(Schema):
    """Schema for user setup"""
    username = fields.Str(required=True, validate=lambda x: len(x.strip()) >= 3)
    dietary_restrictions = fields.List(fields.Str(), required=False, load_default=[])
    preferences = fields.Dict(required=False, load_default={})


class CheckUsernameSchema(Schema):
    """Schema for checking username availability"""
    username = fields.Str(required=True, validate=lambda x: len(x.strip()) >= 3)


class TestUserSchema(Schema):
    """Schema for test user creation (development only)"""
    name = fields.Str(required=True)
    email = fields.Email(required=True)
    username = fields.Str(required=False, load_default='')
    preferences = fields.Dict(required=False, load_default={})
    dietary_restrictions = fields.List(fields.Str(), required=False, load_default=[])


# Routes
@auth_bp.route('/firebase-login', methods=['POST'])
def firebase_login():
    """Authenticate user with Firebase ID token (email link or other Firebase auth)"""
    try:
        # Validate input
        schema = FirebaseAuthSchema()
        data = schema.load(request.get_json())
        
        # Verify Firebase ID token
        try:
            decoded_token = firebase_auth.verify_id_token(data['firebase_token'])
            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email')
            name = decoded_token.get('name', '')
            picture = decoded_token.get('picture', '')
            phone = decoded_token.get('phone_number', '')
            
            # Check if email is verified in Firebase
            firebase_user = firebase_auth.get_user(firebase_uid)
            email_verified = firebase_user.email_verified
            
        except Exception as e:
            print(f"Firebase token verification error: {e}")
            return jsonify({
                'error': 'Invalid Firebase token',
                'message': 'The Firebase token is invalid or expired.'
            }), 401
        
        # Create or update user in Firestore
        firebase_user_data = {
            'firebase_uid': firebase_uid,
            'email': email,
            'name': name,
            'profile_picture': picture,
            'phone_number': phone,
            'email_verified': email_verified
        }
        
        user = user_service.create_or_update_firebase_user(firebase_user_data)
        
        # Create JWT tokens
        tokens = jwt_service.create_tokens(user)
        
        return jsonify({
            'message': 'Firebase authentication successful',
            'user': {
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'username': user['username'],
                'firebase_uid': user['firebase_uid'],
                'profile_picture': user.get('profile_picture', ''),
                'phone_number': user.get('phone_number', ''),
                'setup_completed': user.get('setup_completed', False),
                'preferences': user.get('preferences', {}),
                'dietary_restrictions': user.get('dietary_restrictions', [])
            },
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'token_type': tokens['token_type'],
            'expires_in': tokens['expires_in'],
            'setup_required': not user.get('setup_completed', False)
        }), 200
        
    except ValidationError as e:
        return jsonify({
            'error': 'Validation error',
            'message': 'Invalid input data',
            'details': e.messages
        }), 400
    except Exception as e:
        print(f"Firebase login error: {e}")
        return jsonify({
            'error': 'Authentication failed',
            'message': 'An error occurred during authentication. Please try again.'
        }), 500


@auth_bp.route('/google', methods=['POST'])
def google_login():
    """Google Sign-In authentication"""
    try:
        # Validate input
        schema = GoogleLoginSchema()
        data = schema.load(request.get_json())
        
        # Get Google Client ID from environment
        google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        
        if not google_client_id:
            return jsonify({
                'error': 'Google authentication not configured',
                'message': 'Google Sign-In is not available at the moment.'
            }), 500
        
        # Verify Google token
        try:
            idinfo = id_token.verify_oauth2_token(
                data['google_token'], 
                requests.Request(), 
                google_client_id
            )
            
            # Extract user information
            google_user_data = {
                'google_id': idinfo['sub'],
                'email': idinfo['email'],
                'name': idinfo.get('name', ''),
                'picture': idinfo.get('picture', ''),
                'email_verified': idinfo.get('email_verified', False)
            }
            
        except ValueError as e:
            return jsonify({
                'error': 'Invalid Google token',
                'message': 'The Google token is invalid or expired.'
            }), 401
        
        # Create Firebase user for Google authentication
        try:
            # Create or get Firebase user
            firebase_user = None
            try:
                firebase_user = firebase_auth.get_user_by_email(google_user_data['email'])
            except firebase_auth.UserNotFoundError:
                # Create new Firebase user
                firebase_user = firebase_auth.create_user(
                    email=google_user_data['email'],
                    display_name=google_user_data['name'],
                    photo_url=google_user_data.get('picture'),
                    email_verified=google_user_data['email_verified']
                )
            
            # Create or update user in Firestore
            firebase_user_data = {
                'firebase_uid': firebase_user.uid,
                'email': google_user_data['email'],
                'name': google_user_data['name'],
                'profile_picture': google_user_data.get('picture', ''),
                'google_id': google_user_data['google_id'],
                'email_verified': google_user_data['email_verified']
            }
            
            user = user_service.create_or_update_firebase_user(firebase_user_data)
            
            # Create JWT tokens
            tokens = jwt_service.create_tokens(user)
            
            return jsonify({
                'message': 'Google login successful',
                'user': {
                    'id': user['id'],
                    'name': user['name'],
                    'email': user['email'],
                    'username': user['username'],
                    'firebase_uid': user['firebase_uid'],
                    'google_id': user.get('google_id'),
                    'profile_picture': user.get('profile_picture', ''),
                    'setup_completed': user.get('setup_completed', False),
                    'preferences': user.get('preferences', {}),
                    'dietary_restrictions': user.get('dietary_restrictions', [])
                },
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'token_type': tokens['token_type'],
                'expires_in': tokens['expires_in'],
                'setup_required': not user.get('setup_completed', False)
            }), 200
            
        except Exception as e:
            print(f"Firebase user creation error: {e}")
            print(f"Error type: {type(e)}")
            print(f"Error details: {str(e)}")
            return jsonify({
                'error': 'User creation failed',
                'message': f'Could not create user account: {str(e)}'
            }), 500
        
    except ValidationError as e:
        return jsonify({
            'error': 'Validation error',
            'message': 'Invalid input data',
            'details': e.messages
        }), 400
    except Exception as e:
        print(f"Google login error: {e}")
        return jsonify({
            'error': 'Google login failed',
            'message': 'An error occurred during Google authentication. Please try again.'
        }), 500


@auth_bp.route('/test-create-user', methods=['POST'])
def test_create_user():
    """Create a test user for development purposes (bypasses Firebase auth)"""
    try:
        # Only allow in development mode
        if os.getenv('FLASK_DEBUG', 'False').lower() != 'true':
            return jsonify({
                'error': 'Not available',
                'message': 'This endpoint is only available in development mode.'
            }), 403
        
        # Validate input
        schema = TestUserSchema()
        data = schema.load(request.get_json())
        
        # Create mock Firebase user data
        firebase_user_data = {
            'firebase_uid': f"test_uid_{hash(data['email'])}",
            'email': data['email'],
            'name': data['name'],
            'profile_picture': '',
            'phone_number': '',
            'email_verified': True
        }
        
        # Create user in Firestore
        user = user_service.create_or_update_firebase_user(firebase_user_data)
        
        # If username provided, complete setup automatically
        if data.get('username'):
            setup_data = {
                'username': data['username'],
                'dietary_restrictions': data.get('dietary_restrictions', []),
                'preferences': data.get('preferences', {})
            }
            user = user_service.complete_user_setup(user['id'], setup_data)
        
        # Create JWT tokens
        tokens = jwt_service.create_tokens(user)
        
        return jsonify({
            'message': 'Test user created successfully',
            'user': {
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'username': user['username'],
                'firebase_uid': user['firebase_uid'],
                'profile_picture': user.get('profile_picture', ''),
                'phone_number': user.get('phone_number', ''),
                'setup_completed': user.get('setup_completed', False),
                'preferences': user.get('preferences', {}),
                'dietary_restrictions': user.get('dietary_restrictions', [])
            },
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'token_type': tokens['token_type'],
            'expires_in': tokens['expires_in'],
            'setup_required': not user.get('setup_completed', False)
        }), 201
        
    except ValidationError as e:
        return jsonify({
            'error': 'Validation error',
            'message': 'Invalid input data',
            'details': e.messages
        }), 400
    except Exception as e:
        print(f"Test user creation error: {e}")
        return jsonify({
            'error': 'User creation failed',
            'message': 'An error occurred while creating test user.'
        }), 500


@auth_bp.route('/setup', methods=['POST'])
@jwt_required()
def complete_user_setup():
    """Complete user setup with username and dietary restrictions"""
    try:
        # Validate input
        schema = UserSetupSchema()
        data = schema.load(request.get_json())
        
        # Get current user
        user_id = get_jwt_identity()
        current_user = user_service.get_user_by_id(user_id)
        
        if not current_user:
            return jsonify({
                'error': 'User not found',
                'message': 'User account not found.'
            }), 404
        
        # Check if setup is already completed
        if current_user.get('setup_completed'):
            return jsonify({
                'error': 'Setup already completed',
                'message': 'User setup has already been completed.'
            }), 400
        
        # Complete setup
        updated_user = user_service.complete_user_setup(user_id, data)
        
        if not updated_user:
            return jsonify({
                'error': 'Setup failed',
                'message': 'Username may already be taken or invalid.'
            }), 400
        
        # Create new JWT tokens with updated user data
        tokens = jwt_service.create_tokens(updated_user)
        
        return jsonify({
            'message': 'User setup completed successfully',
            'user': {
                'id': updated_user['id'],
                'name': updated_user['name'],
                'email': updated_user['email'],
                'username': updated_user['username'],
                'firebase_uid': updated_user['firebase_uid'],
                'profile_picture': updated_user.get('profile_picture', ''),
                'setup_completed': updated_user['setup_completed'],
                'preferences': updated_user.get('preferences', {}),
                'dietary_restrictions': updated_user.get('dietary_restrictions', [])
            },
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'token_type': tokens['token_type'],
            'expires_in': tokens['expires_in'],
            'setup_required': False  # Setup is now completed
        }), 200
        
    except ValidationError as e:
        return jsonify({
            'error': 'Validation error',
            'message': 'Invalid input data',
            'details': e.messages
        }), 400
    except Exception as e:
        print(f"User setup error: {e}")
        return jsonify({
            'error': 'Setup failed',
            'message': 'An error occurred during setup. Please try again.'
        }), 500


@auth_bp.route('/check-username', methods=['POST'])
def check_username():
    """Check if username is available"""
    try:
        # Validate input
        schema = CheckUsernameSchema()
        data = schema.load(request.get_json())
        
        # Check if username is taken
        is_taken = user_service.is_username_taken(data['username'])
        
        return jsonify({
            'username': data['username'],
            'available': not is_taken
        }), 200
        
    except ValidationError as e:
        return jsonify({
            'error': 'Validation error',
            'message': 'Invalid input data',
            'details': e.messages
        }), 400
    except Exception as e:
        print(f"Username check error: {e}")
        return jsonify({
            'error': 'Check failed',
            'message': 'An error occurred while checking username availability.'
        }), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user information"""
    try:
        user_id = get_jwt_identity()
        user = user_service.get_user_by_id(user_id)
        
        if not user:
            return jsonify({
                'error': 'User not found',
                'message': 'The user account could not be found.'
            }), 404
        
        return jsonify({
            'user': {
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'username': user['username'],
                'firebase_uid': user['firebase_uid'],
                'google_id': user.get('google_id'),
                'profile_picture': user.get('profile_picture', ''),
                'phone_number': user.get('phone_number', ''),
                'setup_completed': user.get('setup_completed', False),
                'preferences': user.get('preferences', {}),
                'dietary_restrictions': user.get('dietary_restrictions', []),
                'created_at': user.get('created_at'),
                'updated_at': user.get('updated_at')
            }
        }), 200
        
    except Exception as e:
        print(f"Get current user error: {e}")
        return jsonify({
            'error': 'Failed to get user',
            'message': 'An error occurred while retrieving user information.'
        }), 500


@auth_bp.route('/update-profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile information"""
    try:
        user_id = get_jwt_identity()
        updates = request.get_json()
        
        # Remove sensitive fields that shouldn't be updated directly
        sensitive_fields = ['firebase_uid', 'google_id', 'setup_completed', 'created_at', 'updated_at']
        for field in sensitive_fields:
            updates.pop(field, None)
        
        # Update user
        updated_user = user_service.update_user(user_id, updates)
        
        if not updated_user:
            return jsonify({
                'error': 'Update failed',
                'message': 'Could not update user profile. Username may already be taken.'
            }), 400
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': {
                'id': updated_user['id'],
                'name': updated_user['name'],
                'email': updated_user['email'],
                'username': updated_user['username'],
                'firebase_uid': updated_user['firebase_uid'],
                'profile_picture': updated_user.get('profile_picture', ''),
                'phone_number': updated_user.get('phone_number', ''),
                'setup_completed': updated_user.get('setup_completed', False),
                'preferences': updated_user.get('preferences', {}),
                'dietary_restrictions': updated_user.get('dietary_restrictions', [])
            }
        }), 200
        
    except Exception as e:
        print(f"Profile update error: {e}")
        return jsonify({
            'error': 'Update failed',
            'message': 'An error occurred while updating profile.'
        }), 500


@auth_bp.route('/check-token', methods=['GET'])
@jwt_required()
def check_token():
    """Check if current token is valid"""
    try:
        token_status = check_token_validity()
        
        if token_status['valid']:
            return jsonify({
                'valid': True,
                'user': {
                    'id': token_status['user_id'],
                    'email': token_status['email'],
                    'username': token_status['username'],
                    'name': token_status['name'],
                    'setup_completed': token_status.get('setup_completed', False)
                }
            }), 200
        else:
            return jsonify({
                'valid': False,
                'error': token_status.get('error', 'Invalid token')
            }), 401
            
    except Exception as e:
        print(f"Token check error: {e}")
        return jsonify({
            'valid': False,
            'error': 'Token validation failed'
        }), 401


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (client-side token removal)"""
    try:
        # In a stateless JWT system, logout is typically handled client-side
        # by removing the token from storage. We can add token blacklisting
        # here if needed in the future.
        
        return jsonify({
            'message': 'Logout successful',
            'instructions': 'Please remove the access token from your client storage.'
        }), 200
        
    except Exception as e:
        print(f"Logout error: {e}")
        return jsonify({
            'error': 'Logout failed',
            'message': 'An error occurred during logout.'
        }), 500


@auth_bp.route('/debug-token', methods=['GET'])
@jwt_required()
def debug_token():
    """Debug endpoint to check JWT token contents"""
    try:
        from flask_jwt_extended import get_jwt, get_jwt_identity
        
        # Get token identity and claims
        user_id = get_jwt_identity()
        claims = get_jwt()
        
        return jsonify({
            'jwt_identity': user_id,
            'jwt_claims': claims,
            'user_from_token': get_user_from_token()
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Debug failed',
            'message': str(e)
        }), 500


# Error handlers for the auth blueprint
@auth_bp.errorhandler(ValidationError)
def handle_validation_error(e):
    """Handle marshmallow validation errors"""
    return jsonify({
        'error': 'Validation error',
        'message': 'Invalid input data',
        'details': e.messages
    }), 400


@auth_bp.errorhandler(404)
def handle_not_found(e):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Not found',
        'message': 'The requested resource was not found.'
    }), 404


@auth_bp.errorhandler(500)
def handle_internal_error(e):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred. Please try again later.'
    }), 500 