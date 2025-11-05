# Missing Documentation Analysis - Bombe LLM 2.0

**Generated:** Multi-revision deep analysis of repository
**Purpose:** Identify critical information gaps in existing documentation

---

## 1. API ENDPOINTS & INTERFACE DETAILS ⚠️ **CRITICAL GAP**

### Missing: FastAPI Endpoint Specifications

**What's undocumented:**

#### `/query/` POST Endpoint
```python
Request Body:
{
    "question": str,           # REQUIRED - The user's query
    "session_id": str | None   # OPTIONAL - UUID for chat history context
}

Response (Success):
{
    "simple_summary": str,
    "key_insights": List[str],
    "detailed_explanation": str,
    "context_relevance": float,
    "return_answer": bool,
    "bypass_user_intent": bool,
    "requires_clarification": bool,      # Only in Standard Mode
    "clarification_message": str | None, # Only in Standard Mode
    "suggested_query": str | None        # Only in Standard Mode
}
```

#### `/health` GET Endpoint
```python
Response:
{
    "status": "ok" | "error",
    "agent_initialized": bool,
    "database_connection": "ok" | "error",
    "context_caching": "enabled" | "disabled",
    "bypass_user_intent": bool,
    "performance_optimizations": {
        "context_caching": bool,
        "direct_query_mode": bool
    },
    "features": {
        "user_intent_clarification": bool,
        "direct_query_processing": bool,
        "langsmith_tracing": bool
    }
}
```

**Security Missing:**
- API Key authentication via `X-API-Key` header
- Controlled by `PROD_LLM_API_KEY` environment variable
- Returns 403 if key doesn't match

---

## 2. DATABASE SCHEMA DETAILS ⚠️ **CRITICAL GAP**

### Missing: Complete Table/View Definitions

**Undocumented Schema Components:**

#### Chat History Tables (Session Support)
```sql
chat_history
├── chat_session_id (UUID)     # Links to session
├── source (TEXT)               # 'User' or 'Bombe'
├── payload (JSONB)             # Message content
└── created_at (TIMESTAMP)      # Message timestamp

chat_session
├── session_id (UUID)           # Primary key
└── [other session metadata]
```

**Payload Structure:**
- **User messages:** `{"question": "..."}`
- **Bombe messages:** `{"simple_summary": "...", "detailed_explanation": "...", ...}`

#### Personas Table Structure
```sql
personas
├── id (INT)
├── code (TEXT)          # e.g., "Persona 1", "Bombe 2"
├── name (TEXT)
├── label (TEXT)         # Human-readable description
├── description (TEXT)   # Detailed characteristics
└── type (TEXT)          # "Demographic" or "Commercial"
```

**Key Constraint:**
- Everyone belongs to EXACTLY ONE Demographic persona (1-9)
- Everyone belongs to EXACTLY ONE Commercial persona (Bombe 1-7)

---

## 3. TWO DIFFERENT ENTRY POINTS ⚠️ **MAJOR GAP**

### Missing: Distinction Between main.py and main_test.py

**Critical Difference:**

#### `main.py` (CLI/Interactive)
- Designed for command-line usage
- Simpler UserIntentAgent integration
- Calls: `user_intent_agent.clarify_and_refine_query()`
- Returns: `(clarified_query, intent_context)` tuple
- **Uses input() for interactive clarification**

#### `main_test.py` (FastAPI/Production)
- Full FastAPI web service
- Session-aware with chat history support
- Calls: `user_intent_agent.clarify_and_refine_query(external_chat_history=...)`
- Handles multi-step clarification responses
- **Non-interactive - returns clarification requests to caller**

**Status Codes in FastAPI:**
- `clarified` → Process with HighLevelAgent
- `ask_clarification` → Return question to user
- `suggest_refinement` → Offer suggested query
- `error` / `max_interactions` → Return error response

---

## 4. GLOSSARY & DOMAIN MODEL ⚠️ **CRITICAL GAP**

### Missing: Behavioral Model Types Explanation

**The system works with 3 MODEL TYPES:**

