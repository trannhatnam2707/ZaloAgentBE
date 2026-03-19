from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status, Path
from jose import JWTError
from bson.errors import InvalidId
from bson.objectid import ObjectId

from Database.MongoDB import Conversation_collection
from Services.User_service import user_collection
from Utils.JWT import verify_access_token

#------middleware for get user tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # 1. Giải mã token
        payload = verify_access_token(token)
        
        # 2. Lấy user_id từ trường "sub" (Vì lúc login ta lưu id vào sub)
        user_id: str = payload.get("sub")
        if not user_id: 
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Không xác thực được token !!")
            
        # 3. Tìm user trong DB theo _id
        user = user_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User không tồn tại hoặc đã bị xóa !!")
            
        return user
        
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Không xác thực được token hoặc token đã bị hết hạn !!")
    except InvalidId:
         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token chứa ID không hợp lệ !!")


def require_owner(
    conversation_id: str = Path(..., description="ID của cuộc hôi thoai trên URL"), 
    token: str = Depends(oauth2_scheme)
):
    try:
        # 1. Giải mã token và lấy user_id
        payload = verify_access_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Không xác thực được token !!")
            
        # 2. Tìm User trong DB
        user = user_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=401, detail="Người dùng không tồn tại")

        # 3. Tìm Group trong DB
        conversation = Conversation_collection.find_one({"_id": ObjectId(conversation_id)})
        if not conversation:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")

        #4. CHỐT CHẶN KIỂM TRA QUYỀN: 
        # Bắt buộc type phải là 'group' và owner_id phải khớp
        if conversation.get("type") != "group":
            raise HTTPException(status_code=400, detail="Đây là chat 1-1, không có chức năng chủ nhóm!")
            
        if str(conversation.get("owner_id")) != str(user["_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Từ chối truy cập! Chỉ chủ nhóm mới có quyền thực hiện hành động này."
            )

        return conversation

    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ hoặc đã hết hạn")
    except InvalidId:
        raise HTTPException(status_code=400, detail="Mã group_id hoặc user_id không hợp chuẩn ObjectId")