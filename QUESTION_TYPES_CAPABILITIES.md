# Question Types & Capabilities

This document describes the types of questions the Bombe LLM 2.0 service can handle.

---

## Question Complexity Levels

### 1. Simple Queries (Single-Step)

**Characteristics:**
- Answered with a single SQL query
- Direct lookup from one table/view
- Clear and specific
- Typically 1 iteration

**Examples:**
1. "What are the top 5 personas in London?"
2. "Show me persona percentages for postcode E11 3QA"
3. "Which region has the highest Bombe 2 concentration?"
4. "What is the national average for Persona 3?"

---

### 2. Moderate Queries (Multi-Step)

**Characteristics:**
- Require 2-3 SQL queries
- May need data from multiple tables
- Require some context building
- Typically 2-3 iterations

**Examples:**
1. "Compare commercial personas between Manchester and Birmingham"
2. "Show me Persona 3 distribution across North West regions"
3. "Which behavioral models are associated with Camden Market?"
4. "What personas are most likely to shop at Tesco?"

---

### 3. Complex Queries (Multi-Iteration)

**Characteristics:**
- Require multiple rounds of data gathering
- May need exploratory SQL queries to determine next steps
- Build on previous results
- Typically 3-4 iterations

**Examples:**
1. "Which postcodes in London are most likely to visit Borough Market and what are their demographic characteristics?"
2. "Compare shopping behaviors across affluent personas in different regions"
3. "What drives Ryanair usage across different demographic and commercial segments?"
4. "Analyze the relationship between geographic location and shopping center preferences"

---

## Question Categories by Data Type

### 4. Geographic Distribution Queries

**What they ask:** Where are personas located?

**Capabilities:**
- Persona concentrations by geography
- Top personas in specific areas
- Geographic patterns and hotspots
- Multi-level geographic analysis (region → LA → ward → postcode)

**Examples:**
1. "Where in the UK has the highest concentration of Persona 5?"
2. "Show me commercial persona distribution across London boroughs"
3. "Which wards have the most diverse persona mix?"
4. "What is the persona makeup of the South East region?"

---

### 5. Comparative Analysis Queries

**What they ask:** How do areas or personas differ?

**Capabilities:**
- Side-by-side comparisons
- Multiple location analysis
- Persona contrast
- Regional differences

**Examples:**
1. "Compare Persona 3 percentages between Manchester and Liverpool"
2. "How does the North West differ from the South East in commercial personas?"
3. "Which cities have similar persona distributions to London?"
4. "Compare Bombe 1 vs Bombe 7 concentrations nationally"

---

### 6. Behavioral & Predictive Queries

**What they ask:** What drives behaviors? Who does what?

**Capabilities:**
- Behavioral model lookup
- Persona-specific behaviors
- Factor analysis
- Predictive insights

**Examples:**
1. "Which personas are most likely to visit Borough Market?"
2. "What factors influence shopping at Aldi for Persona 3?"
3. "What drives British Airways usage across different personas?"
4. "Which commercial personas prefer shopping centers?"

---

### 7. Ranking & Top-N Queries

**What they ask:** What are the top/bottom items?

**Capabilities:**
- Top personas by percentage
- Highest/lowest concentrations
- Ranked lists
- Threshold-based filtering

**Examples:**
1. "What are the top 3 commercial personas in Birmingham?"
2. "Which 5 regions have the highest Persona 8 percentages?"
3. "Show me the least common personas in London"
4. "Top 10 postcodes for Bombe 2"

---

### 8. Postcode-Specific Queries

**What they ask:** Tell me about this specific postcode

**Capabilities:**
- Exact postcode lookup
- Postcode pattern matching (e.g., "postcodes starting with M1")
- Persona breakdowns for postcodes
- Links to behavioral models

**Examples:**
1. "What personas live in postcode E11 3QA?"
2. "Show me all postcodes in Manchester with high Bombe 1 percentages"
3. "Which postcodes in London are most likely to shop at luxury stores?"
4. "Tell me about the demographic makeup of SW1 postcodes"

---

### 9. Exploratory & Trend Queries

**What they ask:** Show me patterns or insights

**Capabilities:**
- Pattern identification
- Trend analysis across geographies
- Cluster identification
- Insight generation

**Examples:**
1. "How does persona distribution vary across the North West region?"
2. "Show me patterns in commercial persona geography"
3. "What trends exist in behavioral models for urban vs rural areas?"
4. "Are there clusters of specific personas in London?"

---

### 10. Definitional & Explanatory Queries

**What they ask:** What is/who are these personas?

**Capabilities:**
- Persona definitions
- Category explanations
- Data availability questions
- Methodology clarification

**Examples:**
1. "What is Persona 3?"
2. "Tell me about Bombe personas"
3. "How are commercial personas different from demographic ones?"
4. "What data do you have for Liverpool?"

---

## Question Handling Modes

