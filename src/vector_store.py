"""
Vector Store initialization and management for Qdrant
Complete implementation with embeddings, upsert, search, and relationship retrieval
"""

from typing import List, Dict, Any, Optional
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from openai import OpenAI, AzureOpenAI
import hashlib
from tqdm import tqdm

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Complete Vector Store implementation with:
    - Embedding generation (OpenAI)
    - Batch upsert to Qdrant
    - Search with similarity
    - Relationship-aware retrieval
    - Metadata filtering
    """
    
    def __init__(self, qdrant_url: str, openai_api_key: str, collection_name: str = "confidential_docs",
                 azure_endpoint: str = None, api_version: str = None,
                 embedding_deployment: str = None):
        """
        Initialize Vector Store.

        For Azure OpenAI embeddings, pass azure_endpoint and api_version.
        The embedding_deployment name replaces the model name in API calls.

        Args:
            qdrant_url: Qdrant server URL
            openai_api_key: OpenAI or Azure OpenAI API key
            collection_name: Name of Qdrant collection
            azure_endpoint: Azure OpenAI endpoint URL (enables Azure mode)
            api_version: Azure OpenAI API version
            embedding_deployment: Azure deployment name for embeddings
        """
        try:
            self.client = QdrantClient(url=qdrant_url, prefer_grpc=False)

            if azure_endpoint:
                self.openai_client = AzureOpenAI(
                    api_key=openai_api_key,
                    azure_endpoint=azure_endpoint,
                    api_version=api_version or "2025-01-01-preview"
                )
            else:
                self.openai_client = OpenAI(api_key=openai_api_key)

            self.collection_name = collection_name
            # text-embedding-3-large: 3072 dims (highest quality)
            # text-embedding-3-small: 1536 dims (faster, cheaper)
            self.embedding_model = embedding_deployment or "text-embedding-3-large"
            self.embedding_dimensions = 3072 if "large" in self.embedding_model else 1536

            logger.info(f"✓ Connected to Qdrant at {qdrant_url}")
            logger.info(f"✓ Embedding model: {self.embedding_model} ({self.embedding_dimensions} dims)")
        except Exception as e:
            logger.error(f"✗ Failed to connect to Qdrant: {e}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check Qdrant server health.
        
        Returns:
            Dict with status and details
        """
        try:
            # qdrant_client exposes a .get_collections() or similar check
            collections = self.client.get_collections()
            return {
                'status': 'healthy',
                'collections': len(collections.collections)
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {'status': 'unhealthy', 'error': str(e)}
    
    def create_collection(self, recreate: bool = False, **kwargs) -> bool:
        """
        Create collection if it doesn't exist
        
        Args:
            recreate: If True, delete existing collection and create new
        
        Returns:
            True if created, False if already exists
        """
        try:
            # Check if exists
            self.client.get_collection(self.collection_name)
            
            if recreate:
                logger.info(f"Deleting existing collection: {self.collection_name}")
                self.client.delete_collection(self.collection_name)
            else:
                logger.info(f"✓ Collection '{self.collection_name}' already exists")
                return False
        except:
            pass
        
        # Create collection
        logger.info(f"Creating collection: {self.collection_name}...")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.embedding_dimensions,
                distance=Distance.COSINE
            )
        )
        logger.info(f"✓ Collection '{self.collection_name}' created")
        return True
    
    def generate_embeddings(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Generate embeddings for texts using OpenAI
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for API calls
        
        Returns:
            List of embedding vectors
        """
        all_embeddings = []
        
        logger.info(f"Generating embeddings for {len(texts)} texts...")
        
        for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
            batch = texts[i:i + batch_size]
            
            try:
                response = self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                logger.error(f"Error generating embeddings for batch {i}: {e}")
                # Add zero vectors as fallback
                all_embeddings.extend([[0.0] * self.embedding_dimensions] * len(batch))
        
        logger.info(f"✓ Generated {len(all_embeddings)} embeddings")
        return all_embeddings
    
    def _prepare_text_for_embedding(self, element: Dict[str, Any]) -> str:
        """
        Prepare element text for embedding
        Uses summary_medium if available, else content
        
        Args:
            element: Element dict with content and summaries
        
        Returns:
            Text to embed
        """
        # Prefer medium summary for embeddings (optimized length)
        if 'summary_medium' in element:
            return element['summary_medium']
        elif 'summary_short' in element:
            return element['summary_short']
        elif 'content' in element:
            content = element['content']
            # Truncate if too long
            return content[:2000] if len(content) > 2000 else content
        else:
            return f"{element.get('type', 'unknown')} element"
    
    def upsert_elements(self, elements: List[Dict[str, Any]], batch_size: int = 100) -> Dict[str, int]:
        """
        Add or update elements in Qdrant
        
        Args:
            elements: List of processed elements with metadata
            batch_size: Batch size for upsert
        
        Returns:
            Dict with success/failure counts
        """
        if len(elements) == 0:
            logger.warning("No elements to upsert")
            return {'success': 0, 'failed': 0, 'successful': 0, 'embeddings_generated': 0}
        
        logger.info(f"\n{'='*60}")
        logger.info(f"UPSERTING {len(elements)} ELEMENTS TO QDRANT")
        logger.info(f"{'='*60}\n")
        
        success_count = 0
        failed_count = 0
        embeddings_generated = 0
        total_batches = (len(elements) + batch_size - 1) // batch_size
        
        logger.info(f"Processing {total_batches} batches of {batch_size} (embed + upsert per batch)...")
        
        for i in tqdm(range(0, len(elements), batch_size), desc="Embed+Upsert batches", total=total_batches):
            batch_elements = elements[i:i + batch_size]
            
            # Step 1: Embed this batch
            try:
                texts = [self._prepare_text_for_embedding(elem) for elem in batch_elements]
                response = self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=texts
                )
                batch_embeddings = [item.embedding for item in response.data]
                embeddings_generated += len(batch_embeddings)
            except Exception as e:
                logger.error(f"Embedding error at batch {i//batch_size}: {e}")
                failed_count += len(batch_elements)
                continue  # Skip upsert for this batch, try next
            
            # Step 2: Build points
            points = []
            for element, embedding in zip(batch_elements, batch_embeddings):
                point_id = hashlib.sha256(element['element_id'].encode()).hexdigest()[:16]
                point_id = int(point_id, 16) % (10**15)
                
                payload = {
                    'element_id': element['element_id'],
                    'file_id': element['file_id'],
                    'filename': element['filename'],
                    'type': element['type'],
                    'source_type': element.get('source_type'),
                    'hierarchy_path': element.get('hierarchy_path', ''),
                    
                    # Content (truncated for payload size)
                    'content': (element.get('content', '') or '')[:2000],
                    
                    # Summaries
                    'summary_short': element.get('summary_short', ''),
                    'summary_medium': element.get('summary_medium', ''),
                    
                    # Position metadata
                    'element_index': element.get('element_index', 0),
                    'page_number': element.get('page_number'),
                    
                    # Relationships
                    'related_text_ids': element.get('related_text_ids', []),
                    'related_table_ids': element.get('related_table_ids', []),
                    'related_image_ids': element.get('related_image_ids', []),
                    'all_sibling_ids': element.get('all_sibling_ids', [])[:10],
                    
                    # Timestamps
                    'loaded_at': element.get('loaded_at', '')
                }
                points.append(PointStruct(id=point_id, vector=embedding, payload=payload))
            
            # Step 3: Upsert this batch immediately
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                success_count += len(points)
            except Exception as e:
                logger.error(f"Upsert error at batch {i//batch_size}: {e}")
                failed_count += len(points)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"UPSERT COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Success: {success_count}")
        logger.info(f"Failed:  {failed_count}")
        logger.info(f"{'='*60}\n")
        
        return {'success': success_count, 'successful': success_count, 'failed': failed_count, 'embeddings_generated': embeddings_generated}
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_by: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar elements
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filter_by: Optional metadata filters (e.g., {'type': 'text'})
        
        Returns:
            List of search results with scores
        """
        # Generate query embedding
        query_embedding = self.generate_embeddings([query])[0]
        
        # Build filter if provided
        query_filter = None
        if filter_by:
            if isinstance(filter_by, Filter):
                # Already a qdrant Filter object — use directly
                query_filter = filter_by
            elif isinstance(filter_by, dict):
                conditions = []
                for key, value in filter_by.items():
                    conditions.append(FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    ))
                if conditions:
                    query_filter = Filter(must=conditions)
        
        # Search (qdrant-client v1.17+ uses query_points instead of search)
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=top_k,
            query_filter=query_filter
        )
        
        # Format results
        formatted_results = []
        for result in response.points:
            formatted_results.append({
                'score': result.score,
                'element_id': result.payload.get('element_id'),
                'file_id': result.payload.get('file_id'),
                'filename': result.payload.get('filename'),
                'type': result.payload.get('type'),
                'hierarchy_path': result.payload.get('hierarchy_path'),
                'content': result.payload.get('content', ''),
                'summary_short': result.payload.get('summary_short'),
                'summary_medium': result.payload.get('summary_medium'),
                'page_number': result.payload.get('page_number'),
                'related_text_ids': result.payload.get('related_text_ids', []),
                'related_table_ids': result.payload.get('related_table_ids', []),
                'related_image_ids': result.payload.get('related_image_ids', []),
                'payload': result.payload
            })
        
        return formatted_results
    
    def search_with_relationships(
        self,
        query: str,
        top_k: int = 5,
        include_related: bool = True
    ) -> Dict[str, Any]:
        """
        Search and retrieve related elements automatically
        
        Args:
            query: Search query text
            top_k: Number of main results
            include_related: Whether to fetch related elements
        
        Returns:
            Dict with main results and related elements
        """
        # Get main results
        main_results = self.search(query, top_k=top_k)
        
        if not include_related:
            return {'main_results': main_results, 'related_elements': []}
        
        # Collect all related element IDs
        related_ids = set()
        for result in main_results:
            related_ids.update(result.get('related_text_ids', []))
            related_ids.update(result.get('related_table_ids', []))
            related_ids.update(result.get('related_image_ids', []))
        
        # Fetch related elements
        related_elements = []
        if related_ids:
            related_elements = self._fetch_by_element_ids(list(related_ids))
        
        return {
            'main_results': main_results,
            'related_elements': related_elements,
            'total_results': len(main_results) + len(related_elements)
        }
    
    def _fetch_by_element_ids(self, element_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch elements by their element_ids"""
        if not element_ids:
            return []
        
        # Search with filter
        results = []
        for element_id in element_ids[:20]:  # Limit to avoid too many requests
            try:
                search_results = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=Filter(
                        must=[FieldCondition(
                            key="element_id",
                            match=MatchValue(value=element_id)
                        )]
                    ),
                    limit=1
                )
                
                if search_results[0]:
                    point = search_results[0][0]
                    results.append({
                        'element_id': point.payload.get('element_id'),
                        'type': point.payload.get('type'),
                        'filename': point.payload.get('filename'),
                        'summary_short': point.payload.get('summary_short'),
                        'summary_medium': point.payload.get('summary_medium'),
                        'payload': point.payload
                    })
            except Exception as e:
                logger.warning(f"Could not fetch element {element_id}: {e}")
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                'collection_name': self.collection_name,
                'points_count': getattr(info, 'points_count', 0),
                'vectors_count': getattr(info, 'vectors_count', getattr(info, 'points_count', 0)),
                'indexed_vectors_count': getattr(info, 'indexed_vectors_count', 0),
                'status': getattr(info, 'status', 'unknown')
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
