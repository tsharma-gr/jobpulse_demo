from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import List, Optional
import uuid
import asyncio
from datetime import datetime
import json
import random
import sys

# Fix for Windows asyncio NotImplementedError with Playwright subprocesses
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from backend.config.settings import settings
from backend.browser.pool import browser_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing Playwright browser pool...")
    await browser_pool.initialize()
    yield
    print("Closing Playwright browser pool...")
    await browser_pool.close()

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Enable CORS for Next.js frontend and Vercel deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---

class SearchRequest(BaseModel):
    job_titles: List[str]
    industries: List[str]
    location: str
    radius: int
    posted_date: Optional[str] = "Last 30 days"
    posted_dates: Optional[dict] = {}
    platforms: Optional[List[str]] = ["CV-Library"]

class SearchResponse(BaseModel):
    session_id: str
    status: str
    message: str

# --- In-Memory State for SSE (in production, use Redis pub/sub) ---
session_event_queues = {}
session_cancel_events = {}

from backend.discovery.orchestrator import discovery_orchestrator
from backend.crawler.manager import crawler_manager
from backend.ai.deepseek_parser import deepseek_parser
import os
import signal

# --- Global Agency Blocklist ---
# Hardcoded blocklist to instantly reject disguised recruitment agencies.
KNOWN_AGENCIES = [
    "kenton black",
    "fawkes & reece",
    "fawkes and reece",
    "tiptopjob",
    "elb recruit",
    "redfish solutions",
    "principal people",
    "anderselite",
    "stirling warrington",
    "mcgregor boyall"
]

