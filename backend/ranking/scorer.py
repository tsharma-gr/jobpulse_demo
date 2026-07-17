from datetime import datetime, timezone

class DeterministicRanker:
    """
    Calculates a deterministic final score based on multiple factors.
    Final Score = Match Score + Freshness Score + Distance Score + Industry Score + Confidence Score
    """
    
    @staticmethod
    def calculate_score(
        match_score: float, 
        confidence_score: float, 
        posted_date: datetime, 
        distance_miles: float, 
        is_exact_industry: bool
    ) -> float:
        
        # 1. Base Match Score (0 - 100)
        # Provided by AI
        
        # 2. Base Confidence Score (0 - 100)
        # Provided by AI
        
        # 3. Freshness Score (0 - 30)
        # Newer is better. Max 30 points for jobs posted today.
        freshness_score = 0.0
        if posted_date:
            days_old = (datetime.now(timezone.utc) - posted_date).days
            if days_old <= 0:
                freshness_score = 30.0
            elif days_old <= 7:
                freshness_score = 20.0
            elif days_old <= 14:
                freshness_score = 10.0
            elif days_old <= 30:
                freshness_score = 5.0
                
        # 4. Distance Score (0 - 20)
        # Closer is better.
        distance_score = 0.0
        if distance_miles <= 5:
            distance_score = 20.0
        elif distance_miles <= 15:
            distance_score = 15.0
        elif distance_miles <= 30:
            distance_score = 10.0
        elif distance_miles <= 50:
            distance_score = 5.0
            
        # 5. Industry Score (0 - 20)
        industry_score = 20.0 if is_exact_industry else 0.0
        
        # Normalize final score (we can weight these as needed, currently out of 270 theoretically, 
        # but we'll scale it to 100 for user display).
        total_raw = match_score + confidence_score + freshness_score + distance_score + industry_score
        
        # Scale to 100 assuming max realistic raw is around 250
        scaled = min((total_raw / 250.0) * 100, 100.0)
        
        return round(scaled, 2)

ranker = DeterministicRanker()
