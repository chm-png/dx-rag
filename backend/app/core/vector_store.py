"""
DX-RAG 向量存储模块
纯 Python 实现（numpy + json），无需 ChromaDB，零 C 编译依赖
基于余弦相似度的向量检索，支持多知识库管理
"""
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np

from app.core.config import settings


# ============================================================
#  嵌入模型管理
# ============================================================

_embedding_model = None


def get_embedding_model():
    """获取 Sentence-Transformers 嵌入模型（单例懒加载）"""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        if os.path.exists(settings.embed_model):
            model_path = settings.embed_model
        else:
            model_path = "BAAI/bge-small-zh-v1.5"

        _embedding_model = SentenceTransformer(model_path)
    return _embedding_model


# ============================================================
#  向量存储（纯 Python 实现）
# ============================================================

class VectorStore:
    """
    纯 Python 向量存储

    存储结构：
        {persist_dir}/
        └── {collection_name}/
            ├── data.json      # 文档 + 元数据 + ID
            └── vectors.npy    # 向量矩阵 (N, 384)
    """

    def __init__(self, collection_name: str = None):
        self.collection_name = collection_name or settings.chroma_collection
        self._data_dir = Path(settings.chroma_persist_dir) / self.collection_name
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._data_file = self._data_dir / "data.json"
        self._vectors_file = self._data_dir / "vectors.npy"

        # 加载已有数据
        self._documents: List[str] = []
        self._metadatas: List[Dict[str, Any]] = []
        self._ids: List[str] = []
        self._vectors: Optional[np.ndarray] = None  # shape: (N, 384)

        self._load()

    # ---------- 持久化 ----------

    def _load(self):
        """从磁盘加载数据"""
        if self._data_file.exists():
            try:
                with open(self._data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._documents = data.get("documents", [])
                self._metadatas = data.get("metadatas", [])
                self._ids = data.get("ids", [])
            except Exception:
                self._documents, self._metadatas, self._ids = [], [], []

        if self._vectors_file.exists():
            try:
                self._vectors = np.load(self._vectors_file)
            except Exception:
                self._vectors = None

    def _save(self):
        """持久化到磁盘"""
        # 保存元数据
        data = {
            "documents": self._documents,
            "metadatas": self._metadatas,
            "ids": self._ids,
        }
        with open(self._data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 保存向量
        if self._vectors is not None and len(self._vectors) > 0:
            np.save(self._vectors_file, self._vectors)

    # ---------- 嵌入 ----------

    def _embed(self, texts: List[str]) -> np.ndarray:
        """将文本转为向量"""
        model = get_embedding_model()
        vectors = model.encode(texts, normalize_embeddings=True)
        return np.array(vectors, dtype=np.float32)

    # ---------- 文本操作 ----------

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        source_file: str = "",
    ) -> List[str]:
        """批量添加文本到向量库"""
        if not texts:
            return []

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]

        if metadatas is None:
            metadatas = [{"source_file": source_file} for _ in texts]

        for i, meta in enumerate(metadatas):
            if meta is None:
                metadatas[i] = {}
            metadatas[i]["source_file"] = source_file

        # 生成向量
        new_vectors = self._embed(texts)

        # 合并到现有数据
        self._documents.extend(texts)
        self._metadatas.extend(metadatas)
        self._ids.extend(ids)

        if self._vectors is None:
            self._vectors = new_vectors
        else:
            self._vectors = np.vstack([self._vectors, new_vectors])

        self._save()
        return ids

    def search(self, query_vector: List[float], top_k: int = 5) -> List[tuple]:
        """
        余弦相似度检索（向量已归一化，点积 = 余弦相似度）

        Returns:
            [(file_name, content, similarity_score), ...]
        """
        if self._vectors is None or len(self._vectors) == 0:
            return []

        query = np.array(query_vector, dtype=np.float32).reshape(1, -1)

        # 点积计算余弦相似度（向量已归一化）
        scores = np.dot(self._vectors, query.T).flatten()

        # Top-K
        if len(scores) <= top_k:
            top_indices = np.argsort(scores)[::-1]
        else:
            top_indices = np.argpartition(scores, -top_k)[-top_k:]
            top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        results = []
        for idx in top_indices:
            doc = self._documents[idx]
            meta = self._metadatas[idx] if idx < len(self._metadatas) else {}
            file_name = meta.get("source_file", "")
            similarity = float(scores[idx])
            results.append((file_name, doc, similarity))

        return results

    def get_all_data(self):
        """获取全部数据（用于构建倒排索引等）"""
        return {
            "documents": self._documents,
            "metadatas": self._metadatas,
            "ids": self._ids,
        }

    # ---------- 文件操作 ----------

    def delete_file(self, file_name: str) -> int:
        """删除指定文件的所有相关向量数据"""
        keep_indices = []
        deleted = 0

        for i, meta in enumerate(self._metadatas):
            if meta.get("source_file") == file_name:
                deleted += 1
            else:
                keep_indices.append(i)

        if deleted == 0:
            return 0

        self._documents = [self._documents[i] for i in keep_indices]
        self._metadatas = [self._metadatas[i] for i in keep_indices]
        self._ids = [self._ids[i] for i in keep_indices]

        if self._vectors is not None:
            self._vectors = self._vectors[keep_indices]

        self._save()
        return deleted

    def get_files(self) -> List[Dict[str, Any]]:
        """获取当前知识库的文件列表"""
        file_stats: Dict[str, Dict] = {}

        for meta in self._metadatas:
            file_name = meta.get("source_file", "unknown")
            if file_name not in file_stats:
                file_stats[file_name] = {
                    "file_name": file_name,
                    "chunks": 0,
                }
            file_stats[file_name]["chunks"] += 1

        # 添加文件大小信息
        for file_name in file_stats:
            file_path = Path(settings.upload_dir) / file_name
            if file_path.exists():
                file_stats[file_name]["size_bytes"] = file_path.stat().st_size

        return list(file_stats.values())

    def get_file_chunks(self, file_name: str) -> List[str]:
        """获取指定文件的所有文本块"""
        chunks = []
        for doc, meta in zip(self._documents, self._metadatas):
            if meta.get("source_file") == file_name:
                chunks.append(doc)
        return chunks

    def count(self) -> int:
        """返回文档总数"""
        return len(self._documents)

    def get_collection_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        return {
            "collection_name": self.collection_name,
            "total_chunks": self.count(),
            "files": self.get_files(),
        }

    # ---------- 知识库管理 ----------

    @staticmethod
    def list_collections() -> List[str]:
        """列出所有知识库名称"""
        persist_dir = Path(settings.chroma_persist_dir)
        if not persist_dir.exists():
            return []
        return [
            d.name
            for d in persist_dir.iterdir()
            if d.is_dir() and (d / "data.json").exists()
        ]

    @staticmethod
    def create_collection(name: str) -> "VectorStore":
        """创建新知识库"""
        return VectorStore(collection_name=name)

    @staticmethod
    def rename_collection(old_name: str, new_name: str) -> bool:
        """重命名知识库（直接重命名目录）"""
        persist_dir = Path(settings.chroma_persist_dir)
        old_dir = persist_dir / old_name
        new_dir = persist_dir / new_name

        if not old_dir.exists():
            return False
        if new_dir.exists():
            return False

        try:
            shutil.move(str(old_dir), str(new_dir))
            return True
        except Exception:
            return False

    @staticmethod
    def delete_collection(name: str) -> bool:
        """删除知识库（删除整个目录）"""
        col_dir = Path(settings.chroma_persist_dir) / name
        if not col_dir.exists():
            return False

        try:
            shutil.rmtree(str(col_dir))
            return True
        except Exception:
            return False


# --- 便捷函数 ---

_vector_stores: Dict[str, VectorStore] = {}


def get_vector_store(collection_name: str = None) -> VectorStore:
    """获取向量存储实例（带缓存）"""
    name = collection_name or settings.chroma_collection
    if name not in _vector_stores:
        _vector_stores[name] = VectorStore(collection_name=name)
    return _vector_stores[name]
