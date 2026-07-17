import re

class MarkdownCleaner:
    """
    Cleans up the raw markdown returned by Crawl4AI to minimize token usage for the LLM.
    """
    @staticmethod
    def clean(raw_markdown: str) -> str:
        if not raw_markdown:
            return ""
            
        # Remove navigation, headers, footers (simplistic heuristic)
        # In a real scenario, Crawl4AI's extraction strategies often handle this,
        # but this adds an extra layer of token saving.
        
        # Remove empty links [text]() 
        cleaned = re.sub(r'\[([^\]]+)\]\(\)', r'\1', raw_markdown)
        
        # Remove excessive blank lines
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        return cleaned.strip()

markdown_cleaner = MarkdownCleaner()
