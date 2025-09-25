from unittest.mock import Base
from pydantic import BaseModel


class UserBase(BaseModel):
    username: str
   
class UserCreate(UserBase):
    password: str  #them password khi tao user

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: str
   


