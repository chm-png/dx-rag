"""
DX-RAG 后端入口
FastAPI 应用主文件
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import router

# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    description="DX-RAG 知识库问答系统 API",
    version="1.0.0",
)

# 配置 CORS 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化操作"""
    print(f"[DX-RAG] 应用启动: {settings.app_name}")
    print(f"[DX-RAG] ChromaDB 目录: {settings.chroma_persist_dir}")
    print(f"[DX-RAG] 上传目录: {settings.upload_dir}")
    print(f"[DX-RAG] 嵌入模型: {settings.embed_model}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理操作"""
    print("[DX-RAG] 应用关闭")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
