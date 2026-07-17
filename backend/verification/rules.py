from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple

class BusinessRulesEngine:
    """
    Evaluates basic business rules before sending data to the AI.
    This saves expensive API calls by filtering out obvious mismatches.
    """
    
    @staticmethod
    def evaluate(job_data: Dict[str, Any], search_criteria: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Returns (passed, reason)
        """
        # 1. Posted within 90 days
        posted_date = job_data.get("posted_date")
        if posted_date:
            if isinstance(posted_date, str):
                try:
                    posted_date = datetime.fromisoformat(posted_date)
                except ValueError:
                    posted_date = None
                    
            if posted_date:
                ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
                # Make naive dates aware for comparison if needed
                if posted_date.tzinfo is None:
                    posted_date = posted_date.replace(tzinfo=timezone.utc)
                    
                if posted_date < ninety_days_ago:
                    return False, "Job posted more than 90 days ago."
                    
        # 2. Basic Location check (can be improved with geocoding, but simple text match for now)
        target_location = search_criteria.get("location", "").lower()
        job_location = job_data.get("location", "").lower()
        if target_location and target_location not in job_location:
            # We don't strictly reject on simple string mismatch because radius matters,
            # but this is a placeholder for actual distance calculation.
            pass
            
        # 3. Agency Check (Basic heuristic, AI does this better later, but we can filter obvious ones)
        company_name = job_data.get("company_name", "").lower()
        agency_keywords = ["recruitment", "staffing", "agency", "resourcing"]
        if any(keyword in company_name for keyword in agency_keywords):
            return False, f"Detected recruitment agency: {company_name}"
            
        return True, "Passed business rules."

rules_engine = BusinessRulesEngine()
