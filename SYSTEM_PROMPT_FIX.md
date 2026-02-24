Two targeted fixes in gateway/orchestrator.py only.

FIX 1: Add load_system_prompt() function at module level that reads 
/memory/user.md and builds BASE_SYSTEM_PROMPT string. Replace all 
`system_prompt or ""` with `system_prompt or BASE_SYSTEM_PROMPT`.

FIX 2: In execute_skill(), after capturing script output and before 
calling Ollama, fetch lightweight RAG context (max_tokens=100) and 
include it in the wrap prompt alongside the skill output.

Do not touch any other files. Syntax check after changes.
