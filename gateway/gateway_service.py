#!/usr/bin/env python3
"""
Gateway Service - Multi-channel messaging with Claude Code orchestration
Routes messages intelligently using skill matching and complexity classification

Author: SecureBot Project
License: MIT
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import hmac
import httpx
import os
import sys
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our orchestrator
from orchestrator import route_query, SkillMatcher, skill_registry
from common.config import get_config
from common.auth import SignedClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gateway Service", version="2.0.0")

# ── Gateway API Key Middleware ────────────────────────────────────────────────
# Protects all non-/health endpoints from unauthenticated public access.
# Set GATEWAY_API_KEY in .env and send as X-API-Key header on every request.
_GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "")


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Reject requests missing a valid X-API-Key (except /health)."""
    if request.url.path == "/health":
        return await call_next(request)
    if not _GATEWAY_API_KEY:
        logger.warning("GATEWAY_API_KEY not set — gateway is unprotected")
        return await call_next(request)
    provided = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(provided, _GATEWAY_API_KEY):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


class Message(BaseModel):
    """Incoming message from any channel"""
    channel: str
    user_id: str
    text: str
    metadata: Optional[Dict[str, Any]] = {}
    system: Optional[str] = None


class SearchDetector:
    """Detect if query needs web search - now skill-based"""

    def __init__(self, skills_dir: str = "/app/skills"):
        """Initialize with skills from directory"""
        self.skills_dir = Path(skills_dir)
        self.config = get_config()
        self.search_skills = self._load_search_skills()

        # Determine sensitivity based on config
        detection_mode = self.config.get("gateway.search_detection", "normal")
        self._set_indicators(detection_mode)

    def _load_search_skills(self) -> List[Dict[str, Any]]:
        """Load all search skills from skills directory"""
        from orchestrator import SkillMatcher

        matcher = SkillMatcher(str(self.skills_dir))
        search_skills = []

        for skill_name, skill in matcher.skills.items():
            # Check if it's a search skill
            category = skill.get('frontmatter', {}).get('category')
            if category == 'search':
                # Check if skill is enabled in config
                if self.config.is_skill_enabled(skill_name):
                    search_skills.append(skill)
                    logger.info(f"Loaded search skill: {skill_name}")

        # Sort by priority
        search_skills.sort(key=lambda s: self.config.get_skill_priority(
            s['name'],
            s.get('frontmatter', {}).get('priority', 999)
        ))

        return search_skills

    def _set_indicators(self, mode: str) -> None:
        """Set search indicators based on detection mode"""
        if mode == "strict":
            self.SEARCH_INDICATORS = [
                lambda text: any(phrase in text.lower() for phrase in [
                    "search for",
                    "find information about",
                    "look up"
                ])
            ]
        elif mode == "relaxed":
            self.SEARCH_INDICATORS = [
                lambda text: any(phrase in text.lower() for phrase in [
                    "search", "find", "look up", "what is", "who is",
                    "latest", "recent", "news about", "information about"
                ])
            ]
        else:  # normal
            self.SEARCH_INDICATORS = [
                lambda text: any(phrase in text.lower() for phrase in [
                    "search for",
                    "find information about",
                    "latest news about",
                    "recent news about",
                    "look up"
                ])
            ]

    def needs_search(self, text: str) -> bool:
        """Check if query needs web search"""
        # No search skills available
        if not self.search_skills:
            logger.warning("No search skills available")
            return False

        return any(indicator(text) for indicator in self.SEARCH_INDICATORS)

    def get_available_providers(self) -> List[str]:
        """Get list of available search provider names"""
        return [skill['name'] for skill in self.search_skills]


