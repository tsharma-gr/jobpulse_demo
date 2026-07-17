import json
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
from openai import AsyncOpenAI
import asyncio
from backend.config.settings import settings
from backend.utils.web_search import search_company_context

logger = logging.getLogger(__name__)

class JobAIAnalysis(BaseModel):
    is_fit: bool
    confidence_score: int = 0
    seniority_level: str = ""
    skills_matched: list[str] = []
    industry_match: str = ""
    hiring_confidence: str = ""
    job_summary: str = ""
    reason_for_match: str = ""

class DeepSeekParser:
    """
    Integrates with the DeepSeek API to parse markdown job descriptions
    and return structured JSON analysis.
    """
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.model = settings.AI_MODEL
        # DeepSeek is OpenAI API compatible
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        ) if self.api_key else None

    async def analyze_job(self, markdown_content: str, search_criteria: dict, company_name: str = None) -> Optional[JobAIAnalysis]:
        """
        Sends the job description, search criteria, and web context to DeepSeek.
        """
        if not self.client:
            logger.warning("DeepSeek API Key missing! Returning mock data.")
            await asyncio.sleep(2)
            return JobAIAnalysis(
                is_fit=True,
                confidence_score=90,
                seniority_level="Unknown",
                skills_matched=[],
                industry_match="Unknown",
                hiring_confidence="Medium",
                job_summary="MOCK: API key not configured.",
                reason_for_match="MOCK: Please add DEEPSEEK_API_KEY to backend/.env"
            )

        logger.info("Sending job data to DeepSeek API for analysis...")
        
        search_context = ""
        if company_name:
            loop = asyncio.get_event_loop()
            snippet = await loop.run_in_executor(None, search_company_context, company_name)
            if snippet:
                search_context = f"\nBackground Web Search Context for '{company_name}':\n{snippet}\n"
        
        prompt = f"""
You are an expert technical recruiter AI. Analyze this job description against the following user search criteria:
Criteria: {json.dumps(search_criteria, indent=2)}
{search_context}
CRITICAL INSTRUCTIONS:
1. Identify the core business of the company and the primary responsibilities of the role.
2. Determine if the job is a FIT or UNFIT for the user's criteria.
3. The hiring company MUST be highly specialized in the specific sector/industry requested by the user. If the user requested "Joinery", the company must specialize in Joinery.
4. STRICT SPECIALIZATION RULE: If the company is just a generic construction firm, general main contractor, or fit-out company, and NOT highly specialized in the requested sector, you MUST mark it as UNFIT (is_fit: false). We ONLY want specialized companies.
5. Base your final FIT/UNFIT decision on whether the employer's core business perfectly matches the user's requested sector.
6. [RECRUITMENT AGENCY EXCLUSION]: If the hiring company is a Recruitment Agency, Staffing Agency, or Talent Acquisition firm (e.g., their name contains "Recruitment", "Resourcing", or the description says they are an agency recruiting on behalf of a client, or the Background Web Search Context identifies them as an agency), mark it as UNFIT (is_fit: false) and state this in the reason. The user is a recruitment company looking for direct employer clients, not competitors.
7. [LARGE ENTERPRISE EXCLUSION]: If the hiring company is a massive global enterprise or extremely large corporation that almost certainly has its own internal Talent Acquisition / HR department, mark it as UNFIT (is_fit: false). The user wants mid-sized or standard companies that actually need external recruitment services to fill roles.

Job Description Markdown:
{markdown_content[:6000]}  # Trim to avoid context window issues if extremely long

Provide a structured JSON response matching this schema:
{{
    "detected_industry": str (The actual industry you found in the text),
    "is_industry_match": bool (True if it reasonably aligns with the user's requested industries),
    "is_fit": bool (True if the job is a FIT, False if UNFIT),
    "confidence_score": int (0-100),
    "seniority_level": str,
    "skills_matched": [str],
    "industry_match": str (The same as detected_industry),
    "hiring_confidence": str,
    "job_summary": str (1-2 sentences),
    "reason_for_match": str (Explain why it was marked as FIT or UNFIT)
}}
"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a recruitment AI that outputs raw JSON strictly matching the requested schema. No markdown formatting blocks."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            raw_json = response.choices[0].message.content
            parsed = json.loads(raw_json)
            return JobAIAnalysis(**parsed)
            
        except Exception as e:
            print(f"DeepSeek API error: {e}")
            return None

deepseek_parser = DeepSeekParser()
