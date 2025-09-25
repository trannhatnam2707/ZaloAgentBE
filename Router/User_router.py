from fastapi import APIRouter, HTTPException
from Schemas.User_schema import UserCreate, UserLogin, UserResponse
from Services.User_service import create_user, delete_user, get_user_by_id, login_user


router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/register", response_model=UserResponse)
def api_register_user(user: UserCreate ):
    try: 
        return create_user(user.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=dict)
def api_login_user(user_login: UserLogin):
    try:
        return login_user(user_login.username, user_login.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

# Get All Users
# @router.get("/", response_model=list[UserResponse])
# def api_get_all_users():
#     return get_all_users()

# Get User by ID
@router.get("/{user_id}", response_model=UserResponse)
def api_get_user_by_id(user_id: str):
    try:
        return get_user_by_id(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{user_id}")
def api_delete_user(user_id: str):
    success = delete_user(user_id)
    if not success:
        raise HTTPException (status_code = 404, detail="User not found")
    return {"success": True, "message": "User deleted Successfully"}