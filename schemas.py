from pydantic import BaseModel, Field
from typing import List, Optional

class SelectionCreate(BaseModel):
    name: str
    node_ids: List[int]

class TestCase(BaseModel):
    id: str = Field(..., description="E.g., TC-CT200-01")
    title: str = Field(..., description="Actionable summary of test case")
    description: str = Field(..., description="Step-by-step instructions to execute")
    expected_result: str = Field(..., description="System response requirements")

class TestCaseGenerationSchema(BaseModel):
    test_cases: List[TestCase]
