from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, List
import uuid
from datetime import datetime
import os

from agent import run_agent

app = FastAPI(
    title="Playwright Browser Automation API",
    description="AI-powered browser automation using Gemini + Playwright MCP",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# To store task results, Currently very simple for this POC. In production I might use Redis, or very big data MongoDB
tasks: Dict[str, dict] = {}

class AutomationRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "goal": "Go to Amazon and find the price of the first laptop",
                    "max_iterations": 15
                }
            ]
        }
    )
    
    goal: str = Field(..., description="The automation task to perform")
    max_iterations: Optional[int] = Field(15, description="Maximum iterations", ge=5, le=30)

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskResult(BaseModel):
    task_id: str
    status: str
    goal: str
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    iterations_used: Optional[int] = None
    history: Optional[List[str]] = None
    execution_log: Optional[List[Dict]] = None
    logs: Optional[List[Dict]] = None

async def run_automation_task(task_id: str, goal: str, max_iterations: int):
    tasks[task_id]["logs"] = []

    def log_callback(message: str, level: str = "info"):
        if "logs" not in tasks[task_id]:
            tasks[task_id]["logs"] = []
        tasks[task_id]["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        })
    
    try:
        tasks[task_id]["status"] = "running"
        tasks[task_id]["started_at"] = datetime.now().isoformat()
        
        # Run the agent
        result_data = await run_agent(goal, max_iter=max_iterations, verbose=False, log_callback=log_callback)
        
        tasks[task_id]["status"] = "completed" if result_data["success"] else "failed"
        tasks[task_id]["result"] = result_data["result"]
        tasks[task_id]["iterations_used"] = result_data["iterations"]
        tasks[task_id]["history"] = result_data["history"]
        tasks[task_id]["execution_log"] = result_data["execution_log"]
        tasks[task_id]["completed_at"] = datetime.now().isoformat()
        
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        tasks[task_id]["completed_at"] = datetime.now().isoformat()


@app.get("/")
async def root():
    """API info"""
    return {
        "name": "Playwright Browser Automation API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "POST /automate": "Submit automation task",
            "GET /task/{task_id}": "Get task status/result",
            "GET /tasks": "List all tasks",
            "DELETE /task/{task_id}": "Delete a task",
            "GET /health": "Health check",
            "GET /docs": "API documentation (Swagger UI)",
            "GET /redoc": "API documentation (ReDoc)"
        },
        "example": {
            "curl": 'curl -X POST http://localhost:8000/automate -H "Content-Type: application/json" -d \'{"goal": "Go to Amazon and find laptop prices"}\'',
        }
    }

# this will run the task in background and send back the task uuid immediately, doing this design as this should be used in production as the task might take long to finish.
@app.post("/automate", response_model=TaskResponse)
async def create_automation_task(request: AutomationRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    
    tasks[task_id] = {
        "task_id": task_id,
        "goal": request.goal,
        "status": "pending",
        "result": None,
        "error": None,
        "started_at": None,
        "completed_at": None,
        "iterations_used": None,
        "history": None,
        "execution_log": None,
        "logs": []
    }
    
    # Run in background
    background_tasks.add_task(run_automation_task, task_id, request.goal, request.max_iterations)
    
    return TaskResponse(task_id=task_id, status="pending", message=f"Task submitted successfully. Check status at /task/{task_id}")

@app.get("/task/{task_id}", response_model=TaskResult)
async def get_task_status(task_id: str):
    """Get task status and result"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    return TaskResult(**task)


@app.get("/tasks")
async def list_tasks(limit: int = 50, status: Optional[str] = None):
    """List all tasks with optional filtering"""
    filtered_tasks = list(tasks.values())
    
    if status:
        filtered_tasks = [t for t in filtered_tasks if t["status"] == status]
    
    return {
        "tasks": filtered_tasks[:limit],
        "total": len(filtered_tasks),
        "showing": min(len(filtered_tasks), limit)
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    gemini_key = os.getenv("GEMINI_API_KEY")
    return {
        "status": "healthy",
        "gemini_configured": bool(gemini_key),
        "tasks_count": len(tasks),
        "tasks_by_status": {
            "pending": len([t for t in tasks.values() if t["status"] == "pending"]),
            "running": len([t for t in tasks.values() if t["status"] == "running"]),
            "completed": len([t for t in tasks.values() if t["status"] == "completed"]),
            "failed": len([t for t in tasks.values() if t["status"] == "failed"])
        }
    }

@app.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """Delete a task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del tasks[task_id]
    return {"message": "Task deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
