"""
User-related Pydantic schemas and validators.
Shared password strength validation for registration and user creation.
"""
import re
from pydantic import field_validator


def validate_password_strength(value: str) -> str:
    """
    Validate password meets security requirements.
    Raises ValueError with descriptive message if validation fails.
    
    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    """
    if not value or len(value) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one digit")
    return value


