#!/usr/bin/env python3
"""
Test script for the Persona Analytics Agent.
This script demonstrates how to use the agent programmatically.
"""

import os
import sys
from dotenv import load_dotenv
from main import PersonaAnalyticsAgent

# Load environment variables
load_dotenv()


def test_agent_with_sample_queries():
    """Test the agent with a variety of sample queries."""
    
    # Sample queries to test different aspects of the system
    sample_queries = [
        "Which postcodes in london are most likely to visit Borough Market?",
        "What are the top 3 commercial personas by percentage in London?",
        "Which areas have the highest concentration of Persona 5?",
        "Compare commercial personas in Manchester vs Birmingham",
        "What behavioral models are associated with Camden Market?"
    ]
    
    try:
        print("🚀 Initializing Persona Analytics Agent for testing...")
        agent = PersonaAnalyticsAgent()
        
        print("🔗 Testing database connection...")
        if not agent.test_connection():
            print("❌ Database connection failed. Skipping tests.")
            return
        
        print("✅ Database connection successful!")
        print("\n" + "="*80)
        print("RUNNING SAMPLE QUERIES")
        print("="*80)
        
        for i, query in enumerate(sample_queries, 1):
            print(f"\n🔍 Test Query {i}/{len(sample_queries)}: {query}")
            print("⏳ Processing...")
            
            try:
                response = agent.query(query)
                
                # Print a condensed version of the response
                print(f"\n✅ Query {i} completed:")
                print(f"📊 Summary: {response.get('simple_summary', 'No summary')[:100]}...")
                print(f"📈 Relevance: {response.get('context_relevance', 0.0):.1%}")
                print(f"✅ Answer provided: {response.get('return_answer', False)}")
                
                if response.get('key_insights'):
                    print("🔍 Key insights:")
                    for insight in response.get('key_insights', [])[:2]:  # Show first 2 insights
                        print(f"  • {insight[:80]}...")
                
            except Exception as e:
                print(f"❌ Error processing query {i}: {e}")
            
            print("-" * 80)
        
        print("\n✅ All test queries completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")


def test_single_query(query: str):
    """Test the agent with a single query."""
    try:
        print(f"🚀 Testing single query: {query}")
        agent = PersonaAnalyticsAgent()
        
        if not agent.test_connection():
            print("❌ Database connection failed.")
            return
        
        response = agent.query(query)
        agent.print_formatted_response(response)
        
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Main test function."""
    if len(sys.argv) > 1:
        # Test with a specific query
        query = " ".join(sys.argv[1:])
        test_single_query(query)
    else:
        # Run sample query tests
        test_agent_with_sample_queries()


if __name__ == "__main__":
    main() 