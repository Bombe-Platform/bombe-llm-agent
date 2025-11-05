import os
import logging
import json
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import uvicorn

# Import the agent and its components
from db_manager import DatabaseManager
from sql_executor import SQLExecutor
from sql_agent import SQLAgent
from high_level_agent import HighLevelAgent
from user_intent_agent import UserIntentAgent

# Environment Variables:
# - GOOGLE_API_KEY: Required for all AI functionality
# - DATABASE_URL: Required for database connections
# - PROD_LLM_API_KEY: Optional API key for production security
# - DEBUG: Optional, enables verbose logging and debug output
# - MAX_ITERATIONS: Optional, controls maximum iterations for high-level agent (default: 4)
# - BYPASS_USER_INTENT_AGENT: Optional, if set to 'true', skips user intent clarification (default: false)
# - LANGSMITH_TRACING: Optional, enables LangSmith tracing for observability (default: false)
# - LANGSMITH_API_KEY: Optional, LangSmith API key for tracing
# 
# Context Caching:
# The HighLevelAgent now uses Google Gemini context caching for improved performance.
# Database schema and glossary information is cached automatically.
# Falls back to standard LangChain approach if caching fails.

# Configure logging (same as main_test.py)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_bypass_user_intent_enabled() -> bool:
    """Check if BYPASS_USER_INTENT_AGENT environment variable is set to 'true'."""
    return os.getenv('BYPASS_USER_INTENT_AGENT', '').lower() == 'true'

