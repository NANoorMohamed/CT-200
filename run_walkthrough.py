import time
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

MANUAL_V1 = """
1. Device Overview
The CardioTrack CT-200 is an upper-arm blood pressure monitor.
2. Physical and Electrical Specifications
2.1 General Specifications
Pressure range | 0-299 mmHg
2.1.1.1 Battery Life Under Typical Use
Four AA batteries provide approximately 250 measurement cycles.
"""

# V2: We update battery life cycles and remove 2.1 General Specifications to verify deletion/modification drift
MANUAL_V2 = """
1. Device Overview
The CardioTrack CT-200 is an upper-arm blood pressure monitor.
2. Physical and Electrical Specifications
2.1.1.1 Battery Life Under Typical Use
Four AA batteries provide approximately 300 measurement cycles.
"""

def execute_walkthrough():
    print("--- STEP 1: Ingesting Manual V1 ---")
    r_v1 = client.post("/api/documents/ingest?version_string=v1", content=MANUAL_V1)
    print("Ingestion Status:", r_v1.status_code, r_v1.json())

    print("\n--- STEP 2: Browsing Top-Level Nodes (v1) ---")
    r_browse = client.get("/api/documents/browse?version=v1")
    print("Top-Level Sections:", r_browse.json())

    print("\n--- STEP 3: Selecting Nodes & Pinning to Selection (v1) ---")
    # Fetching the specific node IDs created
    search_res = client.get("/api/documents/search?query=Battery")
    node_id = search_res.json()[0]["id"]
    print(f"Found Node ID {node_id} matching section 2.1.1.1")

    selection_payload = {"name": "Battery Safety Suite", "node_ids": [node_id]}
    r_sel = client.post("/api/selections", json=selection_payload)
    sel_id = r_sel.json()["selection_id"]
    print("Selection Record Created with Pinned Node IDs:", r_sel.json())

    print("\n--- STEP 4: Generating Test Cases (v1) ---")
    r_gen = client.post(f"/api/selections/{sel_id}/generate")
    print("LLM Output Parsed into JSON:", r_gen.json())

    print("\n--- STEP 5: Ingesting Manual V2 (Simulating Updates) ---")
    r_v2 = client.post("/api/documents/ingest?version_string=v2", content=MANUAL_V2)
    print("V2 Ingestion Status:", r_v2.status_code, r_v2.json())

    print("\n--- STEP 6: Verifying Version Pinning Integrity (Retrieval API Audit) ---")
    # Pinned selection continues to resolve to its original version-safe structure!
    r_audit = client.get(f"/api/test-cases/{sel_id}")
    audit_data = r_audit.json()
    print("Staleness Analysis Summary:")
    print("  Selection Name:", audit_data["selection_name"])
    print("  Is Stale:", audit_data["is_stale"])
    print("  Change Impacts:", audit_data["drift_summary"])

if __name__ == "__main__":
    execute_walkthrough()
