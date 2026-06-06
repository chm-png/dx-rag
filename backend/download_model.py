"""
一键下载 BGE 中文嵌入模型（使用镜像加速）
运行: python download_model.py
"""
import os
import sys

# 设置 HuggingFace 镜像（国内加速）
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

print("正在下载 BGE 中文嵌入模型（约 400MB，首次需 2-5 分钟）...")
print(f"镜像源: {os.environ['HF_ENDPOINT']}")
print("目标路径: ./models/bge-small-zh-v1.5\n")

from sentence_transformers import SentenceTransformer

model_name = "BAAI/bge-small-zh-v1.5"
local_path = os.path.join(os.path.dirname(__file__), "models", "bge-small-zh-v1.5")

try:
    print("[1/2] 下载模型...")
    model = SentenceTransformer(model_name)

    print(f"[2/2] 保存到本地: {local_path}")
    model.save(local_path)

    print("\n✅ 模型下载完成！")

    # 验证
    test_vec = model.encode("测试", normalize_embeddings=True)
    print(f"✅ 编码测试通过，向量维度: {test_vec.shape}")

except Exception as e:
    print(f"\n❌ 下载失败: {e}")
    print("\n可能的原因:")
    print("  1. 网络问题 — 重试几次")
    print("  2. 镜像站不可用 — 尝试: set HF_ENDPOINT= && python download_model.py")
    sys.exit(1)
