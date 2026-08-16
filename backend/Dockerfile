FROM python:3.10-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# 仅安装 Web 服务核心依赖；重型 AI 依赖见 requirements.txt
COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
