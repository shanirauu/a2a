import json
import logging
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from common.utils.push_notification_auth import PushNotificationReceiverAuth
import jwt

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# Define agents and their JWKS URLs
AGENTS = {
    "NewsAgent": {
        "port": 10010,
        "jwks_url": "http://localhost:10010/.well-known/jwks.json"
    },
    "WeatherAgent": {
        "port": 10011,
        "jwks_url": "http://localhost:10011/.well-known/jwks.json"
    },
    "CurrencyAgent": {
        "port": 10012,
        "jwks_url": "http://localhost:10012/.well-known/jwks.json"
    },
    "JointlyQueryAgent": {
        "port": 10013,
        "jwks_url": "http://localhost:10013/.well-known/jwks.json"
    }
}
# Initialize PushNotificationReceiverAuth for each agent
receiver_auths = {name: PushNotificationReceiverAuth() for name in AGENTS}

async def load_jwks_with_retries(auth, jwks_url, agent_name):
    retries = 5
    for attempt in range(1, retries + 1):
        try:
            await auth.load_jwks(jwks_url)
            logger.info(f"JWKS loaded successfully for {agent_name} from {jwks_url}")
            return True
        except Exception as e:
            logger.error(f"Attempt {attempt}/{retries} - Failed to load JWKS for {agent_name}: {e}")
            if attempt == retries:
                logger.error(f"All JWKS load attempts failed for {agent_name}")
                return False
            await asyncio.sleep(3)
    return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting lifespan handler...")
    for agent_name, auth in receiver_auths.items():
        jwks_url = AGENTS[agent_name]["jwks_url"]
        if not auth.jwks_client:
            if not await load_jwks_with_retries(auth, jwks_url, agent_name):
                logger.error(f"Lifespan JWKS loading failed for {agent_name}")
                raise RuntimeError(f"Failed to load JWKS for {agent_name}")
        else:
            logger.info(f"JWKS already loaded for {agent_name}, skipping lifespan load")
    yield
    logger.info("Shutting down receiver...")

app.lifespan = lifespan

@app.get("/notify", response_class=PlainTextResponse)
async def validate_url(validationToken: str = None):
    if not validationToken:
        logger.warning("Missing validationToken in GET /notify")
        raise HTTPException(status_code=400, detail="Missing validationToken")
    logger.debug(f"Received validation request with token: {validationToken}")
    return validationToken

@app.post("/notify")
async def receive_notification(request: Request):
    try:
        headers = dict(request.headers)
        body = await request.body()
        logger.debug(f"Received POST /notify with headers: {json.dumps(headers, indent=2)}")
        logger.debug(f"POST /notify body: {body}")

        auth_header = headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.error("Missing or invalid Authorization header")
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        token = auth_header[len("Bearer "):]
        decoded_header = jwt.get_unverified_header(token)
        logger.debug(f"JWT header: {json.dumps(decoded_header, indent=2)}")

        kid = decoded_header.get("kid")
        selected_auth = None
        selected_agent = None
        for agent_name, auth in receiver_auths.items():
            if auth.jwks_client and any(key.get("kid") == kid for key in auth.jwks_client.get_jwk_set().keys):
                selected_auth = auth
                selected_agent = agent_name
                logger.debug(f"Matched JWT kid {kid} to {agent_name}")
                break
        if not selected_auth:
            logger.warning(f"No JWKS found for kid {kid}, trying all agents...")
            for agent_name, auth in receiver_auths.items():
                try:
                    is_verified = await auth.verify_push_notification(request)
                    if is_verified:
                        selected_auth = auth
                        selected_agent = agent_name
                        logger.debug(f"Verified JWT with {agent_name}")
                        break
                except Exception as e:
                    logger.debug(f"Verification failed for {agent_name}: {e}")
                    continue

        if not selected_auth:
            logger.error("No valid JWKS found for any agent")
            raise HTTPException(status_code=401, detail="No valid JWKS found")

        try:
            is_verified = await selected_auth.verify_push_notification(request)
            if not is_verified:
                logger.error(f"JWT signature verification failed for {selected_agent}")
                raise HTTPException(status_code=401, detail="Invalid JWT signature")
        except Exception as e:
            logger.error(f"JWT verification error for {selected_agent}: {e}")
            logger.info(f"Attempting to reload JWKS for {selected_agent}...")
            if not await load_jwks_with_retries(selected_auth, AGENTS[selected_agent]["jwks_url"], selected_agent):
                logger.error(f"JWT signature verification failed after reload for {selected_agent}")
                raise HTTPException(status_code=401, detail="Invalid JWT signature after reload")
            is_verified = await selected_auth.verify_push_notification(request)
            if not is_verified:
                logger.error(f"JWT signature verification failed after reload for {selected_agent}")
                raise HTTPException(status_code=401, detail="Invalid JWT signature after reload")

        payload = json.loads(body)
        logger.info(f"Received notification from {selected_agent} (Port: {AGENTS[selected_agent]['port']}): {json.dumps(payload, indent=2)}")

        log_file = "notifications.log"
        logger.debug(f"Writing notification to {os.path.abspath(log_file)}")
        with open(log_file, "a") as f:
            f.write(f"Agent: {selected_agent} (Port: {AGENTS[selected_agent]['port']})\n")
            f.write(json.dumps(payload, indent=2) + "\n\n")
        logger.debug(f"Successfully wrote notification to {os.path.abspath(log_file)}")

        return {"status": "received"}

    except Exception as e:
        logger.error(f"Error processing notification: {e}")
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting notification receiver...")
    for agent_name, auth in receiver_auths.items():
        jwks_url = AGENTS[agent_name]["jwks_url"]
        if not auth.jwks_client:
            if not asyncio.run(load_jwks_with_retries(auth, jwks_url, agent_name)):
                logger.error(f"Initial JWKS loading failed for {agent_name}")
                raise RuntimeError(f"Failed to load JWKS for {agent_name}")
        else:
            logger.info(f"JWKS already loaded for {agent_name}, skipping initial load")
    uvicorn.run(app, host="0.0.0.0", port=9000)