#### 1. Persona Models
- **What:** Likelihood of behavior broken down by persona
- **Predictor:** The persona itself
- **Example:** "Visit Borough Market by Persona 3"
- **Data:** `mrp_data_persona_models` table

#### 2. Persona Consumer Models
- **What:** Factors affecting behavior FOR ONE SPECIFIC PERSONA
- **Predictor:** Factors like convenience, loyalty, price
- **Example:** "Factors affecting Persona 5 shopping at Aldi"
- **Single persona + single activity**

#### 3. Non-Persona Models
- **What:** General behavioral drivers (persona-independent)
- **Predictor:** Activities, attitudes, demographics
- **Example:** "Factors affecting Ryanair usage"
- **Data:** `mrp_data_non_persona_models` table

**Statistical Significance:**
- Only statistically significant factors are displayed
- Impact scores range from ~-0.01 to 0.01
- Expressed as normalized coefficients (percentage scale)

---

## 5. CONTEXT CACHING IMPLEMENTATION ⚠️ **TECHNICAL GAP**

### Missing: How Caching Actually Works

**Google Gemini Context Caching Details:**

#### Cached Content Structure
```python
cached_content = caching.CachedContent.create(
    model='models/gemini-2.5-pro',
    display_name='persona_schema_cache',
    system_instruction="...",
    contents=[schema_info + glossary],
    ttl=datetime.timedelta(hours=2)  # 2-hour cache lifetime
)
```

**What Gets Cached:**
1. Complete database schema information
2. Full glossary definitions
3. SQL generation rules
4. Planning approach guidelines

**Cache Usage:**
- `_get_cached_initial_planning_response()` - First iteration
- `_get_cached_followup_planning_response()` - Subsequent iterations
- Automatic fallback to LangChain if caching fails

**Performance Impact:**
- Reduced API token costs (schema not sent each time)
- Faster response times for planning stage
- Cache persists for 2 hours across multiple queries

#### UserIntentAgent Also Has Caching

**Three-Level Cache Strategy:**

1. **System Message Cache** - Static schema/glossary (cached at init)
2. **Prompt Cache** - Generated prompts (max 100 entries, FIFO)
3. **Response Cache** - LLM responses (max 50 entries, FIFO)

**Cache Statistics Available:**
```python
agent.get_cache_stats() → {
    "cache_enabled": bool,
    "prompt_cache_size": int,
    "response_cache_size": int,
    "cache_hits": int,
    "cache_misses": int,
    "hit_rate_percent": float
}
```

**Runtime Control:**
```python
agent.set_caching_enabled(True/False)
agent.clear_cache()
```

---

## 6. SQL QUERY VALIDATION & CONSTRAINTS ⚠️ **SECURITY GAP**

### Missing: SQL Security Implementation

**Validation in `sql_executor.py`:**

#### Allowed Operations
- **ONLY SELECT statements** permitted
- Queries must start with SELECT (after removing comments)

#### Blocked Keywords (Security)
```python
DANGEROUS = [
    'DROP', 'DELETE', 'INSERT', 'UPDATE',
    'ALTER', 'CREATE', 'TRUNCATE'
]
```

**SQL Comment Handling:**
- Lines starting with `--` are stripped before validation
- Prevents comment-based SQL injection
- Cleaned query must still start with SELECT

**Query Limits:**
- Planning stage generates max 3 SQL queries per iteration
- Results limited via LIMIT clauses (typically 20-30 rows)
- Max display rows: 10 (in formatting)

---

## 7. ERROR HANDLING PATTERNS ⚠️ **OPERATIONAL GAP**

### Missing: Error Response Structures

**Standard Error Response:**
```python
{
    "simple_summary": "Unable to complete analysis due to error: {error}",
    "key_insights": ["Analysis could not be completed", "Please check query..."],
    "detailed_explanation": "The system encountered an error...",
    "context_relevance": 0.0,
    "return_answer": False
}
```

**Error States:**

1. **Planning Failure** → `state['error_message']` set, workflow ends
2. **SQL Validation Failure** → Query skipped, logged, continues with next
3. **SQL Execution Failure** → Logged as error, stored in results with `success: False`
4. **Max Iterations Reached** → Forces final answer generation with available data
5. **Clarification Failure** → Returns clarification request or error status

