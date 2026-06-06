"""
DX-RAG 诊断脚本 — 逐个测试每个组件，找出问题所在
"""
import sys
import os

print("=" * 60)
print("DX-RAG 诊断工具")
print("=" * 60)

# 1. 测试导入
print("\n[1/5] 测试模块导入...")
try:
    from app.core.config import settings
    print("  ✅ config 导入成功")
except Exception as e:
    print(f"  ❌ config 导入失败: {e}")
    sys.exit(1)

try:
    from app.core.vector_store import VectorStore, get_vector_store
    print("  ✅ vector_store 导入成功")
except Exception as e:
    print(f"  ❌ vector_store 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from app.services.ingest import read_text_from_file, split_text, clean_text
    print("  ✅ ingest 导入成功")
except Exception as e:
    print(f"  ❌ ingest 导入失败: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.services.qa import HybridRetriever, query, get_model
    print("  ✅ qa 导入成功")
except Exception as e:
    print(f"  ❌ qa 导入失败: {e}")
    import traceback
    traceback.print_exc()

# 2. 测试嵌入模型
print("\n[2/5] 测试嵌入模型加载...")
print(f"  模型路径: {settings.embed_model}")
print(f"  路径存在: {os.path.exists(settings.embed_model)}")
try:
    model = get_model()
    print(f"  ✅ 嵌入模型加载成功: {model}")
    # 测试编码
    test_vec = model.encode("测试文本", normalize_embeddings=True)
    print(f"  ✅ 编码测试通过, 向量维度: {test_vec.shape}")
except Exception as e:
    print(f"  ❌ 嵌入模型加载失败: {e}")
    print("  → 模型将从 HuggingFace 在线下载，首次可能需要 2-5 分钟")

# 3. 测试向量存储
print("\n[3/5] 测试向量存储...")
try:
    from app.core.vector_store import _vector_stores
    _vector_stores.clear()  # 清空缓存

    vs = get_vector_store("_test_diag_")
    print(f"  ✅ 向量存储创建成功: {vs.collection_name}")
    print(f"  数据文件: {vs._data_file}")
    print(f"  向量文件: {vs._vectors_file}")
    print(f"  当前文档数: {vs.count()}")
except Exception as e:
    print(f"  ❌ 向量存储创建失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 测试文本切分
print("\n[4/5] 测试文本处理...")
try:
    test_text = "## 测试标题\n\n这是测试内容，用于验证文本切分功能。\n\n### 子标题\n\n更多测试内容在这里。"
    cleaned = clean_text(test_text)
    chunks = split_text(cleaned, "test.md")
    print(f"  ✅ 文本切分成功: {len(chunks)} 个 chunks")
    for i, c in enumerate(chunks):
        print(f"     Chunk {i+1}: {len(c)} 字符")
except Exception as e:
    print(f"  ❌ 文本切分失败: {e}")
    import traceback
    traceback.print_exc()

# 5. 测试 DeepSeek API 连通性
print("\n[5/5] 测试 DeepSeek API...")
api_key = settings.deepseek_api_key
print(f"  API Key: {api_key[:15]}...{api_key[-4:] if len(api_key) > 20 else ''}")
print(f"  Base URL: {settings.deepseek_base_url}")
try:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=settings.deepseek_base_url)
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": "你好，回复'OK'即可"}],
        max_tokens=10,
    )
    print(f"  ✅ DeepSeek API 连通成功: {response.choices[0].message.content}")
except Exception as e:
    print(f"  ❌ DeepSeek API 失败: {e}")

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)

# 清理测试知识库
try:
    VectorStore.delete_collection("_test_diag_")
    print("  已清理测试数据")
except:
    pass