# --- Background Task ---
async def execute_search_pipeline(session_id: str, request: SearchRequest):
    """
    Orchestrates the entire search process and pushes events to the SSE queue.
    """
    queue = session_event_queues.get(session_id)
    if not queue:
        return
        
    async def push_event(event_type: str, data: dict = None):
        # Send as the default 'message' SSE event with event type inside the JSON
        # This ensures eventSource.onmessage fires on the frontend
        payload = json.dumps({"event": event_type, "data": data or {}})
        await queue.put({"data": payload})

    try:
        print(f"[{session_id}] Starting pipeline...")
        await push_event("SEARCH_STARTED", {"query": request.dict()})
        
        # Broadcast starting event
        await push_event("SEARCH_STARTED")
        await push_event("DISCOVERY_STARTED", {"sources": ["linkedin", "indeed"]})
        
        processed_jobs = []
        page = 1
        max_pages = 5
        seen_urls = set()
        job_queue = asyncio.Queue()
        
        source_counts = {}
        
        # --- Producer Loop ---
        from backend.discovery.orchestrator import DiscoveryOrchestrator
        local_orchestrator = DiscoveryOrchestrator(platforms=request.platforms)
        
        # We set a high safety limit of 500 total jobs to prevent endless scraping on massive queries
        total_target = 500
        print(f"[{session_id}] Target set to max {total_target} jobs across {len(local_orchestrator.adapters)} platforms.")
        
        # --- Consumer Task ---
        async def ai_consumer():
            is_first = True
            
            while True:
                job = await job_queue.get()
                if job is None: # Sentinel
                    break
                    
                # Check for cancellation
                if session_cancel_events.get(session_id, asyncio.Event()).is_set():
                    print(f"[{session_id}] AI Consumer detected cancellation. Stopping.")
                    break

                if job.job_url in seen_urls:
                    job_queue.task_done()
                    continue
                seen_urls.add(job.job_url)

                # --- Global Blocklist Pre-Filter ---
                company_lower = (job.company_name or "").lower()
                is_blocked = any(blocked in company_lower for blocked in KNOWN_AGENCIES)
                if is_blocked:
                    print(f"[{session_id}] PRE-CLASSIFIED UNFIT: Skipping '{job.job_title}' - Detected known agency in Global Blocklist! ({job.company_name})")
                    job_queue.task_done()
                    continue
                
                if is_first:
                    await push_event("AI_STARTED")
                    is_first = False
                    
                print(f"[{session_id}] AI Analyzing: {job.job_title} ({job.job_site})...", flush=True)
                
                if hasattr(job, 'full_text') and job.full_text:
                    markdown = job.full_text
                    print(f"[{session_id}] Natively extracted {len(markdown)} characters from {job.job_site} pane.")
                else:
                    markdown = await crawler_manager.extract_page(job.job_url)
                    
                if not markdown:
                    job_queue.task_done()
                    continue
                    
                ai_result = await deepseek_parser.analyze_job(markdown, search_criteria, company_name=job.company_name)
                if ai_result:
                    print(f"[{session_id}] AI Match: {ai_result.is_fit} | Reason: {ai_result.reason_for_match}")
                    job.match_score = 100 if ai_result.is_fit else 0
                    job.reason_for_match = ai_result.reason_for_match
                    job.industry_match = ai_result.industry_match
                    
                    if ai_result.is_fit:
                        source = job.job_site
                        source_counts[source] = source_counts.get(source, 0) + 1
                        
                        processed_jobs.append(job)
                        await push_event("JOB_VERIFIED", job.dict())
                        print(f"[{session_id}] Verified {source_counts[source]}/10 jobs for {source}.")
                        
                job_queue.task_done()
                
        # Start Consumer
        consumer_task = asyncio.create_task(ai_consumer())
        
        try:
            while page <= 9999: # Practically infinite, will break when no more jobs found
                
                # Check for cancellation
                if session_cancel_events.get(session_id, asyncio.Event()).is_set():
                    print(f"[{session_id}] Search pipeline cancelled by user.")
                    await push_event("SEARCH_CANCELLED")
                    break

                if not local_orchestrator.adapters:
                    print(f"[{session_id}] All adapters have finished.")
                    break
                
                search_criteria = request.dict()
                search_criteria["page"] = page
                search_criteria["source_counts"] = source_counts
                print(f"[{session_id}] Fetching page {page}...", flush=True)
                
                # Discovery pushes directly to job_queue now
                discovered_jobs = await local_orchestrator.execute_discovery(search_criteria, job_queue)
                
                if page == 1:
                    await push_event("DISCOVERY_COMPLETED", {"urls_found": len(discovered_jobs)})
                    await push_event("EXTRACTION_STARTED")
                    
                # Check if any adapter still has more pages
                any_more_pages = any(getattr(adapter, 'has_more_pages', True) for adapter in local_orchestrator.adapters)
                if not any_more_pages:
                    print(f"[{session_id}] All adapters have reached their last page. Ending discovery.")
                    break
                    
                # Check if overall quota is met
                total_verified = sum(source_counts.values())
                if total_verified >= total_target:
                    print(f"[{session_id}] Target quota of {total_target} jobs met. Ending discovery.")
                    break
                    
                page += 1
                
                # Give consumer a chance to catch up if we are fetching pages too fast
                await asyncio.sleep(2)
                
        finally:
            print(f"[{session_id}] Search complete. Waiting for consumer to finish...")
            # Signal consumer to stop
            await job_queue.put(None)
            await consumer_task
            
            # Close stateful adapters
            for adapter in local_orchestrator.adapters:
                if hasattr(adapter, 'close'):
                    await adapter.close()
            
            await push_event("SEARCH_COMPLETE", {"found": len(processed_jobs)})
        
        await push_event("VERIFICATION_COMPLETED", {"verified_jobs": len(processed_jobs)})
        await push_event("RANKING_COMPLETED")
        
        await push_event("FINISHED", {
            "session_id": session_id,
            "jobs_ready": len(processed_jobs)
        })
        print(f"[{session_id}] Pipeline finished with {len(processed_jobs)} jobs passing AI.")
        
        await crawler_manager.close()
        
    except Exception as e:
        print(f"[{session_id}] Error in pipeline: {e}")
        await push_event("ERROR", {"detail": str(e)})
    finally:
        # Signal the SSE stream to close
        await queue.put(None)
        if session_id in session_cancel_events:
            del session_cancel_events[session_id]

