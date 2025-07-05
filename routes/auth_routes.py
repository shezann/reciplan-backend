from flask import request, jsonify
from flask_restful import Resource
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from services.firestore_service import firestore_service
from marshmallow import Schema, fields, ValidationError
import bcrypt

class LoginSchema(Schema):
    """Schema for login validation"""
    email = fields.Email(required=True)
    password = fields.Str(required=True)

class AuthResource(Resource):
    """Resource for handling authentication operations"""
    
    def post(self):
        """User login"""
        try:
            # Validate input data
            login_schema = LoginSchema()
            data = login_schema.load(request.get_json())
            
            # Find user by email
            users = firestore_service.query_collection('users', 'email', '==', data['email'])
            
            if not users:
                return {'error': 'Invalid email or password'}, 401
            
            user = users[0]
            
            # Verify password
            if not bcrypt.checkpw(data['password'].encode('utf-8'), user['password'].encode('utf-8')):
                return {'error': 'Invalid email or password'}, 401
            
            # Create access token
            access_token = create_access_token(identity=user['id'])
            
            # Return user data and token (without password)
            user_data = user.copy()
            user_data.pop('password', None)
            
            return {
                'access_token': access_token,
                'user': user_data
            }, 200
            
        except ValidationError as e:
            return {'error': 'Validation error', 'details': e.messages}, 400
        except Exception as e:
            return {'error': 'Login failed'}, 500
    
    @jwt_required()
    def get(self):
        """Get current user information"""
        try:
            current_user_id = get_jwt_identity()
            
            # Get user from Firestore
            user = firestore_service.get_document('users', current_user_id)
            
            if not user:
                return {'error': 'User not found'}, 404
            
            # Remove sensitive information
            user.pop('password', None)
            
            return {'user': user}, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve user information'}, 500 