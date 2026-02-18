#!/usr/bin/env python3
"""
Claude Code Orchestrator
Manages skill creation, validation, and execution using Claude Code CLI format

Author: SecureBot Project
License: MIT
"""

import os
import sys
import json
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx
import yaml
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import get_config
from common.auth import SignedClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SkillMatcher:
    """Match queries to existing skills using Claude Code format"""

    def __init__(self, skills_dir: str = "/home/tasker0/securebot/skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.config = get_config()
        self.skills = self._load_skills()
    
    def _load_skills(self) -> Dict[str, Any]:
        """Load all Claude Code format skills (respecting user config)"""
        skills = {}

        if not self.skills_dir.exists():
            return skills

        # Look for SKILL.md files in skill directories
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                skill = self._parse_skill_file(skill_file)

                # Check if skill is enabled in config
                if self.config.is_skill_enabled(skill['name']):
                    skills[skill['name']] = skill
                    logger.info(f"Loaded skill: {skill['name']} (category: {skill.get('category', 'general')})")
                else:
                    logger.info(f"Skipped disabled skill: {skill['name']}")

            except Exception as e:
                logger.error(f"Failed to load skill {skill_file}: {e}")

        return skills
    
    def _parse_skill_file(self, skill_file: Path) -> Dict[str, Any]:
        """Parse Claude Code SKILL.md format"""
        content = skill_file.read_text()
        
        # Extract YAML frontmatter
        if content.startswith('---\n'):
            parts = content.split('---\n', 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                markdown_content = parts[2].strip()
            else:
                frontmatter = {}
                markdown_content = content
        else:
            frontmatter = {}
            markdown_content = content
        
        return {
            'name': frontmatter.get('name', skill_file.parent.name),
            'description': frontmatter.get('description', ''),
            'category': frontmatter.get('category', 'general'),
            'priority': frontmatter.get('priority', 999),
            'content': markdown_content,
            'frontmatter': frontmatter,
            'path': skill_file,
            'triggers': self._extract_triggers(frontmatter.get('description', ''))
        }
    
    def _extract_triggers(self, description: str) -> List[str]:
        """Extract trigger keywords from description"""
        # Simple keyword extraction
        words = description.lower().split()
        # Filter out common words - expanded to prevent false matches
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'this', 'that', 'with', 'from', 'will', 'when', 'where', 'what', 'how',
            'your', 'you', 'any', 'all', 'can', 'use', 'using', 'used', 'useful',
            'data', 'text', 'string', 'function', 'method', 'code', 'program',
            'processing', 'manipulation', 'practice', 'algorithm', 'implementation'
        }
        return [w for w in words if w not in stop_words and len(w) > 3]
    
    def find_matching_skill(self, query: str, category: Optional[str] = None, exclude_categories: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Find skill that best matches the query

        Args:
            query: Query text to match
            category: Optional category filter (e.g., 'search')
            exclude_categories: Optional list of categories to exclude (e.g., ['search'])

        Returns:
            Best matching skill or None
        """
        query_lower = query.lower()
        best_match = None
        best_score = 0

        # Filter by category if specified
        skills_to_check = self.skills.items()
        if category:
            skills_to_check = [(name, skill) for name, skill in skills_to_check
                              if skill.get('category') == category]
        elif exclude_categories:
            # Exclude specific categories
            skills_to_check = [(name, skill) for name, skill in skills_to_check
                              if skill.get('category') not in exclude_categories]

        for skill_name, skill in skills_to_check:
            score = 0

            # Check trigger words (higher weight for specificity)
            for trigger in skill['triggers']:
                if trigger in query_lower:
                    score += 3  # Increased from 2 to require stronger match

            # Check if query mentions skill name (exact match)
            if skill_name.replace('-', ' ') in query_lower:
                score += 5  # Increased from 3 for exact name match

            # Check description overlap (reduced weight to prevent false matches)
            desc_words = set(skill['description'].lower().split())
            query_words = set(query_lower.split())
            overlap = len(desc_words & query_words)
            score += overlap * 0.5  # Reduced weight from 1 to 0.5 per overlap

            if score > best_score:
                best_score = score
                best_match = skill

        # Require STRONGER minimum score to prevent false matches
        if best_score >= 5:  # Increased from 2 to 5
            return best_match

        return None

    def get_skills_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all skills in a category, sorted by priority

        Args:
            category: Category name (e.g., 'search')

        Returns:
            List of skills sorted by priority (lower priority = higher precedence)
        """
        category_skills = [
            skill for skill in self.skills.values()
            if skill.get('category') == category
        ]

        # Sort by configured priority first, then skill's own priority
        category_skills.sort(key=lambda s: (
            self.config.get_skill_priority(s['name'], s.get('priority', 999)),
            s.get('priority', 999)
        ))

        return category_skills


class IntentClassifier:
    """Classify query intent: ACTION vs KNOWLEDGE with hybrid LLM disambiguation"""

    # High-confidence KNOWLEDGE patterns - unambiguous questions
    KNOWLEDGE_PATTERNS_HIGH = [
        # Question starters
        "explain", "what is", "what are", "what do", "what does",
        "why", "why is", "why are", "why do", "why does",
        "how does", "how do", "how is", "how are",
        "describe", "tell me about", "tell me what",
        "define", "definition of",
        "can you explain", "help me understand",
        "could you explain", "would you explain",

        # Comparative/informational
        "difference between", "differences between",
        "what's the difference",
        "what does X mean", "what do X mean",
        "meaning of", "purpose of",

        # Knowledge queries
        "what do you know", "do you know",
        "have you heard", "are you familiar",
        "summarize", "summary of",
        "tell me", "show me what"
    ]

    # High-confidence ACTION patterns - unambiguous action requests
    ACTION_PATTERNS_HIGH = [
        # Unambiguous creation/execution
        "reverse", "encrypt", "decode", "decrypt", "hash",
        "parse", "convert", "transform", "execute",
        "run", "perform",
        "schedule", "automate", "set up", "setup",
        "configure", "install", "deploy",
        "write a script", "generate a script",

        # Modification
        "fix", "update", "change", "modify", "edit",
        "refactor", "optimize", "improve", "enhance",

        # Search/retrieval (when action-oriented)
        "search for", "find me", "look up", "get me",
        "fetch", "retrieve", "pull"
    ]

    # Ambiguous verbs - can be action OR knowledge depending on context
    AMBIGUOUS_VERBS = [
        "design", "develop", "implement", "build", "create",
        "make", "write", "code", "compare"
    ]

    # Analytical signals - indicate knowledge intent even with ambiguous verbs
    ANALYTICAL_SIGNALS = [
        "trade-off", "trade-offs", "tradeoff", "tradeoffs",
        "consider", "considering",
        "pros and cons", "advantages and disadvantages",
        "when to use", "when should",
        "difference", "compare", "comparison",
        "best practice", "best practices",
        "why", "how does", "what is",
        "explain", "describe",
        "architecture", "strategy", "approach",
        "pattern", "patterns",
        "philosophy", "principles"
    ]

    @staticmethod
    def classify_intent(query: str) -> tuple[str, str]:
        """
        Classify query intent with confidence scoring

        Returns:
            Tuple of (intent, confidence) where:
            - intent: "knowledge" or "action"
            - confidence: "high" or "ambiguous"
        """
        query_lower = query.lower().strip()

        # Check high-confidence KNOWLEDGE patterns first
        for pattern in IntentClassifier.KNOWLEDGE_PATTERNS_HIGH:
            if query_lower.startswith(pattern) or f" {pattern}" in f" {query_lower}":
                return ("knowledge", "high")

        # Check for analytical signals (knowledge even with action verbs)
        has_analytical = any(signal in query_lower for signal in IntentClassifier.ANALYTICAL_SIGNALS)

        # Check for ambiguous verbs
        has_ambiguous_verb = any(verb in query_lower for verb in IntentClassifier.AMBIGUOUS_VERBS)

        # If has ambiguous verb + analytical signals = ambiguous (needs LLM)
        if has_ambiguous_verb and has_analytical:
            return ("knowledge", "ambiguous")

        # Check high-confidence ACTION patterns
        for pattern in IntentClassifier.ACTION_PATTERNS_HIGH:
            if query_lower.startswith(pattern):
                return ("action", "high")

        # If has ambiguous verb without analytical signals = likely action
        if has_ambiguous_verb:
            return ("action", "high")

        # Default to knowledge (safer/cheaper)
        return ("knowledge", "high")


async def classify_with_ollama(query: str, ollama_url: str, rag_url: str, signed_client: Optional[Any] = None) -> str:
    """
    Fast LLM classification for ambiguous queries using few-shot examples from ChromaDB.

    Uses minimal tokens for quick classification (~3-5s on phi4-mini).

    Args:
        query: The user query to classify
        ollama_url: Ollama service URL
        rag_url: RAG service URL for fetching examples
        signed_client: Optional SignedClient for authenticated requests

    Returns:
        "action" or "knowledge"
    """
    # Fetch similar examples from RAG service
    examples = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{rag_url}/classify/examples"
            params = {"query": query, "k": 3}

            if signed_client:
                response = await signed_client.get(client, url, params=params)
            else:
                response = await client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                examples = data.get("examples", [])
                if examples:
                    logger.info(f"Retrieved {len(examples)} few-shot examples from RAG")
            else:
                logger.warning(f"Failed to fetch examples: HTTP {response.status_code}")
    except Exception as e:
        logger.warning(f"Failed to fetch few-shot examples: {e}, falling back to zero-shot")

    # Build prompt - few-shot if examples available, zero-shot otherwise
    if examples:
        # Build few-shot prompt
        system_prompt = """You are a query intent classifier.
ACTION = user wants a specific artifact, script, transformation, or execution
KNOWLEDGE = user wants explanation, analysis, comparison, or architectural guidance

Examples:"""

        for ex in examples:
            system_prompt += f"\nQ: {ex['query']}\nA: {ex['label']}\n"

        system_prompt += "\nReply with only one word: ACTION or KNOWLEDGE"
        full_prompt = f"{system_prompt}\n\nQ: {query}\nA:"
        logger.info("Using few-shot classification prompt")
    else:
        # Fallback to zero-shot
        system_prompt = """You are a query classifier. Classify the query as exactly one of:

ACTION - user wants you to create, build, execute, or produce something specific (code, script, file, output)
KNOWLEDGE - user wants explanation, analysis, comparison, discussion, or theoretical understanding

Reply with only the single word: ACTION or KNOWLEDGE"""
        full_prompt = f"{system_prompt}\n\nQuery: {query}\n\nClassification:"
        logger.info("Using zero-shot classification prompt (no examples available)")

    try:
        logger.info("🔍 Using LLM for ambiguous query classification")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": "phi4-mini:3.8b",
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 5,  # Only need one word
                        "temperature": 0.1,  # Low temperature for deterministic output
                        "top_p": 0.9
                    }
                }
            )

            data = response.json()
            result = data.get("response", "").strip().upper()

            # Parse result - look for ACTION or KNOWLEDGE
            if "ACTION" in result:
                logger.info("✓ LLM classified as: ACTION")
                return "action"
            elif "KNOWLEDGE" in result:
                logger.info("✓ LLM classified as: KNOWLEDGE")
                return "knowledge"
            else:
                logger.warning(f"LLM returned unexpected result: {result}, defaulting to KNOWLEDGE")
                return "knowledge"

    except Exception as e:
        logger.warning(f"LLM classification failed: {e}, defaulting to KNOWLEDGE")
        return "knowledge"  # Graceful fallback


