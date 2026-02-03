# 后端 Dockerfile - FastAPI + Gunicorn
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（可能需要编译某些 Python 包）
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# 复制应用代码
COPY app/ ./app/

# 创建数据目录（SQLite 存放）
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 8000

# 使用 Gunicorn 运行 FastAPI（多进程）
CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
