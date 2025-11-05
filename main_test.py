#!/usr/bin/env python3
"""
Main application for the LangGraph persona analytics agent.
"""

import os
import logging
from db_manager import DatabaseManager
from sql_executor import SQLExecutor
from sql_agent import SQLAgent
from high_level_agent import HighLevelAgent
from user_intent_agent import UserIntentAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PersonaAnalyticsAgent:
    """
    Main application class that coordinates all components.
    """
    
    def __init__(self):
        """Initialize the analytics agent."""
        # Get configuration from environment
        self.api_key = os.getenv('GOOGLE_API_KEY')
        self.db_connection_string = os.getenv('DATABASE_URL')
        
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        # Initialize components
        logger.info("Initializing database manager...")
        self.db_manager = DatabaseManager(self.db_connection_string)
        
        logger.info("Initializing SQL executor...")
        self.sql_executor = SQLExecutor(self.db_manager)
        
        logger.info("Initializing SQL agent...")
        self.sql_agent = SQLAgent(self.sql_executor, self.api_key, self.db_manager)
        
        logger.info("Initializing high-level agent...")
        self.high_level_agent = HighLevelAgent(self.sql_agent, self.api_key, self.db_manager)
        
        logger.info("Initializing user intent agent...")
        self.user_intent_agent = UserIntentAgent(self.api_key, self.db_manager)
        
        logger.info("Persona Analytics Agent initialized successfully!")
    
    def test_connection(self) -> bool:
        """Test database connection."""
        return self.db_manager.test_connection()
    
    def query(self, user_question: str) -> dict:
        """
        Process a user query and return structured results.
        
        Args:
            user_question: The user's natural language question
            
        Returns:
            Dictionary containing analysis results
        """
        logger.info(f"Received user question: {user_question}")
        
        try:
            # First, clarify the query with UserIntentAgent
            logger.info("Clarifying user intent...")
            clarified_query, intent_context = self.user_intent_agent.clarify_and_refine_query(user_question)
            
            if not clarified_query:
                logger.warning("Query clarification did not result in a usable query.")
                return {
                    "simple_summary": "Could not understand the query after clarification.",
                    "key_insights": ["Query unclear"],
                    "detailed_explanation": intent_context,
                    "context_relevance": 0.0,
                    "return_answer": False
                }
            
            logger.info(f"Clarified query: {clarified_query}")
            logger.info(f"Intent context: {intent_context}")

            # Then, process the clarified query with HighLevelAgent
            logger.info(f"Processing clarified query with HighLevelAgent: {clarified_query}")
            result = self.high_level_agent.process_query(clarified_query, intent_context=intent_context)
            
            return result
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "simple_summary": f"Error processing query: {str(e)}",
                "key_insights": ["Query processing failed"],
                "detailed_explanation": f"An error occurred while processing your query: {str(e)}",
                "context_relevance": 0.0,
                "return_answer": False
            }
    
    def print_formatted_response(self, response: dict):
        """
        Print a formatted response to the console.
        
        Args:
            response: Response dictionary from query method
        """
        print("\n" + "="*80)
        print("PERSONA ANALYTICS RESULTS")
        print("="*80)
        
        print(f"\n📊 SIMPLE SUMMARY:")
        print(f"{response.get('simple_summary', 'No summary available')}")
        
        print(f"\n🔍 KEY INSIGHTS:")
        insights = response.get('key_insights', [])
        if insights:
            for i, insight in enumerate(insights, 1):
                print(f"  {i}. {insight}")
        else:
            print("  No key insights available")
        
        print(f"\n📋 DETAILED EXPLANATION:")
        print(f"{response.get('detailed_explanation', 'No detailed explanation available')}")
        
        print(f"\n📈 ANALYSIS METRICS:")
        print(f"  • Context Relevance: {response.get('context_relevance', 0.0):.1%}")
        print(f"  • Answer Provided: {'Yes' if response.get('return_answer', False) else 'No'}")
        
        print("\n" + "="*80)


def interactive_mode(agent: PersonaAnalyticsAgent):
    """
    Run the agent in interactive mode.
    
    Args:
        agent: PersonaAnalyticsAgent instance
    """
    print("\n🚀 Welcome to the Persona Analytics Agent!")
    print("Ask questions about persona distributions, geographic analysis, or behavioral models.")
    print("Type 'quit', 'exit', or 'q' to stop.\n")
    
    while True:
        try:
            user_input = input("❓ Your question: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q', '']:
                print("👋 Thank you for using the Persona Analytics Agent!")
                break
            
            # The clarification process is now part of agent.query()
            # The UserIntentAgent will print its own prompts for clarification
            print("\n⏳ Understanding and processing your query...")
            response = agent.query(user_input)
            
            # Display results
            agent.print_formatted_response(response)
            
        except KeyboardInterrupt:
            print("\n\n👋 Thank you for using the Persona Analytics Agent!")
            break
        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
            logger.error(f"Error in interactive mode: {e}")


def single_query_mode(agent: PersonaAnalyticsAgent, query: str):
    """
    Process a single query and exit.
    
    Args:
        agent: PersonaAnalyticsAgent instance
        query: The query to process
    """
    print(f"\n🔍 Initial query: {query}")
    print("\n⏳ Understanding and processing your query...")
    # agent.query() now handles the clarification then processing
    response = agent.query(query)
    agent.print_formatted_response(response)


def main():
    """Main entry point."""
    try:
        # Initialize the agent
        print("🚀 Initializing Persona Analytics Agent...")
        agent = PersonaAnalyticsAgent()
        
        # Test database connection
        print("🔗 Testing database connection...")
        if not agent.test_connection():
            print("❌ Database connection failed. Please check your DATABASE_URL.")
            return
        
        print("✅ Database connection successful!")
        
        # Check for command line arguments
        import sys
        
        if len(sys.argv) > 1:
            # Single query mode
            query = " ".join(sys.argv[1:])
            single_query_mode(agent, query)
        else:
            # Interactive mode
            interactive_mode(agent)
            
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("Please make sure you have set the required environment variables:")
        print("  - GOOGLE_API_KEY: Your Google Gemini API key")
        print("  - DATABASE_URL: Your PostgreSQL connection string (optional)")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.error(f"Unexpected error in main: {e}")


if __name__ == "__main__":
    main() 