**Graceful Degradation:**
- SQL errors don't halt entire workflow
- Partial results still synthesized into final answer
- Evaluation stage determines sufficiency of partial data

---

## 8. DEPLOYMENT CONFIGURATION ⚠️ **INFRASTRUCTURE GAP**

### Missing: Production Deployment Details

**Dockerfile Configuration:**
```dockerfile
# Production Server
CMD ["gunicorn",
     "-w", "4",                              # 4 worker processes
     "-k", "uvicorn.workers.UvicornWorker", # ASGI workers
     "--timeout", "180",                     # 3-minute timeout
     "-b", "0.0.0.0:8008",                  # Bind to port 8008
     "main:app"]
```

**Key Settings:**
- **Workers:** 4 (suitable for CPU-bound LLM operations)
- **Timeout:** 180 seconds (allows for multi-iteration workflows)
- **Port:** 8008 (production), 8002 (development default)
- **Base Image:** python:3.10-slim

**Cloud Run Compatibility:**
- Designed for Google Cloud Run
- PORT environment variable support
- `.gcloudignore` file present

**Environment Requirements for Production:**
```bash
GOOGLE_API_KEY=required
DATABASE_URL=required
PROD_LLM_API_KEY=required_for_security

# Optional
BYPASS_USER_INTENT_AGENT=false
DEBUG=false
MAX_ITERATIONS=4
LANGSMITH_TRACING=false
```

---

## 9. MODEL TEMPERATURE SETTINGS ⚠️ **CONFIGURATION GAP**

### Missing: Temperature Strategy

**Model Configurations:**

```python
# UserIntentAgent
ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.4    # Moderate creativity for understanding intent
)

# SQLAgent
ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    temperature=0.2    # Low temp for deterministic SQL generation
)

# HighLevelAgent - Flash
ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.5    # Balanced for planning
)

# HighLevelAgent - Pro
ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    temperature=0.5    # Balanced for evaluation/synthesis
)
```

**Rationale:**
- **0.2:** SQL generation needs determinism
- **0.4:** Intent clarification needs some flexibility
- **0.5:** Planning/synthesis needs creative reasoning

---

## 10. SESSION & CHAT HISTORY ⚠️ **FUNCTIONAL GAP**

### Missing: How Session Context Works

**Session Flow (FastAPI only):**

1. **Client sends `session_id`** (UUID) with query
2. **System fetches history:** `db_manager.get_chat_history_by_session_id(session_id)`
3. **History formatted:**
   ```python
   [
       {"role": "user", "content": "previous question"},
       {"role": "assistant", "content": "previous summary"},
       ...
   ]
   ```
4. **History passed to UserIntentAgent** as `external_chat_history`
5. **UserIntentAgent uses context** to avoid re-asking same questions

**History Format in DB:**
- **User records:** `{"question": "..."}`
- **Bombe records:** Full response JSON with `simple_summary`, etc.

**Benefits:**
- Multi-turn conversations
- Context-aware clarification
- Avoids repetitive questions
- Better understanding of user intent

---

## 11. ITERATION & LOOP CONTROL ⚠️ **BEHAVIOR GAP**

### Missing: Workflow Termination Logic

**When Workflow Stops:**

1. **Max Iterations Hit** → `MAX_ITERATIONS` (default 4) reached
2. **Sufficient Data** → Evaluation returns "SUFFICIENT"
3. **Error Occurs** → Planning or critical failure
4. **Explicit Answer** → Evaluation generates complete response

**Iteration Counter:**
- Starts at 0
- Incremented in `_planning_node`
- Checked in `_evaluation_node` and `_should_continue_or_end`

**Edge Cases:**
```python
# Clarification detected in generated answer
if "clarification" in answer:
    state['needs_more_data'] = True
    state['return_answer'] = False
    return "continue"  # Loop back to planning
```

**Force Final Answer:**
- At max iterations, `_generate_final_answer()` called
- Synthesizes answer from whatever data is available
- Sets `evaluation_result = "Maximum iterations reached"`

---

## 12. DEBUG MODE DETAILS ⚠️ **OPERATIONAL GAP**

