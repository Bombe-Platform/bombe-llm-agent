import psycopg2
import os
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Database manager for handling all I/O operations with the persona and geographic database.
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize the database manager.
        
        Args:
            connection_string: PostgreSQL connection string. If None, will try to read from environment.
        """
        self.connection_string = connection_string or os.getenv(
            'DATABASE_URL', 
            'postgresql://username:password@localhost:5432/database_name'
        )
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        """
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)
            yield conn
        except psycopg2.Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dictionaries.
        
        Args:
            query: SQL query string
            params: Query parameters for prepared statements
            
        Returns:
            List of dictionaries representing query results
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    columns = [desc[0] for desc in cursor.description]
                    results = cursor.fetchall()
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except psycopg2.Error as e:
            logger.error(f"Query execution error: {e}")
            logger.error(f"Query: {query}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test the database connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1;")
                    cursor.fetchone()
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get schema information for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column information dictionaries
        """
        query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = %s
        ORDER BY ordinal_position;
        """
        return self.execute_query(query, (table_name,))
    
    def get_available_tables(self) -> List[str]:
        """
        Get list of available tables in the database.
        
        Returns:
            List of table names
        """
        query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
        """
        results = self.execute_query(query)
        return [row['table_name'] for row in results]
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get sample data from a table.
        
        Args:
            table_name: Name of the table
            limit: Number of rows to return
            
        Returns:
            List of sample row dictionaries
        """
        query = f"SELECT * FROM {table_name} LIMIT %s;"
        return self.execute_query(query, (limit,))
    
    def execute_count_query(self, table_name: str, where_clause: str = "") -> int:
        """
        Execute a count query on a table.
        
        Args:
            table_name: Name of the table
            where_clause: Optional WHERE clause
            
        Returns:
            Count of rows
        """
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        result = self.execute_query(query)
        return result[0]['count'] if result else 0
    
    def get_personas_summary_string(self) -> str:
        """
        Fetches all personas (excluding description) and formats them into a nice string.

        Returns:
            A string summarizing all personas.
        """
        query = "SELECT id, code, name, label, type FROM personas ORDER BY id;"
        try:
            personas_data = self.execute_query(query)
            
            if not personas_data:
                return "No persona data found."

            # Determine column widths for formatting (simple approach)
            # More sophisticated alignment could be added if needed
            headers = ["ID", "Code", "Name", "Label", "Type"]
            
            # Create header string
            output_lines = [" | ".join(headers)]
            output_lines.append("-" * (sum(len(h) for h in headers) + (len(headers) -1) * 3)) # Separator line

            for persona in personas_data:
                row_values = [
                    str(persona.get('id', 'N/A')),
                    str(persona.get('code', 'N/A')),
                    str(persona.get('name', 'N/A')),
                    str(persona.get('label', 'N/A')),
                    str(persona.get('type', 'N/A'))
                ]
                output_lines.append(" | ".join(row_values))
            
            return "\n".join(output_lines)

        except Exception as e:
            logger.error(f"Error fetching personas summary: {e}")
            return f"Error fetching personas summary: {str(e)}"

    def get_chat_history_by_session_id(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Fetches chat history for a given session_id.

        Args:
            session_id: The UUID of the chat session.

        Returns:
            A list of chat history records, ordered by creation time.
        """
        # Note: This query joins chat_history with chat_session
        # to filter by the session_id UUID.
        query = """
        SELECT source, payload
        FROM chat_history
        WHERE chat_session_id = %s
        ORDER BY created_at ASC;
        """
        try:
            logger.info(f"Fetching chat history for session_id: {session_id}")
            history = self.execute_query(query, (session_id,))
            logger.info(f"Found {len(history)} history entries for session_id: {session_id}")
            return history
        except Exception as e:
            logger.error(f"Error fetching chat history for session {session_id}: {e}", exc_info=True)
            return [] 