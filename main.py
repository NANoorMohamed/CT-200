import os
import difflib
import uuid
import json
import requests
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from database import (
    Base, engine, get_db, DocumentVersion, DocumentNode, 
    Selection, SelectionNode, LocalJSONDocumentStore
)
from parser import parse_document
from schemas import SelectionCreate, TestCaseGenerationSchema

app = FastAPI(title="CardioTrack Traceability API")
Base.metadata.create_all(bind=engine)
nosql_store = LocalJSONDocumentStore()

# ----------------- INGESTION -----------------
@app.post("/api/documents/ingest", status_code=201)
def ingest_document(version_string: str, text: str, db: Session = Depends(get_db)):
    existing_ver = db.query(DocumentVersion).filter(DocumentVersion.version_string == version_string).first()
    if existing_ver:
        raise HTTPException(status_code=400, detail="Version already exists")
        
    doc_version = DocumentVersion(version_string=version_string)
    db.add(doc_version)
    db.commit()
    db.refresh(doc_version)
    
    parsed_nodes = parse_document(text)
    
    # Fetch v1 nodes to resolve Logical Node IDs if applicable
    previous_nodes = {}
    prev_version = db.query(DocumentVersion).filter(DocumentVersion.id != doc_version.id).order_by(DocumentVersion.id.desc()).first()
    if prev_version:
        prev_nodes = db.query(DocumentNode).filter(DocumentNode.version_id == prev_version.id).all()
        previous_nodes = {node.path: node for node in prev_nodes}
        
    db_node_map = {} # Maps section_number to DB Node
    
    for p_node in parsed_nodes:
        # Check semantic lineage using normalized path
        path = p_node["path"]
        if path in previous_nodes:
            logical_uuid = previous_nodes[path].logical_node_uuid
        else:
            logical_uuid = str(uuid.uuid4())
            
        db_node = DocumentNode(
            version_id=doc_version.id,
            logical_node_uuid=logical_uuid,
            heading=p_node["heading"],
            section_number=p_node["section_number"],
            level=p_node["level"],
            body_text=p_node["body_text"],
            content_hash=p_node["content_hash"],
            path=path
        )
        db.add(db_node)
        db.flush() # Populates db_node.id
        db_node_map[p_node["section_number"]] = db_node
        
    # Wire relationships
    for p_node in parsed_nodes:
        db_node = db_node_map[p_node["section_number"]]
        if p_node["parent_section"]:
            parent_db_node = db_node_map[p_node["parent_section"]]
            db_node.parent_id = parent_db_node.id
            
    db.commit()
    return {"message": "Document ingested successfully", "version_id": doc_version.id, "nodes_parsed": len(parsed_nodes)}

# ----------------- BROWSE API -----------------
@app.get("/api/documents/browse")
def list_top_level(version: Optional[str] = None, db: Session = Depends(get_db)):
    if version:
        ver_record = db.query(DocumentVersion).filter(DocumentVersion.version_string == version).first()
    else:
        ver_record = db.query(DocumentVersion).order_by(DocumentVersion.id.desc()).first()
        
    if not ver_record:
        raise HTTPException(status_code=404, detail="No versions found")
        
    nodes = db.query(DocumentNode).filter(
        DocumentNode.version_id == ver_record.id,
        DocumentNode.parent_id == None
    ).all()
    
    return [{"id": n.id, "section": n.section_number, "heading": n.heading, "level": n.level} for n in nodes]