### Missing: What DEBUG Actually Shows

**When `DEBUG=true`:**

```python
# Prints for Planning Stage
- Full planning prompt (messages truncated to 2000 chars)
- Cache usage indicator
- Raw LLM response
- Parsed plan text
- Parsed SQL queries (numbered)

# Prints for Query Execution
- Full SQL query
- Current context length
- SQL validation result
- Execution success/failure
- Row count and columns
- Sample data (first 3 rows)
- Formatted results preview (500 chars)

# Prints for Evaluation
- Total query results count
- Cumulative context length
- Context preview (500 chars)
- Evaluation prompt (truncated)
- Raw evaluation response
- Sufficiency determination
- Clarification detection logic

# Prints for Workflow Control
- Current iteration
- Needs more data flag
- Has final answer flag
- Workflow decision (continue/end)
```

**Performance Impact:**
- Significant console output (can be 1000+ lines per query)
- Useful for debugging SQL generation issues
- Shows exact prompts sent to LLM

---

## 13. POSTCODE NORMALIZATION ⚠️ **DATA HANDLING GAP**

### Missing: Postcode Search Requirements

**Critical for Postcode Queries:**

- Database stores: `normalised_pcd` (lowercase, no spaces)
- User input: "E11 3QA" or "e11 3qa" or "E113QA"
- **SQL must use:** `normalised_pcd = 'e113qa'`

**SQL Generation Rule:**
```sql
-- CORRECT
WHERE normalised_pcd = 'e113qa'

-- WRONG (won't match)
WHERE pcd = 'E11 3QA'
```

**Schema Reminder in Prompts:**
- "Postcode searches should use normalised_pcd (lowercase, no spaces)"
- System must convert user input to normalized form

---

## 14. RESPONSE FIELD SEMANTICS ⚠️ **CONTRACT GAP**

### Missing: What Each Response Field Actually Means

**Field Definitions:**

- **`simple_summary`**
  - 2-3 sentence overview
  - Should NOT mention SQL queries or methods
  - Should NOT quote percentages above 100%
  - User-facing, plain language

- **`key_insights`**
  - List of bullet points (3-5 typically)
  - Focus on "what the data shows"
  - Patterns, trends, notable findings
  - Include limitations/caveats if applicable

- **`detailed_explanation`**
  - Comprehensive analysis
  - Expands on key insights
  - Should NOT mention SQL queries or methods
  - Should NOT quote percentages above 100%

- **`context_relevance`**
  - Float 0.0 to 1.0
  - Fraction of analysis contextually relevant to question
  - Lower if query was too broad or data insufficient
  - Default: 0.8 for successful queries

- **`return_answer`**
  - `True` = Valid answer provided
  - `False` = Error, clarification needed, or incomplete

- **`bypass_user_intent`**
  - Indicates which mode was used
  - Helps caller understand processing path

---

## 15. EXAMPLE SCRIPTS PURPOSES ⚠️ **USAGE GAP**

### Missing: What Each Example Script Does

#### `test_script.py`
- **Purpose:** Automated testing with sample queries
- **Queries:** 5 diverse test cases (geographic, behavioral, comparative)
- **Output:** Condensed results with relevance scores
- **Usage:** `python test_script.py` or `python test_script.py "custom query"`

#### `example_with_tracing.py`
- **Purpose:** Demonstrate LangSmith tracing setup
- **Features:** Environment configuration, trace viewing guide
- **Sample Queries:** 3 examples (simple, comparative, behavioral)
- **Usage:** Shows how to enable and use tracing

#### `example_direct_mode.py`
- **Purpose:** Performance comparison between modes
- **Features:** Timing measurements, mode switching, recommendations
- **Output:** Speed comparison statistics
- **Usage:** Demonstrates when to use each mode

#### `main_test.py`
- **Purpose:** CLI/development testing (different from main.py FastAPI version)
- **Features:** Interactive or single-query CLI
- **Note:** Older version without session support

---

## 16. LIMIT CLAUSES ⚠️ **QUERY BEHAVIOR GAP**

### Missing: Result Limiting Strategy

