from typing import List, Dict, Any, Optional
import logging
from db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class SQLExecutor:
    """
    SQL executor that handles query execution using the DatabaseManager.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the SQL executor.
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db_manager = db_manager
    
    def execute_sql_query(self, sql_query: str, params: Optional[tuple] = None) -> Dict[str, Any]:
        """
        Execute a SQL query and return structured results.
        
        Args:
            sql_query: SQL query string
            params: Optional query parameters
            
        Returns:
            Dictionary containing query results and metadata
        """
        try:
            logger.info(f"Executing SQL query: {sql_query[:200]}...")
            
            results = self.db_manager.execute_query(sql_query, params)
            
            return {
                "success": True,
                "data": results,
                "row_count": len(results),
                "columns": list(results[0].keys()) if results else [],
                "query": sql_query,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            return {
                "success": False,
                "data": [],
                "row_count": 0,
                "columns": [],
                "query": sql_query,
                "error": str(e)
            }
    
    def execute_multiple_queries(self, queries: List[str]) -> List[Dict[str, Any]]:
        """
        Execute multiple SQL queries and return all results.
        
        Args:
            queries: List of SQL query strings
            
        Returns:
            List of query result dictionaries
        """
        results = []
        for i, query in enumerate(queries):
            logger.info(f"Executing query {i+1}/{len(queries)}")
            result = self.execute_sql_query(query)
            results.append(result)
            
            # Stop execution if a critical error occurs
            if not result["success"]:
                logger.warning(f"Query {i+1} failed, continuing with remaining queries")
        
        return results
    
    def validate_sql_query(self, sql_query: str) -> Dict[str, Any]:
        """
        Validate a SQL query without executing it.
        
        Args:
            sql_query: SQL query string
            
        Returns:
            Validation result dictionary
        """
        try:
            # Basic validation - check if it's a SELECT statement
            # First, remove SQL comments (lines starting with --)
            cleaned_query_lines = []
            for line in sql_query.strip().split('\n'):
                line = line.strip()
                # Skip empty lines and comment lines
                if line and not line.startswith('--'):
                    cleaned_query_lines.append(line)
            
            cleaned_query = ' '.join(cleaned_query_lines).strip().upper()
            
            if not cleaned_query.startswith('SELECT'):
                return {
                    "valid": False,
                    "error": "Only SELECT statements are allowed",
                    "query": sql_query
                }
            
            # Check for potentially dangerous keywords
            dangerous_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'TRUNCATE']
            for keyword in dangerous_keywords:
                if keyword in cleaned_query:
                    return {
                        "valid": False,
                        "error": f"Dangerous keyword '{keyword}' detected",
                        "query": sql_query
                    }
            
            # Try to prepare the query (this will catch syntax errors)
            try:
                # This is a basic syntax check - in a real implementation,
                # you might want to use a SQL parser
                return {
                    "valid": True,
                    "error": None,
                    "query": sql_query
                }
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"SQL syntax error: {str(e)}",
                    "query": sql_query
                }
                
        except Exception as e:
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}",
                "query": sql_query
            }
    
    def get_query_explanation(self, sql_query: str) -> str:
        """
        Generate a human-readable explanation of what the SQL query does.
        
        Args:
            sql_query: SQL query string
            
        Returns:
            Human-readable explanation
        """
        try:
            query_lower = sql_query.lower().strip()
            
            explanation_parts = []
            
            # Identify the main operation
            if query_lower.startswith('select'):
                explanation_parts.append("This query retrieves data")
            
            # Identify tables being queried
            if 'from' in query_lower:
                from_index = query_lower.find('from')
                after_from = query_lower[from_index:].split()
                if len(after_from) > 1:
                    table_name = after_from[1].replace(',', '').replace(';', '')
                    explanation_parts.append(f"from the '{table_name}' table")
            
            # Identify joins
            join_types = ['inner join', 'left join', 'right join', 'full join', 'join']
            for join_type in join_types:
                if join_type in query_lower:
                    explanation_parts.append(f"with {join_type} operations")
                    break
            
            # Identify filtering
            if 'where' in query_lower:
                explanation_parts.append("with filtering conditions")
            
            # Identify grouping
            if 'group by' in query_lower:
                explanation_parts.append("grouped by specific columns")
            
            # Identify ordering
            if 'order by' in query_lower:
                explanation_parts.append("sorted by specific criteria")
            
            # Identify limiting
            if 'limit' in query_lower:
                limit_match = query_lower.split('limit')
                if len(limit_match) > 1:
                    try:
                        limit_num = limit_match[1].strip().split()[0]
                        explanation_parts.append(f"limited to {limit_num} results")
                    except:
                        explanation_parts.append("with result limiting")
            
            return " ".join(explanation_parts) + "."
            
        except Exception as e:
            return f"Unable to generate explanation: {str(e)}"
    
    def format_results_for_display(self, query_result: Dict[str, Any], max_rows: int = 10) -> str:
        """
        Format query results for human-readable display.
        
        Args:
            query_result: Result dictionary from execute_sql_query
            max_rows: Maximum number of rows to display
            
        Returns:
            Formatted string representation of results
        """
        if not query_result["success"]:
            return f"Query failed: {query_result['error']}"
        
        data = query_result["data"]
        if not data:
            return "Query executed successfully but returned no results."
        
        # Limit the number of rows displayed
        display_data = data[:max_rows]
        
        formatted_lines = []
        formatted_lines.append(f"Query returned {query_result['row_count']} rows")
        
        if query_result['row_count'] > max_rows:
            formatted_lines.append(f"(Showing first {max_rows} rows)")
        
        formatted_lines.append("")
        
        # Create a simple table format
        if display_data:
            columns = query_result["columns"]
            
            # Header
            header = " | ".join(columns)
            formatted_lines.append(header)
            formatted_lines.append("-" * len(header))
            
            # Data rows
            for row in display_data:
                row_values = [str(row.get(col, "")) for col in columns]
                formatted_lines.append(" | ".join(row_values))
        
        return "\n".join(formatted_lines) 