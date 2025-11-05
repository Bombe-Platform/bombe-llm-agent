from typing import List, Dict, Any, Optional, TypedDict
import logging
import os
import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from sql_agent import SQLAgent
from pydantic import BaseModel, Field
from pTemplates import GLOSSARY
from db_manager import DatabaseManager
from models import gemini2_5_pro, gemini2_5_flash
import json
import google.generativeai as genai
from google.generativeai import caching

# LangSmith tracing imports
from langsmith import traceable
from langsmith.wrappers import wrap_openai

logger = logging.getLogger(__name__)

"""
LangSmith Tracing Configuration:

To enable tracing, set the following environment variables:
- LANGSMITH_TRACING=true
- LANGSMITH_API_KEY=<your-langsmith-api-key>

Optional configuration:
- LANGSMITH_PROJECT=<project-name> (defaults to "default")
- LANGSMITH_SESSION=<session-name> (for grouping related traces)

The HighLevelAgent workflow is instrumented with @traceable decorators to provide
comprehensive visibility into:
- Overall query processing workflow
- Individual planning, execution, and evaluation stages
- LLM calls (both LangChain and direct Google AI calls)
- SQL query parsing and execution
- Final answer generation

Traces will automatically capture inputs, outputs, timing, and any errors
that occur during the workflow execution.
"""


def is_debug_enabled() -> bool:
    """Check if DEBUG environment variable is set to 'true'."""
    return os.getenv('DEBUG', '').lower() == 'true'


def is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled."""
    return os.getenv('LANGSMITH_TRACING', '').lower() == 'true'


def get_max_iterations() -> int:
    """Get the maximum number of iterations from environment variable, default to 4."""
    try:
        return int(os.getenv('MAX_ITERATIONS', '4'))
    except ValueError:
        return 4

class QueryResult(TypedDict):
    """Individual query result with metadata."""
    query: str
    sql_query: str
    success: bool
    data: List[Dict[str, Any]]
    formatted_results: str
    error: Optional[str]
    iteration: int


class QueryState(TypedDict):
    """State object for the LangGraph workflow."""
    original_query: str
    intent_context: Optional[str]
    
    # Planning stage outputs
    current_plan: Optional[str]
    planned_queries: List[str]
    
    # Query execution outputs  
    all_query_results: List[QueryResult]
    current_iteration: int
    
    # Evaluation outputs
    evaluation_result: Optional[str]
    needs_more_data: bool
    
    # Final outputs
    final_answer: Optional[str]
    error_message: Optional[str]


class OutputSchema(BaseModel):
    """Output Schema for the API."""
    simple_summary: str = Field(description="A simple summary of the analysis")
    key_insights: List[str] = Field(description="The key insights from the analysis")
    detailed_explanation: str = Field(description="The detailed explanation of the insights")
    context_relevance: float = Field(description="The fraction (out of 1.0) of analysis that are contextually relevant to the question.")
    return_answer: bool = Field(description="If the agent returned an answer or asked for more clarification")


class HighLevelAgent:
    """
    High-level agent that orchestrates query breakdown and result synthesis using LangGraph.
    """
    
    def __init__(self, sql_agent: SQLAgent, api_key: str, db_manager: DatabaseManager):
        """
        Initialize the high-level agent.
        
        Args:
            sql_agent: SQLAgent instance for executing queries
            api_key: Google Gemini API key
            db_manager: DatabaseManager instance
        """
        self.sql_agent = sql_agent
        self.api_key = api_key
        self.llm = ChatGoogleGenerativeAI(
            model=gemini2_5_flash,
            google_api_key=api_key,
            temperature=0.5
        )
        self.llm_large = ChatGoogleGenerativeAI(
            model=gemini2_5_pro,
            google_api_key=api_key,
            temperature=0.5
        )
        self.db_manager = db_manager
        self.table_schema = self.db_manager.get_personas_summary_string()
        self.schema_info = self._get_schema_info(self.table_schema)
        
        # Set up context caching for schema and glossary information
        self._setup_context_caching()
        
        # Log tracing status
        if is_tracing_enabled():
            logger.info("LangSmith tracing is enabled")
        else:
            logger.info("LangSmith tracing is disabled. Set LANGSMITH_TRACING=true to enable.")
        
        # Build the LangGraph workflow
        self.workflow = self._build_workflow()
    
    def _get_schema_info(self, table_schema: str) -> str:
        """
        Get database schema information for SQL query generation.
        """
        schema_info = f"""
        DATABASE SCHEMA INFORMATION:
        
        Available Tables and Views:
        
        1. personas - Contains persona definitions (id, code, name, label, description, type)
        
        2. normal_value_uk_view - National level persona percentages
           - persona: Persona name (Persona 1-9 or Bombe 1-7)
           - name: Persona label
           - avg_pct: Average percentage proportion
        
        3. normal_value_regions_with_labels_view - Regional breakdowns
           - persona, persona_label, region_code, region_name, avg_pct
        
        4. normal_value_la_with_labels_view - Local Authority breakdowns
           - persona, persona_label, local_authority_code, local_authority_name, avg_pct
        
        5. normal_value_wards_with_labels_view - Ward level breakdowns
           - persona, persona_label, ward_code, ward_name, avg_pct
        
        6. normal_value_pcon_with_labels_view - Constituency breakdowns
           - persona, persona_label, constituency_code, constituency_name, avg_pct
        
        7. normal_value_pcd_with_labels_view - Postcode breakdowns
           - persona, persona_label, output_area, normalised_pcd, pcd, avg_pct
        
        8. uk_geographies_basic_with_names_view - Geographic mapping
           - rgn, pcd, normalised_pcd, oa21, pcon, ward, local_authority, constituency, region, oslaua, osward
        
        9. mrp_data_persona_models - Behavioral prediction models by persona
           - model, dependent, persona_code, persona_label, pct
        
        10. mrp_data_non_persona_models - Non-persona behavioral models
            - model, predictor, pct
        
        PERSONA TYPES:
        - Demographic Category: Persona 1-9
        - Commercial Category: Bombe 1-7

        {table_schema}
        
        SQL GENERATION RULES:
        - Generate ONLY valid SELECT statements
        - Do NOT include SQL comments (--) - generate clean, direct SQL queries
        - Use proper JOIN syntax when combining tables
        - Always use ILIKE for text matching (case-insensitive)
        - Include appropriate LIMIT clauses (30 rows typically)
        - Use descriptive column aliases for better readability
        - Round numeric values to 2 decimal places where appropriate
        - Order results meaningfully (usually by percentage DESC or name ASC)
        - Use LEFT JOIN when joining tables
        - Postcode searches should use normalised_pcd (lowercase, no spaces)
        - Always include persona_label when available for better readability
        
        EXAMPLE QUERIES:

        For persona distribution in a region:
        SELECT persona, persona_label, region_name, ROUND(avg_pct::numeric, 2) as percentage
        FROM normal_value_regions_with_labels_view
        WHERE region_name ILIKE '%North West%'
        ORDER BY avg_pct DESC
        LIMIT 20;

        For postcode lookup:
        SELECT persona, persona_label, pcd as postcode, ROUND(avg_pct::numeric, 2) as percentage
        FROM normal_value_pcd_with_labels_view
        WHERE normalised_pcd = 'e113qa'
        ORDER BY avg_pct DESC;

        For behavioral models:
        SELECT persona_code, persona_label, dependent, pct
        FROM mrp_data_persona_models
        WHERE dependent ILIKE '%Camden Market%'
        ORDER BY pct DESC;
        """
        return schema_info
    
    def _setup_context_caching(self):
        """
        Set up Google Gemini context caching for static schema and glossary information.
        This caches the frequently used database schema and glossary to speed up inference.
        """
        try:
            # Configure the generative AI client
            genai.configure(api_key=self.api_key)
            
            # Create cached content with schema and glossary information
            # This content will be reused across multiple planning requests
            cached_content_text = f"""DATABASE SCHEMA AND PLANNING CONTEXT:

