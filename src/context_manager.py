from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
import os
from datetime import datetime
from pinecone import Pinecone


class ConversationContextManager:
    """Manages conversation context in Pinecone for semantic retrieval"""
    
    def __init__(self, index_name="chatbot-conversations"):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.index_name = index_name
        
        # Initialize Pinecone vector store
        self.vector_store = PineconeVectorStore(
            index_name=self.index_name,
            embedding=self.embeddings,
            pinecone_api_key=os.getenv("PINECONE_API_KEY")
        )

    
    def store_conversation_turn(self, candidate_id: str, role: str, message: str, metadata: dict = None):
        """Store a single conversation turn in Pinecone"""
        
        # Create document
        doc = Document(
            page_content=f"{role}: {message}",
            metadata={
                "candidate_id": candidate_id,
                "role": role,
                "timestamp": datetime.now().isoformat(),
                "stage": metadata.get("stage", "unknown") if metadata else "unknown",
                **(metadata or {})
            }
        )
        
        # Add to Pinecone
        self.vector_store.add_documents([doc])
    
    def get_relevant_context(self, candidate_id: str, query: str, k: int = 5):
        """Retrieve relevant conversation context based on semantic similarity"""
        
        results = self.vector_store.similarity_search(
            query,
            k=k,
            filter={"candidate_id": candidate_id}
        )
        
        return [{"content": doc.page_content, "metadata": doc.metadata} for doc in results]
    