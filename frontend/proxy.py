from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8090"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

BACKEND_URL = "http://localhost:10014"

@app.api_route("/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def proxy(request: Request, path: str):
    logger.debug(f"Proxying {request.method} request to {BACKEND_URL}/{path}")
    async with httpx.AsyncClient() as client:
        try:
            if request.method == "OPTIONS":
                return {
                    "status_code": 200,
                    "headers": {
                        "Access-Control-Allow-Origin": "http://localhost:8090",
                        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                        "Access-Control-Allow-Headers": "*",
                        "Access-Control-Allow-Credentials": "true",
                    }
                }
            
            # Forward the request to the backend
            headers = {k: v for k, v in request.headers.items() if k.lower() not in ["host", "origin"]}
            body = await request.body()
            backend_response = await client.request(
                method=request.method,
                url=f"{BACKEND_URL}/{path}",
                headers=headers,
                content=body,
                timeout=60
            )

            # Stream the response back to the client
            async def stream_response():
                async for chunk in backend_response.aiter_raw():
                    yield chunk

            return StreamingResponse(
                stream_response(),
                status_code=backend_response.status_code,
                headers={
                    "Access-Control-Allow-Origin": "http://localhost:8090",
                    "Content-Type": backend_response.headers.get("Content-Type", "text/event-stream"),
                    "Cache-Control": "no-store",
                    "X-Accel-Buffering": "no",
                }
            )
        except Exception as e:
            logger.error(f"Proxy error: {str(e)}")
            return {"error": str(e)}, 500

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)