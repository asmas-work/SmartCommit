from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GPTClient:
    _instance = None

    def __init__(self):
        self.client = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = GPTClient()
        return cls._instance

    def initialize(self, api_key):
        """Initialize or update the OpenAI client with the given API key"""
        self.client = OpenAI(api_key=api_key)

    def is_initialized(self):
        """Check if the client has been initialized"""
        return self.client is not None

# Create a global instance
gpt_client = GPTClient.get_instance()

def generate_commit_message(diff_content):
    """
    Generate a commit message using GPT based on the provided diff content.
    """
    if not gpt_client.is_initialized():
        raise ValueError("OpenAI client not initialized. Please set an API key first.")

    prompt = f"""Analyze the following code changes and generate a comprehensive commit message.
    Follow these guidelines:
    1. First line: Write a concise summary (max 50 characters)
    2. Leave one blank line
    3. Detailed description:
       - List all significant changes
       - Explain the reason for changes
       - Mention any breaking changes
       - Note any dependencies added/removed
    4. Use imperative mood (e.g., "Add" not "Added")
    5. Focus on what changed and why, not how
    6. If the changes include multiple distinct updates, list them with bullet points
    
    Code changes:
    {diff_content}
    """
    
    try:
        response = gpt_client.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior developer who writes clear, detailed, and professional git commit messages following best practices."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating commit message: {str(e)}"

def analyze_changes(diff_content):
    """
    Analyze the changes to provide additional context about the modifications.
    """
    prompt = f"""Analyze the following code changes and provide a brief summary of:
    1. Type of changes (feature, bugfix, refactor, etc.)
    2. Files affected
    3. Potential impact
    4. Suggested reviewers (based on affected components)
    
    Code changes:
    {diff_content}
    """
    
    try:
        response = gpt_client.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a code review assistant that analyzes code changes and provides helpful insights."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error analyzing changes: {str(e)}" 