#!/usr/bin/env python3
"""
Vault Service - Secrets Isolation with Multi-Provider Search
Provides secure API key injection and multi-provider web search with automatic fallback.

Author: SecureBot Project
License: MIT
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import json
import httpx
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, List, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Vault Service", version="1.0.0")


class ToolRequest(BaseModel):
    """Request model for tool execution"""
    tool: str
    params: dict
    session_id: str


class UsageTracker:
    """Track API usage to respect rate limits"""
    
    def __init__(self):
        self.usage = defaultdict(lambda: {
            "daily": 0,
            "monthly": 0,
            "last_reset": datetime.now()
        })
    
    def log_usage(self, provider: str) -> None:
        """Log a search query"""
        now = datetime.now()
        
        # Reset daily counter if new day
        if (now - self.usage[provider]["last_reset"]).days >= 1:
            self.usage[provider]["daily"] = 0
            self.usage[provider]["last_reset"] = now
        
        # Reset monthly counter if new month
        if now.month != self.usage[provider]["last_reset"].month:
            self.usage[provider]["monthly"] = 0
        
        self.usage[provider]["daily"] += 1
        self.usage[provider]["monthly"] += 1
    
    def can_use(self, provider: str, daily_limit: Optional[int] = None, 
                monthly_limit: Optional[int] = None) -> bool:
        """Check if provider is under limits"""
        if daily_limit and self.usage[provider]["daily"] >= daily_limit:
            return False
        if monthly_limit and self.usage[provider]["monthly"] >= monthly_limit:
            return False
        return True
    
    def get_usage(self, provider: str) -> Dict[str, Any]:
        """Get current usage for a provider"""
        return {
            "daily": self.usage[provider]["daily"],
            "monthly": self.usage[provider]["monthly"],
            "last_reset": self.usage[provider]["last_reset"].isoformat()
        }


class SearchProvider:
    """Base class for search providers"""
    
    async def search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        raise NotImplementedError("Subclasses must implement search()")


class GoogleCustomSearch(SearchProvider):
    """
    Google Custom Search API Provider
    FREE: 100 queries/day (3,000/month)
    Best for: General queries, coding, nutrition, planning
    """
    
    def __init__(self, api_key: str, search_engine_id: str):
        self.api_key = api_key
        self.cx = search_engine_id
        self.name = "google"
    
    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Execute Google Custom Search"""
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": min(max_results, 10)
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            
            if response.status_code == 429:
                raise Exception("Rate limit exceeded")
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            
            data = response.json()
            
            if "items" not in data:
                logger.warning(f"No results found for query: {query}")
                return []
            
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                }
                for item in data.get("items", [])
            ]


class TavilySearch(SearchProvider):
    """
    Tavily API Provider
    FREE: 1,000 queries/month
    Best for: AI-optimized research, fact-finding, direct answers
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.name = "tavily"
    
    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Execute Tavily search"""
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": True
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code == 429:
                raise Exception("Rate limit exceeded")
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            
            data = response.json()
            results = []
            
            # Add direct answer if available
            if data.get("answer"):
                results.append({
                    "title": "Direct Answer",
                    "url": "",
                    "snippet": data["answer"],
                    "type": "answer"
                })
            
            # Add search results
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")[:300]
                })
            
            return results


