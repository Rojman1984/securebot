#!/usr/bin/env python3
"""
Claude Code Orchestrator
Manages skill creation, validation, and execution using Claude Code CLI format

Author: SecureBot Project
License: MIT
"""

import os
import json
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx
import yaml
from datetime import datetime

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
        self.skills = self._load_skills()
    
    def _load_skills(self) -> Dict[str, Any]:
        """Load all Claude Code format skills"""
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
                skills[skill['name']] = skill
                logger.info(f"Loaded skill: {skill['name']}")
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
            'content': markdown_content,
            'frontmatter': frontmatter,
            'path': skill_file,
            'triggers': self._extract_triggers(frontmatter.get('description', ''))
        }
    
    def _extract_triggers(self, description: str) -> List[str]:
        """Extract trigger keywords from description"""
        # Simple keyword extraction
        words = description.lower().split()
        # Filter out common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        return [w for w in words if w not in stop_words and len(w) > 3]
    
    def find_matching_skill(self, query: str) -> Optional[Dict[str, Any]]:
        """Find skill that best matches the query"""
        query_lower = query.lower()
        best_match = None
        best_score = 0
        
        for skill_name, skill in self.skills.items():
            score = 0
            
            # Check trigger words
            for trigger in skill['triggers']:
                if trigger in query_lower:
                    score += 2
            
            # Check if query mentions skill name
            if skill_name.replace('-', ' ') in query_lower:
                score += 3
            
            # Check description overlap
            desc_words = set(skill['description'].lower().split())
            query_words = set(query_lower.split())
            overlap = len(desc_words & query_words)
            score += overlap
            
            if score > best_score:
                best_score = score
                best_match = skill
        
        # Require minimum score
        if best_score >= 2:
            return best_match
        
        return None


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
    
    def __init__(self, vault_url: str = "http://vault:8200"):
        self.vault_url = vault_url
        self.skills_dir = Path("/home/tasker0/securebot/skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)
    
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
    
    async def execute_skill(
        self, 
        skill: Dict[str, Any], 
        query: str, 
        arguments: str,
        ollama_url: str
    ) -> str:
        """Execute skill with Ollama"""
        logger.info(f"Executing skill: {skill['name']}")
        
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
        
        # Final prompt
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
                response = await client.post(
                    f"{self.vault_url}/execute",
                    json={
                        "tool": "claude_api",
                        "params": {
                            "prompt": prompt,
                            "max_tokens": 4000
                        },
                        "session_id": "orchestrator"
                    }
                )
                
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
    ollama_url: str = "http://host.docker.internal:11434"
) -> Dict[str, Any]:
    """
    Main routing logic for intelligent query handling
    
    This is the entry point called by Gateway
    """
    
    # Step 1: Check for matching skill
    matcher = SkillMatcher()
    matching_skill = matcher.find_matching_skill(query)
    
    # Step 2: Classify complexity
    complexity = ComplexityClassifier.classify(query, bool(matching_skill))
    
    logger.info(f"Query: '{query[:50]}...'")
    logger.info(f"Classification: {complexity}")
    if matching_skill:
        logger.info(f"Matched skill: {matching_skill['name']}")
    
    # Step 3: Route based on classification
    orchestrator = ClaudeCodeOrchestrator(vault_url)
    
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
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": "phi4-mini:3.8b",
                    "prompt": query,
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
