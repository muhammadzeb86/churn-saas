"""
Schemas package for the RetainWise Analytics API
"""

from .waitlist import WaitlistRequest, WaitlistResponse, LeadInfo

__all__ = [
    "WaitlistRequest",
    "WaitlistResponse",
    "LeadInfo",
] 