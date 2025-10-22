from fastapi import Depends, HTTPException
from fastapi.security.api_key import APIKeyHeader
import os
import bcrypt
from fastapi.security import HTTPBearer
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import jwt

API_KEY = "jd_7mK9pL2nX8qR4vW6jY1zF3bH5tN0sA9cG7eU4xQ2wV8mP6rT1kJ3nL5h"
API_KEY_NAME = "Authorization"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)


def verify_api_key(api_key: str = Depends(api_key_header)):
    expected = f"Bearer {API_KEY}"
    if api_key != expected:
        raise HTTPException(status_code=403, detail="Invalid API KEY")
