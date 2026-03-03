"""
RAG (Retrieval-Augmented Generation) Store
Manages document embeddings, indexing, and semantic search
"""
import os
import json
import pickle
import numpy as np
from typing import List, Dict, Optional, Tuple
import logging
from sentence_transformers import SentenceTransformer
import faiss

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGStore:
    def __init__(
        self, 
        model_name: str = "all-MiniLM-L6-v2",
        index_path: str = "data/rag_index.faiss",
        metadata_path: str = "data/rag_metadata.pkl"
    ):
        """
        Initialize RAG store with embedding model and vector index
        
        Args:
            model_name: Sentence transformer model name
            index_path: Path to save/load FAISS index
            metadata_path: Path to save/load document metadata
        """
        self.model_name = model_name
        self.index_path = index_path
        self.metadata_path = metadata_path
        
        # Load embedding model
        logger.info(f"Loading embedding model: {model_name}")
        self.embedding_model = SentenceTransformer(model_name)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        
        # Initialize or load index
        self.index = None
        self.documents = []  # Store original documents
        self.metadata = []   # Store metadata (source, chunk_id, etc.)
        
        self.load_index()
        
        logger.info("RAG Store initialized successfully")
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Split text into overlapping chunks
        
        Args:
            text: Text to chunk
            chunk_size: Maximum characters per chunk
            overlap: Overlapping characters between chunks
            
        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence or word boundary
            if end < len(text):
                # Look for sentence end
                last_period = text.rfind('.', start, end)
                last_newline = text.rfind('\n', start, end)
                last_break = max(last_period, last_newline)
                
                if last_break > start + chunk_size // 2:
                    end = last_break + 1
                else:
                    # Look for word boundary
                    last_space = text.rfind(' ', start, end)
                    if last_space > start + chunk_size // 2:
                        end = last_space
            
            chunks.append(text[start:end].strip())
            start = end - overlap
        
        return chunks
    
    def add_documents(
        self, 
        documents: List[str], 
        metadata: Optional[List[Dict]] = None,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> int:
        """
        Add documents to the RAG store
        
        Args:
            documents: List of document texts
            metadata: Optional list of metadata dicts for each document
            chunk_size: Size of text chunks
            overlap: Overlap between chunks
            
        Returns:
            Number of chunks added
        """
        if metadata is None:
            metadata = [{"doc_id": i} for i in range(len(documents))]
        
        all_chunks = []
        all_chunk_metadata = []
        
        # Chunk all documents
        for doc_idx, (doc, meta) in enumerate(zip(documents, metadata)):
            chunks = self.chunk_text(doc, chunk_size, overlap)
            
            for chunk_idx, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                chunk_meta = meta.copy()
                chunk_meta.update({
                    "chunk_id": chunk_idx,
                    "total_chunks": len(chunks),
                    "doc_idx": doc_idx
                })
                all_chunk_metadata.append(chunk_meta)
        
        if not all_chunks:
            logger.warning("No chunks to add")
            return 0
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(all_chunks)} chunks...")
        embeddings = self.embedding_model.encode(
            all_chunks,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        
        # Create or update FAISS index
        if self.index is None:
            self.index = faiss.IndexFlatL2(self.embedding_dim)
        
        # Add to index
        self.index.add(embeddings.astype('float32'))
        
        # Store documents and metadata
        self.documents.extend(all_chunks)
        self.metadata.extend(all_chunk_metadata)
        
        logger.info(f"Added {len(all_chunks)} chunks to RAG store")
        
        # Save index
        self.save_index()
        
        return len(all_chunks)
    
    def search(
        self, 
        query: str, 
        top_k: int = 3,
        score_threshold: Optional[float] = None
    ) -> List[Tuple[str, float, Dict]]:
        """
        Search for relevant documents using semantic similarity
        
        Args:
            query: Search query
            top_k: Number of top results to return
            score_threshold: Optional minimum similarity score
            
        Returns:
            List of tuples (document_text, score, metadata)
        """
        if self.index is None or self.index.ntotal == 0:
            logger.warning("RAG store is empty")
            return []
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode(
            [query],
            convert_to_numpy=True
        )
        
        # Search in FAISS index
        # Note: FAISS returns L2 distances, lower is better
        distances, indices = self.index.search(
            query_embedding.astype('float32'), 
            min(top_k, self.index.ntotal)
        )
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self.documents):
                # Convert L2 distance to similarity score (0-1, higher is better)
                # Using negative exponential transformation
                similarity_score = np.exp(-dist / 10)
                
                if score_threshold is None or similarity_score >= score_threshold:
                    results.append((
                        self.documents[idx],
                        float(similarity_score),
                        self.metadata[idx]
                    ))
        
        return results
    
    def get_context_for_query(
        self, 
        query: str, 
        top_k: int = 3,
        max_context_length: int = 2000
    ) -> str:
        """
        Get formatted context string for a query
        
        Args:
            query: User query
            top_k: Number of documents to retrieve
            max_context_length: Maximum characters in context
            
        Returns:
            Formatted context string
        """
        results = self.search(query, top_k=top_k)
        
        if not results:
            return ""
        
        context_parts = []
        total_length = 0
        
        for idx, (doc_text, score, meta) in enumerate(results, 1):
            if total_length + len(doc_text) > max_context_length:
                break
            
            source = meta.get('source', 'Document')
            context_parts.append(f"[Source {idx} - {source}]:\n{doc_text}")
            total_length += len(doc_text)
        
        if context_parts:
            return "\n\n".join(context_parts)
        
        return ""
    
    def save_index(self):
        """Save FAISS index and metadata to disk"""
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            
            # Save FAISS index
            if self.index is not None:
                faiss.write_index(self.index, self.index_path)
                logger.info(f"Saved FAISS index to {self.index_path}")
            
            # Save metadata and documents
            metadata_dict = {
                'documents': self.documents,
                'metadata': self.metadata,
                'model_name': self.model_name,
                'embedding_dim': self.embedding_dim
            }
            
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(metadata_dict, f)
            
            logger.info(f"Saved metadata to {self.metadata_path}")
            
        except Exception as e:
            logger.error(f"Error saving index: {e}")
    
    def load_index(self):
        """Load FAISS index and metadata from disk"""
        try:
            # Load FAISS index
            if os.path.exists(self.index_path):
                self.index = faiss.read_index(self.index_path)
                logger.info(f"Loaded FAISS index from {self.index_path}")
            else:
                logger.info("No existing index found, creating new one")
                self.index = None
            
            # Load metadata and documents
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, 'rb') as f:
                    metadata_dict = pickle.load(f)
                
                self.documents = metadata_dict.get('documents', [])
                self.metadata = metadata_dict.get('metadata', [])
                
                logger.info(f"Loaded {len(self.documents)} documents from metadata")
            else:
                logger.info("No existing metadata found")
                
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            self.index = None
            self.documents = []
            self.metadata = []
    
    def clear_index(self):
        """Clear all documents from the index"""
        self.index = None
        self.documents = []
        self.metadata = []
        
        # Delete files if they exist
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        if os.path.exists(self.metadata_path):
            os.remove(self.metadata_path)
        
        logger.info("Cleared RAG store")
    
    def get_stats(self) -> Dict:
        """Get statistics about the RAG store"""
        return {
            "total_documents": len(self.documents),
            "embedding_model": self.model_name,
            "embedding_dimension": self.embedding_dim,
            "index_size": self.index.ntotal if self.index else 0
        }
