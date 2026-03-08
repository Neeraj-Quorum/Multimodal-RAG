"""
RAG Chain for querying documents
Complete implementation with LangChain integration, context assembly, and source tracking
"""

from typing import List, Dict, Any, Optional
import logging
from openai import OpenAI, AzureOpenAI

try:
    from src.vector_store import VectorStore
except ImportError:
    from vector_store import VectorStore

logger = logging.getLogger(__name__)


class RAGChain:
    """
    Complete RAG Chain implementation:
    - Retrieve similar documents from vector store
    - Assemble context with related elements
    - Generate answers using LLM
    - Track and cite sources
    - Format multimodal responses
    """
    
    def __init__(
        self,
        vector_store: VectorStore,
        openai_api_key: str,
        model: str = "gpt-4.1",
        temperature: float = 0.3,
        azure_endpoint: str = None,
        api_version: str = None,
        azure_deployment: str = None
    ):
        """
        Initialize RAG Chain.

        For Azure OpenAI, pass azure_endpoint and api_version.
        The azure_deployment name replaces the model name in API calls.

        Args:
            vector_store: VectorStore instance
            openai_api_key: OpenAI or Azure OpenAI API key
            model: Model/deployment name (default: gpt-4.1)
            temperature: Generation temperature
            azure_endpoint: Azure OpenAI endpoint URL (enables Azure mode)
            api_version: Azure OpenAI API version
            azure_deployment: Azure chat deployment name (overrides model)
        """
        self.vector_store = vector_store

        if azure_endpoint:
            self.openai_client = AzureOpenAI(
                api_key=openai_api_key,
                azure_endpoint=azure_endpoint,
                api_version=api_version or "2025-01-01-preview"
            )
        else:
            self.openai_client = OpenAI(api_key=openai_api_key)

        self.model = azure_deployment or model
        self.temperature = temperature

        logger.info(f"✓ RAG Chain initialized with model: {self.model}")
    
    def query(
        self,
        user_query: str,
        top_k: int = 5,
        include_related: bool = True,
        max_context_length: int = 4000
    ) -> Dict[str, Any]:
        """
        Query the RAG system
        
        Args:
            user_query: User's question
            top_k: Number of documents to retrieve
            include_related: Whether to include related elements
            max_context_length: Max characters for context
        
        Returns:
            Dict with answer, sources, and metadata
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"QUERY: {user_query}")
        logger.info(f"{'='*60}\n")
        
        # Step 1: Retrieve relevant documents
        logger.info("Step 1: Retrieving relevant documents...")
        search_results = self.vector_store.search_with_relationships(
            query=user_query,
            top_k=top_k,
            include_related=include_related
        )
        
        main_results = search_results['main_results']
        related_elements = search_results['related_elements']
        
        logger.info(f"  Retrieved {len(main_results)} main results")
        logger.info(f"  Retrieved {len(related_elements)} related elements")
        
        if len(main_results) == 0:
            return {
                'answer': "I couldn't find any relevant information to answer your question.",
                'sources': [],
                'confidence': 0.0,
                'retrieved_count': 0
            }
        
        # Step 2: Assemble context
        logger.info("\nStep 2: Assembling context...")
        context = self._assemble_context(
            main_results=main_results,
            related_elements=related_elements,
            max_length=max_context_length
        )
        
        logger.info(f"  Context length: {len(context)} chars")
        
        # Step 3: Generate answer
        logger.info("\nStep 3: Generating answer...")
        answer = self._generate_answer(
            query=user_query,
            context=context
        )
        
        # Step 4: Extract and format sources
        logger.info("\nStep 4: Formatting sources...")
        sources = self._format_sources(main_results, related_elements)
        
        # Step 5: Calculate confidence
        avg_score = sum(r['score'] for r in main_results) / len(main_results)
        confidence = min(avg_score * 1.2, 1.0)  # Scale to 0-1
        
        result = {
            'answer': answer,
            'sources': sources,
            'confidence': confidence,
            'retrieved_count': len(main_results) + len(related_elements),
            'main_results': main_results,
            'related_elements': related_elements
        }
        
        logger.info(f"\n{'='*60}")
        logger.info(f"ANSWER GENERATED")
        logger.info(f"Confidence: {confidence:.2%}")
        logger.info(f"Sources: {len(sources)}")
        logger.info(f"{'='*60}\n")
        
        return result
    
    def _assemble_context(
        self,
        main_results: List[Dict[str, Any]],
        related_elements: List[Dict[str, Any]],
        max_length: int = 4000
    ) -> str:
        """
        Assemble context from search results
        
        Args:
            main_results: Main search results
            related_elements: Related elements
            max_length: Maximum context length
        
        Returns:
            Formatted context string
        """
        context_parts = []
        current_length = 0
        
        # Add main results first
        for idx, result in enumerate(main_results, 1):
            if current_length >= max_length:
                break
            
            part = self._format_result_for_context(result, idx, is_main=True)
            part_length = len(part)
            
            if current_length + part_length > max_length:
                break
            
            context_parts.append(part)
            current_length += part_length
        
        # Add related elements
        if related_elements and current_length < max_length:
            context_parts.append("\n--- Related Content ---\n")
            
            for elem in related_elements:
                if current_length >= max_length:
                    break
                
                part = self._format_related_for_context(elem)
                part_length = len(part)
                
                if current_length + part_length > max_length:
                    break
                
                context_parts.append(part)
                current_length += part_length
        
        return "\n\n".join(context_parts)
    
    def _format_result_for_context(
        self,
        result: Dict[str, Any],
        idx: int,
        is_main: bool = True
    ) -> str:
        """Format a search result for context"""
        parts = []
        
        # Header
        header = f"[Document {idx}]" if is_main else f"[Related Content]"
        parts.append(header)
        
        # Metadata
        filename = result.get('filename', 'Unknown')
        doc_type = result.get('type', 'unknown')
        hierarchy = result.get('hierarchy_path', '')
        
        parts.append(f"Source: {filename}")
        if hierarchy:
            parts.append(f"Location: {hierarchy}")
        parts.append(f"Type: {doc_type}")
        
        # Content
        content = result.get('summary_medium') or result.get('summary_short', '')
        if content:
            parts.append(f"\nContent:\n{content}")
        
        # Related items indicator
        has_text = len(result.get('related_text_ids', [])) > 0
        has_images = len(result.get('related_image_ids', [])) > 0
        has_tables = len(result.get('related_table_ids', [])) > 0
        
        if has_text or has_images or has_tables:
            related_info = []
            if has_text:
                related_info.append("text")
            if has_images:
                related_info.append("images")
            if has_tables:
                related_info.append("tables")
            parts.append(f"Related: {', '.join(related_info)}")
        
        return "\n".join(parts)
    
    def _format_related_for_context(self, element: Dict[str, Any]) -> str:
        """Format a related element for context"""
        parts = []
        
        elem_type = element.get('type', 'unknown')
        filename = element.get('filename', 'Unknown')
        
        parts.append(f"[Related {elem_type.title()}]")
        parts.append(f"From: {filename}")
        
        content = element.get('summary_short') or element.get('summary_medium', '')
        if content:
            parts.append(f"{content}")
        
        return "\n".join(parts)
    
    def _generate_answer(self, query: str, context: str) -> str:
        """
        Generate answer using LLM
        
        Args:
            query: User's question
            context: Assembled context
        
        Returns:
            Generated answer
        """
        # Build system prompt
        system_prompt = """You are a helpful AI assistant that answers questions based on provided documentation.

