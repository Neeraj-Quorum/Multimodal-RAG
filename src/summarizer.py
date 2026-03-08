"""
Intelligent Summarization System
Summarizes text content and describes images using LLMs
Optimizes content for embedding and retrieval
"""

from typing import Dict, Any, List
import logging
from openai import OpenAI, AzureOpenAI
import base64

logger = logging.getLogger(__name__)


class IntelligentSummarizer:
    """
    Summarize content intelligently:
    - Text: Create multi-level summaries (short, medium, full)
    - Images: Describe using GPT-4 Vision
    - Code: Extract structure and purpose (no summarization)
    - Tables: Compress to key insights
    """
    
    def __init__(self, openai_api_key: str, model: str = "gpt-4.1",
                 text_model: str = None, vision_model: str = None,
                 azure_endpoint: str = None, api_version: str = None,
                 azure_deployment: str = None):
        """
        Initialize the summarizer.

        For Azure OpenAI, pass azure_endpoint and api_version.
        The deployment name is used in place of the model name.

        Args:
            openai_api_key: OpenAI or Azure OpenAI API key
            model: Model/deployment name (default: gpt-4.1)
            text_model: Explicit model for text summarization (overrides model)
            vision_model: Explicit model for image description (overrides model)
            azure_endpoint: Azure OpenAI endpoint URL (enables Azure mode)
            api_version: Azure OpenAI API version
            azure_deployment: Azure deployment name (overrides model for Azure)
        """
        if azure_endpoint:
            self.client = AzureOpenAI(
                api_key=openai_api_key,
                azure_endpoint=azure_endpoint,
                api_version=api_version or "2025-01-01-preview"
            )
        else:
            self.client = OpenAI(api_key=openai_api_key)

        resolved_model = azure_deployment or text_model or model
        self.model = resolved_model
        self.vision_model = azure_deployment or vision_model or resolved_model  # gpt-4.1 has vision built-in
        
        # Summarization thresholds
        self.text_length_threshold = 1000  # Characters
        self.summarization_stats = {
            'text_summarized': 0,
            'images_described': 0,
            'code_processed': 0,
            'tables_summarized': 0,
            'total_api_calls': 0
        }
        
        logger.info(f"✓ IntelligentSummarizer initialized with model: {model}")
    
    def should_summarize_text(self, text: str) -> bool:
        """Determine if text needs summarization"""
        return len(text) > self.text_length_threshold
    
    def summarize_text(self, text: str, target_length: str = "medium") -> Dict[str, str]:
        """
        Create multi-level summaries of text
        
        Args:
            text: Text to summarize
            target_length: "short" (50 chars), "medium" (500 chars), or "full"
        
        Returns:
            Dict with different summary levels
        """
        if not self.should_summarize_text(text):
            return {
                'short': text[:50] + "..." if len(text) > 50 else text,
                'medium': text[:500] + "..." if len(text) > 500 else text,
                'full': text,
                'was_summarized': False
            }
        
        try:
            # Create summaries at different lengths
            summaries = {}
            
            # Short summary (50 chars)
            short_prompt = f"Summarize in ONE sentence (max 50 chars):\n\n{text[:2000]}"
            short_response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise summarizer. Create extremely concise summaries."},
                    {"role": "user", "content": short_prompt}
                ],
                max_tokens=20,
                temperature=0.3
            )
            summaries['short'] = short_response.choices[0].message.content.strip()
            
            # Medium summary (500 chars)
            medium_prompt = f"Summarize this text in 2-3 sentences (max 500 chars), preserving key technical details:\n\n{text[:4000]}"
            medium_response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a technical summarizer. Preserve important details."},
                    {"role": "user", "content": medium_prompt}
                ],
                max_tokens=150,
                temperature=0.3
            )
            summaries['medium'] = medium_response.choices[0].message.content.strip()
            
            # Full context (original)
            summaries['full'] = text
            summaries['was_summarized'] = True
            
            self.summarization_stats['text_summarized'] += 1
            self.summarization_stats['total_api_calls'] += 2
            
            return summaries
            
        except Exception as e:
            logger.error(f"Error summarizing text: {e}")
            return {
                'short': text[:50],
                'medium': text[:500],
                'full': text,
                'error': str(e),
                'was_summarized': False
            }
    
    def describe_image(self, image_base64: str, context: str = "") -> Dict[str, str]:
        """
        Describe image using GPT-4 Vision
        
        Args:
            image_base64: Base64 encoded image
            context: Optional context about the image
        
        Returns:
            Dict with image descriptions
        """
        try:
            # Prepare prompt
            prompt = "Describe this image in detail. Include:"
            prompt += "\n1. What the image shows"
            prompt += "\n2. Key visual elements"
            prompt += "\n3. Any text or labels visible"
            prompt += "\n4. Technical details (if diagram/chart)"
            
            if context:
                prompt += f"\n\nContext: {context}"
            
            # Call GPT-4 Vision
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            description = response.choices[0].message.content.strip()
            
            # Create short version
            short_desc_response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Create a 1-sentence description (max 50 chars)."},
                    {"role": "user", "content": f"Summarize: {description}"}
                ],
                max_tokens=20,
                temperature=0.3
            )
            short_desc = short_desc_response.choices[0].message.content.strip()
            
            self.summarization_stats['images_described'] += 1
            self.summarization_stats['total_api_calls'] += 2
            
            return {
                'short': short_desc,
                'full': description,
                'was_described': True
            }
            
        except Exception as e:
            logger.error(f"Error describing image: {e}")
            return {
                'short': "Image",
                'full': f"Image (description failed: {str(e)})",
                'error': str(e),
                'was_described': False
            }
    
    def extract_code_structure(self, code: str, language: str) -> Dict[str, Any]:
        """
        Extract code structure without full summarization
        Preserve the code but add metadata
        
        Args:
            code: Source code
            language: Programming language
        
        Returns:
            Dict with code structure info
        """
        try:
            # Use LLM to extract high-level structure
            prompt = f"Analyze this {language} code and provide:\n"
            prompt += "1. Main purpose (1 sentence)\n"
            prompt += "2. Key functions/classes (list)\n"
            prompt += "3. Dependencies (list)\n\n"
            prompt += f"Code:\n{code[:2000]}"
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a code analyzer. Be concise."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            analysis = response.choices[0].message.content.strip()
            
            self.summarization_stats['code_processed'] += 1
            self.summarization_stats['total_api_calls'] += 1
            
            return {
                'short': f"{language} code",
                'structure': analysis,
                'full': code,  # Keep full code
                'language': language,
                'lines': len(code.split('\n')),
                'was_analyzed': True
            }
            
        except Exception as e:
            logger.error(f"Error analyzing code: {e}")
            return {
                'short': f"{language} code",
                'structure': "Analysis failed",
                'full': code,
                'language': language,
                'lines': len(code.split('\n')),
                'error': str(e),
                'was_analyzed': False
            }
    
    def summarize_table(self, table_content: str) -> Dict[str, str]:
        """
        Summarize table to key insights
        
        Args:
            table_content: Table content as string
        
        Returns:
            Dict with table summary
        """
        try:
            prompt = "Summarize this table in 2-3 sentences. Include:"
            prompt += "\n1. What the table shows"
            prompt += "\n2. Key data points or patterns"
            prompt += "\n3. Any important values\n\n"
            prompt += f"Table:\n{table_content[:2000]}"
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a data analyst. Summarize tables clearly."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Short version
            short = summary.split('.')[0][:50]
            
            self.summarization_stats['tables_summarized'] += 1
            self.summarization_stats['total_api_calls'] += 1
            
            return {
                'short': short,
                'medium': summary,
                'full': table_content,
                'was_summarized': True
            }
            
        except Exception as e:
            logger.error(f"Error summarizing table: {e}")
            return {
                'short': "Table",
                'medium': table_content[:500],
                'full': table_content,
                'error': str(e),
                'was_summarized': False
            }
    
    def process_element(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process any element type and add summaries
        
        Args:
            element: Element from context preserver
        
        Returns:
            Element with added summary fields
        """
        element_type = element.get('type')
        content = element.get('content', '')
        
        if element_type == 'text':
            summaries = self.summarize_text(content)
            element['summary_short'] = summaries['short']
            element['summary_medium'] = summaries['medium']
            element['summary_full'] = summaries['full']
            element['was_summarized'] = summaries['was_summarized']
        
        elif element_type == 'image':
            # Check if image data exists
            if 'image_data' in element or 'content' in element:
                image_data = element.get('image_data') or element.get('content')
                descriptions = self.describe_image(image_data)
                element['summary_short'] = descriptions['short']
                element['summary_full'] = descriptions['full']
                element['was_described'] = descriptions['was_described']
        
        elif element_type == 'code':
            language = element.get('language', 'unknown')
            structure = self.extract_code_structure(content, language)
            element['summary_short'] = structure['short']
            element['structure_analysis'] = structure['structure']
            element['was_analyzed'] = structure['was_analyzed']
        
        elif element_type == 'table':
            summaries = self.summarize_table(content)
            element['summary_short'] = summaries['short']
            element['summary_medium'] = summaries['medium']
            element['was_summarized'] = summaries['was_summarized']
        
        return element
    
    def process_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process multiple elements
        
        Args:
            elements: List of elements from context preserver
        
        Returns:
            List of elements with summaries
        """
        logger.info(f"\n{'='*60}")
        logger.info("SUMMARIZING ELEMENTS")
        logger.info(f"{'='*60}\n")
        
        processed_elements = []
        total = len(elements)
        
        for idx, element in enumerate(elements, 1):
            if idx % 10 == 0:
                logger.info(f"Processing element {idx}/{total}...")
            
            processed = self.process_element(element)
            processed_elements.append(processed)
        
        logger.info(f"\n{'='*60}")
        logger.info("SUMMARIZATION STATISTICS")
        logger.info(f"{'='*60}")
        logger.info(f"Text summarized:    {self.summarization_stats['text_summarized']}")
        logger.info(f"Images described:   {self.summarization_stats['images_described']}")
        logger.info(f"Code analyzed:      {self.summarization_stats['code_processed']}")
        logger.info(f"Tables summarized:  {self.summarization_stats['tables_summarized']}")
        logger.info(f"Total API calls:    {self.summarization_stats['total_api_calls']}")
        logger.info(f"{'='*60}\n")
        
        return processed_elements
    
    def get_statistics(self) -> Dict[str, int]:
        """Get summarization statistics"""
        return self.summarization_stats.copy()


# Backward compatibility
class Summarizer(IntelligentSummarizer):
    """Alias for backward compatibility"""
    pass
