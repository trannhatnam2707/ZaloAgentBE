from fastapi import FastAPI
from Config.Cors_config import configure_cors

from Router import Ask_router, Report_router, User_router


app = FastAPI()

# Cấu hình CORS
configure_cors(app)

# Đăng ký các router
app.include_router(Report_router.router)
app.include_router(User_router.router)
app.include_router(Ask_router.router)