# --- API Endpoints ---

@app.post("/api/search", response_model=SearchResponse)
async def start_search(request: SearchRequest, background_tasks: BackgroundTasks):
    import re
    cleaned_titles = []
    for t in request.job_titles:
        # Split by comma if multiple were pasted in one chip, then remove brackets and quotes
        for sub_t in t.split(','):
            cleaned = re.sub(r'[()\"\'`]', '', sub_t)
            if cleaned.strip():
                cleaned_titles.append(cleaned.strip())
    request.job_titles = cleaned_titles
    
    cleaned_industries = []
    for i in request.industries:
        for sub_i in i.split(','):
            cleaned = re.sub(r'[()\"\'`]', '', sub_i)
            if cleaned.strip():
                cleaned_industries.append(cleaned.strip())
    request.industries = cleaned_industries

    session_id = str(uuid.uuid4())
    
    # Initialize an async queue for this session's events
    session_event_queues[session_id] = asyncio.Queue()
    session_cancel_events[session_id] = asyncio.Event()
    
    # Kick off the search pipeline in the background
    background_tasks.add_task(execute_search_pipeline, session_id, request)
    
    return SearchResponse(
        session_id=session_id,
        status="STARTED",
        message="Search session initialized and dispatched to discovery engine."
    )

@app.get("/api/events/{session_id}")
async def sse_events(request: Request, session_id: str):
    """
    Server-Sent Events endpoint to stream real-time progress to the frontend.
    """
    queue = session_event_queues.get(session_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Session not found or already completed.")

    async def event_generator():
        try:
            while True:
                # If client closes connection, stop sending
                if await request.is_disconnected():
                    break
                    
                message = await queue.get()
                if message is None: # None is our termination signal
                    break
                    
                yield message
        except asyncio.CancelledError:
            pass
        finally:
            if session_id in session_event_queues:
                del session_event_queues[session_id]

    return EventSourceResponse(event_generator())

@app.get("/api/search/{session_id}")
async def get_search_status(session_id: str):
    # Fetch status from DB (placeholder)
    return {"session_id": session_id, "status": "COMPLETED", "jobs_found": 85}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: int):
    # Fetch specific job details from DB (placeholder)
    return {"job_id": job_id, "title": "Example Estimator"}

@app.get("/api/history")
async def get_search_history():
    # Fetch user's search history (placeholder)
    return {"history": [{"session_id": "1234", "date": "2026-07-16", "query": "Estimator in London"}]}

@app.post("/api/export")
async def export_results(session_id: str, format: str = "csv"):
    # Generate export file (placeholder)
    return {"message": f"Exporting session {session_id} to {format}"}

@app.get("/api/metrics")
async def get_metrics():
    # Aggregate metrics from DB (placeholder)
    return {
        "urls_discovered": 1500,
        "urls_processed": 1400,
        "cache_hit_rate": "35%",
        "queue_time_avg_ms": 120,
        "ai_time_avg_ms": 2500,
        "total_jobs_verified": 850
    }

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "timestamp": datetime.now().isoformat()}

@app.post("/api/search/{session_id}/cancel")
async def cancel_search(session_id: str):
    """Cancels an active search pipeline."""
    if session_id in session_cancel_events:
        session_cancel_events[session_id].set()
        return {"status": "CANCELLED", "message": "Search cancellation requested."}
    raise HTTPException(status_code=404, detail="Session not found.")

@app.post("/api/shutdown")
async def shutdown_server():
    """Gracefully shuts down the background PyInstaller server."""
    print("Shutdown requested via API. Exiting...")
    # Delay exit slightly so the response can be sent
    async def _exit():
        await asyncio.sleep(0.5)
        os._exit(0)
    asyncio.create_task(_exit())
    return {"status": "SHUTDOWN", "message": "JobPulse Engine is shutting down."}
