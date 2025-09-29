from fastapi import FastAPI

from Router import Ask_router, Report_router, User_router


app = FastAPI()

# Đăng ký các router
app.include_router(Report_router.router)
app.include_router(User_router.router)
app.include_router(Ask_router.router)
