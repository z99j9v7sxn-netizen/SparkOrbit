FROM python:3.12-slim

WORKDIR /app

# Debian 源换阿里云（腾讯云国内机访问 deb.debian.org 极慢）
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
        /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
        /etc/apt/sources.list; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

# 预置 Chroma 默认 ONNX（构建前需 vendor/chroma_onnx/all-MiniLM-L6-v2/onnx/ 就绪）
# 运行时离线：禁止请求路径再下载 onnx.tar.gz
RUN set -eux; \
    mkdir -p /root/.cache/chroma/onnx_models; \
    if [ -f vendor/chroma_onnx/all-MiniLM-L6-v2/onnx/model.onnx ]; then \
      cp -a vendor/chroma_onnx/all-MiniLM-L6-v2 /root/.cache/chroma/onnx_models/; \
      echo "chroma onnx baked into image"; \
    else \
      echo "WARNING: vendor chroma onnx missing — RAG will stay offline until model is provided"; \
    fi

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV SPARKORBIT_CHROMA_OFFLINE=1

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
