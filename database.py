import os
import json
import datetime
import uuid
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///./cardiotrack.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Local Document Store Mocking MongoDB
NOSQL_FILE = "nosql_test_cases.json"

class DocumentVersion(Base):
    __tablename__ = 'document_versions'
    id = Column(Integer, primary_key=True, index=True)
    version_string = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DocumentNode(Base):
    __tablename__ = 'document_nodes'
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey('document_versions.id'), nullable=False)
    logical_node_uuid = Column(String, nullable=False) # Identical across versions
    heading = Column(String, nullable=False)
    section_number = Column(String, nullable=True)
    level = Column(Integer, nullable=False)
    body_text = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey('document_nodes.id'), nullable=True)
    content_hash = Column(String, nullable=False)
    path = Column(String, nullable=False) # E.g., "3/3.3"

    version = relationship("DocumentVersion")
    parent = relationship("DocumentNode", remote_side=[id], backref="children")

class Selection(Base):
    __tablename__ = 'selections'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    version_id = Column(Integer, ForeignKey('document_versions.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SelectionNode(Base):
    __tablename__ = 'selection_nodes'
    id = Column(Integer, primary_key=True)
    selection_id = Column(String, ForeignKey('selections.id'), nullable=False)
    node_id = Column(Integer, ForeignKey('document_nodes.id'), nullable=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class LocalJSONDocumentStore:
    """A lightweight local JSON document store playing the role of MongoDB."""
    def __init__(self, filename=NOSQL_FILE):
        self.filename = filename
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as f:
                json.dump({}, f)

    def save(self, key: str, value: dict):
        with open(self.filename, 'r') as f:
            data = json.load(f)
        data[key] = value
        with open(self.filename, 'w') as f:
            json.dump(data, f, indent=4)

    def get(self, key: str) -> dict:
        with open(self.filename, 'r') as f:
            data = json.load(f)
        return data.get(key)