# --- Agent Code (adapted from main_test.py) ---
class PersonaAnalyticsAgent:
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY')
        self.db_connection_string = os.getenv('DATABASE_URL')
        
        if not self.api_key:
            logger.error("GOOGLE_API_KEY environment variable is required")
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        logger.info("Initializing database manager...")
        self.db_manager = DatabaseManager(self.db_connection_string)
        
        logger.info("Initializing SQL executor...")
        self.sql_executor = SQLExecutor(self.db_manager)
        
        logger.info("Initializing SQL agent...")
        self.sql_agent = SQLAgent(self.sql_executor, self.api_key, self.db_manager)
        
        logger.info("Initializing high-level agent with context caching...")
        try:
            self.high_level_agent = HighLevelAgent(self.sql_agent, self.api_key, self.db_manager)
            
            # Check if context caching was successfully initialized
            if hasattr(self.high_level_agent, 'cached_model') and self.high_level_agent.cached_model is not None:
                logger.info("Context caching enabled for improved performance")
            else:
                logger.info("Context caching not available - using standard LangChain approach")
                
        except Exception as e:
            logger.error(f"Failed to initialize high-level agent: {e}")
            raise
        
        logger.info("Initializing user intent agent...")
        self.user_intent_agent = UserIntentAgent(self.api_key, self.db_manager)
        
        # Log bypass configuration
        if is_bypass_user_intent_enabled():
            logger.info("BYPASS_USER_INTENT_AGENT is enabled - queries will go directly to HighLevelAgent")
        else:
            logger.info("User intent clarification is enabled - queries will be processed through UserIntentAgent first")
        
        logger.info("Persona Analytics Agent initialized successfully!")

    def _format_chat_history(self, history_entries: list[dict]) -> list[dict]:
        """Formats raw chat history entries from DB into the required format."""
        formatted_history = []
        if not history_entries:
            return formatted_history
            
        for entry in history_entries:
            source = entry.get('source')
            payload_str = entry.get('payload')
            
            if not source or not payload_str:
                logger.warning(f"Skipping entry with missing source or payload: {entry}")
                continue

            try:
                if isinstance(payload_str, dict):
                    payload = payload_str
                else:
                    payload = json.loads(payload_str)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Skipping malformed JSON payload: {payload_str}")
                continue
            
            if source == 'User':
                question = payload.get('question')
                if question:
                    formatted_history.append({"role": "user", "content": question})
                else:
                    logger.warning(f"Skipping 'User' entry with no 'question' in payload: {payload}")
            elif source == 'Bombe':
                content = payload.get('simple_summary')
                if not content:
                    content = payload.get('detailed_explanation', 'Previous response.')
                formatted_history.append({"role": "assistant", "content": content})
        
        return formatted_history

    def test_connection(self) -> bool:
        return self.db_manager.test_connection()

    def query(self, user_question: str, session_id: str | None = None) -> dict:
        logger.info(f"Received user question: {user_question}")
        
        # Check if user intent agent should be bypassed
        if is_bypass_user_intent_enabled():
            logger.info("BYPASS_USER_INTENT_AGENT is enabled - sending query directly to HighLevelAgent")
            try:
                # Process query directly with HighLevelAgent
                result = self.high_level_agent.process_query(user_question, intent_context=None)
                
                # Add bypass status to result for transparency
                result['requires_clarification'] = False
                result['clarification_message'] = None
                result['suggested_query'] = None
                result['bypass_user_intent'] = True
                return result
                
            except Exception as e:
                logger.error(f"Error processing direct query: {e}", exc_info=True)
                return {
                    "simple_summary": f"Error processing query: {str(e)}",
                    "key_insights": ["Direct query processing failed"],
                    "detailed_explanation": f"An error occurred while processing your query directly: {str(e)}",
                    "return_answer": False,
                    "requires_clarification": False,
                    "clarification_message": None,
                    "suggested_query": None,
                    "bypass_user_intent": True
                }
        
        # Standard flow with user intent agent
        chat_history_list = []
        if session_id:
            logger.info(f"Fetching chat history for session_id: {session_id}")
            raw_history = self.db_manager.get_chat_history_by_session_id(session_id)
            chat_history_list = self._format_chat_history(raw_history)

        if chat_history_list:
            logger.info(f"Using chat history with {len(chat_history_list)} items.")
        else:
            logger.info("No chat history found or provided.")

        try:
            logger.info("Clarifying user intent...")
            clarification_result = self.user_intent_agent.clarify_and_refine_query(
                user_question, 
                external_chat_history=chat_history_list
            )
            
            status = clarification_result.get("status")
            value = clarification_result.get("value")
            intent_context = clarification_result.get("summary")

            if status == "clarified":
                clarified_query = value
                logger.info(f"Clarified query: {clarified_query}")
                logger.info(f"Intent context: {intent_context}")

                logger.info(f"Processing clarified query with HighLevelAgent: {clarified_query}")
                
                # Check if context caching is available for this query
                if hasattr(self.high_level_agent, 'cached_model') and self.high_level_agent.cached_model is not None:
                    logger.debug("Using context caching for enhanced performance")
                
                result = self.high_level_agent.process_query(clarified_query, intent_context=intent_context)
                
                # Add clarification status to final successful result
                result['requires_clarification'] = False
                result['clarification_message'] = None
                result['suggested_query'] = None
                result['bypass_user_intent'] = False
                return result

            elif status == "ask_clarification":
                logger.info(f"Clarification needed, asking user: {value}")
                return {
                    "simple_summary": "I need more information to answer your question.",
                    "key_insights": ["Clarification Required"],
                    "detailed_explanation": value, # The question to ask the user
                    "return_answer": False,
                    "requires_clarification": True,
                    "clarification_message": value, # Keep for compatibility, but detailed_explanation is primary
                    "suggested_query": None,
                    "bypass_user_intent": False
                }

            elif status == "suggest_refinement":
                logger.info(f"Suggesting a query refinement to the user: {value}")
                return {
                    "simple_summary": "I can refine your query to be more specific.",
                    "key_insights": ["Refinement Suggested"],
                    "detailed_explanation": f"Based on your request, I can ask a more precise question. You can accept this suggestion, modify it, or ask something else.",
                    "return_answer": False,
                    "requires_clarification": True,
                    "clarification_message": "Would you like to run this query instead?",
                    "suggested_query": value,
                    "bypass_user_intent": False
                }

            else: # Fallback for other statuses like 'error' or 'max_interactions'
                logger.warning(f"Query clarification failed with status: {status}. Value: {value}")
                return {
                    "simple_summary": "Sorry, I'm having trouble understanding your request.",
                    "key_insights": ["Query Unclear"],
                    "detailed_explanation": value,
                    "return_answer": False,
                    "requires_clarification": True, # Indicates that the user should try again
                    "clarification_message": "Could you please rephrase your question?",
                    "suggested_query": None,
                    "bypass_user_intent": False
                }

        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return {
                "simple_summary": f"Error processing query: {str(e)}",
                "key_insights": ["Query processing failed"],
                "detailed_explanation": f"An error occurred while processing your query: {str(e)}",
                "return_answer": False,
                "requires_clarification": False,
                "clarification_message": None,
                "suggested_query": None,
                "bypass_user_intent": False
            }

# --- FastAPI Setup ---
app = FastAPI(title="Bombe LLM Service", version="2.0")

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
PROD_LLM_API_KEY = os.getenv("PROD_LLM_API_KEY")

if not PROD_LLM_API_KEY:
    logger.warning("PROD_LLM_API_KEY environment variable not set. API will be insecure if this is not a dev environment.")

async def get_api_key(key: str = Security(api_key_header)):
    if PROD_LLM_API_KEY and key == PROD_LLM_API_KEY:
        return key
    elif not PROD_LLM_API_KEY:
        logger.warning("Allowing access without API key (PROD_LLM_API_KEY not set).")
        return "development_key_not_set"
    else:
        logger.warning(f"Invalid API Key received: {key}")
        raise HTTPException(
            status_code=403, detail="Could not validate credentials"
        )

