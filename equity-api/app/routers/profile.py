from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.services.profile_service import get_profile, save_profile

router = APIRouter()


class ProfileUpdate(BaseModel):
    name: str = ""
    sectors: List[str] = []
    risk_appetite: str = "balanced"
    default_horizon: str = "long"


@router.get("")
def read_profile():
    """Get the saved user profile (or defaults if none exists yet)."""
    return get_profile()


@router.post("")
def update_profile(profile: ProfileUpdate):
    """Save user preferences from the onboarding form."""
    return save_profile(profile.dict())