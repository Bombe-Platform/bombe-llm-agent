#!/usr/bin/env python3
"""
Example script demonstrating Bombe LLM 2.0 with LangSmith tracing enabled.

This script shows how to:
1. Configure LangSmith tracing environment variables
2. Run sample queries with comprehensive tracing
3. Monitor the LangGraph workflow execution

Prerequisites:
- LangSmith account and API key
- Database connection configured
- Google Gemini API key

Usage:
    python example_with_tracing.py
"""

import os
import sys
from datetime import datetime

# Example environment setup (you would set these in your actual environment)
def setup_tracing_environment():
    """
    Set up LangSmith tracing environment variables.
    In production, these should be set in your shell or deployment config.
    """
    # Enable tracing
    os.environ['LANGSMITH_TRACING'] = 'true'
    
    # Set your LangSmith API key (replace with your actual key)
    # os.environ['LANGSMITH_API_KEY'] = 'your_langsmith_api_key_here'
    
    # Optional: Set custom project and session names
    os.environ['LANGSMITH_PROJECT'] = 'bombe-llm-demo'
    os.environ['LANGSMITH_SESSION'] = f'demo-session-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    
    # Optional: Add tags for filtering traces
    os.environ['LANGSMITH_TAGS'] = 'demo,persona-analysis,example'
    
    print("🔍 LangSmith tracing environment configured:")
    print(f"   Project: {os.environ.get('LANGSMITH_PROJECT', 'default')}")
    print(f"   Session: {os.environ.get('LANGSMITH_SESSION', 'default')}")
    print(f"   Tags: {os.environ.get('LANGSMITH_TAGS', 'none')}")
    print()

def check_environment():
    """Check if required environment variables are set."""
    required_vars = ['GOOGLE_API_KEY', 'DATABASE_URL']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables before running the example.")
        return False
    
    # Check if LangSmith API key is set for tracing
    if not os.getenv('LANGSMITH_API_KEY'):
        print("⚠️  LANGSMITH_API_KEY not set - tracing will be disabled")
        print("   Get your API key from: https://smith.langchain.com/")
        print()
    
    return True

def main():
    """Main example execution with tracing."""
    print("🚀 Bombe LLM 2.0 - LangSmith Tracing Example")
    print("=" * 50)
    print()
    
    # Check environment first
    if not check_environment():
        sys.exit(1)
    
    # Set up tracing (if API key is available)
    if os.getenv('LANGSMITH_API_KEY'):
        setup_tracing_environment()
    else:
        print("📝 Running without tracing (LANGSMITH_API_KEY not set)")
        print()
    
    # Import after environment setup to ensure tracing is configured
    try:
        from main import PersonaAnalyticsAgent
    except ImportError as e:
        print(f"❌ Error importing PersonaAnalyticsAgent: {e}")
        print("Make sure you're running from the project directory.")
        sys.exit(1)
    
    # Initialize the agent
    print("🔧 Initializing PersonaAnalyticsAgent...")
    try:
        agent = PersonaAnalyticsAgent()
        print("✅ Agent initialized successfully")
        
        # Test database connection
        if agent.test_connection():
            print("✅ Database connection successful")
        else:
            print("❌ Database connection failed")
            sys.exit(1)
        
    except Exception as e:
        print(f"❌ Error initializing agent: {e}")
        sys.exit(1)
    
    print()
    print("🎯 Running sample queries with tracing...")
    print("=" * 50)
    
    # Sample queries to demonstrate different aspects of the system
    sample_queries = [
        {
            "query": "What are the top 3 personas in London?",
            "description": "Simple geographic query - demonstrates basic SQL generation and execution"
        },
        {
            "query": "Compare commercial personas between Manchester and Birmingham",
            "description": "Comparative analysis - demonstrates multi-query planning and data synthesis"
        },
        {
            "query": "Which behavioral models are associated with shopping centers?",
            "description": "Behavioral model query - demonstrates MRP data analysis"
        }
    ]
    
    for i, example in enumerate(sample_queries, 1):
        print(f"\n📊 Example {i}: {example['description']}")
        print(f"Query: '{example['query']}'")
        print("-" * 40)
        
        try:
            # Process the query - this will be fully traced if tracing is enabled
            result = agent.query(example['query'])
            
            # Display results
            if result.get('return_answer', False):
                print("✅ Query processed successfully")
                print(f"Summary: {result['simple_summary']}")
                print(f"Key insights: {len(result['key_insights'])} insights found")
                print(f"Context relevance: {result['context_relevance']:.2f}")
            else:
                print("❌ Query processing failed")
                print(f"Error: {result['simple_summary']}")
            
        except Exception as e:
            print(f"❌ Error processing query: {e}")
        
        print()
    
    # Provide information about viewing traces
    if os.getenv('LANGSMITH_TRACING') == 'true' and os.getenv('LANGSMITH_API_KEY'):
        print("🔍 Viewing Your Traces")
        print("=" * 50)
        print("1. Visit: https://smith.langchain.com/")
        print(f"2. Select project: '{os.environ.get('LANGSMITH_PROJECT', 'default')}'")
        print(f"3. Look for session: '{os.environ.get('LANGSMITH_SESSION', 'default')}'")
        print("4. Explore the trace tree to see:")
        print("   - Complete workflow execution")
        print("   - Individual SQL queries and results")
        print("   - LLM interactions and token usage")
        print("   - Performance metrics and timing")
        print("   - Error details (if any)")
        print()
        print("📈 Key metrics to monitor:")
        print("   - Total execution time")
        print("   - Number of SQL queries generated")
        print("   - LLM token usage across planning/evaluation")
        print("   - Success rate of SQL query execution")
        print("   - Query iteration count (planning cycles)")
    else:
        print("💡 To enable tracing for future runs:")
        print("   1. Get API key: https://smith.langchain.com/")
        print("   2. Set: export LANGSMITH_API_KEY=your_key_here")
        print("   3. Set: export LANGSMITH_TRACING=true")
        print("   4. Re-run this example")
    
    print()
    print("🎉 Example completed!")

if __name__ == "__main__":
    main() 