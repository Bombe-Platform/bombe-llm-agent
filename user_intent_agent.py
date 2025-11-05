from typing import Tuple, Dict, Any
import logging
import hashlib
from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage, HumanMessage
from db_manager import DatabaseManager
from pTemplates import GLOSSARY

logger = logging.getLogger(__name__)

class UserIntentAgent:
    """
    Agent responsible for clarifying and refining the user's query 
    through interaction. Includes prompt caching for improved performance.
    
    Caching Features:
    - System Message Caching: The static system message (containing schema and glossary) 
      is cached at initialization to avoid regenerating it.
    - Prompt Caching: Generated prompts are cached based on query and chat history 
      to avoid recreating identical prompts.
    - Response Caching: LLM responses are cached to avoid repeated API calls for 
      identical prompts.
    - Cache Statistics: Track cache hits/misses and hit rates for performance monitoring.
    - Runtime Cache Control: Enable/disable caching and clear caches as needed.
    
    Cache Benefits:
    - Reduced API costs by avoiding duplicate LLM calls
    - Faster response times for repeated or similar queries
    - Improved performance for interactive sessions
    - Better resource utilization in high-traffic scenarios
    """

    def __init__(self, api_key: str, db_manager: DatabaseManager, llm_model: str = "gemini-2.5-flash", enable_caching: bool = True):
        """
        Initialize the UserIntentAgent.

        Args:
            api_key: Google Gemini API key.
            db_manager: DatabaseManager instance.
            llm_model: The LLM model to use.
            enable_caching: Whether to enable prompt and response caching.
        """
        self.api_key = api_key
        self.db_manager = db_manager
        self.llm_model = llm_model  # Store model name for caching
        self.llm = ChatGoogleGenerativeAI(
            model=llm_model,
            google_api_key=api_key,
            temperature=0.4 
        )
        self.table_schema = self.db_manager.get_personas_summary_string()
        self.glossary = GLOSSARY
        
        # Caching configuration
        self.enable_caching = enable_caching
        self._prompt_cache = {}  # Cache for generated prompts
        self._response_cache = {}  # Cache for LLM responses
        self._system_message_cache = None  # Cache for the static system message
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Pre-generate and cache the static system message
        if self.enable_caching:
            self._system_message_cache = self._generate_system_message()

    def _generate_cache_key(self, original_query: str, chat_history_str: str = "") -> str:
        """
        Generate a cache key for the given query and chat history.
        
        Args:
            original_query: The user's query.
            chat_history_str: The chat history string.
            
        Returns:
            A hash string to use as cache key.
        """
        # Normalize inputs for consistent caching
        normalized_query = original_query.strip().lower()
        normalized_history = chat_history_str.strip()
        
        # Create a composite string and hash it
        composite = f"{normalized_query}|{normalized_history}|{self.llm_model}"
        return hashlib.md5(composite.encode()).hexdigest()

    def _generate_system_message(self) -> str:
        """
        Generate the static system message content that includes schema and glossary.
        This is cached since it doesn't change during the agent's lifetime.
        
        Returns:
            The system message content string.
        """
        return f"""You are an AI assistant helping a user clarify their data analysis query. 
Your goal is to understand exactly what the user wants to know and ensure their query is specific and actionable.
You have access to the following information about the available data:

Data Schema Summary:
{self.table_schema}

Glossary of Terms:
{self.glossary}

Based on the user's query and the chat history (if any), do one of the following:
1. If the query is clear and actionable, respond with "QUERY_CLEAR: [refined query]". The refined query should be the user's query, possibly rephrased for clarity or to better match the available data.
2. If the query is ambiguous, or unclear, ask a specific clarifying question to help narrow it down. Respond with "ASK_CLARIFICATION: [your question]".
3. If you can propose a more specific version of their query based on common use cases or the available data, respond with "SUGGEST_REFINEMENT: [proposed refined query]". The user can then accept, reject, or modify this.

Do not assume that the user knows what is available in the data. The user may not know what data is available to query. The user may not know exactly what the data is called that they're looking for. Do not ask them to clarify the same thing more than once. Try to allow for insufficient knowledge on the users part and give QUERY_CLEAR or SUGGEST_REFINEMENT if it doesn't seem like they'll be able to clarify further.
Keep your questions concise. Reference the schema or glossary if it helps the user. Do not ask the user for specific models or data points, this can be figured out when the answer is generated.
For example, if a user asks "Tell me about rich people", you could ask "When you say 'rich people', are you referring to a specific income bracket, or perhaps one of the 'Affluence' segments in our persona data? We have segments like 'High Earners Not Yet Rich' and 'Established Affluence'."
"""

    def _generate_clarification_prompt(self, original_query: str, chat_history_str: str = "") -> ChatPromptTemplate:
        """
        Generates a prompt to ask for clarification or suggest a refined query.
        Uses caching to avoid regenerating identical prompts.
        """
        if not self.enable_caching:
            # Generate prompt without caching
            system_message = self._generate_system_message()
            return ChatPromptTemplate.from_messages([
                SystemMessage(content=system_message),
                HumanMessage(content=f"""Chat History:
{chat_history_str}

User's current query: {original_query}

Your response:""")
            ])
        
        # Check prompt cache
        cache_key = self._generate_cache_key(original_query, chat_history_str)
        
        if cache_key in self._prompt_cache:
            self._cache_hits += 1
            logger.debug(f"Prompt cache hit for key: {cache_key[:8]}...")
            return self._prompt_cache[cache_key]
        
        self._cache_misses += 1
        logger.debug(f"Prompt cache miss for key: {cache_key[:8]}...")
        
        # Use cached system message
        system_message = self._system_message_cache or self._generate_system_message()
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_message),
            HumanMessage(content=f"""Chat History:
{chat_history_str}

User's current query: {original_query}

Your response:""")
        ])
        
        # Cache the prompt
        self._prompt_cache[cache_key] = prompt
        
        # Limit cache size to prevent memory issues
        if len(self._prompt_cache) > 100:
            # Remove oldest entries (simple FIFO)
            oldest_key = next(iter(self._prompt_cache))
            del self._prompt_cache[oldest_key]
        
        return prompt

    def _invoke_llm_with_cache(self, prompt: ChatPromptTemplate) -> str:
        """
        Invoke the LLM with response caching.
        
        Args:
            prompt: The prompt to send to the LLM.
            
        Returns:
            The LLM response content.
        """
        if not self.enable_caching:
            response = self.llm.invoke(prompt.format_messages())
            return response.content.strip()
        
        # Generate cache key based on the formatted prompt
        formatted_messages = prompt.format_messages()
        prompt_text = "\n".join([msg.content for msg in formatted_messages])
        cache_key = hashlib.md5(f"{prompt_text}|{self.llm_model}".encode()).hexdigest()
        
        if cache_key in self._response_cache:
            logger.debug(f"Response cache hit for key: {cache_key[:8]}...")
            return self._response_cache[cache_key]
        
        logger.debug(f"Response cache miss for key: {cache_key[:8]}...")
        
        # Get response from LLM
        response = self.llm.invoke(formatted_messages)
        response_content = response.content.strip()
        
        # Cache the response
        self._response_cache[cache_key] = response_content
        
        # Limit cache size
        if len(self._response_cache) > 50:
            oldest_key = next(iter(self._response_cache))
            del self._response_cache[oldest_key]
        
        return response_content

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get caching statistics.
        
        Returns:
            Dictionary with cache statistics.
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "cache_enabled": self.enable_caching,
            "prompt_cache_size": len(self._prompt_cache),
            "response_cache_size": len(self._response_cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate_percent": round(hit_rate, 2),
            "system_message_cached": self._system_message_cache is not None
        }

    def clear_cache(self):
        """Clear all caches."""
        self._prompt_cache.clear()
        self._response_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("All caches cleared")

    def set_caching_enabled(self, enabled: bool):
        """
        Enable or disable caching at runtime.
        
        Args:
            enabled: Whether to enable caching.
        """
        if enabled and not self.enable_caching:
            # Re-initialize caching
            self.enable_caching = True
            if not self._system_message_cache:
                self._system_message_cache = self._generate_system_message()
            logger.info("Caching enabled")
        elif not enabled and self.enable_caching:
            # Disable caching and clear cache
            self.enable_caching = False
            self.clear_cache()
            logger.info("Caching disabled")
        else:
            logger.info(f"Caching already {'enabled' if enabled else 'disabled'}")

    def clarify_and_refine_query(self, initial_query: str, external_chat_history: list[dict] | None = None, max_interactions: int = 5, interactive: bool = False) -> Dict[str, Any]:
        """
        Interacts with the user to clarify and refine their query.

        Args:
            initial_query: The user's initial question.
            external_chat_history: A list of previous chat messages, e.g., [{"role": "user", "content": "..."}, {"role": "ai", "content": "..."}].
            max_interactions: Maximum number of clarification attempts.
            interactive: If True, uses input() for interactive clarification. For API use, this should be False.

        Returns:
            A dictionary containing:
            - 'status': One of 'clarified', 'ask_clarification', 'suggest_refinement', 'error', 'max_interactions'.
            - 'value': The refined query, question for the user, or suggested query.
            - 'summary': A summary of the conversation.
        """
        current_query = initial_query
        print(f"[DEBUG] initial_query: {repr(initial_query)}") 

        interaction_summary_str = ""
        if external_chat_history:
            for message in external_chat_history:
                role = message.get("role", "unknown").capitalize()
                content = message.get("content", "")
                interaction_summary_str += f"{role}: {content}\n"
        interaction_summary_str += f"User: {str(initial_query)}\n" # Start current turn with user's query
        
        for i in range(max_interactions):
            logger.info(f"Clarification attempt {i+1} for query: {current_query}")
            
            # Use interaction_summary_str which now includes external history + current turn summary
            prompt = self._generate_clarification_prompt(current_query, interaction_summary_str) 
            
            try:
                response = self._invoke_llm_with_cache(prompt)
                ai_response_text = response.strip()
                logger.info(f"LLM response for clarification: {ai_response_text}")

                if ai_response_text.startswith("QUERY_CLEAR:"):
                    refined_query = ai_response_text.replace("QUERY_CLEAR:", "").strip()
                    interaction_summary_str += f"AI: Query is clear. Refined query: {refined_query}\n"
                    logger.info(f"Query clarified: {refined_query}")
                    return {"status": "clarified", "value": refined_query, "summary": interaction_summary_str}

                elif ai_response_text.startswith("ASK_CLARIFICATION:"):
                    question_to_user = ai_response_text.replace("ASK_CLARIFICATION:", "").strip()
                    interaction_summary_str += f"AI asks: {question_to_user}\n"

                    if not interactive:
                        logger.info("Non-interactive mode: returning clarification question to API caller.")
                        return {"status": "ask_clarification", "value": question_to_user, "summary": interaction_summary_str}
                    
                    print(f"\n🤖 AI Assistant: {question_to_user}")
                    # This agent is designed for interactive CLI, FastAPI needs non-interactive
                    # For FastAPI, this branch means the query isn't clear yet. We might need to return a signal.
                    # For now, we assume this agent won't be used interactively via FastAPI.
                    # If it were, we'd need to return the question_to_user to the FastAPI caller.
                    # As this path uses input(), it will block in a server environment.
                    # For now, this modification assumes clarify_and_refine_query might be used
                    # in a mode where it *doesn't* expect further input() within this call. 
                    # The primary goal here is to feed history *into* the first LLM call.
                    # For a non-interactive server, if it reaches ASK_CLARIFICATION, it means the query + history wasn't enough.
                    # It should probably return a special status or the clarification question.
                    # For now, let's assume for server use, it should reach QUERY_CLEAR with history if possible.
                    # This part of the code with input() will not be hit by the FastAPI flow if history is effective.
                    user_response = input("Your answer: ").strip()
                    interaction_summary_str += f"User: {user_response}\n"
                    current_query = f"{current_query}. User clarification: {user_response}"

                elif ai_response_text.startswith("SUGGEST_REFINEMENT:"):
                    suggested_query = ai_response_text.replace("SUGGEST_REFINEMENT:", "").strip()
                    interaction_summary_str += f"AI suggests: {suggested_query}\n"

                    if not interactive:
                        logger.info("Non-interactive mode: returning suggested refinement to API caller.")
                        return {"status": "suggest_refinement", "value": suggested_query, "summary": interaction_summary_str}

                    print(f'\n🤖 AI Assistant: I can refine your query to: "{suggested_query}"')
                    print("   Type 'yes' to accept, 'no' to keep your original query, or provide a new query.")
                    # Similar to above, input() is problematic for server. 
                    user_feedback = input("Your choice: ").strip().lower()
                    
                    interaction_summary_str += f"User: {user_feedback}\n"
                    if user_feedback == 'yes':
                        current_query = suggested_query
                        logger.info(f"User accepted refinement: {current_query}")
                        prompt_confirm = self._generate_clarification_prompt(current_query, interaction_summary_str)
                        response_confirm = self._invoke_llm_with_cache(prompt_confirm)
                        ai_response_confirm_text = response_confirm.strip()
                        if ai_response_confirm_text.startswith("QUERY_CLEAR:"):
                             refined_query = ai_response_confirm_text.replace("QUERY_CLEAR:", "").strip()
                             interaction_summary_str += f"AI: Query is clear. Refined query: {refined_query}\n"
                             logger.info(f"Query clarified: {refined_query}")
                             return {"status": "clarified", "value": refined_query, "summary": interaction_summary_str}
                    elif user_feedback == 'no':
                        pass
                    else:
                        current_query = user_feedback
                        logger.info(f"User provided new query: {current_query}")
                else:
                    logger.warning(f"Unexpected LLM response format: {ai_response_text}")
                    interaction_summary_str += f"AI: {ai_response_text}\n"

                    if not interactive:
                        return {"status": "ask_clarification", "value": ai_response_text, "summary": interaction_summary_str}

                    print(f"\n🤖 AI Assistant: {ai_response_text}")
                    print("   Could you please rephrase your query or provide more details?")
                    # Problematic input() call
                    user_response = input("Your refined query: ").strip()
                    interaction_summary_str += f"User: {user_response}\n"
                    current_query = user_response if user_response else current_query

            except Exception as e:
                logger.error(f"Error during clarification interaction: {e}", exc_info=True) # Added exc_info
                interaction_summary_str += f"Error: {str(e)}\n"
                return {"status": "error", "value": str(e), "summary": interaction_summary_str}
        
        logger.warning(f"Max interactions reached. Proceeding with query: {current_query}")
        interaction_summary_str += "Max interactions reached.\n"
        # Renamed interaction_summary to interaction_summary_str to avoid conflict if we pass it directly
        return {"status": "clarified", "value": current_query, "summary": interaction_summary_str} 

    def get_sample_schema_and_glossary_info(self) -> str:
        """
        Returns a string containing the table schema and glossary for display or context.
        """
        return f"""Data Schema Summary:
{self.table_schema}

Glossary of Terms:
{self.glossary}"""

