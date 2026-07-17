from pydantic import BaseModel
from typing import Optional

class DiscoveredJob(BaseModel):
    job_title: str
    company_name: str
    location: str
    job_site: str
    job_url: str
    date_posted: Optional[str] = None
    job_type: Optional[str] = None
    industry_match: Optional[str] = None
    reason_for_match: Optional[str] = None
    match_score: Optional[int] = None
    full_text: Optional[str] = None
