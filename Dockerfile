FROM python:3.12-slim-bookworm

WORKDIR /app

COPY ./django/ /app/

RUN pip install -r requirements.txt