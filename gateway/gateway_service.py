#!/usr/bin/env python3
"""
Gateway Service - Multi-channel messaging with Claude Code orchestration
Routes messages intelligently using skill matching and complexity classification

Author: SecureBot Project
License: MIT
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
import json

# Import our orchestrator
from orchestrator import route_query, SkillMatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gateway Service", version="2.0.0")


class Message(BaseModel):
    """Incoming message from any channel"""
    channel: str
    user_id: str
    text: str
    metadata: Optional[Dict[str, Any]] = {}


class SearchDetector:
    """Detect if query needs web search"""
    
    SEARCH_INDICATORS = [
        lambda text: any(phrase in text.lower() for phrase in [
            "search for",
            "find information about",
            "latest news about",
            "recent news about",
            "look up"
        ])
    ]
    
    @classmethod
    def needs_search(cls, text: str) -> bool:
        """Check if query needs web search"""
        return any(indicator(text) for indicator in cls.SEARCH_INDICATORS)


class GatewayService:
    """
    Gateway service with Claude Code orchestration
    """
    
    def __init__(self):
        self.vault_url = os.getenv("VAULT_URL", "http://vault:8200")
        self.ollama_url = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
        self.search_detector = SearchDetector()
        
        # Initialize skill matcher for stats
        self.skill_matcher = SkillMatcher()
        
        logger.info(f"Gateway initialized - Vault: {self.vault_url}, Ollama: {self.ollama_url}")
        logger.info(f"Loaded {len(self.skill_matcher.skills)} skills")
    
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
            # Step 1: Check if we need web search
            needs_search = self.search_detector.needs_search(message.text)
            search_results = None
            
            if needs_search:
                logger.info(f"Query requires web search: {message.text[:50]}...")
                search_results = await self._execute_search(message.text)
                
                # If we got search results, augment the query
                if search_results:
                    message.text = self._build_search_context(message.text, search_results)
            
            # Step 2: Route through orchestrator
            logger.info(f"Routing query through orchestrator")
            
            orchestrator_result = await route_query(
                query=message.text,
                user_id=message.user_id,
                vault_url=self.vault_url,
                ollama_url=self.ollama_url
            )
            
            # Calculate processing time
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Step 3: Build response
            return {
                "status": "success",
                "response": orchestrator_result["result"],
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
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.vault_url}/execute",
                    json={
                        "tool": "web_search",
                        "params": {
                            "query": query,
                            "max_results": 3  # Reduced for faster processing
                        },
                        "session_id": "gateway"
                    }
                )
                
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
