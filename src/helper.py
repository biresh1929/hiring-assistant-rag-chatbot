from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
import os
from src.prompt import (
    GREETING_PROMPT,
    INFO_GATHERING_PROMPT,
    TECH_QUESTION_GENERATION_PROMPT,
    ANSWER_EVALUATION_PROMPT,
    CONTEXT_MANAGEMENT_PROMPT,
    FALLBACK_PROMPT,
    GOODBYE_PROMPT
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")



class ConversationStage:
    """Enum for conversation stages"""
    GREETING = "greeting"
    COLLECTING_NAME = "collecting_name"
    COLLECTING_EMAIL = "collecting_email"
    COLLECTING_PHONE = "collecting_phone"
    COLLECTING_EXPERIENCE = "collecting_experience"
    COLLECTING_POSITION = "collecting_position"
    COLLECTING_LOCATION = "collecting_location"
    COLLECTING_TECH_STACK = "collecting_tech_stack"
    ASKING_QUESTIONS = "asking_questions"
    COMPLETED = "completed"


def initialize_llm(temperature=0.3):
    """Initialize Groq LLM"""
    return ChatGroq(
        temperature=temperature,
        model="llama-3.3-70b-versatile"
    )


def generate_greeting():
    """Generate initial greeting message"""
    llm = initialize_llm(temperature=0.7)
    
    prompt = PromptTemplate(
        template=GREETING_PROMPT,
        input_variables=[]
    )
    
    chain = prompt | llm
    response = chain.invoke({})
    
    return response.content


def generate_info_gathering_response(context: str, user_input: str):
    """
    Generate context-aware response for information gathering stage
    
    Args:
        context: Recent conversation history
        user_input: Current user input
    
    Returns:
        str: Context-aware response
    """
    llm = initialize_llm(temperature=0.3)
    
    prompt = PromptTemplate(
        template=INFO_GATHERING_PROMPT,
        input_variables=["context", "user_input"]
    )
    
    chain = prompt | llm
    response = chain.invoke({
        "context": context,
        "user_input": user_input
    })
    
    return response.content


def generate_technical_questions(tech_stack: list, experience_years: str, num_questions: int = 5):
    """
    Generate technical questions based on candidate's tech stack and experience
    Questions are RELEVANT to the specific technologies mentioned
    
    Args:
        tech_stack: List of technologies (e.g., ["Python", "Django", "PostgreSQL"])
        experience_years: Years of experience as string
        num_questions: Number of questions to generate (default: 5)
    
    Returns:
        List of technical questions tailored to the tech stack
    """
    llm = initialize_llm(temperature=0.4)  # Slightly higher for variety
    
    # Format tech stack as comma-separated string
    tech_stack_str = ", ".join(tech_stack)
    
    # Determine experience level for difficulty
    try:
        exp_float = float(experience_years)
        if exp_float < 2:
            exp_level = "beginner (0-2 years)"
        elif exp_float < 5:
            exp_level = "intermediate (3-5 years)"
        else:
            exp_level = "advanced (6+ years)"
    except:
        exp_level = "intermediate"
    
    prompt = PromptTemplate(
        template=TECH_QUESTION_GENERATION_PROMPT,
        input_variables=["tech_stack", "experience_years", "num_questions"]
    )
    
    chain = prompt | llm
    response = chain.invoke({
        "tech_stack": tech_stack_str,
        "experience_years": exp_level,
        "num_questions": num_questions
    })
    
    # Parse questions from response
    questions_text = response.content
    questions = []
    
    for line in questions_text.split('\n'):
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Remove numbering patterns
        line = line.lstrip('0123456789.').strip()
        line = line.lstrip('-*').strip()
        line = line.lstrip('•').strip()
        
        # Only keep actual questions
        if line.endswith('?') and len(line) > 20:
            # Remove any remaining markdown or formatting
            line = line.replace('**', '').replace('__', '')
            
            # Avoid duplicates
            if line not in questions:
                questions.append(line)
    
    # Ensure we have exactly the requested number
    if len(questions) < num_questions:
        # If we got fewer questions, try to generate more
        print(f"Warning: Only generated {len(questions)} questions, requested {num_questions}")
    
    # Limit to requested number
    return questions[:num_questions]


def evaluate_answer(question: str, answer: str, tech_stack: list):
    """Evaluate candidate's answer to a technical question"""
    llm = initialize_llm(temperature=0.3)
    
    tech_stack_str = ", ".join(tech_stack)
    
    prompt = PromptTemplate(
        template=ANSWER_EVALUATION_PROMPT,
        input_variables=["question", "answer", "tech_stack"]
    )
    
    chain = prompt | llm
    response = chain.invoke({
        "question": question,
        "answer": answer,
        "tech_stack": tech_stack_str
    })
    
    return response.content


def handle_context(stage: str, collected_info: dict, user_input: str):
    """
    Handle conversation context and flow with awareness of previous exchanges
    
    Args:
        stage: Current conversation stage
        collected_info: Information collected so far
        user_input: Current user input
    
    Returns:
        str: Context-aware response
    """
    llm = initialize_llm(temperature=0.3)
    
    prompt = PromptTemplate(
        template=CONTEXT_MANAGEMENT_PROMPT,
        input_variables=["stage", "collected_info", "user_input"]
    )
    
    chain = prompt | llm
    response = chain.invoke({
        "stage": stage,
        "collected_info": str(collected_info),
        "user_input": user_input
    })
    
    return response.content


def handle_fallback(user_input: str, stage: str):
    """
    Handle unclear or unexpected user input with context
    
    Args:
        user_input: User's unclear input
        stage: Current conversation stage
    
    Returns:
        str: Helpful fallback response
    """
    llm = initialize_llm(temperature=0.3)
    
    prompt = PromptTemplate(
        template=FALLBACK_PROMPT,
        input_variables=["user_input", "stage"]
    )
    
    chain = prompt | llm
    response = chain.invoke({
        "user_input": user_input,
        "stage": stage
    })
    
    return response.content


def generate_goodbye(candidate_name: str):
    """Generate goodbye message"""
    llm = initialize_llm(temperature=0.7)
    
    prompt = PromptTemplate(
        template=GOODBYE_PROMPT,
        input_variables=["candidate_name"]
    )
    
    chain = prompt | llm
    response = chain.invoke({
        "candidate_name": candidate_name
    })
    
    return response.content


def check_exit_intent(user_input: str) -> bool:
    """
    Check if user wants to exit the conversation
    
    Args:
        user_input: User's message
    
    Returns:
        bool: True if exit intent detected
    """
    exit_keywords = [
        "bye", "goodbye", "exit", "quit", "stop", 
        "end", "cancel", "no thanks", "not interested",
        "leave", "close", "finish", "done"
    ]
    
    user_input_lower = user_input.lower().strip()
    
    # Check for exact matches or phrases containing keywords
    return any(keyword in user_input_lower for keyword in exit_keywords)