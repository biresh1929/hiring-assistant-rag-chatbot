from setuptools import find_packages, setup

setup(
    name="hiring-assistant-chatbot",
    version="1.0.0",
    author="Biresh Kumar Singh",
    author_email="bireshkumar1964@gmail.com",
    description="AI-powered hiring assistant chatbot for TalentScout",
    packages=find_packages(),
    install_requires=[
        # UI
        "streamlit",

        # LLM + LangChain
        "langchain-core",
        "langchain-community",
        "langchain-groq",
        "langchain-huggingface",
        "sentence-transformers",

        # Vector DB
        "pinecone-client",
        "langchain-pinecone",

        # Database
        "pymongo",

        # Security & Encryption
        "cryptography",

        # AWS
        "boto3",

        # Scheduling (used in older versions, safe to keep)
        "APScheduler",

        # Env management
        "python-dotenv"
    ],
    python_requires=">=3.9",
)
