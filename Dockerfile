FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ./django/ /app/

RUN pip install -r requirements.txt