### 11. Clear & Well-Formed Questions

**Processing:**
- In Direct Mode: Immediately processed
- In Standard Mode: Quick clarification, then processed
- Usually 1-2 iterations
- High context relevance

**Example:**
"What are the top 5 personas by percentage in London?"

---

### 12. Ambiguous Questions (Require Clarification)

**Processing:**
- Standard Mode: UserIntentAgent asks clarifying questions
- Direct Mode: Best-effort interpretation (may be suboptimal)
- Multiple clarification rounds possible
- Refined into specific query

**Example:**
- **User:** "Tell me about rich people in London"
- **System:** "When you say 'rich people', are you referring to a specific income bracket, or perhaps one of the 'Affluence' segments in our persona data?"

---

### 13. Multi-Part Questions

**Processing:**
- Broken down into sub-queries
- Answered iteratively
- Results synthesized
- Comprehensive final answer

**Example:**
"Which personas are in Manchester, what are their shopping behaviors, and how do they compare to Birmingham?"

---

## Query Limitations & Boundaries

### What the Service CAN Handle:

1. ✅ Natural language queries (no SQL knowledge required)
2. ✅ Multi-step reasoning and planning
3. ✅ Complex geographic hierarchies
4. ✅ Behavioral model analysis
5. ✅ Comparative analysis (up to ~5 locations)
6. ✅ Iterative refinement (up to 4 iterations by default)
7. ✅ Ambiguous query clarification (Standard Mode)
8. ✅ Follow-up questions (with session support)
9. ✅ Context from previous conversation (FastAPI with session_id)

### What the Service CANNOT Handle:

1. ❌ Non-SELECT SQL operations (INSERT, UPDATE, DELETE)
2. ❌ Data outside the persona/geographic/behavioral datasets
3. ❌ Real-time data (only historical/current database state)
4. ❌ Predictions beyond what's in MRP models
5. ❌ Geographic areas not in UK
6. ❌ Custom persona definitions
7. ❌ Aggregations requiring external calculations
8. ❌ Questions requiring data joins not in schema

---

## Response Quality Indicators

### High Context Relevance (0.8-1.0)

**Question characteristics:**
- Specific geographic area mentioned
- Clear persona reference
- Available in database
- Straightforward data lookup

### Medium Context Relevance (0.5-0.7)

**Question characteristics:**
- Somewhat broad scope
- Requires interpretation
- Partial data available
- Multiple iterations needed

### Low Context Relevance (0.0-0.4)

**Question characteristics:**
- Too vague or broad
- Data not fully available
- Outside system capabilities
- Clarification failed

---

## Performance by Question Type

### Fast Processing (<10 seconds)

- Simple geographic lookups
- Top-N queries
- Single postcode queries
- Direct persona definitions

### Moderate Processing (10-30 seconds)

- Comparative analysis
- Multi-location queries
- Behavioral model lookups
- 2-3 iteration queries

### Slower Processing (30-60 seconds)

- Complex multi-step analysis
- Exploratory queries
- 3-4 iteration workflows
- Large geographic comparisons

---

## Special Capabilities

### 14. Conversational Context (Standard Mode with Session)

**What it enables:**
- Follow-up questions that reference previous queries
- Progressive refinement
- "Tell me more about that"
- Context-aware clarification

**Example Conversation:**
1. User: "Show me personas in London"
2. System: [Returns results]
3. User: "How does Manchester compare?"
4. System: [Understands "compare to London results"]

---

### 15. Suggestion & Refinement (Standard Mode)

**What it does:**
- Suggests better query formulations
- Offers specific alternatives
- Guides users to available data
- Educates on data structure

**Example:**
- **User:** "Tell me about shopping"
- **System:** "I can refine your query to: 'What are the shopping behavior patterns across commercial personas?' Would you like me to analyze that?"

---

## Total Question Types: 15 categories

## Summary Capability Matrix

| Question Type | Complexity | Typical Iterations | Mode Preference | Avg Response Time |
|--------------|------------|-------------------|----------------|-------------------|
| Simple Lookup | Low | 1 | Either | <10s |
| Moderate Multi-step | Medium | 2-3 | Either | 10-30s |
| Complex Analysis | High | 3-4 | Either | 30-60s |
| Geographic Distribution | Low-Medium | 1-2 | Either | <20s |
| Comparative | Medium | 2-3 | Either | 15-30s |
| Behavioral/Predictive | Medium | 2-3 | Either | 15-30s |
| Ranking/Top-N | Low | 1 | Either | <10s |
| Postcode-Specific | Low | 1 | Either | <10s |
| Exploratory/Trend | High | 3-4 | Either | 30-60s |
| Definitional | Low | 1 | Direct | <10s |
| Ambiguous | Variable | Variable | Standard | 20-60s |
| Multi-part | High | 3-4 | Either | 30-60s |
| Conversational | Variable | Variable | Standard | Variable |
