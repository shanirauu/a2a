import json
import logging
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from common.utils.push_notification_auth import PushNotificationReceiverAuth

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()
receiver_auth = PushNotificationReceiverAuth()

# Load JWKS from NewsAgent
JWKS_URL = "http://localhost:10010/.well-known/jwks.json"

async def load_jwks_with_retries():
    retries = 5
    for attempt in range(1, retries + 1):
        try:
            await receiver_auth.load_jwks(JWKS_URL)
            logger.info("JWKS loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Attempt {attempt}/{retries} - Failed to load JWKS from {JWKS_URL}: {e}")
            if attempt == retries:
                logger.error("All JWKS load attempts failed")
                return False
            await asyncio.sleep(3)
    return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting lifespan handler...")
    if not receiver_auth.jwks_client:
        if not await load_jwks_with_retries():
            logger.error("Lifespan JWKS loading failed")
            raise RuntimeError("Failed to load JWKS in lifespan")
    else:
        logger.info("JWKS already loaded, skipping lifespan load")
    yield
    logger.info("Shutting down receiver...")

app.lifespan = lifespan

@app.get("/notify", response_class=PlainTextResponse)
async def validate_url(validationToken: str = None):
    """Return the validation token to verify the URL."""
    if not validationToken:
        logger.warning("Missing validationToken in GET /notify")
        raise HTTPException(status_code=400, detail="Missing validationToken")
    logger.debug(f"Received validation request with token: {validationToken}")
    return validationToken

@app.post("/notify")
async def receive_notification(request: Request):
    """Receive and verify push notifications."""
    try:
        # Log request details
        headers = dict(request.headers)
        body = await request.body()
        logger.debug(f"Received POST /notify with headers: {json.dumps(headers, indent=2)}")
        logger.debug(f"POST /notify body: {body}")

        # Extract and decode JWT
        auth_header = headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.error("Missing or invalid Authorization header")
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        token = auth_header[len("Bearer "):]
        try:
            import jwt
            decoded_header = jwt.get_unverified_header(token)
            logger.debug(f"JWT header: {json.dumps(decoded_header, indent=2)}")
        except Exception as e:
            logger.error(f"Failed to decode JWT header: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid JWT: {e}")

        # Verify JWT signature with fallback reload
        try:
            is_verified = await receiver_auth.verify_push_notification(request)
            if not is_verified:
                logger.error("JWT signature verification failed")
                raise HTTPException(status_code=401, detail="Invalid JWT signature")
        except Exception as e:
            logger.error(f"JWT verification error: {e}")
            logger.info("Attempting to reload JWKS...")
            if not await load_jwks_with_retries():
                logger.error("JWT signature verification failed after reload")
                raise HTTPException(status_code=401, detail="Invalid JWT signature after reload")
            is_verified = await receiver_auth.verify_push_notification(request)
            if not is_verified:
                logger.error("JWT signature verification failed after reload")
                raise HTTPException(status_code=401, detail="Invalid JWT signature after reload")

        # Log the notification payload
        payload = json.loads(body)
        logger.info(f"Received notification: {json.dumps(payload, indent=2)}")

        # Write to notifications.log
        log_file = "notifications.log"
        logger.debug(f"Writing notification to {os.path.abspath(log_file)}")
        with open(log_file, "a") as f:
            f.write(json.dumps(payload, indent=2) + "\n\n")
        logger.debug(f"Successfully wrote notification to {os.path.abspath(log_file)}")

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Error processing notification: {e}")
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting notification receiver...")
    if not receiver_auth.jwks_client:
        if not asyncio.run(load_jwks_with_retries()):
            logger.error("Initial JWKS loading failed")
            raise RuntimeError("Failed to load JWKS at startup")
    else:
        logger.info("JWKS already loaded, skipping initial load")
    uvicorn.run(app, host="0.0.0.0", port=9000)  # Change to 9001 if port 9000 is occupied