class ComplexityClassifier:
    """Determine routing strategy based on query complexity"""

    @staticmethod
    def classify(query: str, has_matching_skill: bool) -> str:
        """
        Classify task complexity

        Returns:
            "skill_execution" - Use Ollama with existing skill
            "direct_ollama" - Use Ollama directly (simple)
            "skill_creation" - Use Claude API to create skill
            "direct_claude" - Use Claude API directly (complex one-off)
        """

        # If we have a skill, use it
        if has_matching_skill:
            return "skill_execution"

        # Check if it's skill-worthy (repeatable pattern)
        if ComplexityClassifier._is_skill_worthy(query):
            return "skill_creation"

        # Check if it's complex but one-off
        if ComplexityClassifier._is_complex(query):
            return "direct_claude"

        # Simple query, use Ollama directly
        return "direct_ollama"
    
    @staticmethod
    def _is_skill_worthy(query: str) -> bool:
        """Check if this pattern is worth creating a reusable skill"""
        skill_indicators = [
            # Workflows that could be repeated
            "create a", "generate a", "build a",
            "automate", "always", "every time",
            
            # Code patterns
            "refactor", "optimize", "review",
            "test", "debug", "lint",
            
            # Analysis patterns
            "analyze", "summarize", "extract",
            "compare", "evaluate",
            
            # Research patterns
            "research", "find papers", "survey",
            
            # Documentation
            "document", "write docs", "explain"
        ]
        
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in skill_indicators)
    
    @staticmethod
    def _is_complex(query: str) -> bool:
        """Check if query needs Claude API (complex reasoning)"""
        complex_indicators = [
            # Length (very long query)
            lambda q: len(q.split()) > 50,
            
            # Multi-step reasoning
            lambda q: any(word in q.lower() for word in [
                "step by step", "walk me through",
                "first", "then", "finally",
                "explain in detail"
            ]),
            
            # Deep analysis
            lambda q: any(word in q.lower() for word in [
                "critique", "deeply analyze", "comprehensive",
                "trade-offs", "implications", "philosophy",
                "pros and cons"
            ]),
            
            # Architecture/design
            lambda q: any(word in q.lower() for word in [
                "design system", "architecture",
                "best practices", "patterns"
            ])
        ]
        
        return any(indicator(query) for indicator in complex_indicators)


