from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import openai
import json
from enum import Enum
from datetime import datetime
import logging
from dotenv import load_dotenv
import os
from openai import OpenAI
import ast
from pprint import pprint
from openai import AsyncOpenAI
import asyncio
import traceback
import re


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class QueryContext:
    original_query: str
    timestamp: str
    query_id: str
    feedback: Optional[str] = None
    filter_values: Optional[Dict[str, Any]] = None  # Added filter_values field


@dataclass
class SubProblem:
    category: str
    description: str
    dependencies: List[str]
    priority: int
    context_reference: Dict[str, Any]
    query_segment: str
    relevant_feedback: Optional[str] = None
    relevant_filters: Optional[Dict[str, Any]] = None  # Added relevant_filters field


@dataclass
class Solution:
    sub_problem: SubProblem
    proposed_solution: Dict
    confidence: float
    reasoning: str
    validation_notes: List[str]


class Agent:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)

    def call_llm(self, messages: List[Dict]) -> str:
        try:
            print(json.dumps(messages, indent=2))
            response = self.client.chat.completions.create(
                model="gpt-4o", messages=messages, temperature=0.7
            )
            print((response.choices[0].message.content))
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in LLM call: {e}")
            raise

    async def call_llm_async(self, messages: List[Dict]) -> str:
        try:
            response = await self.async_client.chat.completions.create(
                model="gpt-4o", messages=messages, temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in async LLM call: {e}")
            raise


class FilterAwareIntentAnalysisAgent(Agent):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.system_prompt = """You are an expert recruitment query analyzer specializing in breaking down complex queries into ATOMIC logical sub-problems while prioritizing feedback incorporation and considering existing filter values.

        Your PRIMARY RESPONSIBILITIES (in order of importance):
        1. FEEDBACK FOCUS: Deeply analyze any provided feedback and make it the central guiding principle of your analysis
        2. ATOMICITY: Break down queries into truly atomic sub-problems (each addressing ONE specific aspect only)
        3. FILTER AWARENESS: Carefully consider existing filter values when analyzing the query
        4. INTENT UNDERSTANDING: Comprehend the main intent of the recruitment query
        
        Key principles for FEEDBACK incorporation:
        - Treat feedback as the highest priority guidance for your analysis
        - Explicitly connect each piece of feedback to specific atomic sub-problems
        - If feedback contradicts the original query, prioritize the feedback's direction
        - Use feedback to refine, modify, or completely change your understanding of requirements
        - For each atomic sub-problem, include SPECIFIC quotes from the feedback that are relevant
        
        Key principles for ATOMIC SUB-PROBLEM creation:
        - Each sub-problem must address EXACTLY ONE specific requirement or concept
        - If a potential sub-problem addresses multiple requirements, split it further
        - Test each sub-problem with the question: "Does this solve exactly one thing?"
        - Avoid compound requirements within a single sub-problem
        - Ensure each sub-problem has a singular, clear focus
        
        For each ATOMIC sub-problem, you must:
        1. Focus on a single, specific aspect of the requirement
        2. Connect relevant feedback specifically to this atomic element
        3. Identify which specific filter values (if any) relate to this single element
        4. Assign appropriate priority (1-5, 1 being highest)
        5. Explicitly state dependencies on other atomic sub-problems
        
        Your analysis process should follow these steps:
        1. First, thoroughly analyze the feedback to identify key guidance points
        2. Second, examine existing filter values to understand constraints
        3. Third, break down the query into the smallest possible atomic sub-problems
        4. Finally, connect feedback points and filter values to each atomic sub-problem
        
        Output JSON structure:
        {
            "main_intent": "Clear statement of primary goal",
            "feedback_analysis": "COMPREHENSIVE analysis of how feedback modifies the query - this should be DETAILED",
            "filter_analysis": "Analysis of how existing filter values constrain the solution",
            "thinking": "Step-by-step breakdown of how you arrived at your atomic sub-problems",
            "analysis_notes": ["Detailed thoughts and reasoning"],
            "potential_challenges": ["Identified challenges"],
            "sub_problems": [
                {
                    "category": "job_title/location/education/etc",
                    "description": "Description of this SINGLE atomic requirement",
                    "dependencies": ["other_category_ids"],
                    "priority": "1-5",
                    "context_reference": {"query_segment": "relevant part of original query"},
                    "query_segment": "exact text from original query",
                    "relevant_feedback": "SPECIFIC feedback directly relevant to this atomic sub-problem",
                    "relevant_filters": {"filter_name": "filter_value"} 
                }
            ],
            "confidence_score": 0.0
        }"""

    def analyze(self, query_context: QueryContext) -> Dict:
        feedback_section = ""
        if query_context.feedback:
            feedback_section = f"""
            CRITICAL FEEDBACK INFORMATION:
            The following feedback has been provided about previous attempts to solve this query:
            {query_context.feedback}
            
            THIS FEEDBACK IS YOUR PRIMARY GUIDANCE. You must:
            1. Make this feedback the central focus of your analysis
            2. For each atomic sub-problem, identify specific parts of the feedback that apply to it
            3. Use feedback to reinterpret or modify the original query when needed
            4. If feedback conflicts with the original query, prioritize the feedback's direction
            5. Extract specific quotes from the feedback for each atomic sub-problem
            """

        filter_section = ""
        if query_context.filter_values:
            filter_section = f"""
            EXISTING FILTER VALUES:
            {json.dumps(query_context.filter_values, indent=2)}
            
            Consider these filter values when creating atomic sub-problems:
            1. For each atomic sub-problem, identify specific relevant filter values
            2. Understand how each filter constrains or guides that atomic requirement
            3. Note where existing filters might already address parts of the query
            """

        prompt = f"""Analyze this recruitment query, focusing on breaking it down into TRULY ATOMIC sub-problems: 
        {query_context.original_query}

        {feedback_section}
        
        {filter_section}

        IMPORTANT ANALYSIS INSTRUCTIONS:
        1. PRIMARILY focus on the feedback (if provided) to guide your understanding
        2. Break the query into the SMALLEST POSSIBLE atomic sub-problems (each addressing EXACTLY ONE thing)
        3. Test each sub-problem by asking: "Is this addressing exactly one specific requirement?"
        4. If a sub-problem addresses multiple things, split it further
        5. Connect each piece of feedback to specific atomic sub-problems using direct quotes
        6. Match relevant filter values to each atomic sub-problem
        
        Show your detailed reasoning process, highlighting how you:
        1. Interpreted the feedback
        2. Broke the query into truly atomic sub-problems
        3. Connected feedback to each atomic element
        4. Considered existing filter values in your analysis
        """

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        response = self.call_llm(messages)
        response = eval(response[response.find("{") : response.rfind("}") + 1])
        return response


class FilterAwareSubProblemAnalysisAgent(Agent):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.system_prompt = """You are an expert in solving specific recruitment sub-problems, with the ability to incorporate targeted feedback and existing filter values.
        IMPORTANT: Focus ONLY on the specific sub-problem assigned to you. While you may reference
        the original query for context, your solution should be specifically targeted to your assigned sub-problem.

        ## FILTER SYSTEM REFERENCE GUIDE
        This comprehensive guide explains all available filters, their proper usage, and how they're processed in the backend:

        1. SKILL/KEYWORDS
        - Purpose: Match profiles containing specific skills, expertise, or specializations
        - Format: List of strings (e.g., ["Python", "project management", "recruiting"])
        - Usage: Profiles must contain at least ONE of the listed skills/keywords
        - Example: {"SKILL": ["Python", "machine learning", "data science"]}
        - Backend mapping: Matched in 'summary', 'skills', 'headline', 'experience.title', and 'experience.job_summary'
        - Note: Skills are matched in all titles and job summaries regardless of timeline

        2. INDUSTRY
        - Purpose: Filter profiles by industry experience
        - Format: List of strings (e.g., ["Finance", "Technology", "Healthcare"])
        - Usage: Displays profiles with experience in any of the specified industries
        - Example: {"INDUSTRY": ["Healthcare", "Pharmaceuticals"]}
        - Backend mapping: Matched in 'experience.company_description', 'experience.company_industry', 'experience.company_speciality', 'experience.title', and 'experience.job_summary'
        - Timeline options:
          * Current: Matched where 'experience.end' is null
          * Past: Matched where 'experience.end' is not null
          * Current or Past: Ignores 'experience.end' and matches all
          * Current and Past: Matches where 'experience.end' is null AND where not null

        3. COMPANY
        - Purpose: Filter by current or past company association
        - Format: List of strings representing companies or company characteristics or company prompt
        - Usage: Identifies relevant companies based on extracted information
        - Example: {"COMPANY": ["Microsoft and similar companies", "companies based in USA"]}
        - Backend mapping: Matched in 'experience.company'
        - Timeline options:
          * Current: Matched where 'experience.end' is null
          * Past: Matched where 'experience.end' is not null
          * Current or Past: Ignores 'experience.end' and matches all
          * Current and Past: Matches where 'experience.end' is null AND where not null

        4. LOCATION
        - Purpose: Filter profiles by geographic location
        - Format: List of strings (e.g., ["New York", "Europe", "Countries near Egypt"])
        - Usage: Identifies specific locations or regions, including nearby areas when specified
        - Example: {"LOCATION": ["San Francisco", "Bay Area"]}
        - Backend mapping: Matched in 'location_full_path'

        5. EDUCATION
        - Purpose: Filter by academic qualifications
        - Format: List of dictionaries with degree and optional major
        - Usage: Matches profiles with specific educational backgrounds
        - Example: {"EDUCATION": [{"degree": "Master's", "major": "Business Administration"}]}
        - Backend mapping: Matched in 'education' array of objects

        6. NAME
        - Purpose: Search for specific individuals by name
        - Format: List of strings (e.g., ["John Doe", "Will Smith"])
        - Usage: Only returns profiles with exact name matches
        - Example: {"NAME": ["John Smith", "Maria Garcia"]}
        - Backend mapping: Matched against 'full_name', 'first_name', and 'last_name'

        7. SCHOOL
        - Purpose: Filter by educational institution
        - Format: List of strings (e.g., ["Stanford University", "Yale University"])
        - Usage: Profiles must be associated with at least one of the specified schools
        - Example: {"SCHOOL": ["Harvard University", "MIT"]}
        - Backend mapping: Matched in 'education.school'

        8. COMPANY_TENURE
        - Purpose: Filter by length of time in CURRENT company or industry
        - Format: String representing duration (e.g., "2 years", "5+ years")
        - Usage: Only shows profiles with specified tenure in their current company
        - Example: {"COMPANY_TENURE": "3"}
        - Backend mapping: Calculated from 'experience.start' to current date where 'experience.end' is null

        9. ROLE_TENURE
        - Purpose: Filter by length of time in CURRENT role or position
        - Format: String representing duration (e.g., "2 years", "5+ years")
        - Usage: Only shows profiles with specified tenure in their current role
        - Example: {"ROLE_TENURE": "2+ years"}
        - Backend mapping: Calculated from 'experience.start' to current date where 'experience.end' is null for the current role

        10. TOTAL_WORKING_YEARS
        - Purpose: Filter by overall career duration
        - Format: List of two integers representing minimum and maximum years
        - Usage: Shows profiles with total experience within the specified range
        - Example: {"TOTAL_WORKING_YEARS": [5, 10]}
        - Backend mapping: Matched against 'total_tenure' which is expressed in days in the backend

        11. GENDER
        - Purpose: Filter profiles by gender
        - Format: List containing "Female" if female-only search is required
        - Usage: When specified as ["Female"], only female profiles are shown
        - Example: {"GENDER": ["Female"]}
        - Backend mapping: Matched in 'gender' field

        12. AGE
        - Purpose: Filter profiles by age category
        - Format: List of strings from predefined categories: "Under 25", "Over 50", "Over 65"
        - Usage: Shows profiles matching the specified age categories
        - Example: {"AGE": ["Over 50"]}
        - Backend mapping: Matched against 'age' field

        13. ETHNICITY
        - Purpose: Filter profiles by ethnic background
        - Format: List of strings from predefined ethnicities: "Asian", "African", "Hispanic", etc.
        - Usage: Only applied when explicitly mentioned in the context of ethnicity
        - Example: {"ETHNICITY": ["South Asian", "Hispanic"]}
        - Backend mapping: Matched in 'ethnicity' field

        14. CURRENT_OWNERSHIP
        - Purpose: Filter by company ownership type
        - Format: List of strings from: "Public", "Private", "VC Funded", "Private Equity Backed"
        - Usage: Only applied when explicitly mentioned; shows profiles at companies with that ownership
        - Example: {"CURRENT_OWNERSHIP": ["VC Funded"]}
        - Backend mapping: Matched against company metadata

        15. JOB_TITLE/BUSINESS_FUNCTION
        - Purpose: Filter by job roles or business functions
        - Format: List of strings representing job titles or functions
        - Usage: Matches specific roles or entire functional areas
        - Example: {"JOB_TITLE": ["Chief Sales Officer", "Sales Director"]}
        - Backend mapping: Matched in 'experience.title'
        - Timeline options:
          * Current: Matched where 'experience.end' is null
          * Past: Matched where 'experience.end' is not null
          * Current or Past: Ignores 'experience.end' and matches all
          * Current and Past: Matches where 'experience.end' is null AND where not null
        - Note: May also include company size check on number of people at the company

        16. MANAGEMENT_LEVEL
        - Purpose: Filter by management hierarchy
        - Format: List of strings from predefined levels like "C-Suite/Chiefs", "Director", etc.
        - Usage: Only extracted when user asks for entire management domains
        - Example: {"MANAGEMENT_LEVEL": ["C-Suite/Chiefs", "Executive VP or Sr. VP"]}
        - Backend mapping: Matched in 'experience.title', and behaves with the same timeline relations as JOB_TITLE
        - Important note: For C-Suites, all titles that lie in C-Suites are matched. For Director, the substring "Director" is matched to yield all people at that management level.

        ## IMPORTANT FILTER RELATIONS AND INTERACTIONS
        
        1. Job Title and Management Level
           - Both are mapped to 'experience.title'
           - Their relation is AND 
           - Example: If Job Title is 'Sales' and Management Level is 'Director', both substrings must be present in 'experience.title'
        
        2. Timeline Relations
           - Current: Matched where 'experience.end' is null
           - Past: Matched where 'experience.end' is not null
           - Current or Past: Ignores 'experience.end' and matches all
           - Current and Past: Requires matches in both current and past experiences
        
        3. Filter Ternary Relations
           - The system uses this relation: (Industry OR Companies) AND Job Title AND Management Level AND Skills AND Location AND Experience
           - This determines how multiple filters interact with each other

        4. Company can have ["CompanyName", "CompanyPrompt"] format. If the company name is not found, the company prompt is used to call company generation service to retrieve all relevant companies.

        For this specific sub-problem, follow this detailed analysis process:
        1. Initial Assessment
           - Understand the specific requirement of THIS sub-problem
           - Review any specific feedback provided for this sub-problem
           - Review any existing filter values relevant to this sub-problem
           - Identify relevant filter categories for THIS component
           - Review dependencies and constraints specific to THIS aspect

        2. Feedback and Filter Integration
           - Carefully analyze how the provided feedback applies to this specific sub-problem
           - Consider how existing filter values constrain or guide your solution
           - Adjust your approach based on the feedback and filter values
           - Address any issues or improvements mentioned in the feedback
           - Build upon or refine existing filter values

        3. Solution Generation
           - FILTER-FIRST APPROACH: Each solution MUST manipulate specific filters
           - Try to generate 3 proposed solution for THIS specific sub-problem
           - For each solution, identify exactly which filters to use and what values to assign
           - ALL solutions must involve creating, modifying, or refining filter values
           - Be precise about filter values - use exact formats as shown in the reference guide
           - Generate multiple filter-based approaches for THIS specific requirement
           - Consider edge cases and limitations
           - Ensure solution stays focused on the assigned sub-problem
           - Apply the lessons learned from feedback
           - Consider compatibility with existing filter values
        
        4. Solution Evaluation
           - Score each filter-based solution (1-10)
           - List pros and cons specific to this filter approach
           - Consider implementation feasibility of the filter configuration
           - Evaluate how well the filter solution addresses the feedback
           - Evaluate how well the filter solution integrates with existing filter values

        5. Final Selection
           - Choose optimal filter-based solution for this specific component
           - Document reasoning for this specific filter configuration
           - Provide confidence score for the selected filter approach
           - Explain how feedback influenced your final filter choice
           - Explain how existing filter values influenced your final filter configuration

        CRITICAL: Every proposed solution MUST involve manipulating one or more filters. Solutions that don't directly specify filter actions are invalid.

        Remember: Stay focused on your assigned sub-problem. Don't try to solve the entire query.

        Output structure:
        {
            "sub_problem_analysis": {
                "original_context": "",
                "thought_process": "",
                "interpreted_requirement": "",
                "relevant_filters": {
                    "identified_filters": [],
                    "rationale": ""
                },
                "filter_integration": "",
                "feedback_integration": "",
                "proposed_solutions": [
                    {
                        "thinking": "",
                        "filter_actions": {
                            "filter_name": "description of action with specific values"
                        },
                        "feedback_addressed": "",
                        "identified_interaction_or_filter_relation" : ""
                        "implementation_notes": "",
                        "approach": "",
                        "score": 0,
                        "pros": [],
                        "cons": [],
                        "filter_compatibility": ""
                    }
                ],
                "selected_solution": {
                    "thinking_for_selection": "",
                    "filter_values": {
                        "filter_name": "specific_value"
                    },
                    "confidence": 0.0,
                    "reasoning": "",
                    "validation_notes": [],
                    "feedback_influence": "",
                    "filter_influence": ""
                }
            }
        }"""

    async def solve_async(
        self, sub_problem: SubProblem, query_context: QueryContext
    ) -> Solution:
        feedback_section = ""
        if sub_problem.relevant_feedback:
            feedback_section = f"""
            The following feedback is specifically relevant to this sub-problem:
            {sub_problem.relevant_feedback}
            
            Make sure your solution directly addresses this feedback.
            """
        elif query_context.feedback:
            feedback_section = f"""
            General feedback on the query (consider only what's relevant to this sub-problem):
            {query_context.feedback}
            """

        filter_section = ""
        if sub_problem.relevant_filters:
            filter_section = f"""
            The following filter values are specifically relevant to this sub-problem:
            {json.dumps(sub_problem.relevant_filters, indent=2)}
            
            Consider these filter values when developing your solution.
            You can build upon, refine, or modify these filter values as needed.
            """
        elif query_context.filter_values:
            filter_section = f"""
            General filter values from previous processing (consider only what's relevant to this sub-problem):
            {json.dumps(query_context.filter_values, indent=2)}
            """

        prompt = f"""Focus on solving this specific sub-problem:

        Sub-problem Category: {sub_problem.category}
        Sub-problem Description: {sub_problem.description}
        Specific Query Segment to Address: {sub_problem.query_segment}

        {feedback_section}
        
        {filter_section}

        For reference only, original query context: {query_context.original_query}

        IMPORTANT INSTRUCTIONS:
        1. Your solution MUST involve manipulating specific filters
        2. Each proposed solution must specify exactly which filters to create/modify/refine
        3. Be precise about filter values and formats according to the reference guide
        4. Every solution must result in concrete filter values
        5. Don't just describe what to do - specify exact filter configurations

        Remember: Focus only on solving this specific sub-problem component.
        Do not attempt to solve the entire query.

        Show your detailed reasoning process for this specific component,
        including how you've incorporated the relevant feedback and filter values."""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        response = await self.call_llm_async(messages)
        response = response[response.find("{") : response.rfind("}") + 1]
        return json.loads(response)


class IntegrationAgent(Agent):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.system_prompt = """You are an expert in integrating and validating recruitment filter solutions and converting them into specific JSON filter formats.

        Your critical responsibilities:
        1. Analyze all solutions thoroughly
        2. Provide detailed reasoning for each decision
        3. Convert the solutions into the exact filter format
        4. Only include relevant filters with valid values
        5. Ensure all values are logically consistent
        6. Consider feedback and existing filter values in your integration

        ## FILTER SYSTEM REFERENCE GUIDE
        This comprehensive guide explains how filters are mapped to backend data:

        1. SKILL/KEYWORDS
        - Backend mapping: Matched in 'summary', 'skills', 'headline', 'experience.title', and 'experience.job_summary'
        - Note: Skills are matched in all titles and job summaries regardless of timeline

        2. INDUSTRY
        - Backend mapping: Matched in 'experience.company_description', 'experience.company_industry', 'experience.company_speciality', 'experience.title', and 'experience.job_summary'
        - Timeline options:
          * Current: Matched where 'experience.end' is null
          * Past: Matched where 'experience.end' is not null
          * Current or Past: Ignores 'experience.end' and matches all
          * Current and Past: Matches where 'experience.end' is null AND where not null

        3. COMPANY
        - Backend mapping: Matched in 'experience.company'
        - Timeline options apply as with Industry

        4. LOCATION
        - Backend mapping: Matched in 'location_full_path'
        - Timeline options apply when combined with other filters

        5. JOB_TITLE/BUSINESS_FUNCTION
        - Backend mapping: Matched in 'experience.title'
        - Timeline options apply as with Industry
        - May include company size check on number of people at the company

        6. MANAGEMENT_LEVEL
        - Backend mapping: Matched in 'experience.title'
        - Important note: For C-Suites, all titles that lie in C-Suites are matched. For Director, the substring "Director" is matched.
        - Timeline options apply as with Industry

        7. EDUCATION/SCHOOL/DEGREE
        - Backend mapping: Matched in 'education' array of objects

        8. EXPERIENCE FILTERS (TENURE)
        - TOTAL_WORKING_YEARS: Matched against 'total_tenure' (expressed in days in backend)
        - COMPANY_TENURE: Calculated for current company where 'experience.end' is null
        - ROLE_TENURE: Calculated for current role where 'experience.end' is null

        ## IMPORTANT FILTER RELATIONS
        
        1. Job Title and Management Level
           - Both are mapped to 'experience.title'
           - Their relation is AND
           - Example: If Job Title is 'Sales' and Management Level is 'Director', both substrings must be present in 'experience.title'
        
        2. Ternary Relations
           - The system uses this relation: (Industry OR Companies) AND Job Title AND Management Level AND Skills AND Location AND Experience
           - This determines how multiple filters interact with each other

        The final output must strictly follow this filter structure:
        {
            "job_title/business_function": {
                "current": [{"title_name": "", "min_staff": 0, "max_staff": 50000000}],
                "past": [{"title_name": "", "min_staff": 0, "max_staff": 50000000}],
                "both": [{"title_name": "", "min_staff": 0, "max_staff": 50000000}],
                "event": ""  # Can only be "CURRENT", "PAST", "CURRENT OR PAST", "CURRENT AND PAST"
            },
            "management_level": {
                "current": [],
                "past": [],
                "both": [],
                "event": ""
            },
            "location": {
                "current": [],
                "past": [],
                "both": [],
                "event": ""
            },
            "company": {
                "current_prompt": "",
                "past_prompt": "",
                "event": ""
            },
            "education": [{"degree": "", "major": ""}],
            "school": [],
            "current_ownership": [],
            "name": [],
            "ethnicity": [],
            "age": [],
            "total_working_years": {"min": null, "max": null},
            "role_tenure": {"min": null, "max": null},
            "company_tenure": {"min": null, "max": null},
            "skills": []
        }

        Before providing the final JSON:
        1. Analyze each requirement thoroughly
        2. Explain your reasoning for each filter value
        3. Discuss any assumptions or implicit requirements
        4. Validate logical consistency
        5. Only include filters that have valid values
        6. Explain any complex decisions or trade-offs
        7. Discuss how feedback has been addressed
        8. Explain how existing filter values have been incorporated
        9. Ensure timeline relations (CURRENT, PAST, etc.) are properly configured
        10. Check that filter field mappings align with backend data structure

        Your response should follow this structure:
        1. DETAILED ANALYSIS
        2. REASONING FOR EACH FILTER
        3. ASSUMPTIONS AND IMPLICATIONS
        4. VALIDATION CHECKS
        5. FEEDBACK INCORPORATION
        6. FILTER MAPPING VERIFICATION
        7. FINAL FILTER JSON
        """

    def integrate(self, solutions: List[Solution], query_context: QueryContext) -> Dict:
        print("#" * 47)
        print(solutions)
        print("#" * 47)

        feedback_section = ""
        if query_context.feedback:
            feedback_section = f"""
            Previous feedback on the query solution:
            {query_context.feedback}
            
            Ensure your integration addresses this feedback.
            """

        filter_section = ""
        if query_context.filter_values:
            filter_section = f"""
            Existing filter values from previous processing:
            {json.dumps(query_context.filter_values, indent=2)}
            
            Consider these filter values in your integration.
            You can build upon, refine, or modify these filter values as needed.
            """

        prompt = f"""Integrate these solutions while maintaining alignment with the original query:

        Original Query: {query_context.original_query}

        {feedback_section}
        
        {filter_section}

        Please provide:
        1. Detailed analysis of how each solution component fits into the final filter structure
        2. Explicit reasoning for each filter value being set
        3. Discussion of any assumptions or implicit requirements
        4. Explanation of any trade-offs or decisions made
        5. Explanation of how feedback has been addressed
        6. Explanation of how existing filter values have been incorporated
        7. Verification that filter mappings align with backend data structure
        8. Final filter JSON in the exact specified format

        Number of Solutions to Integrate: {len(solutions)}

        Solutions: {solutions}

        For each solution component, think through:
        - How does this map to our filter structure?
        - What are the explicit vs implicit requirements?
        - Are there any temporal aspects to consider (current vs past)?
        - What are the logical dependencies between different filters?
        - Are there any potential conflicts to resolve?
        - How does the feedback influence this component?
        - How do existing filter values influence this component?
        - How will the backend data structure process these filters?

        Remember the important filter relations:
        - Job Title and Management Level are both matched in 'experience.title' with an AND relation
        - The system uses this relation: (Industry OR Companies) AND Job Title AND Management Level AND Skills AND Location AND Experience

        Show your complete reasoning process before providing the final JSON structure.
        """

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        response = self.call_llm(messages)
        # Split the response into reasoning and JSON parts
        parts = response.split("FINAL FILTER JSON:")
        reasoning = parts[0].strip()

        # Parse the JSON string
        json_str = response[response.find("{") : response.rfind("}") + 1]
        filter_structure = json.loads(json_str)

        return {
            "reasoning_and_analysis": reasoning,
            "filter_structure": filter_structure,
        }


# Updated Recruitment Query Processor with filter values
class FilterAwareRecruitmentQueryProcessor:
    def __init__(self, api_key: str):
        self.intent_agent = FilterAwareIntentAnalysisAgent(api_key)
        self.subproblem_agent = FilterAwareSubProblemAnalysisAgent(api_key)
        self.integration_agent = IntegrationAgent(api_key)

    async def process_sub_problems(
        self, sub_problems: List[Dict], query_context: QueryContext
    ) -> List[Solution]:
        # Create tasks for all sub-problems
        tasks = []
        for sub_problem_dict in sub_problems:
            sub_problem = SubProblem(**sub_problem_dict)
            task = self.subproblem_agent.solve_async(sub_problem, query_context)
            tasks.append(task)

        # Execute all tasks concurrently
        solutions = await asyncio.gather(*tasks)
        return solutions

    async def process_query_async(
        self,
        query: str,
        feedback: Optional[str] = None,
        filter_values: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        query_context = QueryContext(
            original_query=query,
            timestamp=datetime.now().isoformat(),
            query_id=f"query_{hash(query)}",
            feedback=feedback,
            filter_values=filter_values,
        )

        logger.info(f"Processing query: {query_context.query_id}")
        logger.info(f"Feedback provided: {'Yes' if feedback else 'No'}")
        logger.info(f"Filter values provided: {'Yes' if filter_values else 'No'}")

        try:
            # Step 1: Analyze intent and decompose, incorporating feedback and filter values
            print("-" * 47)
            print(
                "Analyzing Intent and Decomposing the Problem (with feedback and filter values)..."
            )
            analysis = self.intent_agent.analyze(query_context)
            logger.info(
                f"Query decomposed into {len(analysis['sub_problems'])} sub-problems"
            )

            # Step 2: Process all sub-problems concurrently, with relevant feedback and filter values
            print("-" * 47)
            print("Processing the Sub-Problems (with feedback and filter values)...")
            solutions = await self.process_sub_problems(
                analysis["sub_problems"], query_context
            )
            logger.info(f"Generated solutions for all sub-problems")

            # Step 3: Integrate solutions, considering how they map to backend data structure
            print("-" * 47)
            print(
                "Integrating Solutions of Sub-Problems and aligning with backend data structure..."
            )
            final_result = self.integration_agent.integrate(solutions, query_context)
            logger.info(
                "Solutions integrated successfully with backend mapping alignment"
            )

            print("-" * 47)
            print("Printing Final Result...")
            print(json.dumps(final_result, indent=2))

            return {
                "query_context": vars(query_context),
                "analysis": analysis,
                "solutions": solutions,
                "final_result": final_result,
            }

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            raise


# Modified main function to demonstrate feedback and filter values
async def main():
    _ = load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    processor = FilterAwareRecruitmentQueryProcessor(api_key)

    # Example of filter values from a previous run
    example_filter_values = {
        "job_title/business_function": {
            "current": [
                {"title_name": "Sales Executive", "min_staff": 0, "max_staff": 50000000}
            ],
            "past": [],
            "both": [],
            "event": "CURRENT",
        },
        "management_level": {"current": [], "past": [], "both": [], "event": ""},
        "location": {"current": [], "past": [], "both": [], "event": ""},
    }

    queries = [
        {
            "query": "Looking for a Germany based communications director who comes from premium FMCG companies",
            "feedback": "",
            "filter_values": "",
        },
        {
            "query": "Site Manager and Director working in Petroleum Company, Company must be US based and should be generating revenue more than 1 million dollar. The person domain should be related to the operational functions on the site of extraction",
            "feedback": "",
            "filter_values": "",
        },
        {
            "query": "Associate Director Biostatistics or Senior RWE Data Scientist in pharmaceutical background in United States",
            "feedback": "",
            "filter_values": "",
        },
        {
            "query": "Chief Operating Officer for a clothing retailer with digital commerce presence such as Nordstrom",
            "feedback": "",
            "filter_values": "",
        },
    ]

    query_results = []
    for query_item in queries:
        print("-" * 47)
        print("QUERY: ", query_item["query"])
        print("FEEDBACK: ", query_item["feedback"])
        print("FILTER VALUES: ", "Provided" if query_item["filter_values"] else "None")

        try:
            result = await processor.process_query_async(
                query_item["query"], query_item["feedback"], query_item["filter_values"]
            )
            query_results.append(
                {
                    "query": query_item["query"],
                    "feedback": query_item["feedback"],
                    "filter_values": query_item["filter_values"],
                    "result": result,
                }
            )
        except Exception as e:
            traceback.print_exc()
            print(f"Error processing query: {e}")

    return query_results


if __name__ == "__main__":
    results = asyncio.run(main())
    # Or for testing single query:
    # result = asyncio.run(test_single_query())

    # Get all files in current directory
    files = os.listdir(".")

    # Initialize max number
    max_num = 0

    # Pattern to match files like sysinfo_filter_results_1.json
    pattern = r"sysinfo_filter_results_(\d+)\.json"

    # Find the highest number in existing files
    for file in files:
        match = re.match(pattern, file)
        if match:
            num = int(match.group(1))
            max_num = max(max_num, num)

    # Create new filename with incremented number
    if max_num == 0 and not os.path.exists("sysinfo_filter_results.json"):
        # If no numbered files exist and base file doesn't exist, use base filename
        filename = "sysinfo_filter_results.json"
    else:
        # Otherwise use next number in sequence
        filename = f"sysinfo_filter_results_{max_num + 1}.json"

    # Save the results
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)

# # If you just want to test a single query with feedback and filter values
# async def test_single_query():
#     _ = load_dotenv()
#     api_key = os.getenv("OPENAI_API_KEY")
#     processor = FilterAwareRecruitmentQueryProcessor(api_key)

#     query = "Find VP-level leaders from AI companies in Western Europe with over 30 years of experience and expertise in corporate finance who have worked previously as Salesman."
#     feedback = ""#"The results included too many professionals from big tech companies like Google and Microsoft. We need to focus on smaller AI startups and scale-ups. Also, 'salesman' is too junior - we need people who were previously in sales management roles, not individual contributors."

#     # Example filter values
#     filter_values = {
#         "job_title/business_function": {
#             "current": [{"title_name": "VP", "min_staff": 0, "max_staff": 50000000}],
#             "past": [{"title_name": "Salesman", "min_staff": 0, "max_staff": 50000000}],
#             "both": [],
#             "event": "CURRENT AND PAST"
#         },
#         "location": {
#             "current": [{"continent": "Europe", "region": "Western Europe"}],
#             "past": [],
#             "both": [],
#             "event": "CURRENT"
#         },
#         "total_working_years": {"min": 30, "max": null}
#     }

#     result = await processor.process_query_async(query, feedback, filter_values)
#     return result
