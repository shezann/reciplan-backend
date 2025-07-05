from typing import Dict, List, Optional, Any
from google.cloud.firestore_v1 import DocumentSnapshot, Query
from google.cloud.firestore_v1.base_query import FieldFilter
from config.firebase_config import firebase_config
from datetime import datetime

class FirestoreService:
    """Service layer for Firestore operations"""
    
    def __init__(self):
        self.db = firebase_config.get_db()
    
    def create_document(self, collection_name: str, document_data: Dict[str, Any], document_id: Optional[str] = None) -> str:
        """
        Create a new document in a collection
        
        Args:
            collection_name: Name of the collection
            document_data: Data to store in the document
            document_id: Optional custom document ID
            
        Returns:
            Document ID of the created document
        """
        try:
            # Add timestamp
            document_data['created_at'] = datetime.utcnow()
            document_data['updated_at'] = datetime.utcnow()
            
            collection_ref = self.db.collection(collection_name)
            
            if document_id:
                doc_ref = collection_ref.document(document_id)
                doc_ref.set(document_data)
                return document_id
            else:
                doc_ref = collection_ref.add(document_data)
                return doc_ref[1].id
                
        except Exception as e:
            print(f"Error creating document: {e}")
            raise
    
    def get_document(self, collection_name: str, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID
        
        Args:
            collection_name: Name of the collection
            document_id: ID of the document
            
        Returns:
            Document data or None if not found
        """
        try:
            doc_ref = self.db.collection(collection_name).document(document_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
            
        except Exception as e:
            print(f"Error getting document: {e}")
            raise
    
    def update_document(self, collection_name: str, document_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update a document
        
        Args:
            collection_name: Name of the collection
            document_id: ID of the document
            update_data: Data to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add timestamp
            update_data['updated_at'] = datetime.utcnow()
            
            doc_ref = self.db.collection(collection_name).document(document_id)
            doc_ref.update(update_data)
            return True
            
        except Exception as e:
            print(f"Error updating document: {e}")
            return False
    
    def delete_document(self, collection_name: str, document_id: str) -> bool:
        """
        Delete a document
        
        Args:
            collection_name: Name of the collection
            document_id: ID of the document
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.db.collection(collection_name).document(document_id)
            doc_ref.delete()
            return True
            
        except Exception as e:
            print(f"Error deleting document: {e}")
            return False
    
    def get_collection(self, collection_name: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all documents in a collection
        
        Args:
            collection_name: Name of the collection
            limit: Optional limit on number of documents
            
        Returns:
            List of documents
        """
        try:
            collection_ref = self.db.collection(collection_name)
            
            if limit:
                query = collection_ref.limit(limit)
            else:
                query = collection_ref
            
            docs = query.stream()
            documents = []
            
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                documents.append(data)
            
            return documents
            
        except Exception as e:
            print(f"Error getting collection: {e}")
            raise
    
    def query_collection(self, collection_name: str, field: str, operator: str, value: Any, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query documents in a collection
        
        Args:
            collection_name: Name of the collection
            field: Field to query on
            operator: Query operator ('==', '!=', '<', '<=', '>', '>=', 'in', 'not-in', 'array-contains', 'array-contains-any')
            value: Value to compare against
            limit: Optional limit on number of documents
            
        Returns:
            List of matching documents
        """
        try:
            collection_ref = self.db.collection(collection_name)
            query = collection_ref.where(field, operator, value)
            
            if limit:
                query = query.limit(limit)
            
            docs = query.stream()
            documents = []
            
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                documents.append(data)
            
            return documents
            
        except Exception as e:
            print(f"Error querying collection: {e}")
            raise
    
    def batch_write(self, operations: List[Dict[str, Any]]) -> bool:
        """
        Perform batch write operations
        
        Args:
            operations: List of operation dictionaries with 'type', 'collection', 'document_id', and 'data' keys
            
        Returns:
            True if successful, False otherwise
        """
        try:
            batch = self.db.batch()
            
            for operation in operations:
                operation_type = operation.get('type')
                collection_name = operation.get('collection')
                document_id = operation.get('document_id')
                data = operation.get('data', {})
                
                doc_ref = self.db.collection(collection_name).document(document_id)
                
                if operation_type == 'set':
                    data['created_at'] = datetime.utcnow()
                    data['updated_at'] = datetime.utcnow()
                    batch.set(doc_ref, data)
                elif operation_type == 'update':
                    data['updated_at'] = datetime.utcnow()
                    batch.update(doc_ref, data)
                elif operation_type == 'delete':
                    batch.delete(doc_ref)
            
            batch.commit()
            return True
            
        except Exception as e:
            print(f"Error in batch write: {e}")
            return False

# Global Firestore service instance
firestore_service = FirestoreService() 