class GatewayService:
    """
    Gateway service with Claude Code orchestration
    """

    def __init__(self):
        self.vault_url = os.getenv("VAULT_URL", "http://vault:8200")
        self.ollama_url = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
        self.rag_url = os.getenv("RAG_URL", "http://rag-service:8400")
        self.config = get_config()
        self.search_detector = SearchDetector()

        # Initialize skill matcher for stats
        self.skill_matcher = SkillMatcher()

        # Initialize signed client for inter-service auth
        service_id = os.getenv("SERVICE_ID", "gateway")
        service_secret = os.getenv("SERVICE_SECRET", "")
        self.signed_client = SignedClient(service_id, service_secret) if service_secret else None

        logger.info(f"Gateway initialized - Vault: {self.vault_url}, Ollama: {self.ollama_url}, RAG: {self.rag_url}")
        logger.info(f"Auth enabled: {bool(self.signed_client)}")
        logger.info(f"Loaded {len(self.skill_matcher.skills)} total skills")
        logger.info(f"Search providers available: {self.search_detector.get_available_providers()}")

    async def _store_conversation(self, user_msg: str, bot_response: str, user_id: Optional[str] = None):
        """Store conversation turn in RAG service for future context retrieval"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                url = f"{self.rag_url}/embed/conversation"
                payload = {
                    "user": user_msg[:500],  # Truncate long messages
                    "assistant": bot_response[:500],
                    "timestamp": datetime.now().isoformat(),
                    "user_id": user_id  # for tenant isolation
                }

                if self.signed_client:
                    await self.signed_client.post(client, url, json=payload)
                else:
                    await client.post(url, json=payload)

                logger.debug("Conversation stored in RAG")
        except Exception as e:
            # Non-critical - don't fail on this
            logger.debug(f"Failed to store conversation in RAG: {e}")

    async def process_message(self, message: Message) -> Dict[str, Any]:
        """
        Main message processing pipeline with orchestration
        
        1. Check if search is needed
        2. Execute search if needed
        3. Route through orchestrator (skill matching + complexity classification)
        4. Return formatted response
        """
        start_time = datetime.now()

        try:
            # Save original query before any augmentation
            original_query = message.text

            # Step 1: Check if we need web search (keyword-based pre-check)
            needs_search = self.search_detector.needs_search(message.text)
            search_results = None
            has_search_results = False

            if needs_search:
                logger.info(f"Query requires web search: {message.text[:50]}...")
                search_results = await self._execute_search(message.text)

                # If we got search results, augment the query
                if search_results:
                    message.text = self._build_search_context(message.text, search_results)
                    has_search_results = True

            # Step 2: Route through orchestrator
            logger.info(f"Routing query through orchestrator (has_search_results={has_search_results})")

            orchestrator_result = await route_query(
                query=message.text,
                user_id=message.user_id,
                vault_url=self.vault_url,
                ollama_url=self.ollama_url,
                has_search_results=has_search_results,
                system_prompt=message.system
            )

            # Step 2b: If orchestrator detected a current-info query the keyword
            # pre-check missed, execute search now and re-route.
            if orchestrator_result.get("method") == "web_search_needed" and not has_search_results:
                logger.info("Orchestrator flagged current-info query — executing web search now")
                search_results = await self._execute_search(original_query)
                if search_results:
                    augmented = self._build_search_context(original_query, search_results)
                    has_search_results = True
                    orchestrator_result = await route_query(
                        query=augmented,
                        user_id=message.user_id,
                        vault_url=self.vault_url,
                        ollama_url=self.ollama_url,
                        has_search_results=True,
                        system_prompt=message.system
                    )
                else:
                    # Search unavailable — fall back to Ollama directly with a note
                    logger.warning("Search execution failed for web_search_needed query — falling back to Ollama directly")
                    _fallback_model = os.getenv("RESPONSE_MODEL", "llama3.2:3b")
                    _fallback_prompt = (
                        "I couldn't access real-time search results for this query. "
                        "Please answer based on your training knowledge, noting any uncertainty. "
                        f"Query: {original_query}"
                    )
                    _fallback_result = ""
                    try:
                        async with httpx.AsyncClient(timeout=120.0) as _c:
                            _r = await _c.post(
                                f"{self.ollama_url}/api/generate",
                                json={
                                    "model": _fallback_model,
                                    "prompt": _fallback_prompt,
                                    "system": message.system or "",
                                    "stream": False,
                                }
                            )
                            _fallback_result = _r.json().get("response", "")
                    except Exception as _e:
                        logger.error(f"Ollama fallback also failed: {_e}")
                    if not _fallback_result:
                        _fallback_result = (
                            "I couldn't retrieve real-time information for this query. "
                            "Please check a web browser for current data."
                        )
                    orchestrator_result = {
                        "result": _fallback_result,
                        "method": "direct_ollama",
                        "cost": 0.0,
                        "engine": "ollama",
                    }

            # Calculate processing time
            elapsed = (datetime.now() - start_time).total_seconds()

            # Store conversation in RAG (non-blocking, best-effort)
            bot_response = orchestrator_result["result"]
            await self._store_conversation(message.text, bot_response, user_id=message.user_id)

            # Step 3: Build response
            return {
                "status": "success",
                "response": bot_response,
                "metadata": {
                    "engine": orchestrator_result["engine"],
                    "method": orchestrator_result["method"],
                    "skill_used": orchestrator_result.get("skill_used"),
                    "skill_created": orchestrator_result.get("skill_created"),
                    "skill_path": orchestrator_result.get("skill_path"),
                    "cost": orchestrator_result["cost"],
                    "search_used": needs_search,
                    "search_results_count": len(search_results) if search_results else 0,
                    "processing_time_seconds": elapsed,
                    "channel": message.channel,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Message processing failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "response": "I encountered an error processing your request. Please try again.",
                "metadata": {
                    "channel": message.channel,
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    async def _execute_search(self, query: str) -> Optional[List[Dict[str, str]]]:
        """Execute web search via Vault"""
        try:
            max_results = self.config.get("gateway.max_search_results", 3)

            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.vault_url}/execute"
                payload = {
                    "tool": "web_search",
                    "params": {
                        "query": query,
                        "max_results": max_results
                    },
                    "session_id": "gateway"
                }

                if self.signed_client:
                    response = await self.signed_client.post(client, url, json=payload)
                else:
                    response = await client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Search completed with {data.get('provider', 'unknown')} provider")
                    return data.get("results", [])
                else:
                    logger.error(f"Search failed: HTTP {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Search execution failed: {e}")
            return None
    
    def _build_search_context(self, query: str, search_results: List[Dict[str, str]]) -> str:
        """Build context with search results (compact format)"""
        if not search_results:
            return query
        
        # Compact format to avoid long prompts
        context_parts = ["Search results:\n"]
        
        for i, result in enumerate(search_results[:3], 1):
            context_parts.append(f"[{i}] {result.get('title', 'No title')}")
            context_parts.append(f"    {result.get('snippet', 'No snippet')[:100]}...\n")
        
        context_parts.append(f"\nQuestion: {query}\n")
        
        return "".join(context_parts)


# Initialize gateway
gateway = GatewayService()


@app.on_event("startup")
async def startup_event():
    """Load GLiClass classifier and seed classifier examples on startup"""
    import asyncio
    from orchestrator import seed_classifier_examples_on_startup
    from gliclass_classifier import load_classifier

    # Load GLiClass into GPU memory — must complete before first request
    load_classifier(device="cuda:0")

    # Run seeding in background (non-blocking)
    asyncio.create_task(
        seed_classifier_examples_on_startup(
            rag_url=os.getenv("RAG_URL", "http://rag-service:8400"),
            signed_client=gateway.signed_client
        )
    )


@app.post("/message")
async def handle_message(message: Message) -> Dict[str, Any]:
    """
    Handle incoming message from any channel
    
    Supports: CLI, Telegram, Slack, WhatsApp, Discord, Web UI
    """
    logger.info(f"Received message from {message.channel} (user: {message.user_id})")
    
    result = await gateway.process_message(message)
    
    return result


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check endpoint"""
    
    # Check connectivity to dependencies
    vault_ok = False
    ollama_ok = False
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            vault_response = await client.get(f"{gateway.vault_url}/health")
            vault_ok = vault_response.status_code == 200
    except:
        pass
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            ollama_response = await client.get(f"{gateway.ollama_url}/api/tags")
            ollama_ok = ollama_response.status_code == 200
    except:
        pass
    
    return {
        "status": "healthy" if (vault_ok and ollama_ok) else "degraded",
        "version": "2.0.0",
        "dependencies": {
            "vault": "healthy" if vault_ok else "unhealthy",
            "ollama": "healthy" if ollama_ok else "unhealthy"
        },
        "skills_loaded": len(gateway.skill_matcher.skills),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/skills")
async def list_skills() -> Dict[str, Any]:
    """List all available skills"""
    
    skills_info = []
    for skill_name, skill in gateway.skill_matcher.skills.items():
        skills_info.append({
            "name": skill['name'],
            "description": skill['description'],
            "path": str(skill['path'])
        })
    
    return {
        "status": "success",
        "skills": skills_info,
        "count": len(skills_info)
    }


@app.post("/skills/reload")
async def reload_skills() -> Dict[str, Any]:
    """Hot-reload skill registry without container restart."""
    skill_registry.reload()
    skills = skill_registry.list_all()
    return {
        "status": "ok",
        "skills_loaded": len(skills),
        "skills": [s["name"] for s in skills]
    }


@app.get("/stats")
async def stats() -> Dict[str, Any]:
    """Get gateway statistics"""
    
    return {
        "status": "success",
        "stats": {
            "skills_available": len(gateway.skill_matcher.skills),
            "vault_url": gateway.vault_url,
            "ollama_url": gateway.ollama_url
        },
        "timestamp": datetime.now().isoformat()
    }


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint"""
    return {
        "service": "SecureBot Gateway with Claude Code",
        "version": "2.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