Available data types:
- Persona distributions by geography (national, regional, local authority, ward, postcode)
- Behavioral prediction models for personas
- Geographic mapping and relationships
- Persona characteristics and labels

Methods:
- If the question is about behaviour in a specific geography, then first check which personas are most relevant to the behaviour and then check geography data for those personas.

{self.schema_info}

GLOSSARY:
{GLOSSARY}

SQL GENERATION RULES:
- Generate ONLY valid SELECT statements
- Do NOT include SQL comments (--) - generate clean, direct SQL queries
- Use proper JOIN syntax when combining tables
- Always use ILIKE for text matching (case-insensitive)
- Include appropriate LIMIT clauses (30 rows typically)
- Use descriptive column aliases for better readability
- Round numeric values to 2 decimal places where appropriate
- Order results meaningfully (usually by percentage DESC or name ASC)
- Use LEFT JOIN when joining tables
- Postcode searches should use normalised_pcd (lowercase, no spaces)
- Always include persona_label when available for better readability

CRITICAL: Generate ONLY clean SQL queries, no markdown code blocks (```sql), no explanations, no comments. Each query should start directly with SELECT and end with semicolon."""
            
            # Create the cached content with a 2-hour TTL
            self.schema_cache = caching.CachedContent.create(
                model='models/gemini-2.5-pro',
                display_name='persona_schema_cache',
                system_instruction="You are an expert at strategic planning and SQL query generation for persona and geographic data analysis.",
                contents=[cached_content_text],
                ttl=datetime.timedelta(hours=2)
            )
            
            # Create cached model for schema-heavy operations
            self.cached_model = genai.GenerativeModel.from_cached_content(
                cached_content=self.schema_cache
            )
            
            logger.info("Context caching successfully initialized")
            
        except Exception as e:
            logger.warning(f"Context caching setup failed: {e}. Falling back to non-cached mode.")
            self.schema_cache = None
            self.cached_model = None
    
    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow with 3 main stages.
        """
        workflow = StateGraph(QueryState)
        
        # Add the 3 main nodes (evaluation now handles both evaluation and synthesis)
        workflow.add_node("planning", self._planning_node)
        workflow.add_node("query_execution", self._query_execution_node)
        workflow.add_node("evaluation", self._evaluation_node)
        
        # Set entry point and edges
        workflow.set_entry_point("planning")
        workflow.add_edge("planning", "query_execution")
        workflow.add_edge("query_execution", "evaluation")
        
        # Conditional edge based on evaluation - either continue or end
        workflow.add_conditional_edges(
            "evaluation",
            self._should_continue_or_end,
            {
                "continue": "planning",
                "end": END
            }
        )
        
        return workflow.compile()
    
    @traceable(run_type="chain", name="Planning Stage")
    def _planning_node(self, state: QueryState) -> QueryState:
        """
        Stage 1: Step-by-step planning and reasoning.
        """
        logger.info(f"Planning stage - Iteration {state.get('current_iteration', 0) + 1}")
        
        # Get context from previous iterations
        previous_context = self._build_cumulative_context(state.get('all_query_results', []))
        
        # Determine if this is initial planning or follow-up planning
        # Use cached responses for improved performance
        try:
            if state.get('current_iteration', 0) == 0:
                if is_debug_enabled():
                    prompt = self._get_initial_planning_prompt(state['original_query'], state.get('intent_context'))
                    formatted_messages = prompt.format_messages()
                    print(f"\n=== DEBUG: PLANNING PROMPT (Iteration {state.get('current_iteration', 0) + 1}) ===")
                    for i, message in enumerate(formatted_messages):
                        print(f"Message {i+1} ({type(message).__name__}):")
                        print(f"{message.content[:2000]}{'...' if len(message.content) > 2000 else ''}")
                        print("-" * 80)
                    if self.cached_model:
                        print(f"Using context caching for improved performance")
                
                planning_output = self._get_cached_initial_planning_response(
                    state['original_query'], 
                    state.get('intent_context')
                )
            else:
                if is_debug_enabled():
                    prompt = self._get_followup_planning_prompt(
                        state['original_query'], 
                        previous_context,
                        state.get('evaluation_result', '')
                    )
                    formatted_messages = prompt.format_messages()
                    print(f"\n=== DEBUG: PLANNING PROMPT (Iteration {state.get('current_iteration', 0) + 1}) ===")
                    for i, message in enumerate(formatted_messages):
                        print(f"Message {i+1} ({type(message).__name__}):")
                        print(f"{message.content[:2000]}{'...' if len(message.content) > 2000 else ''}")
                        print("-" * 80)
                    if self.cached_model:
                        print(f"Using context caching for improved performance")
                
                planning_output = self._get_cached_followup_planning_response(
                    state['original_query'], 
                    previous_context,
                    state.get('evaluation_result', '')
                )
            
            if is_debug_enabled():
                print(f"\n=== DEBUG: PLANNING RESPONSE ===")
                print(f"Raw LLM Response:\n{planning_output}")
                print("=" * 80)
            
            # Parse the planning output to extract plan and queries
            plan, queries = self._parse_planning_output(planning_output)
            
            if is_debug_enabled():
                print(f"\n=== DEBUG: PARSED PLANNING OUTPUT ===")
                print(f"Parsed Plan:\n{plan}")
                print(f"\nParsed SQL Queries ({len(queries)} total):")
                for i, query in enumerate(queries):
                    print(f"  Query {i+1}: {query}")
                print("=" * 80)
            
            state['current_plan'] = plan
            state['planned_queries'] = queries
            state['current_iteration'] = state.get('current_iteration', 0) + 1
            
            logger.info(f"Generated plan with {len(queries)} queries")
            
        except Exception as e:
            logger.error(f"Error in planning stage: {e}")
            state['error_message'] = f"Planning failed: {str(e)}"
        
        return state
    
    @traceable(run_type="chain", name="Query Execution Stage")
    def _query_execution_node(self, state: QueryState) -> QueryState:
        """
        Stage 2: Execute SQL queries directly using the SQL executor.
        """
        logger.info(f"Query execution stage - Processing {len(state.get('planned_queries', []))} SQL queries")
        
        if not state.get('planned_queries'):
            logger.warning("No planned queries to execute")
            return state
        
        # Build context for subsequent queries
        context = self._build_cumulative_context(state.get('all_query_results', []))
        
        # Initialize all_query_results if not exists
        if 'all_query_results' not in state:
            state['all_query_results'] = []
        
        # Execute each planned SQL query
        for i, sql_query in enumerate(state['planned_queries']):
            logger.info(f"Executing SQL query {i+1}/{len(state['planned_queries'])}: {sql_query[:100]}...")
            
            if is_debug_enabled():
                print(f"\n=== DEBUG: SQL EXECUTION {i+1}/{len(state['planned_queries'])} ===")
                print(f"Full SQL Query:\n{sql_query}")
                print(f"Current Context Length: {len(context)} characters")
                print("-" * 80)
            
            try:
                # Validate the SQL query
                validation_result = self.sql_agent.sql_executor.validate_sql_query(sql_query)
                
                if is_debug_enabled():
                    print(f"=== DEBUG: SQL VALIDATION ===")
                    print(f"Validation Result: {validation_result}")
                    print("-" * 40)
                
                if not validation_result["valid"]:
                    logger.error(f"Invalid SQL query: {validation_result['error']}")
                    
                    if is_debug_enabled():
                        print(f"❌ SQL VALIDATION FAILED: {validation_result['error']}")
                        print("=" * 80)
                    
                    query_result = QueryResult(
                        query=sql_query,
                        sql_query=sql_query,
                        success=False,
                        data=[],
                        formatted_results='',
                        error=f"Invalid SQL: {validation_result['error']}",
                        iteration=state['current_iteration']
                    )
                    state['all_query_results'].append(query_result)
                    continue
                
                # Execute the SQL query
                execution_result = self.sql_agent.sql_executor.execute_sql_query(sql_query)
                
                if is_debug_enabled():
                    print(f"=== DEBUG: SQL EXECUTION RESULT ===")
                    print(f"Execution Success: {execution_result.get('success', False)}")
                    print(f"Row Count: {execution_result.get('row_count', 0)}")
                    print(f"Columns: {execution_result.get('columns', [])}")
                    if execution_result.get('error'):
                        print(f"Execution Error: {execution_result['error']}")
                    if execution_result.get('data'):
                        print(f"Sample Data (first 3 rows): {execution_result['data'][:3]}")
                    print("-" * 40)
                
                # Format results for display
                formatted_results = self.sql_agent.sql_executor.format_results_for_display(execution_result)
                
                if is_debug_enabled():
                    print(f"=== DEBUG: FORMATTED RESULTS ===")
                    print(f"Formatted Results (first 500 chars):\n{formatted_results[:500]}{'...' if len(formatted_results) > 500 else ''}")
                    print("=" * 80)
                
                # Create query result record
                query_result = QueryResult(
                    query=sql_query,
                    sql_query=sql_query,
                    success=execution_result.get('success', False),
                    data=execution_result.get('data', []),
                    formatted_results=formatted_results,
                    error=execution_result.get('error'),
                    iteration=state['current_iteration']
                )
                
                # Append to all results (don't overwrite)
                state['all_query_results'].append(query_result)
                
                # Update context with successful results for subsequent queries
                if execution_result.get('success'):
                    context += f"\n\nSQL Query: {sql_query}\nResults: {formatted_results[:1000]}..."
                    
                    if is_debug_enabled():
                        print(f"✅ QUERY SUCCESSFUL - Added to context")
                        print(f"Updated Context Length: {len(context)} characters")
                        print("=" * 80)
                
            except Exception as e:
                logger.error(f"Error executing SQL query '{sql_query}': {e}")
                
                if is_debug_enabled():
                    print(f"❌ EXCEPTION DURING SQL EXECUTION:")
                    print(f"Exception Type: {type(e).__name__}")
                    print(f"Exception Message: {str(e)}")
                    import traceback
                    print(f"Traceback:\n{traceback.format_exc()}")
                    print("=" * 80)
                
                # Still append the failed query to maintain record
                query_result = QueryResult(
                    query=sql_query,
                    sql_query=sql_query,
                    success=False,
                    data=[],
                    formatted_results='',
                    error=str(e),
                    iteration=state['current_iteration']
                )
                state['all_query_results'].append(query_result)
        
        logger.info(f"Completed query execution. Total queries executed: {len(state['all_query_results'])}")
        return state
    
    @traceable(run_type="chain", name="Evaluation Stage")
    def _evaluation_node(self, state: QueryState) -> QueryState:
        """
        Stage 3: Evaluate data sufficiency and either generate final answer or signal to continue.
        """
        logger.info("Evaluation stage - Assessing data sufficiency and generating response")
        
        # Don't iterate more than max iterations
        if state.get('current_iteration', 0) >= get_max_iterations():
            logger.info("Maximum iterations reached - generating final answer")
            state['needs_more_data'] = False
            state['evaluation_result'] = "Maximum iterations reached"
            # Generate final answer with available data
            self._generate_final_answer(state)
            return state
        
        # If no queries have been executed yet, continue to planning
        if not state.get('all_query_results') or len(state.get('all_query_results', [])) == 0:
            logger.info("No queries executed yet - continuing to planning")
            state['needs_more_data'] = True
            state['evaluation_result'] = "No data gathered yet - need to execute queries"
            return state
        
        # Build comprehensive context from all query results
        cumulative_context = self._build_cumulative_context(state.get('all_query_results', []))
        
        if is_debug_enabled():
            print(f"\n=== DEBUG: EVALUATION STAGE (Iteration {state.get('current_iteration', 0)}) ===")
            print(f"Total Query Results: {len(state.get('all_query_results', []))}")
            print(f"Cumulative Context Length: {len(cumulative_context)} characters")
            print(f"Context Preview (first 500 chars):\n{cumulative_context[:500]}{'...' if len(cumulative_context) > 500 else ''}")
            print("-" * 80)
        
        # If context is empty or minimal, continue planning
        if not cumulative_context.strip() or len(cumulative_context.strip()) < 50:
            logger.info("Insufficient data gathered - continuing to planning")
            state['needs_more_data'] = True
            state['evaluation_result'] = "Insufficient data gathered - need more specific queries"
            
            if is_debug_enabled():
                print(f"❌ INSUFFICIENT DATA: Context too short ({len(cumulative_context.strip())} chars)")
                print("=" * 80)
            
            return state
        
        evaluation_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an expert data analyst evaluating whether sufficient information has been gathered to comprehensively answer a user's question about persona and geographic data.

Your task is to:
1. Analyze if the question can be answered with current data (be generous - partial answers are acceptable)
2. Either generate a complete structured answer OR indicate what additional data is needed. The answer should not comment directly on the SQL queries, or on the method used to answer the question. It should just be a concise answer to the users question.

RESPONSE FORMAT:
If you can provide ANY meaningful and relevant answer, start with "SUFFICIENT" and provide analysis:

SUFFICIENT

SIMPLE SUMMARY: [2-3 sentence overview of what can be determined, do not comment on the SQL queries or the method used to answer the question. Do not quote any percentage figures above 100%]
KEY INSIGHTS: 
- [insight 1 - what the data shows]
- [insight 2 - patterns or trends]
- [insight 3 - limitations or caveats if needed]
DETAILED EXPLANATION: [thorough analysis of available data]
CONTEXT RELEVANCE: [0.0 to 1.0]

If not enough useful information can be extracted, start with "INSUFFICIENT":

INSUFFICIENT
[Brief explanation of what specific data is needed and why current data is inadequate]

Remember: Partial answers are better than no answers. Focus on what the data DOES show."""),
            
            HumanMessage(content=f"""Original Question: {state['original_query']}

Current Iteration: {state.get('current_iteration', 0)}
Total Queries Executed: {len(state.get('all_query_results', []))}

All Gathered Data:
{cumulative_context[:30000]}...

Evaluation and Response:""")
        ])
        
        try:
            if is_debug_enabled():
                formatted_messages = evaluation_prompt.format_messages()
                print(f"\n=== DEBUG: EVALUATION PROMPT ===")
                for i, message in enumerate(formatted_messages):
                    print(f"Message {i+1} ({type(message).__name__}):")
                    print(f"{message.content[:1500]}{'...' if len(message.content) > 1500 else ''}")
                    print("-" * 80)
            
            response = self.llm_large.invoke(evaluation_prompt.format_messages())
            evaluation_result = response.content.strip()
            
            if is_debug_enabled():
                print(f"\n=== DEBUG: EVALUATION RESPONSE ===")
                print(f"Raw Evaluation Result:\n{evaluation_result}")
                print("=" * 80)
            
            state['evaluation_result'] = evaluation_result
            
            if evaluation_result.startswith("SUFFICIENT"):
                state['needs_more_data'] = False
                logger.info("Evaluation: Sufficient data available - generating final answer")
                
                if is_debug_enabled():
                    print(f"✅ EVALUATION: SUFFICIENT DATA DETERMINED")
                    print("-" * 40)
                
                # Extract the answer portion after "SUFFICIENT"
                answer_content = evaluation_result.replace("SUFFICIENT", "").strip()
                structured_output = self._parse_final_answer(answer_content, state['original_query'])
                state['final_answer'] = structured_output
                
                if is_debug_enabled():
                    print(f"=== DEBUG: PARSED FINAL ANSWER ===")
                    print(f"Structured Output: {structured_output}")
                    print("-" * 40)
                
                # Check if the generated answer is actually a clarification request
                if structured_output and isinstance(structured_output, dict):
                    simple_summary = structured_output.get('simple_summary', '').lower()
                    detailed_explanation = structured_output.get('detailed_explanation', '').lower()
                    
                    # Look for clarification keywords
                    clarification_keywords = ['clarification', 'clarify', 'specify', 'which type', 'more specific', 'need to know']
                    is_clarification = any(keyword in simple_summary or keyword in detailed_explanation 
                                         for keyword in clarification_keywords)
                    
                    if is_debug_enabled():
                        print(f"=== DEBUG: CLARIFICATION CHECK ===")
                        print(f"Simple Summary: {simple_summary}")
                        print(f"Detailed Explanation: {detailed_explanation}")
                        print(f"Is Clarification: {is_clarification}")
                        print(f"Keywords Found: {[kw for kw in clarification_keywords if kw in simple_summary or kw in detailed_explanation]}")
                        print("-" * 40)
                    
                    if is_clarification:
                        logger.info("Generated answer appears to be a clarification request - continuing to planning")
                        state['needs_more_data'] = True
                        structured_output['return_answer'] = False
                        state['final_answer'] = structured_output
                        
                        if is_debug_enabled():
                            print(f"🔄 CLARIFICATION DETECTED - Will continue planning")
                            print("=" * 80)
                
            else:
                state['needs_more_data'] = True
                logger.info(f"Evaluation: More data needed - {evaluation_result[:200]}...")
                
                if is_debug_enabled():
                    print(f"🔄 EVALUATION: MORE DATA NEEDED")
                    print(f"Reason: {evaluation_result[:300]}...")
                    print("=" * 80)
                
        except Exception as e:
            logger.error(f"Error in evaluation stage: {e}")
            # Generate final answer on error to avoid infinite loops
            state['needs_more_data'] = False
            state['evaluation_result'] = f"Evaluation error: {str(e)}"
            state['final_answer'] = self._create_error_response(str(e))
        
        return state
    
    @traceable(run_type="chain", name="Generate Final Answer")
    def _generate_final_answer(self, state: QueryState) -> None:
        """
        Generate final answer when maximum iterations reached.
        """
        cumulative_context = self._build_cumulative_context(state.get('all_query_results', []))
        
        synthesis_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an expert data analyst. Generate a comprehensive structured answer based on all available data.
The answer should not comment directly on the SQL queries, or on the method used to answer the question. It should just be a concise answer to the users question.
Format your response as:

SIMPLE SUMMARY: [2-3 sentence overview of what can be determined, do not comment on the SQL queries or the method used to answer the question. Do not quote any percentage figures above 100%]
KEY INSIGHTS: 
- [insight 1 - what the data shows]
- [insight 2 - patterns or trends]
- [insight 3 - limitations or caveats if needed]
DETAILED EXPLANATION: [thorough analysis of available data. Do not quote any percentage figures above 100%]
CONTEXT RELEVANCE: [0.0 to 1.0]

Focus on what CAN be determined from available data."""),
            
            HumanMessage(content=f"""Original Question: {state['original_query']}

All Available Data:
{cumulative_context}

Generate final answer:""")
        ])
        
        try:
            response = self.llm_large.invoke(synthesis_prompt.format_messages())
            final_answer = response.content.strip()
            structured_output = self._parse_final_answer(final_answer, state['original_query'])
            state['final_answer'] = structured_output
        except Exception as e:
            logger.error(f"Error generating final answer: {e}")
            state['final_answer'] = self._create_error_response(str(e))
    
    def _should_continue_or_end(self, state: QueryState) -> str:
        """
        Conditional edge function to determine next step based on evaluation.
        """
        if is_debug_enabled():
            print(f"\n=== DEBUG: WORKFLOW DECISION ===")
            print(f"Current Iteration: {state.get('current_iteration', 0)}")
            print(f"Needs More Data: {state.get('needs_more_data', False)}")
            print(f"Has Final Answer: {state.get('final_answer') is not None}")
            print("-" * 40)
        
        # Check if we've reached maximum iterations
        if state.get('current_iteration', 0) >= get_max_iterations():
            if is_debug_enabled():
                print(f"🛑 WORKFLOW DECISION: END (Max iterations reached)")
                print("=" * 80)
            return "end"
        
        # If evaluation explicitly says we need more data, continue
        if state.get('needs_more_data', False):
            if is_debug_enabled():
                print(f"🔄 WORKFLOW DECISION: CONTINUE (More data needed)")
                print("=" * 80)
            return "continue"
        
        # If we have a final answer, check if it's a real answer or just a clarification
        final_answer = state.get('final_answer')
        if final_answer and isinstance(final_answer, dict):
            # If return_answer is False (clarification/error), continue planning
            if not final_answer.get('return_answer', True):
                logger.info("Final answer indicates clarification needed - continuing to planning")
                # Reset needs_more_data to allow continuation
                state['needs_more_data'] = True
                
                if is_debug_enabled():
                    print(f"🔄 WORKFLOW DECISION: CONTINUE (Clarification needed)")
                    print(f"Return Answer Flag: {final_answer.get('return_answer', True)}")
                    print("=" * 80)
                
                return "continue"
        
        # Otherwise end the workflow
        if is_debug_enabled():
            print(f"🛑 WORKFLOW DECISION: END (Normal completion)")
            print("=" * 80)
        return "end"
    
    def _get_initial_planning_prompt(self, original_query: str, intent_context: Optional[str] = None) -> ChatPromptTemplate:
        """
        Get the prompt for initial planning stage.
        """
        context_header = ""
        if intent_context:
            context_header = f"""The following is a summary of the conversation that led to the refined query:
{intent_context}

---

"""

        return ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""You are an expert at strategic planning and SQL query generation for persona and geographic data analysis.

{context_header}Your task is to create a step-by-step plan to comprehensively answer the user's question, then generate 1-2 specific SQL queries to start executing that plan.

PLANNING APPROACH:
1. Break down the question into logical components
2. Identify what types of data are needed (personas, geography, behavioral models)
3. Determine the sequence of queries needed
4. Start with the most fundamental/foundational queries

Available data types:
- Persona distributions by geography (national, regional, local authority, ward, postcode)
- Behavioral prediction models for personas
- Geographic mapping and relationships
- Persona characteristics and labels

{self.schema_info}

GLOSSARY:
{GLOSSARY}

FORMAT YOUR RESPONSE AS:

PLAN:
[Provide a clear step-by-step plan explaining your approach to answering this question]

QUERIES:
1. [First specific SQL query to execute - provide ONLY the raw SQL, no markdown formatting, no explanations]
2. [Second specific SQL query to execute, if needed - provide ONLY the raw SQL, no markdown formatting, no explanations]

CRITICAL: Generate ONLY clean SQL queries, no markdown code blocks (```sql), no explanations, no comments. Each query should start directly with SELECT and end with semicolon."""),
            
            HumanMessage(content=f"Original Question: {original_query}\n\nProvide a strategic plan and initial SQL queries:")
        ])
    
    @traceable(run_type="llm", name="Cached Initial Planning")
    def _get_cached_initial_planning_response(self, original_query: str, intent_context: Optional[str] = None) -> str:
        """
        Get initial planning response using cached model for improved performance.
        Falls back to LangChain if caching is not available.
        """
        if self.cached_model is None:
            # Fallback to original LangChain approach
            prompt = self._get_initial_planning_prompt(original_query, intent_context)
            response = self.llm.invoke(prompt.format_messages())
            return response.content.strip()
        
        try:
            context_header = ""
            if intent_context:
                context_header = f"""The following is a summary of the conversation that led to the refined query:
{intent_context}

