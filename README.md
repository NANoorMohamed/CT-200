This project is a FastAPI-based backend designed to ingest, version, and manage structured medical device documentation (specifically the CardioTrack CT-200 User Manual). It includes an API to parse document trees, track document version drift, and generate/manage LLM-driven QA test cases that are safely pinned to specific document versions.

📋 Prerequisites
 * Python: 3.9 or newer
 * pip: Python package manager

🗂️ Project Structure
Ensure all the files provided in the previous step are saved in the same root directory:
 * database.py - SQLAlchemy models and local JSON NoSQL implementation.
 * schemas.py - Pydantic models for API validation.
 * parser.py - Core logic for parsing text, handling heading irregularities, and hashing.
 * main.py - The FastAPI application routes.

🚀 Installation & Setup
1. Navigate to your directory
Open your terminal and navigate to the directory where you saved the python files.

2. Create a Virtual Environment

python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

3. Install Dependencies
Install the required packages using pip.

pip install fastapi uvicorn sqlalchemy pydantic requests pytest


💻 Running the Application
Run the Live Server:
To boot up the live API and interact with it yourself:

uvicorn main:app --reload

Once the server is running, you can access the interactive Swagger UI documentation to manually test endpoints:
 * API Docs: http://127.0.0.1:8000/docs
 * Alternative Docs (ReDoc): http://127.0.0.1:8000/redoc

 🗃️ Database Files
After running the application or tests, you will notice two local database files created in your directory:
 * cardiotrack.db: The SQLite database storing the relational version-tree and selections.
 * nosql_test_cases.json: The local JSON document store mocking a NoSQL database (like MongoDB) for the generated LLM test case output.
