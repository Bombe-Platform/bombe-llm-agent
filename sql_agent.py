from typing import List, Dict, Any, Optional
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from sql_executor import SQLExecutor
from db_manager import DatabaseManager
from pTemplates import GLOSSARY
logger = logging.getLogger(__name__)


class SQLAgent:
    """
    SQL agent that converts natural language queries to SQL and executes them.
    """
    
    def __init__(self, sql_executor: SQLExecutor, api_key: str, db_manager: DatabaseManager):
        """
        Initialize the SQL agent.
        
        Args:
            sql_executor: SQLExecutor instance
            api_key: Google Gemini API key
        """
        self.sql_executor = sql_executor
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            google_api_key=api_key,
            temperature=0.2
        )
        
        # Database schema information
        self.db_manager = db_manager
        self.table_schema = self.db_manager.get_personas_summary_string()
        self.schema_info = self._get_schema_info(self.table_schema)

    
    def _get_schema_info(self, table_schema: str) -> str:
        """
        Get database schema information for the prompt.
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
        
        IMPORTANT NOTES:
        - Use ILIKE for case-insensitive text matching
        - Postcode searches should use normalised_pcd (lowercase, no spaces)
        - Always include persona_label when available for better readability
        - Use LEFT JOIN when joining tables
        - Limit results appropriately (typically 20 rows)
        """
        return schema_info
    
    def generate_sql_query(self, natural_language_query: str, context: Optional[str] = None) -> str:
        """
        Convert a natural language query to SQL.
        
        Args:
            natural_language_query: The user's question in natural language
            context: Optional context from previous queries
            
        Returns:
            Generated SQL query
        """
        
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""You are an expert SQL query generator for a persona and geographic analytics database.

{self.schema_info}

GLOSSARY:
{GLOSSARY}

QUERY GENERATION RULES:
1. Generate ONLY valid SELECT statements
2. Use proper JOIN syntax when combining tables
3. Always use ILIKE for text matching (case-insensitive)
4. Include appropriate LIMIT clauses (20 rows typically)
5. Use descriptive column aliases for better readability
6. Round numeric values to 2 decimal places where appropriate
7. Order results meaningfully (usually by percentage DESC or name ASC)

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

Generate a SQL query that answers the user's question. Respond with ONLY the SQL query, no explanations."""),
            
            HumanMessage(content=f"""Context: {context if context else 'No previous context'}

User Question: {natural_language_query}

Generate SQL query:""")
        ])
        
        try:
            response = self.llm.invoke(prompt_template.format_messages())
            sql_query = response.content.strip()
            
            # Clean up the SQL query
            sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            
            logger.info(f"Generated SQL query: {sql_query}")
            return sql_query
            
        except Exception as e:
            logger.error(f"Error generating SQL query: {e}")
            raise
    
    def execute_natural_language_query(self, natural_language_query: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a natural language query by converting to SQL and executing it.
        
        Args:
            natural_language_query: The user's question in natural language
            context: Optional context from previous queries
            
        Returns:
            Dictionary containing query results and metadata
        """
        try:
            # Generate SQL query
            sql_query = self.generate_sql_query(natural_language_query, context)
            
            # Validate the query
            validation_result = self.sql_executor.validate_sql_query(sql_query)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Invalid SQL generated: {validation_result['error']}",
                    "sql_query": sql_query,
                    "natural_query": natural_language_query,
                    "data": [],
                    "explanation": ""
                }
            
            # Execute the query
            execution_result = self.sql_executor.execute_sql_query(sql_query)
            
            # Generate explanation
            explanation = self.sql_executor.get_query_explanation(sql_query)
            
            return {
                "success": execution_result["success"],
                "error": execution_result.get("error"),
                "sql_query": sql_query,
                "natural_query": natural_language_query,
                "data": execution_result["data"],
                "row_count": execution_result["row_count"],
                "columns": execution_result["columns"],
                "explanation": explanation,
                "formatted_results": self.sql_executor.format_results_for_display(execution_result)
            }
            
        except Exception as e:
            logger.error(f"Error executing natural language query: {e}")
            return {
                "success": False,
                "error": str(e),
                "sql_query": "",
                "natural_query": natural_language_query,
                "data": [],
                "explanation": ""
            }
    
    def analyze_query_intent(self, natural_language_query: str) -> Dict[str, Any]:
        """
        Analyze the intent and complexity of a natural language query.
        
        Args:
            natural_language_query: The user's question
            
        Returns:
            Analysis of query intent and suggested approach
        """
        
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an expert at analyzing data queries for a persona and geographic analytics system.

Analyze the user's query and determine:
1. What type of data they're asking for (personas, geographic, behavioral models)
2. What geographic level they're interested in (national, regional, local authority, ward, postcode)
3. Whether the query requires multiple sub-queries or can be answered with a single query
4. What specific personas or geographic areas they mention

Respond with a JSON-like analysis including:
- query_type: "persona_distribution" | "geographic_analysis" | "behavioral_model" | "comparison" | "trend"
- geographic_level: "national" | "regional" | "local_authority" | "ward" | "postcode" | "multiple"
- complexity: "simple" | "moderate" | "complex"
- requires_joins: boolean
- specific_personas: list of mentioned personas
- specific_locations: list of mentioned locations
- suggested_approach: brief description of how to answer this query"""),
            
            HumanMessage(content=f"Analyze this query: {natural_language_query}")
        ])
        
        try:
            response = self.llm.invoke(prompt_template.format_messages())
            analysis = response.content.strip()
            
            # For now, return a simple analysis - in production you'd parse the JSON
            return {
                "analysis": analysis,
                "query": natural_language_query
            }
            
        except Exception as e:
            logger.error(f"Error analyzing query intent: {e}")
            return {
                "analysis": f"Error analyzing query: {str(e)}",
                "query": natural_language_query
            } 