class DuckDuckGoSearch(SearchProvider):
    """
    DuckDuckGo Search Provider
    FREE: No API key needed (rate limited)
    Best for: Fallback provider, privacy-focused searches
    """
    
    def __init__(self):
        self.name = "duckduckgo"
    
    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Execute DuckDuckGo search"""
        try:
            from duckduckgo_search import DDGS
            
            ddg = DDGS()
            results = ddg.text(query, max_results=max_results)
            
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                }
                for r in results
            ]
        except Exception as e:
            raise Exception(f"DuckDuckGo search failed: {str(e)}")


class SearchOrchestrator:
    """
    Intelligent search orchestration with automatic fallback
    Tries providers in priority order, respecting rate limits
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.providers = []
        self.usage_tracker = UsageTracker()
        
        # Initialize Google Custom Search if configured
        if config.get("google_api_key") and config.get("google_cx"):
            self.providers.append({
                "provider": GoogleCustomSearch(
                    config["google_api_key"],
                    config["google_cx"]
                ),
                "name": "google",
                "daily_limit": 100,
                "monthly_limit": 3000,
                "priority": 1
            })
            logger.info("Google Custom Search provider initialized")
        
        # Initialize Tavily if configured
        if config.get("tavily_api_key"):
            self.providers.append({
                "provider": TavilySearch(config["tavily_api_key"]),
                "name": "tavily",
                "monthly_limit": 1000,
                "priority": 2
            })
            logger.info("Tavily Search provider initialized")
        
        # Always have DuckDuckGo as fallback
        self.providers.append({
            "provider": DuckDuckGoSearch(),
            "name": "duckduckgo",
            "priority": 3
        })
        logger.info("DuckDuckGo Search provider initialized (fallback)")
        
        # Sort by priority
        self.providers.sort(key=lambda x: x["priority"])
        
        logger.info(f"Search orchestrator initialized with {len(self.providers)} providers")
    
    async def search(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Execute search with automatic fallback
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            Dict containing search results and metadata
            
        Raises:
            Exception: If all providers fail
        """
        last_error = None
        
        for provider_config in self.providers:
            provider = provider_config["provider"]
            name = provider_config["name"]
            
            # Check rate limits
            daily_limit = provider_config.get("daily_limit")
            monthly_limit = provider_config.get("monthly_limit")
            
            if not self.usage_tracker.can_use(name, daily_limit, monthly_limit):
                logger.warning(f"{name} rate limit reached, trying next provider")
                continue
            
            try:
                logger.info(f"Searching with {name} provider for query: '{query}'")
                results = await provider.search(query, max_results)
                
                # Log successful usage
                self.usage_tracker.log_usage(name)
                
                logger.info(f"Search completed with {name}, found {len(results)} results")
                
                return {
                    "status": "success",
                    "provider": name,
                    "query": query,
                    "results": results,
                    "count": len(results),
                    "usage": self.usage_tracker.get_usage(name)
                }
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"{name} search failed: {e}")
                continue
        
        # All providers failed
        error_msg = f"All search providers failed. Last error: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)


class VaultService:
    """
    Vault Service - Manages secrets and provides secure tool execution
    """
    
    def __init__(self):
        # Load secrets from file
        self.secrets = self._load_secrets()
        
        # Initialize search orchestrator
        search_config = self.secrets.get("search", {})
        self.search_orchestrator = SearchOrchestrator(search_config)
        
        logger.info("Vault service initialized successfully")
    
    def _load_secrets(self) -> Dict[str, Any]:
        """Load secrets from JSON file"""
        secrets_file = "/vault/secrets.json"
        
        if not os.path.exists(secrets_file):
            logger.warning(f"Secrets file not found: {secrets_file}")
            return {}
        
        try:
            with open(secrets_file, 'r') as f:
                secrets = json.load(f)
                logger.info(f"Loaded secrets from {secrets_file}")
                return secrets
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse secrets file: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error loading secrets: {e}")
            return {}
    
    def get_secret(self, name: str, default: Any = None) -> Any:
        """
        Get secret by name, supporting nested keys
        
        Args:
            name: Secret name (supports dot notation like 'search.google_api_key')
            default: Default value if secret not found
            
        Returns:
            Secret value or default
        """
        keys = name.split('.')
        value = self.secrets
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
        
        return value


# Initialize vault service
vault = VaultService()


@app.post("/execute")
async def execute_tool(request: ToolRequest) -> Dict[str, Any]:
    """
    Execute tool with injected secrets
    
    The agent never sees API keys - they are injected by the vault at execution time.
    This prevents prompt injection attacks from leaking credentials.
    """
    try:
        if request.tool == "web_search":
            # Multi-provider search with automatic fallback
            query = request.params.get('query', '')
            max_results = request.params.get('max_results', 10)
            
            if not query:
                raise HTTPException(status_code=400, detail="Query parameter is required")
            
            result = await vault.search_orchestrator.search(query, max_results)
            return result
        
        elif request.tool == "claude_api":
            # Inject Anthropic API key and call Claude API
            api_key = vault.get_secret("anthropic_api_key")
            
            if not api_key:
                raise HTTPException(
                    status_code=500, 
                    detail="Anthropic API key not configured in vault"
                )
            
            # Extract parameters
            prompt = request.params.get("prompt", "")
            max_tokens = request.params.get("max_tokens", 4000)
            model = request.params.get("model", "claude-sonnet-4-20250514")
            
            if not prompt:
                raise HTTPException(status_code=400, detail="Prompt is required")
            
            # Call Anthropic API
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        },
                        json={
                            "model": model,
                            "max_tokens": max_tokens,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ]
                        }
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Anthropic API error: {response.status_code} - {response.text}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Anthropic API returned {response.status_code}"
                        )
                    
                    data = response.json()
                    
                    # Extract text from response
                    content = data.get("content", [])
                    if content and len(content) > 0:
                        response_text = content[0].get("text", "")
                    else:
                        response_text = ""
                    
                    return {
                        "status": "success",
                        "response": response_text,
                        "model": data.get("model"),
                        "usage": data.get("usage", {})
                    }
                    
            except httpx.TimeoutException:
                raise HTTPException(status_code=504, detail="Claude API request timed out")
            except Exception as e:
                logger.error(f"Claude API call failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unknown tool: {request.tool}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health() -> Dict[str, Any]:
    """
    Health check endpoint
    Returns vault status and configured providers
    """
    # Check which search providers are configured
    providers = []
    if vault.get_secret("search.google_api_key"):
        providers.append("google")
    if vault.get_secret("search.tavily_api_key"):
        providers.append("tavily")
    providers.append("duckduckgo")  # Always available
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "secrets_loaded": len(vault.secrets),
        "search_providers": providers,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/search/usage")
async def search_usage() -> Dict[str, Any]:
    """
    Get current search usage statistics
    Useful for monitoring rate limit consumption
    """
    usage = {}
    for provider in ["google", "tavily", "duckduckgo"]:
        if provider in vault.search_orchestrator.usage_tracker.usage:
            usage[provider] = vault.search_orchestrator.usage_tracker.get_usage(provider)
    
    return {
        "status": "success",
        "usage": usage,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint"""
    return {
        "service": "SecureBot Vault",
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8200,
        log_level="info"
    )
