"""
Hierarchical Context Preserver
Links related content (text, tables, images) from same document
Maintains relationships for better RAG retrieval
"""

from typing import List, Dict, Any, Set
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class HierarchicalContextPreserver:
    """
    Links related content elements from the same document
    Maintains hierarchical relationships for better retrieval
    """
    
    def __init__(self):
        """Initialize the context preserver"""
        self.file_to_elements = defaultdict(list)
        self.element_relationships = {}
        self._all_elements: List[Dict[str, Any]] = []
        logger.info("✓ HierarchicalContextPreserver initialized")
    
    @property
    def all_elements(self) -> List[Dict[str, Any]]:
        """Get all enriched elements across all processed documents"""
        return list(self._all_elements)
    
    def add_document_elements(self, document: Dict[str, Any] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Process a loaded document and create linked elements.
        
        Supports two calling conventions:
            add_document_elements(document_dict)
            add_document_elements(file_id=..., filename=..., text_chunks=..., tables=..., images=...)
        
        Args:
            document: Document dict from MultiFileLoader
            **kwargs: Alternative keyword-argument style
        
        Returns:
            List of enriched elements with relationship metadata
        """
        # Support keyword-argument calling style used by notebooks
        if document is None:
            document = {
                'file_id': kwargs.get('file_id'),
                'filename': kwargs.get('filename'),
                'text_chunks': kwargs.get('text_chunks', []),
                'tables': kwargs.get('tables', []),
                'images': kwargs.get('images', []),
            }
        file_id = document.get('file_id')
        if not file_id:
            logger.warning("Document missing file_id, skipping")
            return []
        
        enriched_elements = []
        all_element_ids = []
        
        # Collect all element IDs first
        for chunk in document.get('text_chunks', []):
            all_element_ids.append(chunk['element_id'])
        
        for table in document.get('tables', []):
            all_element_ids.append(table['element_id'])
        
        for image in document.get('images', []):
            all_element_ids.append(image['element_id'])
        
        # Now process each element and add relationships
        # Process text chunks
        for idx, chunk in enumerate(document.get('text_chunks', [])):
            enriched = self._enrich_element(
                element=chunk,
                file_id=file_id,
                document=document,
                element_index=idx,
                all_element_ids=all_element_ids
            )
            enriched_elements.append(enriched)
            self.file_to_elements[file_id].append(enriched['element_id'])
        
        # Process tables
        for idx, table in enumerate(document.get('tables', [])):
            enriched = self._enrich_element(
                element=table,
                file_id=file_id,
                document=document,
                element_index=idx,
                all_element_ids=all_element_ids,
                element_type='table'
            )
            enriched_elements.append(enriched)
            self.file_to_elements[file_id].append(enriched['element_id'])
        
        # Process images
        for idx, image in enumerate(document.get('images', [])):
            enriched = self._enrich_element(
                element=image,
                file_id=file_id,
                document=document,
                element_index=idx,
                all_element_ids=all_element_ids,
                element_type='image'
            )
            enriched_elements.append(enriched)
            self.file_to_elements[file_id].append(enriched['element_id'])
        
        logger.info(f"Created {len(enriched_elements)} linked elements from {document.get('filename')}")
        self._all_elements.extend(enriched_elements)
        return enriched_elements
    
    def _enrich_element(
        self,
        element: Dict[str, Any],
        file_id: str,
        document: Dict[str, Any],
        element_index: int,
        all_element_ids: List[str],
        element_type: str = None
    ) -> Dict[str, Any]:
        """
        Enrich an element with hierarchical metadata and relationships
        """
        element_id = element.get('element_id')
        
        # Determine element type
        if not element_type:
            element_type = element.get('type', 'text')
        
        # Find related elements (same document)
        related_text = [eid for eid in all_element_ids if 'text' in eid and eid != element_id]
        related_tables = [eid for eid in all_element_ids if 'table' in eid and eid != element_id]
        related_images = [eid for eid in all_element_ids if 'image' in eid and eid != element_id]
        
        # Build enriched element
        enriched = {
            # Original content
            'element_id': element_id,
            'content': element.get('content', ''),
            'type': element_type,
            
            # File-level metadata
            'file_id': file_id,
            'filename': document.get('filename'),
            'filepath': document.get('filepath'),
            'source_type': document.get('type'),  # pdf, docx, html, etc.
            
            # Position metadata
            'element_index': element_index,
            'page_number': element.get('metadata', {}).get('page_number'),
            
            # Relationship metadata
            'related_text_ids': related_text[:5],  # Limit to top 5
            'related_table_ids': related_tables[:5],
            'related_image_ids': related_images[:5],
            'all_sibling_ids': [eid for eid in all_element_ids if eid != element_id][:10],
            
            # Context hierarchy
            'hierarchy_path': self._build_hierarchy_path(document, element),
            
            # Additional metadata from original element
            'original_metadata': element.get('metadata', {}),
            
            # Timestamp
            'loaded_at': document.get('loaded_at')
        }
        
        # Store relationships
        self.element_relationships[element_id] = {
            'related_text': related_text,
            'related_tables': related_tables,
            'related_images': related_images,
            'file_id': file_id
        }
        
        return enriched
    
    def _build_hierarchy_path(self, document: Dict[str, Any], element: Dict[str, Any]) -> str:
        """
        Build a hierarchical path for the element
        Example: "document_name > Section 1 > Subsection A"
        """
        parts = [document.get('filename', 'Unknown')]
        
        # Add page number if available
        page_num = element.get('metadata', {}).get('page_number')
        if page_num:
            parts.append(f"Page {page_num}")
        
        # Add section if available
        section = element.get('metadata', {}).get('section')
        if section:
            parts.append(section)
        
        return " > ".join(parts)
    
    def get_related_elements(self, element_id: str) -> Dict[str, List[str]]:
        """
        Get all related elements for a given element ID
        
        Args:
            element_id: The element ID to find relationships for
        
        Returns:
            Dict with lists of related element IDs by type
        """
        return self.element_relationships.get(element_id, {})
    
    def get_file_elements(self, file_id: str) -> List[str]:
        """
        Get all element IDs from a specific file
        
        Args:
            file_id: The file ID
        
        Returns:
            List of element IDs
        """
        return self.file_to_elements.get(file_id, [])
    
    def process_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process multiple documents and create all linked elements
        
        Args:
            documents: List of documents from MultiFileLoader
        
        Returns:
            List of all enriched elements with relationships
        """
        all_enriched = []
        
        logger.info(f"\n{'='*60}")
        logger.info("PROCESSING DOCUMENT RELATIONSHIPS")
        logger.info(f"{'='*60}\n")
        
        for doc in documents:
            if 'error' in doc:
                logger.warning(f"Skipping document with error: {doc.get('filename')}")
                continue
            
            enriched = self.add_document_elements(doc)
            all_enriched.extend(enriched)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Total enriched elements: {len(all_enriched)}")
        logger.info(f"Total files processed: {len(self.file_to_elements)}")
        logger.info(f"Total relationships: {len(self.element_relationships)}")
        logger.info(f"{'='*60}\n")
        
        return all_enriched
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about processed elements"""
        stats = {
            'total_files': len(self.file_to_elements),
            'total_elements': sum(len(elements) for elements in self.file_to_elements.values()),
            'total_relationships': len(self.element_relationships),
            'elements_by_file': {
                file_id: len(elements) 
                for file_id, elements in self.file_to_elements.items()
            }
        }
        return stats


# Backward compatibility alias
ContextPreserver = HierarchicalContextPreserver
