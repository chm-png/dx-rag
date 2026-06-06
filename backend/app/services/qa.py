"""
DX-RAG 问答服务模块
实现混合检索（关键词 + 向量）+ DeepSeek LLM 答案生成
"""
import re
from collections import defaultdict
from typing import List, Dict, Optional

from app.core.config import settings
from app.core.vector_store import get_vector_store


# ============================================================
#  嵌入模型管理
# ============================================================

_embedding_model = None


def get_model():
    """获取 Sentence-Transformers 嵌入模型（单例懒加载）"""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        import os

        # 优先使用本地模型
        if os.path.exists(settings.embed_model):
            model_path = settings.embed_model
        else:
            model_path = "BAAI/bge-small-zh-v1.5"

        _embedding_model = SentenceTransformer(model_path)
    return _embedding_model


# ============================================================
#  混合检索器
# ============================================================

class HybridRetriever:
    """
    混合检索器
    结合关键词检索（30%）和向量检索（70%），通过线性加权融合排序
    """

    def __init__(self, collection_name: str = None):
        self.collection_name = collection_name or settings.chroma_collection
        self.inverted_index = None      # 倒排索引缓存
        self.all_docs = []              # 文档缓存

    def _build_inverted_index(self):
        """构建倒排索引用于快速关键词查找"""
        if self.inverted_index is not None:
            return

        self.inverted_index = defaultdict(set)
        self.all_docs = []

        vector_store = get_vector_store(self.collection_name)
        try:
            results = vector_store.get_all_data()
        except Exception:
            return

        docs = results.get("documents", [])
        metadatas = results.get("metadatas", [])

        for idx, doc in enumerate(docs):
            if doc:
                file_name = metadatas[idx].get("source_file", "") if idx < len(metadatas) else ""
                # 分词：提取中文、英文、数字
                words = re.findall(r'[一-龥a-zA-Z0-9]+', doc.lower())
                for word in words:
                    if len(word) >= 2:  # 过滤单字
                        self.inverted_index[word].add((file_name, idx))
                self.all_docs.append({
                    "content": doc,
                    "file_name": file_name,
                })

    def invalidate_index(self):
        """使倒排索引缓存失效（数据更新后调用）"""
        self.inverted_index = None
        self.all_docs = []

    # ---------- 关键词检索 ----------

    def keyword_search(self, query: str, top_k: int = 10) -> List[tuple]:
        """
        基于倒排索引的关键词检索

        Args:
            query: 查询文本
            top_k: 返回结果数

        Returns:
            [(file_name, content, score), ...]
        """
        self._build_inverted_index()

        if not self.inverted_index:
            return []

        # 分词查询
        query_words = re.findall(r'[一-龥a-zA-Z0-9]+', query.lower())
        scores = defaultdict(float)

        # 计算匹配分数（词频累加）
        for word in query_words:
            if len(word) >= 2 and word in self.inverted_index:
                for file_name, idx in self.inverted_index[word]:
                    scores[(file_name, idx)] += 1

        # 归一化分数
        results = []
        for (file_name, idx), score in scores.items():
            if idx < len(self.all_docs):
                normalized_score = score / len(query_words) if query_words else 0
                results.append((file_name, self.all_docs[idx]["content"], normalized_score))

        # 按分数降序排序
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:top_k]

    # ---------- 向量检索 ----------

    def vector_search(self, query: str, top_k: int = 10) -> List[tuple]:
        """
        基于 BGE 嵌入模型的向量语义检索

        Args:
            query: 查询文本
            top_k: 返回结果数

        Returns:
            [(file_name, content, similarity), ...]
        """
        model = get_model()
        query_vector = model.encode(query, normalize_embeddings=True).tolist()

        vector_store = get_vector_store(self.collection_name)
        try:
            results = vector_store.search(query_vector, top_k=top_k)
        except Exception:
            return []

        return results

    # ---------- 混合检索 ----------

    def hybrid_search(
        self,
        query: str,
        weights: List[float] = None,
        top_k: int = 10,
    ) -> List[tuple]:
        """
        混合检索：关键词 + 向量，加权融合

        Args:
            query: 查询文本
            weights: [关键词权重, 向量权重]，默认 [0.3, 0.7]
            top_k: 返回结果数

        Returns:
            [(file_name, content, score), ...]
        """
        if weights is None:
            weights = [settings.keyword_weight, settings.vector_weight]

        expand_k = top_k * settings.search_expand_factor

        # 关键词检索（扩大范围）
        kw_search = self.keyword_search(query, expand_k)
        kw_results = {}
        for file_name, content, score in kw_search:
            kw_results[content] = score * weights[0]

        # 向量检索（扩大范围）
        vec_search = self.vector_search(query, expand_k)
        vec_results = {}
        for file_name, content, score in vec_search:
            vec_results[content] = score * weights[1]

        # 融合分数
        all_contents = set(kw_results.keys()) | set(vec_results.keys())
        final_scores = {}
        for content in all_contents:
            kw_score = kw_results.get(content, 0)
            vec_score = vec_results.get(content, 0)
            final_scores[content] = kw_score + vec_score

        # 去重并排序
        seen_contents = set()
        final_results = []

        for file_name, content, score in kw_search + vec_search:
            if content not in seen_contents and len(final_results) < top_k:
                seen_contents.add(content)
                final_results.append((file_name, content, final_scores.get(content, 0)))

        return final_results


