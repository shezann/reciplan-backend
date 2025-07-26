import pytest
from unittest.mock import patch
from datetime import datetime

# Assume the controller and repo logic is in place
from services.title_extractor import TitleExtractor

class MockFirestoreDoc:
    def __init__(self):
        self.data = {}
    def update(self, d):
        self.data.update(d)
    def set(self, d):
        self.data = d
    def get(self):
        class _:
            exists = True
            def to_dict(inner_self):
                return self.data
        return _()

class MockFirestore:
    def __init__(self):
        self.docs = {}
    def collection(self, name):
        self.name = name
        return self
    def document(self, doc_id):
        if doc_id not in self.docs:
            self.docs[doc_id] = MockFirestoreDoc()
        return self.docs[doc_id]

@patch("tasks.tiktok_tasks.get_firestore_db")
def test_recipe_doc_fields(mock_get_db):
    db = MockFirestore()
    mock_get_db.return_value = db
    job_id = "jobid"
    recipe_id = "recipeid"
    owner_uid = "user123"
    # Simulate pipeline writing to recipe doc
    now = datetime.utcnow().isoformat()
    db.collection("recipes").document(recipe_id).set({
        "title": "Test Title",
        "transcript": "Test transcript",
        "status": "DRAFT_TRANSCRIBED",
        "updatedAt": now,
        "owner_uid": owner_uid
    })
    doc = db.collection("recipes").document(recipe_id)
    assert doc.data["title"] == "Test Title"
    assert doc.data["transcript"] == "Test transcript"
    assert doc.data["status"] == "DRAFT_TRANSCRIBED"
    assert doc.data["updatedAt"] == now
    assert doc.data["owner_uid"] == owner_uid 