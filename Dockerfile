FROM python:3.12-slim

WORKDIR /app

# Copy packaging files FIRST
COPY setup.py .
COPY requirements.txt .
COPY src/ ./src/

# Install dependencies (now -e . works)
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
