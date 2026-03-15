from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from jose import JWTError
from starlette.status import HTTP_401_UNAUTHORIZED
from Database.MongoDB import GroupChat_Collection
from Services.User_service import user_collection
from Utils.JWT import verify_access_token

#------middleware for get user tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = verify_access_token(token)
        username: str = payload.get("sub")
        if not username: 
            raise HTTPException( status_code=status.HTTP_401_UNAUTHORIZED, detail="Không xác thực được token !!")
        user = user_collection.find_one({"Username": username})
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User không tồn tại hoặc đã bị xóa !!")
        return user
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Không xác thực được token hoặc token đã bị hết hạn !!")

def require_owner(token: str = Depends(oauth2_scheme)):
        payload = verify_access_token(token)
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail= "Không xác thực được token !!")
    