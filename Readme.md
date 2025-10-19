# AI-Powered Browser Automation API

> **Intelligent web automation** - Uses Gemini LLM + Playwright MCP

A production-ready FastAPI service that uses Google's Gemini AI to intelligently automate web searches and automation. The agent can navigate, search, scroll, and extract information with zero manual intervention.

---
<p align="center">
  <a href="https://youtu.be/3yAxWyP8RZM">
    <img src="https://img.shields.io/badge/%20Watch%20Demo-YouTube-red?style=for-the-badge&logo=youtube" alt="Watch Demo"/>
  </a>
</p>

## Features

- **Amazon-Optimized**: Prompt specifically designed for Amazon.com workflows
- **Smart Product Search**: Automatically searches and finds products
- **Price Extraction**: Extracts accurate pricing from search results
- **Intelligent Scrolling**: Scrolls dynamically to load more products
- **RESTful API**: Simple HTTP endpoints for automation tasks
- **Real-time Tracking**: Monitor task progress with detailed execution logs
- **Async Processing**: Background task execution with FastAPI

---

## Quick Demo

**Goal**: *"Go to Amazon and find the price of the 5th laptop"*

**Result**: The agent autonomously:
1. Navigates to Amazon.com
2. Fills the search box with "laptop"
3. Clicks the search button
4. Scrolls down 3 times to load more results
5. Extracts the 5th laptop's price: **$379.99**

All in **8 iterations** and **~15 seconds**!

---

## Architecture

```
playwright-browser-automation/
├── agent.py                    # Core automation engine with error handling
├── main.py                     # FastAPI server with async task management
├── prompt.py                   # Amazon-optimized system prompt
├── install.sh                  # One-click setup script
├── .env                        # Configuration (Gemini API key)
└── requirements.txt            # Python dependencies

```

### Key Design Principles

- **Website-Specific Prompts**: The system prompt in `prompt.py` is optimized **exclusively for Amazon.com**. This makes the agent highly precise for Amazon product searches but requires prompt modification for other websites.
  
- **Configurable for Other Sites**: Want to automate eBay or Walmart? Simply modify `prompt.py` with site-specific selectors and patterns.

---

## Installation

### Prerequisites

- Python 3.12+
- Node.js 20+ (for Playwright MCP server)
- Gemini API key ([Get one here](https://aistudio.google.com/app/apikey))

### Setup Commands
1. Clone the repository
```
git clone https://github.com/snehanshu-raj/playwright-browser-automation.git
cd playwright-browser-automation
```

2. Run the install script
```
chmod +x install.sh
./install.sh
```

3. IMPORTANT: Add your Gemini API key to .env file
```
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

4. Start the API server
```
python3 main.py
```

- That's it! Your API is now running at `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

---

## Usage

### 1. Submit an Automation Task

```
curl -X POST http://localhost:8000/automate \
-H "Content-Type: application/json" \
-d '{
"goal": "Go to Amazon and find the price of the first laptop",
"max_iterations": 15
}'
```

**Response:**
```
{
"task_id": "abc-123-def-456",
"status": "pending",
"message": "Task submitted successfully. Check status at /task/abc-123-def-456"
}
```

> You will see browser being open automatically and then your query getting executed step by step.


### 2. Check Task Status

```
curl http://localhost:8000/task/abc-123-def-456
```

**Response:**
```
{
"task_id": "abc-123-def-456",
"status": "completed",
"goal": "Go to Amazon and find the price of the first laptop",
"result": "The price is \$899.00",
"iterations_used": 5,
"started_at": "2025-10-19T09:00:01",
"completed_at": "2025-10-19T09:00:15",
"history": [
    "playwright_navigate succeeded",
    "playwright_fill succeeded",
    "playwright_click succeeded",
    "playwright_evaluate returned: \"899.\""
],
"execution_log": [...]
}
```

### 3. Interactive API Documentation

Try via Swagger as well: URL to visit when the server is running:
- **Swagger UI**: http://localhost:8000/docs

---

**Important**: Use **one website per deployment** for maximum accuracy. The LLM performs best with focused, site-specific instructions.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API information and examples |
| `POST` | `/automate` | Submit automation task |
| `GET` | `/task/{task_id}` | Get task status and result |
| `GET` | `/tasks` | List all tasks |
| `DELETE` | `/task/{task_id}` | Delete a task |
| `GET` | `/health` | Health check |

---

## Project Structure

```
.
├── agent.py               # Automation engine
│   ├── run_agent()        # Main execution loop
│   ├── Error handling     # Retry logic and failure recovery
│   └── Tool calling       # Playwright tool orchestration
│ 
├── .env                   # Your Gemini API key goes here
│ 
├── main.py                # FastAPI application
│   ├── Background tasks   # Async task processing
│   ├── REST endpoints     # API routes
│   └── Task management    # Status tracking
│
├── prompt.py              # AI System Prompt
│   ├── Tool descriptions  # Available Playwright actions
│   ├── Site selectors     # Amazon-specific patterns
│   ├── Scrolling rules    # Scroll behavior
│   └── Decision logic     # When to stop/continue
│
└── install.sh             # Setup automation script

```

---