---

"""
            
            # Use cached model with simplified prompt (schema is already cached)
            cached_prompt = f"""{context_header}Your task is to create a step-by-step plan to comprehensively answer the user's question, then generate 1-2 specific SQL queries to start executing that plan.

PLANNING APPROACH:
1. Break down the question into logical components
2. Identify what types of data are needed (personas, geography, behavioral models)
3. Determine the sequence of queries needed
4. Start with the most fundamental/foundational queries

FORMAT YOUR RESPONSE AS:

PLAN:
[Provide a clear step-by-step plan explaining your approach to answering this question]

QUERIES:
1. [First specific SQL query to execute - provide ONLY the raw SQL, no markdown formatting, no explanations]
2. [Second specific SQL query to execute, if needed - provide ONLY the raw SQL, no markdown formatting, no explanations]

Original Question: {original_query}

Provide a strategic plan and initial SQL queries:"""
            
            response = self.cached_model.generate_content(cached_prompt)
            return response.text
            
        except Exception as e:
            logger.warning(f"Cached planning failed: {e}. Falling back to LangChain.")
            # Fallback to original LangChain approach
            prompt = self._get_initial_planning_prompt(original_query, intent_context)
            response = self.llm.invoke(prompt.format_messages())
            return response.content.strip()
    
    def _get_followup_planning_prompt(self, original_query: str, previous_context: str, evaluation_result: str) -> ChatPromptTemplate:
        """
        Get the prompt for follow-up planning iterations.
        """
        return ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""You are continuing strategic planning and SQL query generation for persona and geographic data analysis based on previous findings.

Based on the evaluation feedback and data gathered so far, create a focused plan for the next set of SQL queries to complete the analysis.

FOLLOW-UP PLANNING APPROACH:
1. Review what has already been found
2. Identify specific gaps highlighted in the evaluation
3. Plan targeted SQL queries to fill those gaps
4. Avoid repeating similar queries unless they target different aspects

{self.schema_info}

FORMAT YOUR RESPONSE AS:

PLAN:
[Explain what additional data is needed and why, based on the evaluation feedback]

QUERIES:
1. [Specific follow-up SQL query - provide ONLY the raw SQL, no markdown formatting, no explanations]
2. [Additional follow-up SQL query, if needed - provide ONLY the raw SQL, no markdown formatting, no explanations]

CRITICAL: Generate ONLY clean SQL queries, no markdown code blocks (```sql), no explanations, no comments. Each query should start directly with SELECT and end with semicolon."""),
            
            HumanMessage(content=f"""Original Question: {original_query}

Previous Data Gathered:
{previous_context[:15000]}...

Evaluation Feedback:
{evaluation_result}

Plan the next set of targeted SQL queries:""")
        ])
    
    @traceable(run_type="llm", name="Cached Followup Planning")
    def _get_cached_followup_planning_response(self, original_query: str, previous_context: str, evaluation_result: str) -> str:
        """
        Get follow-up planning response using cached model for improved performance.
        Falls back to LangChain if caching is not available.
        """
        if self.cached_model is None:
            # Fallback to original LangChain approach
            prompt = self._get_followup_planning_prompt(original_query, previous_context, evaluation_result)
            response = self.llm.invoke(prompt.format_messages())
            return response.content.strip()
        
        try:
            # Use cached model with simplified prompt (schema is already cached)
            cached_prompt = f"""You are continuing strategic planning and SQL query generation for persona and geographic data analysis based on previous findings.

Based on the evaluation feedback and data gathered so far, create a focused plan for the next set of SQL queries to complete the analysis.

FOLLOW-UP PLANNING APPROACH:
1. Review what has already been found
2. Identify specific gaps highlighted in the evaluation
3. Plan targeted SQL queries to fill those gaps
4. Avoid repeating similar queries unless they target different aspects

FORMAT YOUR RESPONSE AS:

PLAN:
[Explain what additional data is needed and why, based on the evaluation feedback]

QUERIES:
1. [Specific follow-up SQL query - provide ONLY the raw SQL, no markdown formatting, no explanations]
2. [Additional follow-up SQL query, if needed - provide ONLY the raw SQL, no markdown formatting, no explanations]

Original Question: {original_query}

Previous Data Gathered:
{previous_context[:30000]}...

Evaluation Feedback:
{evaluation_result}

Plan the next set of targeted SQL queries:"""
            
            response = self.cached_model.generate_content(cached_prompt)
            return response.text
            
        except Exception as e:
            logger.warning(f"Cached follow-up planning failed: {e}. Falling back to LangChain.")
            # Fallback to original LangChain approach
            prompt = self._get_followup_planning_prompt(original_query, previous_context, evaluation_result)
            response = self.llm.invoke(prompt.format_messages())
            return response.content.strip()
    
    @traceable(run_type="parser", name="Parse Planning Output")
    def _parse_planning_output(self, planning_output: str) -> tuple[str, List[str]]:
        """
        Parse the planning output to extract plan and SQL queries.
        Simple approach: extract plan before QUERIES: section, then find all SELECT...semicolon blocks.
        """
        # Split into plan and queries sections
        if 'QUERIES:' in planning_output.upper():
            parts = planning_output.split('QUERIES:', 1)
            if len(parts) == 2:
                plan_section, queries_section = parts
                plan = plan_section.replace('PLAN:', '').strip()
            else:
                plan = ""
                queries_section = planning_output
        else:
            # No QUERIES section found, treat entire output as plan
            plan = planning_output.replace('PLAN:', '').strip()
            queries_section = ""
        
        # Extract all SQL queries from the queries section using SELECT...semicolon boundaries
        sql_queries = self._extract_all_sql_queries(queries_section)
        
        if is_debug_enabled():
            print(f"=== DEBUG: SIMPLE SQL PARSING ===")
            print(f"Plan section: {plan[:200]}...")
            print(f"Queries section: {queries_section[:300]}...")
            print(f"Found {len(sql_queries)} SQL queries")
            for i, query in enumerate(sql_queries):
                print(f"  Query {i+1}: {query[:100]}...")
            print("-" * 40)
        
        return plan, sql_queries[:3]  # Limit to 3 queries
    
    def _extract_all_sql_queries(self, text: str) -> List[str]:
        """
        Extract all SQL queries from text using simple SELECT...semicolon detection.
        Much more robust than trying to parse numbered lists or markdown.
        """
        queries = []
        text = text.strip()
        
        if not text:
            return queries
        
        # Find all SELECT statements in the text
        text_upper = text.upper()
        current_pos = 0
        
        while True:
            # Find the next SELECT
            select_pos = text_upper.find('SELECT', current_pos)
            if select_pos == -1:
                break
            
            # Find the next semicolon after this SELECT
            semicolon_pos = text.find(';', select_pos)
            if semicolon_pos == -1:
                # No semicolon found, take rest of text
                sql_content = text[select_pos:].strip()
            else:
                # Extract from SELECT to semicolon (inclusive)
                sql_content = text[select_pos:semicolon_pos + 1].strip()
            
            # Clean up the SQL content
            sql_content = self._clean_sql_content(sql_content)
            
            if sql_content and sql_content.upper().startswith('SELECT'):
                queries.append(sql_content)
                if is_debug_enabled():
                    print(f"Found SQL query: {sql_content[:100]}...")
            
            # Move past this query
            if semicolon_pos == -1:
                break
            current_pos = semicolon_pos + 1
        
        return queries
    
    def _clean_sql_content(self, sql: str) -> str:
        """
        Clean up SQL content by removing comments and extra whitespace.
        """
        if not sql:
            return ""
        
        # Remove SQL comments and clean up
        lines = []
        for line in sql.split('\n'):
            line = line.strip()
            # Skip comment lines but keep the rest
            if line and not line.startswith('--'):
                lines.append(line)
        
        sql_content = ' '.join(lines).strip()
        
        # Ensure it ends with semicolon
        if sql_content and not sql_content.endswith(';'):
            sql_content += ';'
        
        return sql_content
    
    def _extract_sql_from_text(self, text: str) -> str:
        """
        Extract clean SQL from text that may contain markdown formatting and descriptive text.
        
        Args:
            text: Raw text that may contain SQL with markdown formatting
            
        Returns:
            Clean SQL query string or empty string if no valid SQL found
        """
        text = text.strip()
        
        # First, try to extract SQL from markdown code blocks
        if '```sql' in text and '```' in text:
            # Find the SQL code block
            start_marker = '```sql'
            end_marker = '```'
            
            start_idx = text.find(start_marker)
            if start_idx != -1:
                start_idx += len(start_marker)
                end_idx = text.find(end_marker, start_idx)
                if end_idx != -1:
                    sql_content = text[start_idx:end_idx].strip()
                else:
                    # Handle case where closing ``` might be missing
                    sql_content = text[start_idx:].strip()
        else:
            # No markdown blocks, try to extract SQL directly
            # Look for SELECT keyword and extract from there
            text_upper = text.upper()
            select_idx = text_upper.find('SELECT')
            if select_idx != -1:
                sql_content = text[select_idx:].strip()
            else:
                # No SELECT found, return empty
                return ""
        
        # Clean up the extracted SQL
        sql_content = sql_content.strip()
        
        # Remove any trailing semicolons from markdown artifacts
        if sql_content.endswith('```;'):
            sql_content = sql_content[:-4]
        elif sql_content.endswith('```'):
            sql_content = sql_content[:-3]
        
        # Remove any remaining markdown artifacts
        sql_content = sql_content.replace('```sql', '').replace('```', '').strip()
        
        # Remove comments and clean up
        lines = []
        for line in sql_content.split('\n'):
            line = line.strip()
            # Skip comment lines but keep the rest
            if line and not line.startswith('--'):
                lines.append(line)
        
        sql_content = ' '.join(lines).strip()
        
        # Ensure it ends with semicolon
        if sql_content and not sql_content.endswith(';'):
            sql_content += ';'
        
        # Basic validation - must start with SELECT (case insensitive)
        if sql_content.upper().startswith('SELECT'):
            if is_debug_enabled():
                print(f"=== DEBUG: EXTRACTED SQL ===")
                print(f"Original text: {text[:200]}...")
                print(f"Extracted SQL: {sql_content}")
                print("-" * 40)
            return sql_content
        else:
            if is_debug_enabled():
                print(f"=== DEBUG: SQL EXTRACTION FAILED ===")
                print(f"Original text: {text[:200]}...")
                print(f"Cleaned content: {sql_content}")
                print("No valid SELECT statement found")
                print("-" * 40)
            return ""
    
    @traceable(run_type="parser", name="Build Cumulative Context")
    def _build_cumulative_context(self, all_query_results: List[QueryResult]) -> str:
        """
        Build comprehensive context from all query results across all iterations.
        """
        if not all_query_results:
            return ""
        
        context_parts = []
        
        # Group by iteration
        iteration_groups = {}
        for result in all_query_results:
            iteration = result.get('iteration', 0)
            if iteration not in iteration_groups:
                iteration_groups[iteration] = []
            iteration_groups[iteration].append(result)
        
        # Build context by iteration
        for iteration in sorted(iteration_groups.keys()):
            results = iteration_groups[iteration]
            context_parts.append(f"\n--- ITERATION {iteration} ---")
            
            for i, result in enumerate(results):
                context_parts.append(f"\nSQL Query {i+1}: {result['query']}")
                
                if result['success']:
                    context_parts.append(f"Results: {result['formatted_results'][:500]}...")
                else:
                    context_parts.append(f"Error: {result.get('error', 'Unknown error')}")
                
                context_parts.append("")
        
        return "\n".join(context_parts)
    
    def _parse_final_answer(self, final_answer: str, original_query: str) -> Dict[str, Any]:
        """
        Parse the final answer into structured format.
        """
        # This is a simplified parser - in production you'd want more robust parsing
        try:
            # Extract key sections
            simple_summary = self._extract_section(final_answer, "SIMPLE SUMMARY", "KEY INSIGHTS")
            key_insights = self._extract_section(final_answer, "KEY INSIGHTS", "DETAILED EXPLANATION")
            detailed_explanation = self._extract_section(final_answer, "DETAILED EXPLANATION", "CONTEXT RELEVANCE")
            
            # Extract context relevance
            context_relevance = 0.8  # Default value
            if "CONTEXT RELEVANCE" in final_answer:
                relevance_text = final_answer.split("CONTEXT RELEVANCE")[-1]
                # Try to extract a number
                import re
                numbers = re.findall(r'0\.\d+|\d+\.\d+', relevance_text)
                if numbers:
                    try:
                        context_relevance = float(numbers[0])
                        if context_relevance > 1.0:
                            context_relevance = context_relevance / 100  # Convert percentage
                    except:
                        pass
            
            # Parse key insights into list
            insights_list = []
            if key_insights:
                for line in key_insights.split('\n'):
                    line = line.strip()
                    if line and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                        insights_list.append(line[1:].strip())
            
            return {
                "simple_summary": simple_summary or "Analysis completed based on available persona and geographic data.",
                "key_insights": insights_list or ["Data analysis performed on persona distributions"],
                "detailed_explanation": detailed_explanation or final_answer,
                "context_relevance": max(0.0, min(1.0, context_relevance)),
                "return_answer": True
            }
            
        except Exception as e:
            logger.error(f"Error parsing final answer: {e}")
            return self._create_error_response("Failed to parse analysis results")
    
    def _extract_section(self, text: str, start_marker: str, end_marker: str) -> str:
        """
        Extract a section of text between markers.
        """
        try:
            start_idx = text.find(start_marker)
            if start_idx == -1:
                return ""
            
            start_idx += len(start_marker)
            end_idx = text.find(end_marker, start_idx)
            
            if end_idx == -1:
                section = text[start_idx:].strip()
            else:
                section = text[start_idx:end_idx].strip()
            
            # Clean up the section
            section = section.lstrip(':').strip()
            return section
            
        except Exception:
            return ""
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """
        Create a standardized error response.
        """
        return {
            "simple_summary": f"Unable to complete analysis due to error: {error_message}",
            "key_insights": ["Analysis could not be completed", "Please check query and try again"],
            "detailed_explanation": f"The system encountered an error while processing your request: {error_message}. Please try rephrasing your question or contact support if the issue persists.",
            "context_relevance": 0.0,
            "return_answer": False
        }
    
    @traceable(run_type="chain", name="Process Query")
    def process_query(self, user_query: str, intent_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a user query through the complete workflow.
        
        Args:
            user_query: The user's natural language question (potentially refined)
            intent_context: Optional summary of the conversation that clarified the query
            
        Returns:
            Structured response containing analysis results
            
        Note:
            The workflow now generates SQL queries directly in the planning stage
            and executes them using the SQL executor for improved efficiency.
        """
        logger.info(f"Processing user query: {user_query}")
        if intent_context:
            logger.info(f"With intent context: {intent_context[:200]}...") # Log snippet of context
        
        if is_debug_enabled():
            print(f"\n{'='*100}")
            print(f"🐛 DEBUG MODE ENABLED - VERBOSE SQL GENERATION AND EXECUTION LOGGING")
            print(f"{'='*100}")
            print(f"Query: {user_query}")
            if intent_context:
                print(f"Intent Context: {intent_context[:300]}...")
            print(f"{'='*100}\n")
        
        # Initialize state
        initial_state = QueryState(
            original_query=user_query,
            intent_context=intent_context,
            current_iteration=0,
            all_query_results=[],
            current_plan=None,
            planned_queries=[],
            evaluation_result=None,
            needs_more_data=True,
            final_answer=None,
            error_message=None
        )
        
        try:
            # Run the workflow
            final_state = self.workflow.invoke(initial_state)
            
            if is_debug_enabled():
                print(f"\n{'='*100}")
                print(f"🏁 WORKFLOW COMPLETED - FINAL DEBUG SUMMARY")
                print(f"{'='*100}")
                print(f"Total Iterations: {final_state.get('current_iteration', 0)}")
                print(f"Total SQL Queries Executed: {len(final_state.get('all_query_results', []))}")
                successful_queries = sum(1 for result in final_state.get('all_query_results', []) if result.get('success'))
                print(f"Successful Queries: {successful_queries}")
                print(f"Failed Queries: {len(final_state.get('all_query_results', [])) - successful_queries}")
                print(f"Has Final Answer: {final_state.get('final_answer') is not None}")
                print(f"Has Error: {final_state.get('error_message') is not None}")
                if final_state.get('error_message'):
                    print(f"Error Message: {final_state['error_message']}")
                print(f"{'='*100}\n")
            
            if final_state.get('error_message'):
                return self._create_error_response(final_state['error_message'])
            
            return final_state.get('final_answer', self._create_error_response("No final answer generated"))
            
        except Exception as e:
            logger.error(f"Error in workflow execution: {e}")
            
            if is_debug_enabled():
                print(f"\n❌ WORKFLOW EXCEPTION:")
                print(f"Exception Type: {type(e).__name__}")
                print(f"Exception Message: {str(e)}")
                import traceback
                print(f"Traceback:\n{traceback.format_exc()}")
                print("="*100)
            
            return self._create_error_response(str(e)) 