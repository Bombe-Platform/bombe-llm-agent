# Bombe 2.0 🤖

A sophisticated LangGraph-powered agent system that analyzes persona and geographic data using natural language queries. Built with LangChain and Google Gemini 2.5 Flash.

## 🌟 Features

- **Natural Language Querying**: Ask complex questions about persona distributions and geographic data in plain English
- **Multi-Query Processing**: Automatically breaks down complex questions into sub-queries for comprehensive analysis
- **Geographic Analysis**: Analyze data at multiple geographic levels (national, regional, local authority, ward, postcode)
- **Persona Insights**: Deep dive into demographic and commercial persona distributions
- **Behavioral Models**: Explore MRP (behavioral prediction) models for different personas
- **LangGraph Workflow**: Orchestrated query processing with iterative refinement
- **Dual Processing Modes**: Standard mode with user intent clarification or direct mode for faster processing
- **Structured Output**: Consistent, well-formatted responses with key insights and explanations
- **Comprehensive Tracing**: LangSmith integration for monitoring, debugging, and performance analysis

## 🏗️ Architecture

The system consists of several modular components:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  User Intent    │────│   High Level    │────│   SQL Agent     │────│  SQL Executor   │
│     Agent       │    │     Agent       │    │                 │    │                 │
│ (Query Refine)  │    │  (LangGraph)    │    │ (NL→SQL Conv.)  │    │  (Query Exec.)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                                 │                       │                       │
                                 │                       │                       │
                                 └───────────────────────┼───────────────────────┘
                                                         │
                                            ┌─────────────────┐
                                            │   DB Manager    │
                                            │  (PostgreSQL)   │
                                            └─────────────────┘
```

### Components

1. **User Intent Agent** (`user_intent_agent.py`): Clarifies and refines user queries through interaction.
2. **DB Manager** (`db_manager.py`): Handles all database I/O operations
3. **SQL Executor** (`sql_executor.py`): Executes SQL queries and manages results
4. **SQL Agent** (`sql_agent.py`): Converts natural language to SQL queries
5. **High Level Agent** (`high_level_agent.py`): Orchestrates the complete workflow using LangGraph
6. **Main Application** (`main.py`): Entry point and user interface

### Workflow

The query processing workflow is as follows:

1.  The **Main Application** (`main.py`) receives the initial user query.
2.  The **User Intent Agent** (`user_intent_agent.py`) interacts with the user (if necessary) to clarify and refine the query. It produces a refined query and a summary of the clarification interaction (intent context).
3.  The refined query and intent context are passed to the **High Level Agent** (`high_level_agent.py`).
4.  The High Level Agent, using its LangGraph-defined workflow, manages the overall analysis:
    *   It first analyzes the refined query. If this is the first pass, it uses the intent context. If it's a subsequent iteration to gather more data, it uses the context of previously gathered results.
    *   It breaks down the query into specific sub-queries.
    *   Each sub-query is sent to the **SQL Agent** (`sql_agent.py`).
    *   The SQL Agent converts the natural language sub-query into an SQL query using the database schema and glossary. It then passes the SQL query to the **SQL Executor** (`sql_executor.py`).
    *   The SQL Executor runs the query against the PostgreSQL database (managed by **DB Manager** - `db_manager.py`) and returns the raw results.
    *   The SQL Agent formats these results and returns them to the High Level Agent.
    *   The High Level Agent collects results from all sub-queries.
    *   It then decides if enough information has been gathered to answer the original refined query or if another iteration of generating and executing sub-queries is needed (up to a maximum number of iterations).
5.  Once sufficient data is gathered or the iteration limit is reached, the High Level Agent synthesizes all results into a comprehensive, structured answer.
6.  This final structured answer is returned to the Main Application, which then formats and displays it to the user.

## 📊 Data Schema

The system works with persona and geographic analytics data including:

- **Personas**: Demographic (Persona 1-9) and Commercial (Bombe 1-7) categories
- **Geographic Levels**: National, Regional, Local Authority, Ward, Postcode
- **Behavioral Models**: MRP data for persona-specific predictions
- **Geographic Mapping**: UK geography relationships and hierarchies

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL database with persona analytics data
- Google Gemini API key

### Installation

1. **Set up the project**
   Ensure you have the repository code and navigate to the project directory.
   ```bash
   cd persona-analytics-agent
   ```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**
```bash
cp env_example.txt .env
# Edit .env with your actual values
```

Required environment variables:
- `GOOGLE_API_KEY`: Your Google Gemini API key
- `DATABASE_URL`: PostgreSQL connection string

Optional environment variables:
- `BYPASS_USER_INTENT_AGENT`: Set to `true` to skip user intent clarification and send queries directly to analysis (default: `false`)
- `DEBUG`: Set to `true` to enable verbose debug logging (default: `false`)
- `MAX_ITERATIONS`: Maximum analysis iterations for complex queries (default: `4`)

### Usage

#### Interactive Mode
```bash
python main.py
```

#### Single Query Mode
```bash
python main.py "What are the top personas in London?"
```

#### Test the System
```bash
python test_script.py
```

## 💡 Example Queries

Here are some example queries you can try:

### Geographic Analysis
- "What are the top 5 personas by percentage in London?"
- "Show me the distribution of Bombe 2 across different regions"
- "Which local authorities have the highest concentration of Persona 5?"

### Comparative Analysis
- "Compare commercial personas between Manchester and Birmingham"
- "How does Persona 3 distribution vary across the North West region?"

### Behavioral Models
- "What behavioral models are associated with Camden Market?"
- "Which personas are most likely to visit Borough Market?"

### Postcode Analysis
- "What personas are prevalent in the E11 3QA postcode area?"
- "Show me persona distribution for postcodes starting with M1"

## 🔧 Configuration

### Database Connection

The system expects a PostgreSQL database with the persona analytics schema. Set your connection string in the `.env` file:

```
DATABASE_URL=postgresql://username:password@host:port/database_name
```

### API Configuration

Get your Google Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey) and add it to your `.env` file:

```
GOOGLE_API_KEY=your_api_key_here
```

### LangSmith Tracing (Optional)

The system includes comprehensive tracing support via LangSmith for monitoring and debugging:

```bash
# Enable tracing
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=your_langsmith_api_key

