from fastapi import FastAPI, APIRouter, File, UploadFile, Form, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import json
import uuid
import tempfile
import shutil
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

# Data analysis imports
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import base64
from io import BytesIO
import requests
from bs4 import BeautifulSoup
import duckdb
from PIL import Image
import PyPDF2
import io

# LLM integration
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="Data Analyst Agent", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize LLM Chat
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY not found in environment variables")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables")

class AnalysisRequest(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    question: str
    files_processed: List[str] = []
    status: str = "processing"

class AnalysisResult(BaseModel):
    task_id: str
    result: Any
    execution_time: float
    status: str
    error: Optional[str] = None

# File processing utilities
def process_csv_file(file_path: str) -> pd.DataFrame:
    """Process CSV file and return DataFrame"""
    try:
        return pd.read_csv(file_path)
    except Exception as e:
        logger.error(f"Error processing CSV file: {e}")
        raise HTTPException(status_code=400, detail=f"Error processing CSV: {str(e)}")

def process_pdf_file(file_path: str) -> str:
    """Extract text from PDF file"""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Error processing PDF file: {e}")
        return ""

def process_image_file(file_path: str) -> Dict[str, Any]:
    """Process image file and return basic info"""
    try:
        with Image.open(file_path) as img:
            return {
                "format": img.format,
                "size": img.size,
                "mode": img.mode
            }
    except Exception as e:
        logger.error(f"Error processing image file: {e}")
        return {}

def scrape_wikipedia_table(url: str) -> pd.DataFrame:
    """Scrape table data from Wikipedia URL"""
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find tables
        tables = pd.read_html(url)
        if tables:
            return tables[0]  # Return first table
        else:
            raise HTTPException(status_code=404, detail="No tables found on the webpage")
    except Exception as e:
        logger.error(f"Error scraping Wikipedia: {e}")
        raise HTTPException(status_code=400, detail=f"Error scraping data: {str(e)}")

def create_plot_base64(fig, format_type='png') -> str:
    """Convert matplotlib or plotly figure to base64 string"""
    try:
        if hasattr(fig, 'to_image'):  # Plotly figure
            img_bytes = fig.to_image(format=format_type, width=800, height=600)
            img_base64 = base64.b64encode(img_bytes).decode()
        else:  # Matplotlib figure
            buffer = BytesIO()
            fig.savefig(buffer, format=format_type, dpi=100, bbox_inches='tight')
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)
        
        return f"data:image/{format_type};base64,{img_base64}"
    except Exception as e:
        logger.error(f"Error creating base64 plot: {e}")
        return ""

async def execute_analysis_code(code: str, context: Dict[str, Any]) -> Any:
    """Execute analysis code safely with given context"""
    try:
        # Create a safe execution environment
        safe_globals = {
            '__builtins__': {
                'print': print,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'min': min,
                'max': max,
                'sum': sum,
                'abs': abs,
                'round': round,
                'sorted': sorted,
            },
            'pd': pd,
            'np': np,
            'plt': plt,
            'go': go,
            'px': px,
            'requests': requests,
            'BeautifulSoup': BeautifulSoup,
            'base64': base64,
            'BytesIO': BytesIO,
            'create_plot_base64': create_plot_base64,
            'scrape_wikipedia_table': scrape_wikipedia_table,
        }
        
        # Add context variables
        safe_globals.update(context)
        
        # Execute the code
        local_vars = {}
        exec(code, safe_globals, local_vars)
        
        # Return the result if 'result' variable is defined
        if 'result' in local_vars:
            return local_vars['result']
        else:
            return "Code executed successfully but no result variable found"
            
    except Exception as e:
        logger.error(f"Error executing analysis code: {e}")
        raise HTTPException(status_code=500, detail=f"Code execution error: {str(e)}")

