import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def search_company_context(company_name: str) -> str:
    """
    Invisibly searches DuckDuckGo for the company name to gather background context.
    This is extremely helpful for determining if a company is a recruitment agency.
    """
    if not company_name or company_name.lower() in ["unknown", "confidential"]:
        return ""
        
    try:
        query = f'"{company_name}" UK recruitment agency'
        url = "https://html.duckduckgo.com/html/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        
        res = requests.post(url, data={"q": query}, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        
        context_lines = []
        snippets = soup.find_all("a", class_="result__snippet")
        
        for s in snippets[:2]:
            text = s.text.strip()
            if text:
                context_lines.append(f"- {text}")
                
        if context_lines:
            return "\n".join(context_lines)
            
    except Exception as e:
        logger.warning(f"Failed to perform background web search for {company_name}: {e}")
        
    return ""