# Optional: Set custom project/session names
export LANGSMITH_PROJECT=bombe-llm-analysis
export LANGSMITH_SESSION=production-queries
```

For detailed tracing setup and configuration, see [`tracing_setup.md`](tracing_setup.md).

### Query Processing Modes

The system supports two query processing modes:

#### **Standard Mode (Default)**
```bash
# User intent clarification enabled (default)
export BYPASS_USER_INTENT_AGENT=false  # or don't set it
```
- Queries go through the UserIntentAgent for clarification and refinement
- Best for interactive use where ambiguous queries need clarification
- Handles follow-up questions and conversational context
- May ask users for more specific information

#### **Direct Mode**
```bash
# Skip user intent clarification
export BYPASS_USER_INTENT_AGENT=true
```
- Queries go directly to the HighLevelAgent for analysis
- Best for:
  - Well-formed, specific queries that don't need clarification
  - API/automated usage where human interaction isn't possible
  - Faster processing when you know your query is clear
  - Batch processing of multiple queries

**Note**: In direct mode, ambiguous queries may produce less optimal results since there's no clarification step.

## 📚 API Reference

### PersonaAnalyticsAgent

Main application class that coordinates all components.

#### Methods

- `query(user_question: str) -> dict`: Process a natural language query
- `test_connection() -> bool`: Test database connectivity
- `print_formatted_response(response: dict)`: Display formatted results

### Response Format

All queries return a structured JSON response.

#### Successful Response

A successful query processing will return a dictionary conforming to the following structure:

```python
{
    "simple_summary": "A simple summary of the analysis (e.g., 'Brief overview of findings')",
    "key_insights": ["List of key insights from the analysis (e.g., 'Insight 1', 'Insight 2', ...)"],
    "detailed_explanation": "The detailed explanation of the insights (e.g., 'Comprehensive analysis')",
    "context_relevance": 0.85,  # The fraction (out of 1.0) of analysis that are contextually relevant to the question.
    "return_answer": True,  # Indicates if the agent returned an answer. Will be true for successful analysis.
    "bypass_user_intent": False  # Indicates whether user intent clarification was bypassed (True for direct mode)
}
```

#### Error Response

If an error occurs during query processing (e.g., inability to clarify the query, issues executing SQL, or failures in the analysis workflow), the response will still be a JSON object but with `return_answer` set to `False`. The other fields will contain details about the error:

```python
{
    "simple_summary": "Description of the error (e.g., 'Unable to complete analysis due to error: ...' or 'Could not understand the query after clarification.')",
    "key_insights": ["Usually indicates failure (e.g., ['Query processing failed', 'Query unclear'])"],
    "detailed_explanation": "More details about the error encountered or the context of a clarification failure.",
    "context_relevance": 0.0,
    "return_answer": False,
    "bypass_user_intent": False  # Indicates processing mode when error occurred
}
```

## 🧪 Testing

Run the test suite to verify everything is working:

```bash
# Run all sample queries
python test_script.py

# Test a specific query
python test_script.py "Your specific question here"
```

## 🛠️ Development

### Adding New Features

1. **Database Schema Changes**: Update the schema definitions in `sql_agent.py`
2. **New Query Types**: Extend the prompt templates in `sql_agent.py` and `high_level_agent.py`
3. **Output Formats**: Modify the response parsing in `high_level_agent.py`

### Logging

The system uses Python's logging module. Set the log level in your environment:

```
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

## 🔍 Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Verify your `DATABASE_URL` is correct
   - Ensure PostgreSQL is running and accessible
   - Check network connectivity

2. **API Key Error**
   - Verify your `GOOGLE_API_KEY` is valid
   - Check API quotas and billing
   - Ensure the key has Gemini API access

3. **Query Processing Errors**
   - Check the logs for detailed error messages
   - Verify your database has the required tables/views
   - Try simpler queries first

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
export LOG_LEVEL=DEBUG
python main.py
```

## 📈 Performance

The system is designed to handle complex analytical queries efficiently:

- **Query Optimization**: Automatic SQL query optimization
- **Result Caching**: Context preservation across sub-queries
- **Error Handling**: Graceful degradation on partial failures
- **Rate Limiting**: Respects API rate limits

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- Built with [LangChain](https://langchain.com/) and [LangGraph](https://langchain-ai.github.io/langgraph/)
- Powered by [Google Gemini 2.5 Flash](https://deepmind.google/technologies/gemini/)
- Database connectivity via [psycopg2](https://pypi.org/project/psycopg2/)

## 📞 Support

For questions or support, please:
1. Check the troubleshooting section above
2. Review the example queries
3. Contact the development team

Happy analyzing! 🎉 