agent: PersonaAnalyticsAgent | None = None

class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None

@app.on_event("startup")
async def startup_event():
    global agent, PROD_LLM_API_KEY
    try:
        from dotenv import load_dotenv
        if load_dotenv():
            logger.info(".env file loaded successfully.")
            # Reload potentially updated env vars
            PROD_LLM_API_KEY = os.getenv("PROD_LLM_API_KEY")
            if not PROD_LLM_API_KEY:
                 logger.warning("PROD_LLM_API_KEY is still not set after .env load on startup.")
            else:
                logger.info("PROD_LLM_API_KEY found after .env load on startup.")
        else:
            logger.info(".env file not found or not loaded. Relying on pre-set environment variables.")
    except ImportError:
        logger.info("python-dotenv not installed, skipping .env load during startup.")

    try:
        logger.info("Initializing PersonaAnalyticsAgent during startup...")
        agent = PersonaAnalyticsAgent()
        
        # Test database connection
        if not agent.test_connection():
            logger.error("Database connection test failed during startup.")
        else:
            logger.info("Database connection test successful during startup.")
        
        # Log context caching status
        if hasattr(agent, 'high_level_agent'):
            if hasattr(agent.high_level_agent, 'cached_model') and agent.high_level_agent.cached_model is not None:
                logger.info("Context caching successfully initialized for improved performance")
            else:
                logger.info("Context caching not available - using standard approach")
                
    except ValueError as e:
        logger.critical(f"CRITICAL: PersonaAnalyticsAgent initialization failed: {e}. /query/ endpoint will fail.")
    except Exception as e_gen:
        logger.critical(f"CRITICAL: A general error occurred during agent initialization: {e_gen}. /query/ endpoint will fail.")

@app.post("/query/")
async def process_query_endpoint(request: QueryRequest, api_key: str = Depends(get_api_key)):
    if agent is None:
        logger.error("PersonaAnalyticsAgent is not initialized. Cannot process query.")
        raise HTTPException(status_code=500, detail="LLM Agent not initialized. Check server logs.")
    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        result = agent.query(request.question, session_id=request.session_id)
        return result
    except Exception as e:
        logger.error(f"Unhandled exception in /query/ endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

@app.get("/health")
async def health_check():
    if agent is None:
        return {"status": "error", "detail": "PersonaAnalyticsAgent not initialized"}
    
    # Check database connection
    db_status = "ok"
    if not agent.test_connection():
        db_status = "error"
        logger.warning("Health check: Database connection failed.")
    
    # Check context caching status
    caching_status = "disabled"
    if hasattr(agent, 'high_level_agent'):
        if hasattr(agent.high_level_agent, 'cached_model') and agent.high_level_agent.cached_model is not None:
            caching_status = "enabled"
        elif hasattr(agent.high_level_agent, 'schema_cache') and agent.high_level_agent.schema_cache is not None:
            caching_status = "enabled"
    
    return {
        "status": "ok", 
        "agent_initialized": True, 
        "database_connection": db_status,
        "context_caching": caching_status,
        "bypass_user_intent": is_bypass_user_intent_enabled(),
        "performance_optimizations": {
            "context_caching": caching_status == "enabled",
            "direct_query_mode": is_bypass_user_intent_enabled()
        },
        "features": {
            "user_intent_clarification": not is_bypass_user_intent_enabled(),
            "direct_query_processing": is_bypass_user_intent_enabled(),
            "langsmith_tracing": os.getenv('LANGSMITH_TRACING', '').lower() == 'true'
        }
    }

if __name__ == "__main__":
    # This block is primarily for local Uvicorn execution.
    # In production, Gunicorn (or another ASGI server) would manage the app.
    # Attempt to load .env here again for direct `python main.py` execution convenience.
    # The startup_event also tries to load .env, which is better for ASGI server context.
    try:
        from dotenv import load_dotenv
        if load_dotenv():
            logger.info(".env file loaded in __main__ (if present).")
            # Reload PROD_LLM_API_KEY for the main execution scope if it was set by .env
            PROD_LLM_API_KEY = os.getenv("PROD_LLM_API_KEY") 
            if not PROD_LLM_API_KEY:
                 logger.warning("PROD_LLM_API_KEY is still not set after .env load in __main__.")
            else:
                logger.info("PROD_LLM_API_KEY found after .env load in __main__.")
    except ImportError:
        logger.info("python-dotenv not installed, skipping .env load in __main__.")

    # Agent initialization is now handled by the startup_event for ASGI servers.
    # For direct `python main.py` run, startup_event will handle it before uvicorn.run.

    port = int(os.getenv("PORT", 8002))
    logger.info(f"Starting Uvicorn server on 0.0.0.0:{port} from __main__...")
    uvicorn.run(app, host="0.0.0.0", port=port) 