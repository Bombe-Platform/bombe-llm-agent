# LangSmith Tracing Setup for Bombe LLM 2.0

## Overview

The Bombe LLM 2.0 project now includes comprehensive tracing support using LangSmith to provide visibility into the LangGraph workflow execution, SQL query generation, and multi-stage analysis process.

## Prerequisites

1. **LangSmith Account**: Sign up at [https://smith.langchain.com/](https://smith.langchain.com/)
2. **API Key**: Get your LangSmith API key from the LangSmith dashboard

## Installation

The required dependencies are already included in the project. The tracing uses:
- `langsmith` - Core tracing library
- `@traceable` decorators for custom functions
- Automatic tracing for LangChain components

## Environment Setup

Set the following environment variables to enable tracing:

### Required Variables
```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=your_langsmith_api_key_here
```

### Optional Variables
```bash
# Set a custom project name (defaults to "default")
export LANGSMITH_PROJECT=bombe-llm-analysis

# Set a session name for grouping related traces
export LANGSMITH_SESSION=production-queries

# Set custom tags for filtering traces
export LANGSMITH_TAGS=persona-analysis,sql-generation
```

## What Gets Traced

The LangGraph workflow is comprehensively instrumented to trace:

### 1. High-Level Workflow
- **Process Query** - Main entry point and complete workflow execution
- **Planning Stage** - Query breakdown and SQL planning
- **Query Execution Stage** - SQL generation and execution
- **Evaluation Stage** - Data sufficiency assessment and response generation

### 2. LLM Interactions
- **Cached Initial Planning** - Initial query planning with context caching
- **Cached Followup Planning** - Iterative planning for additional data
- **Generate Final Answer** - Final response synthesis

### 3. Data Processing
- **Parse Planning Output** - Extraction of SQL queries from LLM responses
- **Build Cumulative Context** - Context building across iterations
- **SQL Query Execution** - Individual SQL query execution (via SQLAgent)

### 4. Automatic LangChain Tracing
- All `ChatGoogleGenerativeAI` model calls
- Prompt template formatting and execution
- Message processing and state transitions

## Trace Structure

A typical trace for a user query will show:

```
Process Query
├── Planning Stage (Iteration 1)
│   ├── Cached Initial Planning
│   └── Parse Planning Output
├── Query Execution Stage
│   ├── SQL Query 1 Execution
│   ├── SQL Query 2 Execution
│   └── Build Cumulative Context
├── Evaluation Stage
│   └── LLM Evaluation Call
├── Planning Stage (Iteration 2, if needed)
│   ├── Cached Followup Planning
│   └── Parse Planning Output
├── Query Execution Stage (Iteration 2)
│   └── Additional SQL Queries
└── Generate Final Answer
    └── Final LLM Synthesis Call
```

## Viewing Traces

1. **LangSmith Dashboard**: Visit [https://smith.langchain.com/](https://smith.langchain.com/)
2. **Select Project**: Choose your project (default: "default" or custom project name)
3. **Browse Traces**: View trace timeline, performance metrics, and detailed execution logs

### Key Metrics to Monitor
- **Total Execution Time**: End-to-end query processing duration
- **LLM Token Usage**: Track token consumption across planning, evaluation, and synthesis
- **SQL Query Success Rate**: Monitor SQL generation and execution success
- **Iteration Count**: Track how many planning/execution cycles are needed
- **Error Rates**: Identify common failure points in the workflow

## Debug Integration

The tracing integrates with the existing debug system:

```bash
# Enable both debug logging and tracing
export DEBUG=true
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=your_api_key

# Optional: Enable direct mode for faster processing
export BYPASS_USER_INTENT_AGENT=true
```

When both are enabled:
- Debug logs provide detailed console output
- LangSmith traces provide structured visualization and metrics
- Combined view offers comprehensive observability

## Example Usage

```python
from high_level_agent import HighLevelAgent
from sql_agent import SQLAgent
from db_manager import DatabaseManager

# Initialize components (tracing is automatically configured via environment variables)
db_manager = DatabaseManager(connection_string)
sql_agent = SQLAgent(db_manager, api_key)
agent = HighLevelAgent(sql_agent, api_key, db_manager)

# Process query - this will be fully traced if LANGSMITH_TRACING=true
result = agent.process_query(
    "What are the top personas in London?",
    intent_context="User is asking about demographic personas in London boroughs"
)

# View the trace in LangSmith dashboard at https://smith.langchain.com/
```

## Production Considerations

### Performance Impact
- Tracing adds minimal latency (~5-15ms per traced operation)
- Network calls to LangSmith are asynchronous and don't block execution
- Consider sampling for very high-volume production workloads

### Data Privacy
- Traces contain query inputs, SQL statements, and analysis results
- Ensure LangSmith project access is restricted appropriately
- Consider data retention policies for sensitive information

### Cost Management
- LangSmith pricing is based on trace volume and retention
- Use project-based organization to manage costs
- Set up alerts for unusual trace volume spikes

## Troubleshooting

### Tracing Not Working
1. **Check Environment Variables**: Ensure `LANGSMITH_TRACING=true` and valid API key
2. **Network Connectivity**: Verify access to LangSmith API endpoints
3. **Check Logs**: Look for "LangSmith tracing is enabled" message in application logs

### Missing Traces
1. **Project Configuration**: Verify correct project name in LangSmith dashboard
2. **API Key Permissions**: Ensure API key has write access to the project
3. **Async Flush**: Traces may take 30-60 seconds to appear in dashboard

### Performance Issues
1. **Disable Tracing**: Set `LANGSMITH_TRACING=false` to test performance impact
2. **Sampling**: Consider implementing trace sampling for high-volume scenarios
3. **Async Configuration**: Ensure trace submission is asynchronous (default behavior)

## Integration with CI/CD

For automated testing and monitoring:

```bash
# In your CI/CD pipeline
export LANGSMITH_TRACING=true
export LANGSMITH_PROJECT=bombe-llm-testing
export LANGSMITH_SESSION="ci-run-${BUILD_NUMBER}"

# Run tests with tracing enabled
python -m pytest tests/ --trace-enabled

# Analyze traces programmatically
python scripts/analyze_test_traces.py
```

## Query Processing Modes and Tracing

The system supports two query processing modes that affect what gets traced:

### Standard Mode (Default)
```bash
export BYPASS_USER_INTENT_AGENT=false  # or don't set it
```
**Trace Structure:**
```
Process Query
├── User Intent Clarification
│   ├── Query Analysis
│   └── Clarification Decision
├── Planning Stage
├── Query Execution Stage
└── Evaluation Stage
```

### Direct Mode (Bypass)
```bash
export BYPASS_USER_INTENT_AGENT=true
```
**Trace Structure:**
```
Process Query
├── Planning Stage (directly)
├── Query Execution Stage
└── Evaluation Stage
```

**Benefits of Direct Mode Tracing:**
- Faster execution (fewer traced operations)
- Cleaner traces for well-formed queries
- Better for automated/API usage monitoring
- Easier to identify bottlenecks in core analysis

**When to Use Each Mode:**
- **Standard Mode**: Interactive use, ambiguous queries, need clarification visibility
- **Direct Mode**: API usage, batch processing, well-formed queries, performance optimization

This setup provides comprehensive observability into the Bombe LLM 2.0 analysis workflow, enabling better debugging, performance optimization, and quality monitoring. 