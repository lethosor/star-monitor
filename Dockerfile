FROM python:3.8-slim

RUN pip install redis requests

WORKDIR /app

COPY main.py /app

ENTRYPOINT ["python", "-u", "/app/main.py"]
