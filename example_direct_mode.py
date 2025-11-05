#!/usr/bin/env python3
"""
Example script demonstrating Bombe LLM 2.0 in Direct Mode (bypassing user intent clarification).

This script shows how to:
1. Enable direct query processing mode
2. Process well-formed queries without clarification
3. Compare performance between standard and direct modes

Prerequisites:
- Database connection configured
- Google Gemini API key

Usage:
    python example_direct_mode.py
"""

import os
import sys
import time
from datetime import datetime

def setup_direct_mode():
    """Enable direct mode by setting the bypass environment variable."""
    os.environ['BYPASS_USER_INTENT_AGENT'] = 'true'
    print("🚀 Direct Mode enabled - queries will bypass user intent clarification")
    print()

def setup_standard_mode():
    """Disable direct mode to use standard processing."""
    os.environ['BYPASS_USER_INTENT_AGENT'] = 'false'
    print("🔄 Standard Mode enabled - queries will go through user intent clarification")
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
    
    return True

def process_query_with_timing(agent, query, description):
    """Process a query and measure execution time."""
    print(f"📊 {description}")
    print(f"Query: '{query}'")
    print("-" * 40)
    
    start_time = time.time()
    
    try:
        result = agent.query(query)
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Display results
        if result.get('return_answer', False):
            print("✅ Query processed successfully")
            print(f"Summary: {result['simple_summary'][:100]}{'...' if len(result['simple_summary']) > 100 else ''}")
            print(f"Key insights: {len(result['key_insights'])} insights found")
            print(f"Context relevance: {result['context_relevance']:.2f}")
            bypass_status = "Direct Mode" if result.get('bypass_user_intent', False) else "Standard Mode"
            print(f"Processing mode: {bypass_status}")
            print(f"⏱️  Execution time: {execution_time:.2f} seconds")
        else:
            print("❌ Query processing failed or needs clarification")
            print(f"Response: {result['simple_summary']}")
            if result.get('requires_clarification', False):
                print("💬 This query would need clarification in standard mode")
        
    except Exception as e:
        print(f"❌ Error processing query: {e}")
        execution_time = time.time() - start_time
    
    print()
    return execution_time

def main():
    """Main example execution comparing standard and direct modes."""
    print("🚀 Bombe LLM 2.0 - Direct Mode vs Standard Mode Example")
    print("=" * 60)
    print()
    
    # Check environment first
    if not check_environment():
        sys.exit(1)
    
    # Import after environment check
    try:
        from main import PersonaAnalyticsAgent
    except ImportError as e:
        print(f"❌ Error importing PersonaAnalyticsAgent: {e}")
        print("Make sure you're running from the project directory.")
        sys.exit(1)
    
    # Well-formed queries that work well in direct mode
    test_queries = [
        {
            "query": "What are the top 5 personas by percentage in London?",
            "description": "Geographic query - should work well in both modes"
        },
        {
            "query": "Show me Persona 3 distribution across North West regions",
            "description": "Specific persona and region query - ideal for direct mode"
        },
        {
            "query": "Which local authorities have the highest Bombe 2 percentages?",
            "description": "Commercial persona query - direct and specific"
        }
    ]
    
    print("🎯 Testing queries in both processing modes...")
    print("=" * 60)
    
    total_direct_time = 0
    total_standard_time = 0
    
    for i, example in enumerate(test_queries, 1):
        print(f"\n{'='*20} TEST QUERY {i} {'='*20}")
        
        # Test in Direct Mode first
        print("\n🚀 Testing in DIRECT MODE:")
        setup_direct_mode()
        
        try:
            agent_direct = PersonaAnalyticsAgent()
            direct_time = process_query_with_timing(
                agent_direct, 
                example['query'], 
                example['description']
            )
            total_direct_time += direct_time
        except Exception as e:
            print(f"❌ Error initializing agent in direct mode: {e}")
            continue
        
        # Test in Standard Mode
        print("🔄 Testing in STANDARD MODE:")
        setup_standard_mode()
        
        try:
            agent_standard = PersonaAnalyticsAgent()
            standard_time = process_query_with_timing(
                agent_standard, 
                example['query'], 
                example['description']
            )
            total_standard_time += standard_time
        except Exception as e:
            print(f"❌ Error initializing agent in standard mode: {e}")
            continue
        
        # Compare performance
        if direct_time and standard_time:
            speed_improvement = ((standard_time - direct_time) / standard_time) * 100
            if speed_improvement > 0:
                print(f"⚡ Direct Mode was {speed_improvement:.1f}% faster")
            else:
                print(f"⚡ Standard Mode was {abs(speed_improvement):.1f}% faster")
        
        print()
    
    # Summary
    print("\n📈 PERFORMANCE SUMMARY")
    print("=" * 60)
    if total_direct_time and total_standard_time:
        print(f"Total Direct Mode time: {total_direct_time:.2f} seconds")
        print(f"Total Standard Mode time: {total_standard_time:.2f} seconds")
        overall_improvement = ((total_standard_time - total_direct_time) / total_standard_time) * 100
        if overall_improvement > 0:
            print(f"🚀 Overall, Direct Mode was {overall_improvement:.1f}% faster")
        else:
            print(f"🔄 Overall, Standard Mode was {abs(overall_improvement):.1f}% faster")
    
    print("\n💡 RECOMMENDATIONS")
    print("=" * 60)
    print("✅ Use DIRECT MODE when:")
    print("   - You have well-formed, specific queries")
    print("   - Building APIs or automated systems")
    print("   - Processing batch queries")
    print("   - You want faster response times")
    print("   - Queries are unambiguous (specific personas, locations, etc.)")
    print()
    print("✅ Use STANDARD MODE when:")
    print("   - Queries might be ambiguous or unclear")
    print("   - Interactive use where clarification is helpful")
    print("   - Users might need guidance on query formation")
    print("   - Exploring data without knowing exact parameters")
    print()
    print("🎉 Example completed!")

if __name__ == "__main__":
    main() 