**Default Limits:**
- **Planning prompts:** Suggest "20 rows typically" or "30 rows"
- **Formatting:** Shows first 10 rows max
- **Context building:** Uses first 500 chars of formatted results

**No Hard Limit Enforcement:**
- LLM decides LIMIT value based on query type
- National queries: often LIMIT 20
- Regional/LA queries: often LIMIT 30
- Postcode queries: typically no limit (returns all matches for that postcode)

---

## 17. FALLBACK MECHANISMS ⚠️ **RESILIENCE GAP**

### Missing: System Fallback Behaviors

**Context Caching Failure:**
```python
if self.cached_model is None:
    # Fall back to LangChain
    response = self.llm.invoke(prompt.format_messages())
```

**SQL Query Failure:**
- Failed query logged
- Error stored in query results
- Workflow continues with remaining queries
- Evaluation works with partial data

**Clarification Timeout:**
- `max_interactions=5` in UserIntentAgent
- After 5 attempts, proceeds with last query version
- Returns `status="clarified"` with whatever was gathered

**Database Connection Loss:**
- `test_connection()` checks on startup
- Each query uses connection context manager
- Automatic reconnection on next query attempt

---

## 18. DEPENDENCIES & VERSIONS ⚠️ **TECHNICAL GAP**

### Missing: Specific Package Versions

**From requirements.txt:**
```
fastapi
uvicorn
gunicorn
python-dotenv
langchain-google-genai    # Includes ChatGoogleGenerativeAI
langchain
langgraph                 # StateGraph, workflow engine
langsmith                 # Tracing
google-generativeai       # Context caching, direct API
psycopg2-binary          # PostgreSQL driver
pydantic                 # Data validation
requests
```

**No pinned versions** = potential compatibility issues

**Key Dependencies:**
- **LangGraph:** Provides StateGraph for workflow orchestration
- **LangChain Google GenAI:** Gemini model integration
- **psycopg2-binary:** PostgreSQL connectivity (not psycopg2)

---

## 19. CURSOR RULES ⚠️ **DEVELOPMENT CONSTRAINT**

### Missing: Development Guidelines

**From `.cursorrules`:**
```
do not try to run the code or execute terminal commands,
instead ask the user to do it for you
```

**Implication:**
- This codebase expects humans to run commands
- Automated CI/CD may need special handling
- Not designed for autonomous execution by AI tools

---

## 20. LOGGING LEVELS ⚠️ **OBSERVABILITY GAP**

### Missing: What Gets Logged

**Default Level: INFO**

**Logged Events:**
- Agent initialization steps
- Database connection tests
- Query reception
- Clarification steps
- Planning iteration starts
- SQL query execution (first 200 chars)
- Query results counts
- Evaluation decisions
- Final answer generation
- Errors (with ERROR level)

**DEBUG Level (via DEBUG=true):**
- Enables verbose console printing (not just logging)
- Shows prompts, responses, SQL, results
- Much more detailed than standard logging

**No LOG_LEVEL Environment Variable:**
- Logging level is hardcoded to INFO
- DEBUG env var controls separate debug printing

---

## Summary: Top 10 Most Critical Gaps

1. **FastAPI endpoint contracts** and authentication
2. **Two different main.py implementations** (CLI vs API)
3. **Session/chat history mechanism** (FastAPI only)
4. **Three behavioral model types** and their differences
5. **Context caching implementation details** (two-level caching)
6. **SQL security validation** and constraints
7. **Deployment configuration** (Gunicorn, workers, timeouts)
8. **Postcode normalization** requirements
9. **Error handling and graceful degradation** patterns
10. **Workflow termination logic** and iteration control

---

## Recommended Documentation Additions

### High Priority
1. API Reference (OpenAPI/Swagger spec)
2. Database schema diagram
3. Behavioral model types guide
4. Session management tutorial
5. Deployment guide (Docker, Cloud Run)

### Medium Priority
6. Error handling guide
7. SQL generation rules reference
8. Caching strategy deep-dive
9. Debug mode guide
10. Testing strategy documentation

### Low Priority
11. Example query patterns
12. Performance tuning guide
13. Monitoring & observability setup
14. Contribution guidelines
15. Versioning and changelog

---

**End of Analysis**
