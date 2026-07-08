import sys
sys.stdout.reconfigure(encoding='utf-8')

import threading
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import uvicorn
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from database.storage import ContentStorage
from main import ContentMonitorAgent, load_config
from utils.logger import setup_logger, get_logger

logger = get_logger(__name__)

app = FastAPI(title="Content Monitor API")

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def query_feed(storage: ContentStorage, platform: str = None, search: str = None, sort: str = 'latest', limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    """Query content feed with filtering, searching, and sorting."""
    conn = sqlite3.connect(storage.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Build query
    where_clauses = []
    params = []
    
    if platform and platform != 'all':
        where_clauses.append('platform = ?')
        params.append(platform)
    if search:
        where_clauses.append('(title LIKE ? OR summary LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%'])
    
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    
    # Get total count
    count_sql = f"SELECT COUNT(*) FROM seen_content {where_sql}"
    total = conn.execute(count_sql, params).fetchone()[0]
    
    # Get items
    order = 'analyzed_at DESC' if sort == 'latest' else 'analyzed_at DESC'  # Default sort, handled below for importance
    query_sql = f"SELECT * FROM seen_content {where_sql} ORDER BY {order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    rows = conn.execute(query_sql, params).fetchall()
    
    items = []
    for row in rows:
        item = dict(row)
        # Parse raw_data to extract analysis
        try:
            raw = json.loads(item.get('raw_data', '{}'))
            item['analysis'] = raw
        except Exception:
            item['analysis'] = {}
        items.append(item)
    
    # Sort the items
    if sort == 'importance':
        items.sort(key=lambda x: int(x.get('analysis', {}).get('importance_score') or 0), reverse=True)
    else:
        # Default 'latest': sort by published_at DESC, fallback to analyzed_at
        items.sort(key=lambda x: x.get('analysis', {}).get('published_at') or x.get('analyzed_at') or '', reverse=True)
    
    conn.close()
    return items, total

@app.get("/")
def read_root():
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Dashboard UI not found</h1>")

@app.get("/api/feed")
def get_feed(
    platform: str = Query(None),
    search: str = Query(None),
    sort: str = Query("latest"),
    limit: int = Query(50),
    offset: int = Query(0)
):
    storage = app.state.storage
    items, total = query_feed(storage, platform, search, sort, limit, offset)
    
    return {
        "items": items,
        "total": total,
        "has_more": offset + limit < total
    }

@app.get("/api/stats")
def get_stats():
    storage = app.state.storage
    stats_dict = storage.get_stats()
    
    total = stats_dict.get('total', 0)
    
    # Calculate avg importance from recent items
    recent = storage.get_recent(50)
    total_importance = 0
    count = 0
    for item in recent:
        try:
            raw = json.loads(item.get('raw_data', '{}'))
            score = raw.get('importance_score', 0)
            if score:
                total_importance += int(score)
                count += 1
        except:
            pass
            
    avg_importance = round(total_importance / count, 1) if count > 0 else 0
    
    return {
        "total": total,
        "by_platform": {k: v for k, v in stats_dict.items() if k != 'total'},
        "avg_importance": avg_importance
    }

@app.get("/api/health")
def health_check():
    uptime = datetime.now(timezone.utc) - app.state.start_time
    return {
        "status": "online",
        "uptime": str(uptime).split('.')[0],
        "monitoring": True
    }

def start_server():
    print()
    print("=" * 60)
    print("  [AI] Content Monitor Dashboard")
    print("  Open in browser: http://localhost:8081")
    print("=" * 60)
    print()
    
    os.chdir(Path(__file__).parent)
    
    # Mount static files
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount('/static', StaticFiles(directory='static'), name='static')
    
    config = load_config()
    
    # Create storage and agent
    storage = ContentStorage()
    agent = ContentMonitorAgent(config)
    
    # Store references globally for API access
    app.state.storage = storage
    app.state.agent = agent
    app.state.config = config
    app.state.start_time = datetime.now(timezone.utc)
    
    # Start monitor in background thread
    def run_monitor():
        from apscheduler.schedulers.background import BackgroundScheduler
        agent.send_startup_notifications()
        agent.run_cycle()  # First run
        scheduler = BackgroundScheduler()
        interval = config.get('polling_interval', 5)
        scheduler.add_job(agent.run_cycle, 'interval', minutes=interval, id='content_poll', max_instances=1, coalesce=True)
        scheduler.start()
    
    monitor_thread = threading.Thread(target=run_monitor, daemon=True)
    monitor_thread.start()
    
    # Start web server
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run(app, host='0.0.0.0', port=port, log_level='info')

if __name__ == '__main__':
    start_server()
