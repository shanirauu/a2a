import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_query():
    uri = "ws://localhost:8080/ws"
    async with websockets.connect(uri) as websocket:
        # Send query
        query = {"query": "Use News Agent: What is the latest news on AI?"}
        await websocket.send(json.dumps(query))
        logger.info(f"Sent query: {query}")

        # Receive responses
        try:
            while True:
                response = await websocket.recv()
                response_json = json.loads(response)
                logger.info(f"Received: {json.dumps(response_json, indent=2)}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")

if __name__ == "__main__":
    asyncio.run(send_query())