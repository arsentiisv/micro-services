FROM python:3.11-slim

WORKDIR /app

COPY flight_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY flight_service/app ./app
COPY flight_service/alembic ./alembic
COPY flight_service/alembic.ini .
COPY flight_service/run.sh .
COPY proto/flight.proto ./proto/

# Generate proto
RUN python -m grpc_tools.protoc -I./proto --python_out=./app/grpc_server --pyi_out=./app/grpc_server --grpc_python_out=./app/grpc_server ./proto/flight.proto

ENV PYTHONPATH=/app
RUN chmod +x run.sh

CMD ["./run.sh"]