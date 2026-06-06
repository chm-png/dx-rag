"""
DX-RAG API 路由模块
定义所有 REST API 接口
"""
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Query
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.vector_store import get_vector_store, VectorStore
from app.services.ingest import ingest_file, ingest_file_to_collection, read_text_from_file
from app.services.qa import query as rag_query

router = APIRouter(prefix="/api")


# ============================================================
#  健康检查
# ============================================================

@router.get("/health")
async def health_check():
    """服务健康检查"""
    return {"status": "ok"}


# ============================================================
#  知识库管理
# ============================================================

@router.get("/collections")
async def list_collections():
    """获取所有知识库列表及统计信息"""
    collections = VectorStore.list_collections()

    result = []
    for name in collections:
        try:
            vs = get_vector_store(name)
            stats = vs.get_collection_stats()
            result.append({
                "name": name,
                "total_chunks": stats["total_chunks"],
                "file_count": len(stats["files"]),
            })
        except Exception:
            result.append({
                "name": name,
                "total_chunks": 0,
                "file_count": 0,
            })

    return {"collections": result}


@router.post("/collections")
async def create_collection(name: str = Form(...)):
    """
    创建新知识库

    Args:
        name: 知识库名称（3-50 字符）
    """
    name = name.strip()

    # 验证名称
    if len(name) < 3 or len(name) > 50:
        raise HTTPException(status_code=400, detail="知识库名称长度应在 3-50 字符之间")

    if not name[0].isalnum() or not name[-1].isalnum():
        raise HTTPException(status_code=400, detail="知识库名称应以字母或数字开头和结尾")

    # 检查是否已存在
    existing = VectorStore.list_collections()
    if name in existing:
        raise HTTPException(status_code=400, detail=f"知识库 '{name}' 已存在")

    # 创建
    try:
        VectorStore.create_collection(name)
        return {"message": "知识库创建成功", "name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建知识库失败: {str(e)}")


@router.put("/collections/{name}")
async def rename_collection(name: str, new_name: str = Form(...)):
    """
    重命名知识库

    Args:
        name: 当前名称
        new_name: 新名称
    """
    new_name = new_name.strip()

    if len(new_name) < 3 or len(new_name) > 50:
        raise HTTPException(status_code=400, detail="知识库名称长度应在 3-50 字符之间")

    success = VectorStore.rename_collection(name, new_name)
    if not success:
        raise HTTPException(status_code=400, detail=f"重命名失败，请检查名称是否已存在")

    return {"message": "重命名成功", "old_name": name, "new_name": new_name}


@router.delete("/collections/{name}")
async def delete_collection(name: str):
    """删除知识库及其全部数据"""
    success = VectorStore.delete_collection(name)
    if not success:
        raise HTTPException(status_code=404, detail=f"知识库 '{name}' 不存在")

    return {"message": "知识库已删除", "name": name}


# ============================================================
#  文件上传
# ============================================================

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    collection_name: Optional[str] = Form(None),
):
    """
    上传文件并自动入库

    Args:
        file: 上传的文件
        collection_name: 目标知识库名称（可选，默认使用全局知识库）
    """
    # 验证文件扩展名
    suffix = Path(file.filename).suffix.lower()
    if suffix not in settings.supported_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式 '{suffix}'，支持的格式: {settings.supported_extensions}",
        )

    # 保存文件到 uploads 目录
    # 处理文件名冲突
    base_name = file.filename
    save_path = Path(settings.upload_dir) / base_name

    # 如果文件已存在，添加序号
    counter = 1
    while save_path.exists():
        stem = Path(base_name).stem
        save_path = Path(settings.upload_dir) / f"{stem}_{counter}{suffix}"
        counter += 1

    # 写入文件
    try:
        content = await file.read()
        if len(content) > settings.max_upload_size:
            raise HTTPException(status_code=400, detail="文件大小超过限制（50MB）")

        save_path.write_bytes(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 文件入库
    try:
        if collection_name:
            result = ingest_file_to_collection(save_path, collection_name)
        else:
            result = ingest_file(save_path)

        return JSONResponse(content={
            "message": "上传并入库成功",
            "file_name": result["file_name"],
            "chunks": result["chunks"],
            "collection_name": result.get("collection_name", settings.chroma_collection),
        })
    except ValueError as e:
        # 清理已保存的文件
        if save_path.exists():
            save_path.unlink()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 清理已保存的文件
        if save_path.exists():
            save_path.unlink()
        raise HTTPException(status_code=500, detail=f"文件入库失败: {str(e)}")


# ============================================================
#  知识问答
# ============================================================

@router.post("/query")
async def ask_question(request: dict):
    """
    知识问答接口

    Request Body:
    {
        "question": "课后应该做什么",
        "top_k": 5,
        "collection_name": "my-kb",
        "history": [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好！"}
        ]
    }
    """
    question = request.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    top_k = request.get("top_k", settings.default_top_k)
    collection_name = request.get("collection_name")
    history = request.get("history", [])

    try:
        result = rag_query(
            question=question,
            collection_name=collection_name,
            top_k=top_k,
            history=history,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"问答处理失败: {str(e)}")


# ============================================================
#  文件管理
# ============================================================

@router.get("/files")
async def list_files(collection_name: Optional[str] = Query(None)):
    """获取指定知识库的文件列表"""
    try:
        vs = get_vector_store(collection_name)
        files = vs.get_files()
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.delete("/files/{file_name}")
async def delete_file(
    file_name: str,
    collection_name: Optional[str] = Query(None),
):
    """
    删除知识库中的文件

    Args:
        file_name: 文件名
        collection_name: 知识库名称
    """
    try:
        # 从向量库删除
        vs = get_vector_store(collection_name)
        deleted_count = vs.delete_file(file_name)

        # 从文件系统删除
        file_path = Path(settings.upload_dir) / file_name
        if file_path.exists():
            file_path.unlink()

        return {
            "message": "文件已删除",
            "file_name": file_name,
            "deleted_chunks": deleted_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")


@router.get("/files/{file_name}/preview")
async def preview_file(
    file_name: str,
    collection_name: Optional[str] = Query(None),
):
    """
    预览文件内容

    Args:
        file_name: 文件名
        collection_name: 知识库名称
    """
    try:
        vs = get_vector_store(collection_name)
        chunks = vs.get_file_chunks(file_name)

        if not chunks:
            # 尝试直接读取原文件
            file_path = Path(settings.upload_dir) / file_name
            if file_path.exists():
                try:
                    raw_text = read_text_from_file(file_path)
                    return {
                        "file_name": file_name,
                        "content": raw_text[:10000],  # 最多返回 10000 字符
                        "chunks": [],
                    }
                except Exception:
                    pass

            raise HTTPException(status_code=404, detail="文件不存在或内容为空")

        return {
            "file_name": file_name,
            "chunks": chunks,
            "total_chunks": len(chunks),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览文件失败: {str(e)}")


# ============================================================
#  统计信息
# ============================================================

@router.get("/stats")
async def get_stats(collection_name: Optional[str] = Query(None)):
    """获取知识库统计信息"""
    try:
        vs = get_vector_store(collection_name)
        stats = vs.get_collection_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")
