#!/bin/bash
alembic upgrade head
exec python app/main.py