@app.get("/api/documents/nodes/{node_id}")
def get_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(DocumentNode).filter(DocumentNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
        
    return {
        "id": node.id,
        "heading": node.heading,
        "section_number": node.section_number,
        "level": node.level,
        "body_text": node.body_text,
        "content_hash": node.content_hash,
        "path": node.path,
        "children": [{"id": child.id, "heading": child.heading, "section": child.section_number} for child in node.children]
    }

@app.get("/api/documents/search")
def search_nodes(query: str, db: Session = Depends(get_db)):
    results = db.query(DocumentNode).filter(
        DocumentNode.heading.contains(query) | DocumentNode.body_text.contains(query)
    ).all()
    return [{"id": r.id, "heading": r.heading, "section": r.section_number, "version_id": r.version_id} for r in results]

@app.get("/api/documents/nodes/{node_id}/diff")
def diff_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(DocumentNode).filter(DocumentNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
        
    # Get all version changes for this physical path
    all_versions = db.query(DocumentNode).filter(
        DocumentNode.logical_node_uuid == node.logical_node_uuid
    ).order_by(DocumentNode.version_id.asc()).all()
    
    if len(all_versions) < 2:
        return {"message": "No multiple versions available for diff tracking."}
        
    diff_outputs = []
    for idx in range(1, len(all_versions)):
        v_prev = all_versions[idx - 1]
        v_curr = all_versions[idx]
        
        lines_prev = v_prev.body_text.splitlines()
        lines_curr = v_curr.body_text.splitlines()
        diff = list(difflib.unified_diff(lines_prev, lines_curr, fromfile=f"v{v_prev.version_id}", tofile=f"v{v_curr.version_id}"))
        
        diff_outputs.append({
            "comparison": f"Version ID {v_prev.version_id} -> Version ID {v_curr.version_id}",
            "changed": v_prev.content_hash != v_curr.content_hash,
            "diff": "\n".join(diff)
        })
        
    return {"logical_node_uuid": node.logical_node_uuid, "path": node.path, "changes": diff_outputs}

# ----------------- SELECTION API -----------------
@app.post("/api/selections", status_code=201)
def create_selection(payload: SelectionCreate, db: Session = Depends(get_db)):
    if not payload.node_ids:
        raise HTTPException(status_code=400, detail="Cannot create empty selection")
        
    # Ensure all nodes exist and belong to the exact same document version
    nodes = db.query(DocumentNode).filter(DocumentNode.id.in_(payload.node_ids)).all()
    if len(nodes) != len(payload.node_ids):
        raise HTTPException(status_code=400, detail="Some selection node IDs are invalid")
        
    version_ids = {n.version_id for n in nodes}
    if len(version_ids) > 1:
        raise HTTPException(status_code=400, detail="Selections must be pinned to the same version index")
        
    pinned_version_id = list(version_ids)[0]
    selection_id = str(uuid.uuid4())
    
    selection = Selection(id=selection_id, name=payload.name, version_id=pinned_version_id)
    db.add(selection)
    
    for node in nodes:
        db.add(SelectionNode(selection_id=selection_id, node_id=node.id))
        
    db.commit()
    return {"selection_id": selection_id, "name": payload.name, "pinned_version_id": pinned_version_id}

# ----------------- LLM GENERATION API -----------------
@app.post("/api/selections/{selection_id}/generate")
def generate_test_cases(selection_id: str, force_regenerate: bool = False, db: Session = Depends(get_db)):
    selection = db.query(Selection).filter(Selection.id == selection_id).first()
    if not selection:
        raise HTTPException(status_code=404, detail="Selection not found")
        
    # Check JSON/NoSQL cache for duplicate submissions
    cached = nosql_store.get(selection_id)
    if cached and not force_regenerate:
        return {"source": "cache", "data": cached}
        
    # Build text payload
    selection_nodes = db.query(DocumentNode).join(SelectionNode).filter(SelectionNode.selection_id == selection_id).all()
    combined_context = "\n\n".join([f"Section {n.section_number}: {n.heading}\n{n.body_text}" for n in selection_nodes])
    
    # Structure-isolated LLM Invocations
    prompt = f"""You are a medical device QA Software Test Engineer. 
    Analyze the safety critical requirements below and output exactly 3-5 QA test-case ideas.
    You MUST output valid, plain JSON matches this Pydantic schema structure:
    {{
      "test_cases": [
         {{
           "id": "TC-01",
           "title": "Title description",
           "description": "execution details",
           "expected_result": "expected verification output"
         }}
      ]
    }}
    Do not add extra explanations or Markdown backticks.
    
    Device Requirement Details:
    {combined_context}
    """
    
    test_cases_json = None
    try:
        # Mocking an actual LLM integration (use requests/openai here in real environment)
        # Using a simulated fallback router to handle parsing irregularities gracefully
        test_cases_json = simulate_llm_call(prompt)
        # Validate output formatting structure using Pydantic
        parsed_data = TestCaseGenerationSchema.parse_raw(test_cases_json)
        structured_data = parsed_data.dict()
    except Exception as e:
        # Fallback Recovery Plan
        structured_data = {
            "test_cases": [
                {
                    "id": "TC-FALLBACK",
                    "title": "LLM Validation Failed Recovery Case",
                    "description": f"Failed to cleanly structure JSON output. RAW payload: {test_cases_json}",
                    "expected_result": "Data saved securely with degraded system telemetry for tracing."
                }
            ],
            "telemetry_error": str(e)
        }
        
    # Store pinned state context hashes for drift detection tracking
    payload_to_store = {
        "selection_id": selection_id,
        "selection_name": selection.name,
        "pinned_version_id": selection.version_id,
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "input_node_hashes": {n.logical_node_uuid: n.content_hash for n in selection_nodes},
        "output": structured_data
    }
    
    nosql_store.save(selection_id, payload_to_store)
    return {"source": "live_llm", "data": payload_to_store}

def simulate_llm_call(prompt: str) -> str:
    """Mock helper that returns a standard structure or simulated malformed JSON to test fallbacks."""
    # Real LLM Call template:
    # response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    return json.dumps({
        "test_cases": [
            {
                "id": "TC-CT200-VAL1",
                "title": "Validate Physical Specifications Tolerances",
                "description": "Connect calibrator machine and trigger pressure sweeps to check pressure range of 0-299 mmHg is within precision deviation of +/- 3 mmHg.",
                "expected_result": "Device returns error code or registers reading inside +/- 3 mmHg boundaries."
            }
        ]
    })

