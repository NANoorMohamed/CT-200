import pytest
from parser import parse_document

def test_duplicate_headings_resolution():
    """Verify that identical headings like 'Error Codes' located at different paths resolve correctly."""
    raw_text = """
4. Alarms and Safety Behavior
4.2 Error Codes
Code | Meaning | Device Behavior
E1 | Cuff leak

7. Troubleshooting
7.1 Error Codes
If a code from Section 4.2 appears and persists...
    """
    nodes = parse_document(raw_text)
    
    # Assert nodes are separated by parent scopes
    node_4_2 = next(n for n in nodes if n["section_number"] == "4.2")
    node_7_1 = next(n for n in nodes if n["section_number"] == "7.1")
    
    assert node_4_2["heading"] == "Error Codes"
    assert node_7_1["heading"] == "Error Codes"
    assert node_4_2["path"] == "4/4.2"
    assert node_7_1["path"] == "7/7.1"
    assert node_4_2["parent_section"] == "4"
    assert node_7_1["parent_section"] == "7"

def test_skipped_nesting_levels():
    """Verify that a skipped level (2.1 -> 2.1.1.1) correctly falls back to nearest active parent."""
    raw_text = """
2. Physical and Electrical Specifications
2.1 General Specifications
Parameter | Value
2.1.1.1 Battery Life Under Typical Use
Four AA alkaline batteries provide approximately 250 measurement cycles.
    """
    nodes = parse_document(raw_text)
    
    node_deep = next(n for n in nodes if n["section_number"] == "2.1.1.1")
    assert node_deep["parent_section"] == "2.1" # Successfully skipped 2.1.1 mapping
    assert node_deep["path"] == "2/2.1/2.1.1.1"

def test_out_of_order_headings():
    """Ensure that non-sequential layout numbering order does not break hierarchy association."""
    raw_text = """
3. Device Operation
3.1 Powering On and Profile Selection
Press and hold.
3.4 Auto Shutoff
To conserve battery...
3.3 Result Display and Classification
After a completed measurement...
    """
    nodes = parse_document(raw_text)
    
    node_3_4 = next(n for n in nodes if n["section_number"] == "3.4")
    node_3_3 = next(n for n in nodes if n["section_number"] == "3.3")
    
    assert node_3_4["parent_section"] == "3"
    assert node_3_3["parent_section"] == "3"