# ============================================================
#  LLM 问答
# ============================================================

def generate_answer(
    question: str,
    context_chunks: List[str],
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    使用 DeepSeek LLM 基于检索到的上下文生成答案

    Args:
        question: 用户问题
        context_chunks: 检索到的上下文文本块
        history: 对话历史 [{"role": "user"/"assistant", "content": "..."}]

    Returns:
        生成的答案（Markdown 格式）
    """
    if not context_chunks:
        return "未在知识库中找到相关内容，请尝试上传相关文档或更换问题。"

    # 构建上下文
    context_text = "\n\n---\n\n".join(
        f"[参考片段 {i+1}]\n{chunk}"
        for i, chunk in enumerate(context_chunks)
    )

    # 构建系统提示
    system_prompt = """你是一个专业的知识库问答助手。请根据提供的参考文档内容回答用户的问题。

回答要求：
1. 答案必须基于提供的参考文档内容，不要编造信息
2. 如果参考文档中没有相关信息，请明确说明
3. 使用 Markdown 格式组织回答，使内容结构清晰
4. 适当使用标题、列表、加粗等格式增强可读性
5. 如果文档中有具体的步骤、数据或示例，请尽量引用
6. 回答要简洁、准确，不要过度展开与问题无关的内容"""

    # 构建消息列表
    messages = [{"role": "system", "content": system_prompt}]

    # 添加对话历史（最近 6 轮）
    if history:
        recent_history = history[-12:]  # 最多保留最近 6 轮对话
        messages.extend(recent_history)

    # 添加当前问题（附上下文）
    messages.append({
        "role": "user",
        "content": f"参考文档内容：\n\n{context_text}\n\n---\n\n用户问题：{question}\n\n请根据参考文档内容回答问题。",
    })

    # 调用 DeepSeek API
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
            stream=False,
        )

        answer = response.choices[0].message.content
        return answer.strip()

    except Exception as e:
        # 降级方案：基于检索结果生成简单回答
        return _generate_fallback_answer(question, context_chunks, str(e))


def _generate_fallback_answer(question: str, chunks: List[str], error: str) -> str:
    """
    降级回答：当 LLM 调用失败时，直接返回检索到的相关内容

    Args:
        question: 用户问题
        chunks: 检索到的文本块
        error: 错误信息

    Returns:
        降级回答
    """
    if not chunks:
        return f"抱歉，知识库检索和 AI 服务均暂时不可用。\n\n错误详情：{error}"

    answer_parts = [
        "### AI 服务暂时不可用\n\n",
        f"> 错误信息：{error}\n\n",
        "以下是知识库中与您问题最相关的内容：\n\n",
    ]

    for i, chunk in enumerate(chunks[:3]):
        answer_parts.append(f"**参考片段 {i+1}**\n\n")
        answer_parts.append(f"{chunk[:500]}...\n\n")
        answer_parts.append("---\n\n")

    return "".join(answer_parts)


# ============================================================
#  完整问答流水线
# ============================================================

def query(
    question: str,
    collection_name: str = None,
    top_k: int = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> dict:
    """
    完整的 RAG 问答流水线

    流程：用户提问 → 混合检索 → 上下文构建 → LLM 生成 → 返回答案

    Args:
        question: 用户问题
        collection_name: 知识库名称
        top_k: 检索结果数
        history: 对话历史

    Returns:
        {
            "answer": "...",
            "sources": [{"content": "...", "similarity": 0.85}, ...],
            "query": "...",
            "collection_name": "..."
        }
    """
    collection = collection_name or settings.chroma_collection
    k = top_k or settings.default_top_k

    # 1. 混合检索
    retriever = HybridRetriever(collection_name=collection)
    search_results = retriever.hybrid_search(query=question, top_k=k)

    # 2. 提取上下文
    context_chunks = [content for _, content, _ in search_results]

    # 3. 构建来源信息
    sources = []
    for file_name, content, score in search_results:
        sources.append({
            "content": content[:500],  # 截断预览
            "file_name": file_name,
            "similarity": round(score, 4),
        })

    # 4. LLM 生成答案
    answer = generate_answer(question, context_chunks, history)

    return {
        "answer": answer,
        "sources": sources,
        "query": question,
        "collection_name": collection,
    }
