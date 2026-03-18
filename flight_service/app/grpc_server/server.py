import logging
import grpc
from concurrent import futures
import sys
import os

# Добавляем путь, чтобы Python мог найти сгенерированные файлы flight_pb2 и flight_pb2_grpc
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import flight_pb2_grpc
from .services import FlightServiceServicer

async def serve():
    server = grpc.aio.server()
    flight_pb2_grpc.add_FlightServiceServicer_to_server(FlightServiceServicer(), server)
    port = '[::]:50051'
    server.add_insecure_port(port)
    logging.info(f"Flight Service starting on {port}")
    await server.start()
    await server.wait_for_termination()