Instructions:
1. Answer the question using ONLY the information in the provided context
2. Be specific and cite which document you're referencing
3. If the context doesn't contain enough information, say so
4. If multiple documents provide information, synthesize them
5. Be concise but complete
6. Mention if there are related images, tables, or diagrams that would help

Format your answer clearly and professionally."""
        
        # Build user prompt
        user_prompt = f"""Context from documentation:

{context}

---

Question: {query}

Please provide a comprehensive answer based on the context above."""
        
        try:
            # Call OpenAI
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content.strip()
            return answer
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return f"I encountered an error generating the answer: {str(e)}"
    
    def _format_sources(
        self,
        main_results: List[Dict[str, Any]],
        related_elements: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Format sources for citation
        
        Args:
            main_results: Main search results
            related_elements: Related elements
        
        Returns:
            List of source dicts
        """
        sources = []
        seen_files = set()
        
        # Main sources
        for result in main_results:
            filename = result.get('filename', 'Unknown')
            file_id = result.get('file_id', '')
            
            if file_id not in seen_files:
                source = {
                    'filename': filename,
                    'type': result.get('type', 'unknown'),
                    'hierarchy_path': result.get('hierarchy_path', ''),
                    'page_number': result.get('page_number'),
                    'relevance_score': result.get('score', 0.0)
                }
                sources.append(source)
                seen_files.add(file_id)
        
        # Related sources
        for elem in related_elements:
            filename = elem.get('filename', 'Unknown')
            file_id = elem.get('element_id', '')
            
            if file_id not in seen_files:
                source = {
                    'filename': filename,
                    'type': elem.get('type', 'unknown'),
                    'relationship': 'related'
                }
                sources.append(source)
                seen_files.add(file_id)
        
        return sources
    
    def format_response(self, result: Dict[str, Any]) -> str:
        """
        Format response for display
        
        Args:
            result: Query result dict
        
        Returns:
            Formatted string
        """
        lines = []
        
        # Answer
        lines.append("=" * 60)
        lines.append("ANSWER")
        lines.append("=" * 60)
        lines.append(result['answer'])
        lines.append("")
        
        # Confidence
        confidence = result.get('confidence', 0.0)
        lines.append(f"Confidence: {confidence:.1%}")
        lines.append("")
        
        # Sources
        sources = result.get('sources', [])
        if sources:
            lines.append("=" * 60)
            lines.append("SOURCES")
            lines.append("=" * 60)
            
            for idx, source in enumerate(sources, 1):
                filename = source.get('filename', 'Unknown')
                doc_type = source.get('type', 'unknown')
                hierarchy = source.get('hierarchy_path', '')
                page = source.get('page_number')
                
                lines.append(f"{idx}. {filename} ({doc_type})")
                
                if hierarchy:
                    lines.append(f"   Path: {hierarchy}")
                if page:
                    lines.append(f"   Page: {page}")
                
                if 'relevance_score' in source:
                    score = source['relevance_score']
                    lines.append(f"   Relevance: {score:.2%}")
                
                lines.append("")
        
        return "\n".join(lines)
