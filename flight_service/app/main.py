import asyncio
import logging
from grpc_server.server import serve

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    asyncio.run(serve())