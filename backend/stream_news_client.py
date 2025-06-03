import asyncio
import json
import logging
import os
import uuid
import httpx

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Log streamed news to file
def log_news_to_file(data: dict):
    """Log streamed news to streamed_news.log."""
    log_file = "streamed_news.log"
    try:
        logger.debug(f"Writing news to {os.path.abspath(log_file)}")
        with open(log_file, "a") as f:
            f.write(json.dumps(data, indent=2) + "\n")
        logger.debug(f"Successfully wrote news to {os.path.abspath(log_file)}")
    except Exception as e:
        logger.error(f"Error writing to {log_file}: {e}")

async def stream_news():
    """Send tasks/sendSubscribe request and process SSE responses as NDJSON."""
    url = "http://localhost:10014/"
    request_body = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tasks/sendSubscribe",
        "params": {
            "id": str(uuid.uuid4()),
            "sessionId": str(uuid.uuid4()),
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "Stream sports news updates"}]
            },
            "acceptedOutputModes": ["text"],
            "pushNotification": None
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Sending request to {url}: {json.dumps(request_body, indent=2)}")
            async with client.stream("POST", url, json=request_body, timeout=60) as response:
                if response.status_code != 200:
                    logger.error(f"Request failed with status {response.status_code}")
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            # Extract JSON from SSE data
                            data = json.loads(line[6:])
                            # Simplify output to NDJSON
                            if data.get("result", {}).get("artifact", {}).get("parts"):
                                text = data["result"]["artifact"]["parts"][0]["text"]
                                output = {
                                    "jsonrpc": "2.0",
                                    "id": data["id"],
                                    "result": {
                                        "id": data["result"]["id"],
                                        "sessionId": data["result"].get("sessionId", request_body["params"]["sessionId"]),
                                        "message": text,
                                        "index": data["result"]["artifact"].get("index", 0)
                                    }
                                }
                                logger.debug(f"Processed response: {json.dumps(output, indent=2)}")
                                log_news_to_file(output)
                                print(json.dumps(output))  # Output NDJSON
                            elif data.get("result", {}).get("status", {}).get("state") == "completed":
                                text = data["result"]["status"]["message"]["parts"][0]["text"]
                                output = {
                                    "jsonrpc": "2.0",
                                    "id": data["id"],
                                    "result": {
                                        "id": data["result"]["id"],
                                        "sessionId": data["result"].get("sessionId", request_body["params"]["sessionId"]),
                                        "message": text,
                                        "index": 0
                                    }
                                }
                                logger.debug(f"Processed final response: {json.dumps(output, indent=2)}")
                                log_news_to_file(output)
                                print(json.dumps(output))  # Output NDJSON
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse SSE line: {line} - {e}")
                        except KeyError as e:
                            logger.error(f"Invalid response structure: {line} - {e}")
                    elif line.startswith(": ping"):
                        logger.debug(f"Received ping: {line}")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")

if __name__ == "__main__":
    asyncio.run(stream_news())