class ClaudeCodeOrchestrator:
    """Orchestrate Claude Code CLI for skill management"""

    def __init__(self, vault_url: str = "http://vault:8200", memory_service_url: Optional[str] = None, rag_url: Optional[str] = None):
        self.vault_url = vault_url
        self.memory_service_url = memory_service_url or os.getenv("MEMORY_SERVICE_URL", "http://memory-service:8300")
        self.rag_url = rag_url or os.getenv("RAG_URL", "http://rag-service:8400")
        self.skills_dir = Path("/home/tasker0/securebot/skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.memory_context = None

        # Initialize signed client for inter-service auth
        service_id = os.getenv("SERVICE_ID", "gateway")
        service_secret = os.getenv("SERVICE_SECRET", "")
        self.signed_client = SignedClient(service_id, service_secret) if service_secret else None
    
    async def create_skill(self, query: str, purpose: str) -> Dict[str, Any]:
        """
        Use Claude API to generate a new Claude Code format skill
        
        This costs money but creates reusable value
        """
        logger.info(f"Creating new skill for: {purpose}")
        
        # Generate skill with Claude API
        skill_prompt = f"""
Create a reusable skill in Claude Code format for the following task:

Task: {query}
Purpose: {purpose}

Generate a complete SKILL.md file following this exact format:

---
name: descriptive-skill-name
description: Clear description of what this skill does and when to use it. Include trigger keywords naturally.
disable-model-invocation: false
---

# Skill Name

Clear instructions for what this skill does.

## Usage

Explain how to use this skill and what it expects.

## Steps

1. First step with clear instructions
2. Second step
3. Continue with detailed steps

## Output Format

Describe the expected output format.

## Examples

Show example usage if helpful.

IMPORTANT RULES:
1. Keep skill content under 500 lines
2. Use clear, actionable instructions
3. Include $ARGUMENTS placeholder if skill takes parameters
4. Make description rich with natural keywords so skill matches relevant queries
5. Focus on ONE specific task, not multiple unrelated things
6. Return ONLY the SKILL.md content, nothing else

Generate the complete SKILL.md now:
"""
        
        skill_content = await self._call_claude_api(skill_prompt)
        
        # Parse the generated skill
        try:
            # Extract name from frontmatter
            if '---' in skill_content:
                parts = skill_content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    skill_name = frontmatter.get('name', 'unnamed-skill')
                else:
                    skill_name = 'unnamed-skill'
            else:
                skill_name = 'unnamed-skill'
            
            # Create skill directory
            skill_dir = self.skills_dir / skill_name
            skill_dir.mkdir(exist_ok=True)
            
            # Save SKILL.md
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(skill_content)
            
            logger.info(f"Skill created: {skill_name} at {skill_file}")
            
            # Parse the saved skill
            matcher = SkillMatcher(str(self.skills_dir))
            skill = matcher._parse_skill_file(skill_file)
            
            return skill
            
        except Exception as e:
            logger.error(f"Failed to create skill: {e}")
            raise
    
    async def load_memory_context(self):
        """Load combined memory context from memory service (legacy fallback)"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                url = f"{self.memory_service_url}/memory/context"

                if self.signed_client:
                    response = await self.signed_client.get(client, url)
                else:
                    response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    self.memory_context = data.get("content", "")
                    logger.info("Memory context loaded successfully")
                else:
                    logger.warning(f"Failed to load memory context: HTTP {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not load memory context: {e}")
            # Graceful fallback - continue without memory

    async def get_relevant_context(self, query: str, max_tokens: int = 300) -> str:
        """Get relevant context from RAG service (NEW - replaces full memory loading)"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                url = f"{self.rag_url}/context"
                params = {"query": query, "max_tokens": max_tokens}

                if self.signed_client:
                    response = await self.signed_client.get(client, url, params=params)
                else:
                    response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    context = data.get("context", "")
                    tokens = data.get("tokens_estimate", 0)
                    logger.info(f"RAG context retrieved: {tokens} tokens from {len(data.get('sources', []))} sources")
                    return context
                else:
                    logger.warning(f"RAG service unavailable: HTTP {response.status_code}")
                    return ""
        except Exception as e:
            logger.warning(f"RAG context retrieval failed: {e}, falling back to no context")
            return ""  # Graceful fallback

    async def execute_skill(
        self,
        skill: Dict[str, Any],
        query: str,
        arguments: str,
        ollama_url: str
    ) -> str:
        """Execute skill with Ollama"""
        logger.info(f"Executing skill: {skill['name']}")

        # Get relevant context from RAG (NEW - only loads relevant chunks)
        context = await self.get_relevant_context(query, max_tokens=300)

        # Build prompt from skill content with arguments
        skill_content = skill['content']

        # Replace $ARGUMENTS placeholder
        if '$ARGUMENTS' in skill_content:
            skill_content = skill_content.replace('$ARGUMENTS', arguments)
        else:
            # Append arguments if not in template
            skill_content = f"{skill_content}\n\nARGUMENTS: {arguments}"

        # Replace session ID if present
        if '${CLAUDE_SESSION_ID}' in skill_content:
            session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            skill_content = skill_content.replace('${CLAUDE_SESSION_ID}', session_id)

        # Prepend relevant context if available (NEW - RAG context only)
        if context:
            final_prompt = f"Context:\n{context}\n\n---\n\n{skill_content}\n\nUser query: {query}"
        else:
            final_prompt = f"{skill_content}\n\nUser query: {query}"
        
        # Execute with Ollama
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": "phi4-mini:3.8b",
                        "prompt": final_prompt,
                        "stream": False
                    }
                )
                
                data = response.json()
                result = data.get("response", "")
            
            logger.info(f"Skill execution completed")
            return result
            
        except Exception as e:
            logger.error(f"Skill execution failed: {e}")
            raise
    
    async def _call_claude_api(self, prompt: str) -> str:
        """Call Claude API via Vault"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                url = f"{self.vault_url}/execute"
                payload = {
                    "tool": "claude_api",
                    "params": {
                        "prompt": prompt,
                        "max_tokens": 4000
                    },
                    "session_id": "orchestrator"
                }

                if self.signed_client:
                    response = await self.signed_client.post(client, url, json=payload)
                else:
                    response = await client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "")
                else:
                    raise Exception(f"Claude API call failed: HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise


# Main routing function for Gateway integration
async def route_query(
    query: str,
    user_id: str,
    vault_url: str = "http://vault:8200",
    ollama_url: str = "http://host.docker.internal:11434",
    has_search_results: bool = False,
    memory_service_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main routing logic for intelligent query handling

    This is the entry point called by Gateway

    Args:
        query: User query (may be augmented with search results)
        user_id: User identifier
        vault_url: Vault service URL
        ollama_url: Ollama service URL
        has_search_results: If True, query contains search results and should skip skill matching
    """

    # IMPORTANT: If query has search results, skip ALL skill logic and go directly to Ollama
    if has_search_results:
        logger.info("Query has search results - skipping skill matching/creation, using Ollama for summarization")
        logger.info(f"Query: '{query[:100]}...'")

        # Get relevant context from RAG (NEW - only relevant chunks)
        orchestrator = ClaudeCodeOrchestrator(vault_url, memory_service_url)
        context = await orchestrator.get_relevant_context(query, max_tokens=300)

        # Prepend context if available
        if context:
            enhanced_query = f"Context:\n{context}\n\n---\n\n{query}"
        else:
            enhanced_query = query

        # Use Ollama directly to summarize search results
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": "phi4-mini:3.8b",
                    "prompt": enhanced_query,
                    "stream": False
                }
            )
            result = response.json().get("response", "")

        return {
            "result": result,
            "method": "direct_ollama",
            "cost": 0.0,
            "engine": "ollama"
        }

    # Step 1: Classify intent with confidence scoring
    intent, confidence = IntentClassifier.classify_intent(query)
    logger.info(f"Intent classification: {intent} (confidence: {confidence})")

    # Step 1b: Use LLM for ambiguous cases
    if confidence == "ambiguous":
        logger.info(f"⚠️  Ambiguous query detected, invoking LLM classifier")
        # Create temporary orchestrator to get signed_client
        temp_orchestrator = ClaudeCodeOrchestrator(vault_url, memory_service_url)
        rag_url = temp_orchestrator.rag_url
        intent = await classify_with_ollama(query, ollama_url, rag_url, temp_orchestrator.signed_client)
        logger.info(f"LLM resolved intent: {intent}")

    # If KNOWLEDGE intent, bypass all skill logic and go directly to Ollama
    if intent == "knowledge":
        logger.info("KNOWLEDGE intent detected - bypassing skill matching, using Ollama directly")
        logger.info(f"Query: '{query[:100]}...'")

        # Get relevant context from RAG (NEW - only relevant chunks)
        orchestrator = ClaudeCodeOrchestrator(vault_url, memory_service_url)
        context = await orchestrator.get_relevant_context(query, max_tokens=300)

        # Prepend context if available
        if context:
            enhanced_query = f"Context:\n{context}\n\n---\n\nUser query: {query}"
        else:
            enhanced_query = query

        # Use Ollama directly for knowledge queries
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": "phi4-mini:3.8b",
                    "prompt": enhanced_query,
                    "stream": False
                }
            )
            result = response.json().get("response", "")

        return {
            "result": result,
            "method": "direct_ollama",
            "intent": "knowledge",
            "cost": 0.0,
            "engine": "ollama"
        }

    # Step 2: Check for matching skill (only for ACTION intent)
    matcher = SkillMatcher()
    matching_skill = matcher.find_matching_skill(query, exclude_categories=['search'])

    # Step 3: Classify complexity (for ACTION queries)
    complexity = ComplexityClassifier.classify(query, bool(matching_skill))

    logger.info(f"Query: '{query[:50]}...'")
    logger.info(f"Has search results: {has_search_results}")
    logger.info(f"Intent: {intent}")
    logger.info(f"Classification: {complexity}")
    if matching_skill:
        logger.info(f"Matched skill: {matching_skill['name']}")

    # Step 4: Route based on classification
    orchestrator = ClaudeCodeOrchestrator(vault_url, memory_service_url)
    
    if complexity == "skill_execution":
        # Execute with existing skill
        result = await orchestrator.execute_skill(
            matching_skill,
            query,
            query,  # Full query as arguments
            ollama_url
        )
        
        return {
            "result": result,
            "method": "skill_execution",
            "skill_used": matching_skill['name'],
            "cost": 0.0,
            "engine": "ollama"
        }
    
    elif complexity == "skill_creation":
        # Create new skill, then execute
        logger.info("Creating new skill (this costs $$)")
        
        # Create skill with Claude API
        skill = await orchestrator.create_skill(query, purpose=query)
        
        # Execute with Ollama
        result = await orchestrator.execute_skill(
            skill,
            query,
            query,
            ollama_url
        )
        
        return {
            "result": result,
            "method": "skill_creation",
            "skill_created": skill['name'],
            "skill_path": str(skill['path']),
            "cost": 0.10,  # Skill creation cost
            "engine": "claude+ollama"
        }
    
    elif complexity == "direct_claude":
        # Complex one-off, use Claude directly
        logger.info("Using Claude API directly for complex query")
        
        result = await orchestrator._call_claude_api(query)
        
        return {
            "result": result,
            "method": "direct_claude",
            "cost": 0.006,
            "engine": "claude"
        }
    
    else:  # direct_ollama
        # Simple query, Ollama direct
        logger.info("Using Ollama directly for simple query")

        # Get relevant context from RAG (NEW - only relevant chunks)
        context = await orchestrator.get_relevant_context(query, max_tokens=300)

        # Prepend context if available
        if context:
            enhanced_query = f"Context:\n{context}\n\n---\n\nUser query: {query}"
        else:
            enhanced_query = query

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": "phi4-mini:3.8b",
                    "prompt": enhanced_query,
                    "stream": False
                }
            )
            result = response.json().get("response", "")

        return {
            "result": result,
            "method": "direct_ollama",
            "cost": 0.0,
            "engine": "ollama"
        }


async def seed_classifier_examples_on_startup(rag_url: str, signed_client: Optional[Any] = None):
    """
    Seed classifier examples collection on gateway startup.
    Runs in background, does not block startup.
    """
    try:
        logger.info("Attempting to seed classifier examples...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{rag_url}/classify/seed"

            if signed_client:
                response = await signed_client.post(client, url, json={})
            else:
                response = await client.post(url, json={})

            if response.status_code == 200:
                data = response.json()
                seeded = data.get("seeded", 0)
                if seeded > 0:
                    logger.info(f"✓ Seeded {seeded} classifier examples")
                else:
                    logger.info("Classifier examples already seeded")
            else:
                logger.warning(f"Failed to seed classifier examples: HTTP {response.status_code}")

    except Exception as e:
        logger.warning(f"Failed to seed classifier examples: {e}")
        # Graceful failure - don't block startup


if __name__ == "__main__":
    import asyncio

    # Test the orchestrator
    async def test():
        result = await route_query(
            "Write a function to calculate fibonacci numbers",
            "test_user"
        )
        print(json.dumps(result, indent=2))

    asyncio.run(test())
