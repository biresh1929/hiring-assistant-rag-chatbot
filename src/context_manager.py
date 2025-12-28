from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
import os
from datetime import datetime
from pinecone import Pinecone, ServerlessSpec
import logging

logging.basicConfig(level=logging.INFO)

class ConversationContextManager:
    """Manages conversation context in Pinecone for semantic retrieval"""
    
    def __init__(self, index_name="chatbot-conversations"):
        try:
            # Initialize embeddings model
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            self.index_name = index_name
            
            # Get Pinecone API key
            pinecone_api_key = os.getenv("PINECONE_API_KEY")
            if not pinecone_api_key:
                raise ValueError("PINECONE_API_KEY not found in environment variables")
            
            # Initialize Pinecone client
            pc = Pinecone(api_key=pinecone_api_key)
            
            # Check if index exists, create if not
            existing_indexes = [index.name for index in pc.list_indexes()]
            
            if index_name not in existing_indexes:
                logging.info(f"Creating new Pinecone index: {index_name}")
                pc.create_index(
                    name=index_name,
                    dimension=384,  # all-MiniLM-L6-v2 produces 384-dim embeddings
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=os.getenv("PINECONE_REGION", "us-east-1")
                    )
                )
                logging.info(f"✅ Pinecone index created: {index_name}")
            else:
                logging.info(f"✅ Using existing Pinecone index: {index_name}")
            
            # Initialize vector store
            self.vector_store = PineconeVectorStore(
                index_name=self.index_name,
                embedding=self.embeddings,
                pinecone_api_key=pinecone_api_key
            )
            
            logging.info("✅ ConversationContextManager initialized successfully")
            
        except Exception as e:
            logging.error(f"❌ Failed to initialize ConversationContextManager: {e}")
            raise
    
    def store_conversation_turn(self, candidate_id: str, role: str, message: str, metadata: dict = None):
        """Store a single conversation turn in Pinecone"""
        try:
            # Create document with full metadata
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
            logging.info(f"✅ Stored message for {candidate_id} in Pinecone")
            
        except Exception as e:
            logging.error(f"❌ Failed to store conversation turn: {e}")
            # Don't raise - we don't want to break the conversation flow
    
    def get_relevant_context(self, candidate_id: str, query: str, k: int = 5):
        """Retrieve relevant conversation context based on semantic similarity"""
        try:
            # Perform similarity search with candidate filter
            results = self.vector_store.similarity_search(
                query,
                k=k,
                filter={"candidate_id": candidate_id}
            )
            
            logging.info(f"✅ Retrieved {len(results)} context messages for {candidate_id}")
            
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                } 
                for doc in results
            ]
            
        except Exception as e:
            logging.error(f"❌ Failed to retrieve context: {e}")
            return []  # Return empty list on error
    
    def get_conversation_history(self, candidate_id: str, limit: int = 10):
        """Get recent conversation history for a candidate"""
        try:
            # Query all messages for this candidate
            results = self.vector_store.similarity_search(
                "conversation history",  # Generic query
                k=limit,
                filter={"candidate_id": candidate_id}
            )
            
            # Sort by timestamp
            sorted_results = sorted(
                results,
                key=lambda x: x.metadata.get("timestamp", ""),
                reverse=True
            )
            
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in sorted_results[:limit]
            ]
            
        except Exception as e:
            logging.error(f"❌ Failed to get conversation history: {e}")
            return []