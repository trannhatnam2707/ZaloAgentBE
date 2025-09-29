from fastapi.middleware.cors import CORSMiddleware

def configure_cors(app):
    """
    Cấu hình CORS cho FastAPI app
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Cho phép tất cả origins
        allow_credentials=True,
        allow_methods=["*"],  # Cho phép tất cả HTTP methods
        allow_headers=["*"],  # Cho phép tất cả headers
    )
    
    # Hoặc cấu hình cụ thể hơn:
    # app.add_middleware(
    #     CORSMiddleware,
    #     allow_origins=["http://localhost:3000", "http://localhost:8080"],
    #     allow_credentials=True,
    #     allow_methods=["GET", "POST", "PUT", "DELETE"],
    #     allow_headers=["*"],
    # )