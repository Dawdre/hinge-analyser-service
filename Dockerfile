FROM python:3.12
WORKDIR /hinge-analyser-service

COPY requirements.txt /hinge-analyser-service/requirements.txt
RUN pip install --no-cache-dir -r /hinge-analyser-service/requirements.txt

COPY . /hinge-analyser-service/
CMD ["uvicorn", "main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "8000"]