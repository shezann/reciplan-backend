from flask import request, jsonify
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.firestore_service import firestore_service
from marshmallow import Schema, fields, ValidationError
import bcrypt

class UserSchema(Schema):
    """Schema for user validation"""
    name = fields.Str(required=True, validate=lambda x: len(x) >= 2)
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=lambda x: len(x) >= 6)
    preferences = fields.Dict(load_default={})
    dietary_restrictions = fields.List(fields.Str(), load_default=[])

class UserUpdateSchema(Schema):
    """Schema for user update validation"""
    name = fields.Str(validate=lambda x: len(x) >= 2)
    email = fields.Email()
    preferences = fields.Dict()
    dietary_restrictions = fields.List(fields.Str())

class UserListResource(Resource):
    """Resource for handling user collection operations"""
    
    @jwt_required()
    def get(self):
        """Get all users (admin only) or filtered users"""
        try:
            current_user_id = get_jwt_identity()
            
            # Get query parameters
            limit = request.args.get('limit', type=int)
            
            # Get users from Firestore
            users = firestore_service.get_collection('users', limit=limit)
            
            # Remove sensitive information
            for user in users:
                user.pop('password', None)
            
            return {'users': users}, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve users'}, 500
    
    def post(self):
        """Create a new user"""
        try:
            # Validate input data
            user_schema = UserSchema()
            data = user_schema.load(request.get_json())
            
            # Check if user already exists
            existing_users = firestore_service.query_collection('users', 'email', '==', data['email'])
            if existing_users:
                return {'error': 'User with this email already exists'}, 409
            
            # Hash password
            password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
            data['password'] = password_hash.decode('utf-8')
            
            # Create user
            user_id = firestore_service.create_document('users', data)
            
            # Return user data without password
            user_data = data.copy()
            user_data.pop('password')
            user_data['id'] = user_id
            
            return {'user': user_data}, 201
            
        except ValidationError as e:
            return {'error': 'Validation error', 'details': e.messages}, 400
        except Exception as e:
            return {'error': 'Failed to create user'}, 500

class UserResource(Resource):
    """Resource for handling individual user operations"""
    
    @jwt_required()
    def get(self, user_id):
        """Get a specific user"""
        try:
            current_user_id = get_jwt_identity()
            
            # Users can only access their own data unless they're admin
            if current_user_id != user_id:
                # Here you could add admin check logic
                return {'error': 'Unauthorized'}, 403
            
            # Get user from Firestore
            user = firestore_service.get_document('users', user_id)
            
            if not user:
                return {'error': 'User not found'}, 404
            
            # Remove sensitive information
            user.pop('password', None)
            
            return {'user': user}, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve user'}, 500
    
    @jwt_required()
    def put(self, user_id):
        """Update a user"""
        try:
            current_user_id = get_jwt_identity()
            
            # Users can only update their own data
            if current_user_id != user_id:
                return {'error': 'Unauthorized'}, 403
            
            # Validate input data
            user_schema = UserUpdateSchema()
            data = user_schema.load(request.get_json())
            
            # Check if user exists
            existing_user = firestore_service.get_document('users', user_id)
            if not existing_user:
                return {'error': 'User not found'}, 404
            
            # If email is being updated, check for conflicts
            if 'email' in data:
                existing_users = firestore_service.query_collection('users', 'email', '==', data['email'])
                if existing_users and existing_users[0]['id'] != user_id:
                    return {'error': 'User with this email already exists'}, 409
            
            # Update user
            success = firestore_service.update_document('users', user_id, data)
            
            if not success:
                return {'error': 'Failed to update user'}, 500
            
            # Return updated user data
            updated_user = firestore_service.get_document('users', user_id)
            updated_user.pop('password', None)
            
            return {'user': updated_user}, 200
            
        except ValidationError as e:
            return {'error': 'Validation error', 'details': e.messages}, 400
        except Exception as e:
            return {'error': 'Failed to update user'}, 500
    
    @jwt_required()
    def delete(self, user_id):
        """Delete a user"""
        try:
            current_user_id = get_jwt_identity()
            
            # Users can only delete their own account
            if current_user_id != user_id:
                return {'error': 'Unauthorized'}, 403
            
            # Check if user exists
            existing_user = firestore_service.get_document('users', user_id)
            if not existing_user:
                return {'error': 'User not found'}, 404
            
            # Delete user
            success = firestore_service.delete_document('users', user_id)
            
            if not success:
                return {'error': 'Failed to delete user'}, 500
            
            return {'message': 'User deleted successfully'}, 200
            
        except Exception as e:
            return {'error': 'Failed to delete user'}, 500 