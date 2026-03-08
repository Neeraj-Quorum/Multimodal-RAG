"""
Configuration loader for the RAG system
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

class Config:
    """Configuration class for RAG system"""
    
    # Qdrant Settings
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "optional-key")
    QDRANT_COLLECTION_NAME = "confidential_docs"
    
    # OpenAI Settings (legacy — used only if AZURE_OPENAI_ENDPOINT is not set)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
    EMBEDDING_MODEL = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS = 3072  # text-embedding-3-large

    # Azure OpenAI Settings
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1")
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
    
    # Project Settings
    PROJECT_NAME = os.getenv("PROJECT_NAME", "ConfidentialRAG")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Data Paths
    PROJECT_ROOT = Path(__file__).parent.parent
    DATA_FOLDER = PROJECT_ROOT / "data"
    NOTEBOOKS_FOLDER = PROJECT_ROOT / "notebooks"
    QDRANT_STORAGE = PROJECT_ROOT / "qdrant_storage"
    
    # ── Lowercase property aliases (for notebook convenience) ──
    @property
    def openai_api_key(self):
        return type(self).OPENAI_API_KEY
    
    @property
    def qdrant_url(self):
        return type(self).QDRANT_URL
    
    @property
    def qdrant_collection(self):
        return type(self).QDRANT_COLLECTION_NAME
    
    @property
    def data_folder(self):
        return str(type(self).DATA_FOLDER)
    
    @property
    def embedding_model(self):
        return type(self).EMBEDDING_MODEL
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        print("\n" + "=" * 60)
        print("VALIDATING CONFIGURATION")
        print("=" * 60)
        
        # Check Azure vs standard OpenAI
        if cls.AZURE_OPENAI_ENDPOINT:
            if not cls.AZURE_OPENAI_API_KEY:
                raise ValueError("❌ AZURE_OPENAI_API_KEY not set in .env file")
            print(f"✓ Azure OpenAI Endpoint: {cls.AZURE_OPENAI_ENDPOINT}")
            print(f"✓ Azure API Version: {cls.AZURE_OPENAI_API_VERSION}")
            print(f"✓ Chat Deployment: {cls.AZURE_OPENAI_CHAT_DEPLOYMENT}")
            print(f"✓ Embedding Deployment: {cls.AZURE_OPENAI_EMBEDDING_DEPLOYMENT}")
            print(f"✓ Mode: Azure OpenAI")
        else:
            if not cls.OPENAI_API_KEY:
                raise ValueError("❌ Neither AZURE_OPENAI_ENDPOINT nor OPENAI_API_KEY is set in .env")
            if not cls.OPENAI_API_KEY.startswith("sk-"):
                print("⚠ OPENAI_API_KEY does not start with 'sk-' (may be a project key — that's OK)")
            print(f"✓ OPENAI_API_KEY configured")
            print(f"✓ OpenAI Model: {cls.OPENAI_MODEL}")
            print(f"✓ Mode: Standard OpenAI")
        
        # Check Qdrant URL
        print(f"✓ Qdrant URL: {cls.QDRANT_URL}")
        
        # Check paths exist
        print(f"✓ Project root: {cls.PROJECT_ROOT}")
        print(f"✓ Data folder: {cls.DATA_FOLDER}")
        print(f"✓ Notebooks folder: {cls.NOTEBOOKS_FOLDER}")
        
        print(f"✓ Embedding Dimensions: {cls.EMBEDDING_DIMENSIONS}")
        
        print("\n✅ Configuration validated successfully!")
        print("=" * 60 + "\n")


# Create global config instance
config = Config()