# Example Usage (for testing user_intent_agent.py directly)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Import required components for full agent testing
    from sql_executor import SQLExecutor
    from sql_agent import SQLAgent
    from high_level_agent import HighLevelAgent
    
    # Mock DatabaseManager for standalone testing
    class MockDBManager:
        def get_personas_summary_string(self):
            # Correctly formatted multiline string
            return """
            Available tables:
            - personas_summary: Contains aggregated persona data by various geographic levels.
              Columns: geo_level (TEXT), geo_name (TEXT), persona_segment (TEXT), population_count (INTEGER), household_count (INTEGER)
            - persona_definitions: Describes each persona segment.
              Columns: persona_segment (TEXT), description (TEXT), typical_age_range (TEXT), common_traits (TEXT)
            - geo_hierarchy: Defines relationships between geographic areas.
              Columns: parent_geo_id (TEXT), child_geo_id (TEXT), level_name (TEXT)
            """
        def test_connection(self):
            return True

    # --- IMPORTANT ---
    # Replace with your actual API key for testing
    # Make sure to set this environment variable or replace the string directly.
    import os
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_GOOGLE_API_KEY") 
    DB_CONNECTION_STRING = os.getenv("DATABASE_URL", None)
    # --- IMPORTANT ---
    
    if GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY":
        print("Please replace 'YOUR_GOOGLE_API_KEY' with your actual Google API key or set the GOOGLE_API_KEY environment variable to test.")
    else:
        print("🚀 Initializing User Intent Agent and HighLevelAgent for testing...")
        
        # Use real DatabaseManager if connection string is available, otherwise use mock
        if DB_CONNECTION_STRING:
            print("Using real database connection...")
            db_manager = DatabaseManager(DB_CONNECTION_STRING)
            if not db_manager.test_connection():
                print("❌ Database connection failed. Falling back to mock database.")
                db_manager = MockDBManager()
        else:
            print("No DATABASE_URL provided. Using mock database for testing...")
            db_manager = MockDBManager()
        
        # Initialize all agents for full pipeline testing
        try:
            sql_executor = SQLExecutor(db_manager)
            sql_agent = SQLAgent(sql_executor, GOOGLE_API_KEY, db_manager)
            high_level_agent = HighLevelAgent(sql_agent, GOOGLE_API_KEY, db_manager)
            intent_agent = UserIntentAgent(api_key=GOOGLE_API_KEY, db_manager=db_manager)
            
            full_pipeline_available = True
            print("✅ Full agent pipeline initialized successfully!")
        except Exception as e:
            print(f"⚠️ Failed to initialize full pipeline: {e}")
            print("Falling back to UserIntentAgent only...")
            db_manager = MockDBManager()
            intent_agent = UserIntentAgent(api_key=GOOGLE_API_KEY, db_manager=db_manager)
            full_pipeline_available = False
        
        print("\n🤖 User Intent Agent Test Mode")
        if full_pipeline_available:
            print("✅ Full pipeline mode: Refined queries will be processed by HighLevelAgent")
        else:
            print("⚠️ Intent-only mode: Only query clarification will be tested")
        print("Type 'quit' or 'exit' to stop.")
        print("You can start by asking a general question, e.g., 'Tell me about affluent people in London'")
        
        print("\nHere's some information about the data I have access to:")
        print(intent_agent.get_sample_schema_and_glossary_info())
        
        while True:
            try:
                initial_user_query = input("\n❓ Your initial question: ").strip()
                if initial_user_query.lower() in ['quit', 'exit', 'q']:
                    print("👋 Exiting test mode.")
                    break
                
                if not initial_user_query:
                    continue
                    
                print("\n⏳ Clarifying your query...")
                result_dict = intent_agent.clarify_and_refine_query(initial_user_query, interactive=True)
                
                clarified_query = result_dict.get("value", "No query was refined.")
                summary = result_dict.get("summary", "No summary available.")
                status = result_dict.get("status")

                print("\n" + "="*50)
                if status == 'clarified':
                    print("✅ Query Clarification Complete")
                    print(f"Final Refined Query: {clarified_query}")
                    
                    if full_pipeline_available:
                        print("\n⏳ Processing refined query with HighLevelAgent...")
                        try:
                            final_result = high_level_agent.process_query(clarified_query, intent_context=summary)
                            
                            print("\n🎯 HighLevelAgent Results:")
                            print(f"Simple Summary: {final_result.get('simple_summary', 'N/A')}")
                            print(f"Key Insights: {final_result.get('key_insights', [])}")
                            print(f"Detailed Explanation: {final_result.get('detailed_explanation', 'N/A')}")
                            
                            if final_result.get('return_answer'):
                                print("✅ Query processed successfully!")
                            else:
                                print("⚠️ HighLevelAgent was unable to provide a complete answer.")
                                
                        except Exception as e:
                            print(f"❌ Error processing query with HighLevelAgent: {e}")
                            logger.error(f"HighLevelAgent error: {e}", exc_info=True)
                    else:
                        print("(Full pipeline not available - would pass to HighLevelAgent in real scenario)")
                        
                else:
                    print(f"⚠️ Query Clarification ended with status: {status}")
                    print(f"Final Value: {clarified_query}")

                print("\nIntent Clarification Summary:")
                print(summary)
                
                # Display cache statistics
                cache_stats = intent_agent.get_cache_stats()
                print(f"\n📊 Cache Statistics:")
                print(f"   Cache enabled: {cache_stats['cache_enabled']}")
                print(f"   Prompt cache size: {cache_stats['prompt_cache_size']}")
                print(f"   Response cache size: {cache_stats['response_cache_size']}")
                print(f"   Cache hits: {cache_stats['cache_hits']}")
                print(f"   Cache misses: {cache_stats['cache_misses']}")
                print(f"   Hit rate: {cache_stats['hit_rate_percent']}%")
                print("="*50)
                
            except KeyboardInterrupt:
                print("\n\n👋 Exiting test mode.")
                break
            except Exception as e:
                print(f"\n❌ An error occurred in test mode: {e}")
                logger.error(f"Error in test mode: {e}", exc_info=True)