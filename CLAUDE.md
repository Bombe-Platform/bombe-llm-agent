# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bombe 2.0 is a LangGraph-powered agent system for analyzing persona and geographic data using natural language. Built with LangChain and Google Gemini 2.5 Flash/Pro, it converts natural language questions into SQL queries and synthesizes comprehensive answers.

## Core Architecture

### Agent Workflow (LangGraph-based)

The system uses a **3-stage iterative LangGraph workflow** in `high_level_agent.py`:

1. **Planning Stage** (`_planning_node`)
   - Breaks down user query into SQL sub-queries
   - Uses Google Gemini context caching for schema/glossary (2-hour TTL)
   - Generates 1-2 SQL queries per iteration
   - First iteration uses `intent_context` from UserIntentAgent
   - Subsequent iterations use previous query results

2. **Query Execution Stage** (`_query_execution_node`)
   - Executes SQL queries directly (no LLM SQL generation here)
   - Validates queries before execution
   - Formats results for next stage
   - Accumulates results across iterations

3. **Evaluation Stage** (`_evaluation_node`)
   - Determines if sufficient data has been gathered
   - Either generates final answer or signals to continue
   - Maximum iterations controlled by `MAX_ITERATIONS` env var (default: 4)
   - Checks for clarification requests vs. actual answers

**Conditional Edge Logic**: After evaluation, workflow either loops back to planning (if more data needed) or ends (if sufficient).

### Component Roles

- **UserIntentAgent** (`user_intent_agent.py`): Clarifies ambiguous queries through conversation
  - Can be bypassed with `BYPASS_USER_INTENT_AGENT=true` for direct mode
  - Supports chat history for context-aware clarification
  - Includes prompt/response caching for performance

- **HighLevelAgent** (`high_level_agent.py`): Orchestrates the LangGraph workflow
  - Uses **context caching** (Google Gemini) for schema/glossary to reduce costs
  - Parses planning output to extract SQL queries using `_extract_all_sql_queries()`
  - Manages cumulative context across iterations

- **SQLAgent** (`sql_agent.py`): Converts NL to SQL (legacy - now mostly used for schema access)
  - Planning stage now generates SQL directly using cached context

- **SQLExecutor** (`sql_executor.py`): Validates and executes SQL queries
  - Only allows SELECT statements
  - Checks for dangerous keywords (DROP, DELETE, etc.)

- **DatabaseManager** (`db_manager.py`): PostgreSQL connection management via psycopg2

### Data Schema

Key tables/views:
- `personas` - persona definitions (Persona 1-9 demographic, Bombe 1-7 commercial)
- `normal_value_*_view` - persona percentages by geography (UK, regions, local authority, wards, postcodes)
- `mrp_data_persona_models` - behavioral prediction models
- `uk_geographies_basic_with_names_view` - geographic mapping

## Development Commands

### Running the Application

```bash
# Interactive mode
python main.py

# Single query mode
python main.py "What are the top personas in London?"

# Run tests
python test_script.py

# Start FastAPI server (production)
python main.py  # Starts on port 8002 by default
```

### Testing

```bash
# Test with sample queries
python test_script.py

# Test specific query
python test_script.py "Your specific question here"

# Run main_test.py for comprehensive testing
python main_test.py
```

### Environment Variables

Required:
- `GOOGLE_API_KEY` - Google Gemini API key
- `DATABASE_URL` - PostgreSQL connection string

Optional:
- `BYPASS_USER_INTENT_AGENT` - Skip clarification (`true`/`false`, default: `false`)
- `DEBUG` - Enable verbose logging (`true`/`false`)
- `MAX_ITERATIONS` - Max workflow iterations (default: `4`)
- `LANGSMITH_TRACING` - Enable LangSmith tracing (`true`/`false`)
- `LANGSMITH_API_KEY` - LangSmith API key
- `LANGSMITH_PROJECT` - Project name for tracing
- `PROD_LLM_API_KEY` - API key for FastAPI security

## Key Implementation Details

### SQL Query Parsing

The `_extract_all_sql_queries()` method in `high_level_agent.py` parses SQL queries from LLM output:
- Finds all SELECT statements between semicolons
- Cleans SQL comments and extra whitespace
- Robust to markdown formatting variations
- Returns up to 3 queries per planning iteration

### Context Caching Strategy

The HighLevelAgent uses Google Gemini context caching (`_setup_context_caching()`):
- Caches schema + glossary for 2 hours
- Falls back to LangChain if caching fails
- Applies to both initial and follow-up planning
- Significantly reduces API costs for repeated queries

### Processing Modes

**Standard Mode** (default):
- Queries go through UserIntentAgent for clarification
- Best for interactive use with ambiguous queries
- Maintains conversational context

**Direct Mode** (`BYPASS_USER_INTENT_AGENT=true`):
- Queries bypass clarification and go straight to HighLevelAgent
- Best for well-formed queries, API usage, or batch processing
- Faster but may produce suboptimal results for ambiguous queries

### Debug Mode

Set `DEBUG=true` to enable comprehensive logging:
- Prints planning prompts and responses
- Shows SQL validation and execution details
- Displays context lengths and cache usage
- Tracks workflow decisions and iterations

## Common Pitfalls

1. **SQL Query Format**: LLM must generate clean SQL without markdown code blocks or comments. The parsing logic expects queries to start with SELECT and end with semicolon.

2. **Context Caching**: If context caching fails during initialization, the system automatically falls back to standard LangChain approach. Check logs for "Context caching successfully initialized" vs. "Falling back to non-cached mode".

3. **Iteration Limits**: The workflow will force-generate a final answer at MAX_ITERATIONS even if data is incomplete. Increase MAX_ITERATIONS for complex multi-step queries.

4. **Clarification Detection**: The evaluation stage checks for clarification keywords in generated answers to avoid returning non-answers. See `_evaluation_node()` around line 650.

## Response Format

All queries return structured JSON:

```python
{
    "simple_summary": str,           # 2-3 sentence overview
    "key_insights": List[str],       # Bulleted insights
    "detailed_explanation": str,     # Comprehensive analysis
    "context_relevance": float,      # 0.0 to 1.0
    "return_answer": bool,           # True if successful, False if error/clarification
    "bypass_user_intent": bool       # Indicates processing mode
}
```

For clarification requests (standard mode only):
```python
{
    "requires_clarification": bool,
    "clarification_message": str,
    "suggested_query": str | None
}
```

## Model Usage

- `gemini-2.5-flash`: Default for planning, user intent (fast, cheap)
- `gemini-2.5-pro`: Used for evaluation and final answer synthesis (higher quality)
- Both defined in `models.py`