# ----------------- RETRIEVAL & STALENESS API -----------------
@app.get("/api/test-cases/{selection_id}")
def get_test_cases(selection_id: str, db: Session = Depends(get_db)):
    test_case_record = nosql_store.get(selection_id)
    if not test_case_record:
        raise HTTPException(status_code=404, detail="No generated cases found for this selection ID")
        
    # Analyze Drift (Staleness Audit)
    # Find the latest document version overall
    latest_version = db.query(DocumentVersion).order_by(DocumentVersion.id.desc()).first()
    pinned_hashes = test_case_record["input_node_hashes"]
    
    staleness_reports = []
    is_stale = False
    
    for logical_uuid, saved_hash in pinned_hashes.items():
        # Get the same node in the latest version of the document
        latest_node = db.query(DocumentNode).filter(
            DocumentNode.logical_node_uuid == logical_uuid,
            DocumentNode.version_id == latest_version.id
        ).first()
        
        if not latest_node:
            # Node was deleted in version 2
            is_stale = True
            staleness_reports.append({
                "logical_node_uuid": logical_uuid,
                "status": "DELETED",
                "message": "The reference section has been removed in the latest document update."
            })
        elif latest_node.content_hash != saved_hash:
            # Node body text changed
            is_stale = True
            staleness_reports.append({
                "logical_node_uuid": logical_uuid,
                "section": latest_node.section_number,
                "status": "MODIFIED",
                "message": "The body text of this section has been altered. Test cases may need verification."
            })
        else:
            staleness_reports.append({
                "logical_node_uuid": logical_uuid,
                "section": latest_node.section_number,
                "status": "STABLE",
                "message": "No modification detected."
            })
            
    return {
        "selection_id": selection_id,
        "selection_name": test_case_record["selection_name"],
        "is_stale": is_stale,
        "drift_summary": staleness_reports,
        "test_cases": test_case_record["output"]["test_cases"]
    }
