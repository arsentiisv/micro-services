FROM python:3.11-slim

WORKDIR /app

COPY booking_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY booking_service/app ./app
COPY booking_service/alembic ./alembic
COPY booking_service/alembic.ini .
COPY booking_service/run.sh .
COPY proto/flight.proto ./proto/

# Generate proto
RUN python -m grpc_tools.protoc -I./proto --python_out=./app/grpc_client --pyi_out=./app/grpc_client --grpc_python_out=./app/grpc_client ./proto/flight.proto

ENV PYTHONPATH=/app
RUN chmod +x run.sh

CMD ["./run.sh"]