async def generate_analysis_code(question: str, file_info: Dict[str, Any]) -> str:
    """Use LLM to generate Python analysis code"""
    try:
        chat = LlmChat(
            api_key=GEMINI_API_KEY,
            session_id=str(uuid.uuid4()),
            system_message="""You are an expert data analyst. Generate Python code to answer data analysis questions.

IMPORTANT RULES:
1. Always store the final answer in a variable called 'result'
2. Use the provided context variables (dataframes, data, etc.)
3. For plots, use create_plot_base64() function to return base64 encoded images
4. Keep code concise and focused on the specific question
5. Handle edge cases and potential errors
6. For web scraping, use scrape_wikipedia_table() function for Wikipedia tables
7. Return JSON arrays or objects as specified in the question

Available libraries: pandas (pd), numpy (np), matplotlib.pyplot (plt), plotly.graph_objects (go), plotly.express (px)
Available functions: create_plot_base64(), scrape_wikipedia_table()

Context information: """ + json.dumps(file_info, indent=2)
        ).with_model("gemini", "gemini-2.0-flash")
        
        user_message = UserMessage(
            text=f"Generate Python code to answer this question: {question}\n\nThe code should store the final answer in a variable called 'result'."
        )
        
        response = await chat.send_message(user_message)
        
        # Extract code from response (assuming it's wrapped in ```python ... ```)
        if "```python" in response:
            code = response.split("```python")[1].split("```")[0].strip()
        elif "```" in response:
            code = response.split("```")[1].split("```")[0].strip()
        else:
            code = response.strip()
            
        return code
        
    except Exception as e:
        logger.error(f"Error generating analysis code: {e}")
        raise HTTPException(status_code=500, detail=f"LLM code generation error: {str(e)}")

@api_router.post("/", response_model=AnalysisResult)
async def analyze_data(
    questions: UploadFile = File(...),
    files: List[UploadFile] = File(default=[])
):
    """Main endpoint for data analysis"""
    start_time = asyncio.get_event_loop().time()
    task_id = str(uuid.uuid4())
    
    try:
        # Read questions from the uploaded file
        questions_content = await questions.read()
        questions_text = questions_content.decode('utf-8')
        
        # Create temporary directory for file processing
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Process uploaded files
            file_context = {}
            file_info = {
                "files": [],
                "dataframes": [],
                "text_content": [],
                "images": []
            }
            
            for file in files:
                file_path = Path(temp_dir) / file.filename
                
                # Save file
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                # Process based on file type
                if file.filename.endswith('.csv'):
                    df = process_csv_file(str(file_path))
                    var_name = f"df_{file.filename.replace('.', '_').replace('-', '_')}"
                    file_context[var_name] = df
                    file_info["dataframes"].append({
                        "name": var_name,
                        "shape": df.shape,
                        "columns": df.columns.tolist(),
                        "filename": file.filename
                    })
                    
                elif file.filename.endswith('.pdf'):
                    text = process_pdf_file(str(file_path))
                    var_name = f"text_{file.filename.replace('.', '_').replace('-', '_')}"
                    file_context[var_name] = text
                    file_info["text_content"].append({
                        "name": var_name,
                        "filename": file.filename,
                        "length": len(text)
                    })
                    
                elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    img_info = process_image_file(str(file_path))
                    var_name = f"img_path_{file.filename.replace('.', '_').replace('-', '_')}"
                    file_context[var_name] = str(file_path)
                    file_info["images"].append({
                        "name": var_name,
                        "filename": file.filename,
                        "info": img_info
                    })
                    
                else:
                    # Try to read as text
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        var_name = f"text_{file.filename.replace('.', '_').replace('-', '_')}"
                        file_context[var_name] = content
                        file_info["text_content"].append({
                            "name": var_name,
                            "filename": file.filename,
                            "length": len(content)
                        })
                    except:
                        logger.warning(f"Could not process file: {file.filename}")
                
                file_info["files"].append(file.filename)
            
            # Generate analysis code using LLM
            analysis_code = await generate_analysis_code(questions_text, file_info)
            logger.info(f"Generated analysis code: {analysis_code}")
            
            # Execute the analysis
            result = await execute_analysis_code(analysis_code, file_context)
            
            # Store analysis request in database
            analysis_request = AnalysisRequest(
                task_id=task_id,
                question=questions_text,
                files_processed=file_info["files"],
                status="completed"
            )
            await db.analysis_requests.insert_one(analysis_request.dict())
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            return AnalysisResult(
                task_id=task_id,
                result=result,
                execution_time=execution_time,
                status="completed"
            )
            
        finally:
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        execution_time = asyncio.get_event_loop().time() - start_time
        
        return AnalysisResult(
            task_id=task_id,
            result=None,
            execution_time=execution_time,
            status="error",
            error=str(e)
        )

@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "data-analyst-agent"}

@api_router.get("/tasks")
async def get_analysis_tasks():
    """Get list of analysis tasks"""
    tasks = await db.analysis_requests.find().to_list(100)
    return [AnalysisRequest(**task) for task in tasks]

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()