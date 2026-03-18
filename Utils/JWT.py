from dotenv import load_dotenv
import os
from datetime import timedelta
from datetime import datetime
from fastapi import HTTPException, status
from jose import JWTError, jwt


load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRES_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRES_MINUTES"))
REFRESH_TOKEN_EXPIRES_DAY = int(os.getenv("REFRESH_TOKEN_EXPIRES_DAY"))

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expires = datetime.utcnow() + (expires_delta or timedelta(minutes=int(ACCESS_TOKEN_EXPIRES_MINUTES)))
    if "type" not in to_encode:
        to_encode["type"] = "access" 
    to_encode["exp"] = expires
    endcoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return endcoded_jwt

def create_refresh_token(data: dict, expires_delta: timedelta | None = None ) -> str: 
    to_encode = data.copy()
    expires = datetime.utcnow() + (expires_delta or timedelta(minutes=int(REFRESH_TOKEN_EXPIRES_DAY)))
    if "type" not in to_encode:
        to_encode["type"] = "refresh"
    to_encode["exp"] = expires
    endcoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return endcoded_jwt

#---decode access token------#
def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code = status.HTTP_401_UNAUTHORIZED, detail = "Invalid token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail ="Invalid or expired access token")
#----decode refresh token-----#
def verify_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail = "Invalid or expired refresh token")