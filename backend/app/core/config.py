"""
DX-RAG 核心配置模块
管理应用的所有配置项，包括 API 密钥、路径、模型参数等
"""
import os
from pathlib import Path
from typing import List

# HuggingFace 镜像（国内加速），设为空字符串则使用官方源
_HF_MIRROR = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
if _HF_MIRROR:
    os.environ["HF_ENDPOINT"] = _HF_MIRROR

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 上传文件目录
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ChromaDB 持久化目录
CHROMA_PERSIST_DIR = os.path.join(BASE_DIR, "chroma_db")
os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)

# 嵌入模型本地路径
EMBED_MODEL_PATH = os.path.join(BASE_DIR, "models", "bge-small-zh-v1.5")


class Settings:
    """应用配置类"""

    # --- 应用基础配置 ---
    app_name: str = "dx-rag-demo"
    cors_origins: List[str] = ["*"]

    # --- 知识库配置 ---
    chroma_collection: str = "knowledge_chunks"  # 默认知识库名称
    chroma_persist_dir: str = CHROMA_PERSIST_DIR

    # --- 嵌入模型配置 ---
    embed_model: str = EMBED_MODEL_PATH  # 本地模型路径，或 HuggingFace 模型名

    # --- 文件上传配置 ---
    upload_dir: str = UPLOAD_DIR
    max_upload_size: int = 50 * 1024 * 1024  # 50MB

    # --- 文本切分配置 ---
    max_chunk_size: int = 800
    chunk_overlap: int = 120

    # --- 检索配置 ---
    default_top_k: int = 5
    keyword_weight: float = 0.3
    vector_weight: float = 0.7
    search_expand_factor: int = 2  # 检索时扩大召回范围的倍数

    # --- LLM 配置 ---
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "sk-747051d8dc7548ab9f7ae9a3125e64c8")
    deepseek_base_url: str = "https://api.deepseek.com"

    # --- 视觉模型配置（使用 DeepSeek Vision，与 LLM 共用 Key）---

    # --- 支持的文件格式 ---
    supported_extensions: set = {".pdf", ".docx", ".xlsx", ".xlsm", ".xltx", ".xltm",
                                  ".txt", ".md", ".csv", ".json", ".log"}

    # --- 嵌入模型缓存 ---
    _embedding_model = None  # 单例缓存


# 全局配置实例
settings = Settings()
