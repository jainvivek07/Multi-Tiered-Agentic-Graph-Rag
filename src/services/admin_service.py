from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from src.models.sql import ChatMessage, ChatSession, User

class AdminService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_dashboard_metrics(self) -> dict:
        """
        Runs all dashboard aggregations in a single DB round trip where possible.
        """
        # Total queries (assistant messages only)
        total_queries = await self.session.scalar(
            select(func.count(ChatMessage.id)).where(ChatMessage.role == "assistant")
        ) or 0

        # Total tokens across all responses
        total_tokens = await self.session.scalar(
            select(func.sum(ChatMessage.total_tokens)).where(ChatMessage.role == "assistant")
        ) or 0

        # Prompt vs completion token split
        total_prompt = await self.session.scalar(
            select(func.sum(ChatMessage.prompt_tokens)).where(ChatMessage.role == "assistant")
        ) or 0
        total_completion = await self.session.scalar(
            select(func.sum(ChatMessage.completion_tokens)).where(ChatMessage.role == "assistant")
        ) or 0

        # Average latency
        avg_latency = await self.session.scalar(
            select(func.avg(ChatMessage.latency_ms)).where(ChatMessage.role == "assistant")
        ) or 0

        # Cache hit rate
        cache_hits = await self.session.scalar(
            select(func.count(ChatMessage.id)).where(ChatMessage.route_taken == "cache_hit")
        ) or 0

        # Route distribution
        route_counts_result = await self.session.execute(
            select(ChatMessage.route_taken, func.count(ChatMessage.id))
            .where(ChatMessage.role == "assistant")
            .group_by(ChatMessage.route_taken)
        )
        route_distribution = {"vector": 0, "graph": 0, "hybrid": 0, "cache_hit": 0}
        for row in route_counts_result.all():
            if row[0]:
                route_distribution[row[0]] = row[1]

        # Active users (users with at least one session)
        active_users = await self.session.scalar(
            select(func.count(func.distinct(ChatSession.user_id)))
        ) or 0

        return {
            "total_queries_processed": total_queries,
            "total_tokens_used": total_tokens,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "avg_latency_ms": round(float(avg_latency), 2),  # Fixed key
            "cache_hit_count": cache_hits,
            "cache_hit_rate": round((cache_hits / total_queries * 100), 2) if total_queries > 0 else 0, # Fixed key
            "route_distribution": route_distribution,
            "active_users": active_users,
            "average_tokens_per_query": round(total_tokens / total_queries, 2) if total_queries > 0 else 0,
        }
