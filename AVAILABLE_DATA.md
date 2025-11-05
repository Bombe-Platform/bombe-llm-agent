# Available Data in Bombe LLM 2.0

This document lists all data available to the LLM system for querying and analysis.

---

## Database Tables & Views

### Persona Data

1. **personas** - Persona definitions and characteristics
2. **normal_value_uk_view** - National-level persona percentages across the UK
3. **normal_value_regions_with_labels_view** - Persona distribution by UK regions
4. **normal_value_la_with_labels_view** - Persona distribution by Local Authority (council/borough level)
5. **normal_value_wards_with_labels_view** - Persona distribution by electoral wards
6. **normal_value_pcon_with_labels_view** - Persona distribution by parliamentary constituencies
7. **normal_value_pcd_with_labels_view** - Persona distribution by postcodes

### Behavioral & Prediction Data

8. **mrp_data_persona_models** - Behavioral prediction models broken down by persona
9. **mrp_data_non_persona_models** - General behavioral models (persona-independent)

### Geographic Mapping

10. **uk_geographies_basic_with_names_view** - Geographic relationships and hierarchies (links postcodes to wards to local authorities to regions)

### Session Data

11. **chat_history** - Conversation history by session
12. **chat_session** - Session metadata

---

## Persona Categories

### Demographic Personas (9 total)

13. Persona 1
14. Persona 2
15. Persona 3
16. Persona 4
17. Persona 5
18. Persona 6
19. Persona 7
20. Persona 8
21. Persona 9

### Commercial Personas (7 total)

22. Bombe 1
23. Bombe 2
24. Bombe 3
25. Bombe 4
26. Bombe 5
27. Bombe 6
28. Bombe 7

---

## Geographic Levels

29. National (UK-wide statistics)
30. Regional (e.g., London, North West, South East)
31. Local Authority (council/borough level)
32. Ward (electoral district level)
33. Parliamentary Constituency
34. Postcode (alphanumeric codes like E11 3QA)
35. Output Area (small geographic areas used by postal service)

---

## Behavioral Model Types

36. **Persona Models** - Behavior likelihood by persona (predictor = persona)
37. **Persona Consumer Models** - Behavioral factors for specific personas (predictor = convenience, loyalty, etc.)
38. **Non-Persona Models** - General behavioral drivers (predictor = activities, attitudes)

---

## Data Attributes Available

### Persona Attributes

39. Persona code (e.g., "Persona 1", "Bombe 2")
40. Persona name
41. Persona label (human-readable description)
42. Persona description (detailed characteristics)
43. Persona type (Demographic or Commercial)

### Geographic Attributes

44. Region code
45. Region name
46. Local authority code
47. Local authority name
48. Ward code
49. Ward name
50. Constituency code
51. Constituency name
52. Postcode (formatted, e.g., "E11 3QA")
53. Normalised postcode (lowercase, no spaces, e.g., "e113qa")
54. Output area code

### Percentage/Distribution Data

55. Average percentage (avg_pct) - Persona proportion in geographic area
56. Percentage (pct) - Statistical significance/impact score

### Behavioral Model Attributes

57. Model name (e.g., "London markets", "British Airways usage")
58. Dependent variable (behavior being predicted)
59. Predictor variable (factor influencing behavior)
60. Impact score/Interest score (normalized coefficient, ~-0.01 to 0.01)

---

## Domain Knowledge (Glossary)

61. Definition of Demographic Category personas
62. Definition of Commercial Category personas
63. Explanation of persona model types
64. Geographic hierarchy relationships
65. MRP (Multilevel Regression with Poststratification) behavioral prediction concepts
66. Statistical significance thresholds
67. Postcode format specifications
68. Output area definitions

---

## Contextual Information

69. User's previous questions (via session chat_history)
70. Previous analysis results (via session chat_history)
71. Clarification conversation context (from UserIntentAgent)
72. Database schema definitions
73. SQL query generation rules
74. Column definitions and data types

---

## Constraints & Rules

75. Everyone belongs to exactly ONE Demographic persona (1-9)
76. Everyone belongs to exactly ONE Commercial persona (Bombe 1-7)
77. Only statistically significant factors are displayed in behavioral models
78. Impact scores are normalized as percentages
79. Geographic areas have hierarchical relationships (postcode → ward → LA → region → national)

---

## Total Data Points Available: 79
