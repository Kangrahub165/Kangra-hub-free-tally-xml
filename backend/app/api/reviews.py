import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import get_current_user, CurrentUser
from app.core.db import (
    submit_rating_review,
    get_ratings_reviews,
    add_user_activity_log,
    create_admin_notification
)

logger = logging.getLogger("kangra_hub.reviews")

router = APIRouter(prefix="/reviews", tags=["Reviews & Ratings"])


class SubmitReviewRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Star rating between 1 and 5")
    review_text: Optional[str] = Field(None, max_length=1000, description="User comments or feedback")


@router.post("")
@router.post("/")
async def create_or_update_review(
    payload: SubmitReviewRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Submits or updates a 1 to 5 star rating and review from an authenticated user.
    """
    review_id = submit_rating_review(
        user_id=current_user.id,
        user_name=current_user.full_name or "Verified User",
        user_email=current_user.email,
        rating=payload.rating,
        review_text=payload.review_text or "",
        moderation_status="APPROVED"
    )

    # Log user activity
    add_user_activity_log(
        user_id=current_user.id,
        user_email=current_user.email,
        action="RATING_SUBMITTED",
        module="REVIEWS",
        resource_id=review_id,
        status="SUCCESS",
        metadata={"rating": payload.rating, "has_text": bool(payload.review_text)}
    )

    # If rating is high or low, alert admin
    if payload.rating <= 2:
        create_admin_notification(
            type="LOW_RATING",
            title=f"Low Rating ({payload.rating}★) from {current_user.email}",
            message=payload.review_text or f"User submitted a {payload.rating}-star rating.",
            severity="WARNING",
            related_user_id=current_user.id
        )

    return {
        "success": True,
        "message": "Thank you for your rating and feedback!",
        "review_id": review_id,
        "rating": payload.rating,
        "review_text": payload.review_text
    }


@router.get("/my")
async def get_my_review(current_user: CurrentUser = Depends(get_current_user)):
    """
    Retrieves the currently authenticated user's submitted review if present.
    """
    user_reviews = get_ratings_reviews(user_id=current_user.id, limit=1)
    if not user_reviews:
        return {"has_review": False, "review": None}
    
    return {
        "has_review": True,
        "review": user_reviews[0]
    }


@router.get("/public")
async def get_public_reviews(limit: int = 20):
    """
    Retrieves approved user reviews and aggregate rating metrics for public display.
    """
    reviews = get_ratings_reviews(status="APPROVED", limit=min(limit, 100))
    
    total_reviews = len(reviews)
    if total_reviews > 0:
        avg_rating = round(sum(r["rating"] for r in reviews) / total_reviews, 1)
        stars_breakdown = {
            "5": sum(1 for r in reviews if r["rating"] == 5),
            "4": sum(1 for r in reviews if r["rating"] == 4),
            "3": sum(1 for r in reviews if r["rating"] == 3),
            "2": sum(1 for r in reviews if r["rating"] == 2),
            "1": sum(1 for r in reviews if r["rating"] == 1),
        }
    else:
        avg_rating = 5.0
        stars_breakdown = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}

    # Mask user email for privacy in public endpoint (e.g. j***@example.com)
    sanitized_reviews = []
    for r in reviews:
        email = r.get("user_email") or ""
        masked_email = ""
        if "@" in email:
            parts = email.split("@")
            masked_email = f"{parts[0][0]}***@{parts[1]}"
        
        sanitized_reviews.append({
            "id": r["id"],
            "user_name": r.get("user_name") or "Verified Customer",
            "masked_email": masked_email,
            "rating": r["rating"],
            "review_text": r.get("review_text"),
            "created_at": r.get("created_at")
        })

    return {
        "average_rating": avg_rating,
        "total_reviews": total_reviews,
        "stars_breakdown": stars_breakdown,
        "reviews": sanitized_reviews
    }
