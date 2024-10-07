FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ./django/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY ./django/ /app/

RUN python manage.py collectstatic --noinput