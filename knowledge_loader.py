"""
Knowledge Base Loader
Utility to load documents from various sources into RAG store
"""
import os
import json
import logging
from typing import List, Dict, Optional
from rag_store import RAGStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeBaseLoader:
    def __init__(self, rag_store: RAGStore):
        """
        Initialize knowledge base loader
        
        Args:
            rag_store: RAG store instance to load documents into
        """
        self.rag_store = rag_store
    
    def load_from_text_files(self, directory: str, pattern: str = "*.txt") -> int:
        """
        Load documents from text files in a directory
        
        Args:
            directory: Directory containing text files
            pattern: File pattern to match (default: *.txt)
            
        Returns:
            Number of chunks added
        """
        import glob
        
        documents = []
        metadata = []
        
        # Find all matching files
        file_pattern = os.path.join(directory, "**", pattern)
        files = glob.glob(file_pattern, recursive=True)
        
        logger.info(f"Found {len(files)} files matching pattern {pattern}")
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                if content.strip():
                    documents.append(content)
                    metadata.append({
                        'source': os.path.basename(file_path),
                        'file_path': file_path,
                        'type': 'text_file'
                    })
                    
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")
        
        if documents:
            return self.rag_store.add_documents(documents, metadata)
        
        return 0
    
    def load_from_json(self, file_path: str, text_field: str = "content") -> int:
        """
        Load documents from JSON file
        
        Args:
            file_path: Path to JSON file
            text_field: Field name containing document text
            
        Returns:
            Number of chunks added
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            documents = []
            metadata = []
            
            # Handle different JSON structures
            if isinstance(data, list):
                # List of documents
                for idx, item in enumerate(data):
                    if isinstance(item, dict):
                        text = item.get(text_field, "")
                        if text:
                            documents.append(text)
                            meta = {k: v for k, v in item.items() if k != text_field}
                            meta['source'] = f"{os.path.basename(file_path)}[{idx}]"
                            metadata.append(meta)
                    elif isinstance(item, str):
                        documents.append(item)
                        metadata.append({'source': f"{os.path.basename(file_path)}[{idx}]"})
            
            elif isinstance(data, dict):
                # Single document or dict of documents
                if text_field in data:
                    # Single document
                    documents.append(data[text_field])
                    meta = {k: v for k, v in data.items() if k != text_field}
                    meta['source'] = os.path.basename(file_path)
                    metadata.append(meta)
                else:
                    # Dict of sections/documents
                    for key, value in data.items():
                        if isinstance(value, str):
                            documents.append(value)
                            metadata.append({
                                'source': os.path.basename(file_path),
                                'section': key
                            })
                        elif isinstance(value, dict) and text_field in value:
                            documents.append(value[text_field])
                            meta = {k: v for k, v in value.items() if k != text_field}
                            meta['source'] = os.path.basename(file_path)
                            meta['section'] = key
                            metadata.append(meta)
            
            if documents:
                logger.info(f"Loaded {len(documents)} documents from {file_path}")
                return self.rag_store.add_documents(documents, metadata)
            
        except Exception as e:
            logger.error(f"Error loading JSON from {file_path}: {e}")
        
        return 0
    
    def load_from_csv(self, file_path: str, text_column: str = "text") -> int:
        """
        Load documents from CSV file
        
        Args:
            file_path: Path to CSV file
            text_column: Name of column containing document text
            
        Returns:
            Number of chunks added
        """
        import csv
        
        try:
            documents = []
            metadata = []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for idx, row in enumerate(reader):
                    text = row.get(text_column, "")
                    if text.strip():
                        documents.append(text)
                        meta = {k: v for k, v in row.items() if k != text_column}
                        meta['source'] = f"{os.path.basename(file_path)}[row {idx+1}]"
                        metadata.append(meta)
            
            if documents:
                logger.info(f"Loaded {len(documents)} documents from {file_path}")
                return self.rag_store.add_documents(documents, metadata)
                
        except Exception as e:
            logger.error(f"Error loading CSV from {file_path}: {e}")
        
        return 0
    
    def load_from_markdown(self, file_path: str) -> int:
        """
        Load documents from Markdown file, splitting by headers
        
        Args:
            file_path: Path to Markdown file
            
        Returns:
            Number of chunks added
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split by headers
            import re
            sections = re.split(r'\n#+\s+', content)
            
            documents = []
            metadata = []
            
            for idx, section in enumerate(sections):
                if section.strip():
                    # Extract title from first line
                    lines = section.split('\n', 1)
                    title = lines[0].strip()
                    text = lines[1] if len(lines) > 1 else ""
                    
                    if text.strip():
                        documents.append(text)
                        metadata.append({
                            'source': os.path.basename(file_path),
                            'section': title,
                            'type': 'markdown'
                        })
            
            if documents:
                logger.info(f"Loaded {len(documents)} sections from {file_path}")
                return self.rag_store.add_documents(documents, metadata)
                
        except Exception as e:
            logger.error(f"Error loading Markdown from {file_path}: {e}")
        
        return 0
    
    def load_from_admin_data(self, data_file: str = "data/admin_data.json") -> int:
        """
        Load documents from admin data JSON file
        
        Args:
            data_file: Path to admin data JSON file
            
        Returns:
            Number of chunks added
        """
        try:
            if not os.path.exists(data_file):
                logger.warning(f"Admin data file not found: {data_file}")
                return 0
            
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            documents = []
            metadata = []
            
            # Extract different sections
            if "company_info" in data:
                documents.append(str(data["company_info"]))
                metadata.append({'source': 'admin_data', 'type': 'company_info'})
            
            if "products" in data:
                products_text = "\n".join([str(p) for p in data["products"]])
                documents.append(products_text)
                metadata.append({'source': 'admin_data', 'type': 'products'})
            
            if "faq" in data:
                for faq in data["faq"]:
                    faq_text = f"Q: {faq['question']}\nA: {faq['answer']}"
                    documents.append(faq_text)
                    metadata.append({'source': 'admin_data', 'type': 'faq'})
            
            if "policies" in data:
                documents.append(str(data["policies"]))
                metadata.append({'source': 'admin_data', 'type': 'policies'})
            
            if "contact" in data:
                documents.append(str(data["contact"]))
                metadata.append({'source': 'admin_data', 'type': 'contact'})
            
            if documents:
                logger.info(f"Loaded {len(documents)} documents from admin data")
                return self.rag_store.add_documents(documents, metadata)
                
        except Exception as e:
            logger.error(f"Error loading admin data: {e}")
        
        return 0
    
    def load_knowledge_base(
        self,
        text_dirs: Optional[List[str]] = None,
        json_files: Optional[List[str]] = None,
        csv_files: Optional[List[str]] = None,
        markdown_files: Optional[List[str]] = None,
        include_admin_data: bool = True
    ) -> Dict[str, int]:
        """
        Load complete knowledge base from multiple sources
        
        Args:
            text_dirs: List of directories containing text files
            json_files: List of JSON files to load
            csv_files: List of CSV files to load
            markdown_files: List of Markdown files to load
            include_admin_data: Whether to include admin data
            
        Returns:
            Dictionary with counts from each source
        """
        results = {
            'text_files': 0,
            'json_files': 0,
            'csv_files': 0,
            'markdown_files': 0,
            'admin_data': 0,
            'total': 0
        }
        
        # Load from text directories
        if text_dirs:
            for directory in text_dirs:
                if os.path.exists(directory):
                    count = self.load_from_text_files(directory)
                    results['text_files'] += count
        
        # Load from JSON files
        if json_files:
            for file_path in json_files:
                if os.path.exists(file_path):
                    count = self.load_from_json(file_path)
                    results['json_files'] += count
        
        # Load from CSV files
        if csv_files:
            for file_path in csv_files:
                if os.path.exists(file_path):
                    count = self.load_from_csv(file_path)
                    results['csv_files'] += count
        
        # Load from Markdown files
        if markdown_files:
            for file_path in markdown_files:
                if os.path.exists(file_path):
                    count = self.load_from_markdown(file_path)
                    results['markdown_files'] += count
        
        # Load admin data
        if include_admin_data:
            count = self.load_from_admin_data()
            results['admin_data'] = count
        
        results['total'] = sum(v for k, v in results.items() if k != 'total')
        
        logger.info(f"Loaded total of {results['total']} chunks into RAG store")
        logger.info(f"Breakdown: {results}")
        
        return results


def initialize_rag_with_data(chatbot, knowledge_dirs: Optional[List[str]] = None):
    """
    Helper function to initialize RAG with common data sources
    
    Args:
        chatbot: AdminChatbot instance
        knowledge_dirs: Optional list of directories containing knowledge base files
    """
    if not chatbot.enable_rag or not chatbot.rag_store:
        logger.warning("RAG is not enabled on this chatbot")
        return
    
    loader = KnowledgeBaseLoader(chatbot.rag_store)
    
    # Default knowledge directories
    if knowledge_dirs is None:
        knowledge_dirs = ["data/knowledge", "docs"]
    
    # Load from all available sources
    results = loader.load_knowledge_base(
        text_dirs=knowledge_dirs,
        include_admin_data=True
    )
    
    logger.info(f"RAG initialization complete: {results}")
    return results
