import os
import logging
from dotenv import load_dotenv
import sys

# 📁 Ensure project root is on sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import click
from pathlib import Path

# 📦 A2A modules from shared common/ folder
from common.server import A2AServer
from common.types import AgentCard, AgentCapabilities, AgentSkill, MissingAPIKeyError
from common.utils.push_notification_auth import PushNotificationSenderAuth

# 🧠 Local agent and task manager for Weather Alerts
from agents.weather_alerts.agent import WeatherAlertsAgent
from agents.weather_alerts.task_manager import AgentTaskManager

# 🌍 Load .env from project root
root_dir = Path(__file__).resolve().parents[3]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option("--host", default="localhost", help="Host to bind the WeatherAlertsAgent server.")
@click.option("--port", default=10012, help="Port to serve the WeatherAlertsAgent.")
def main(host, port):
    print(f"⚠️ Starting WeatherAlertsAgent server at http://{host}:{port}")

    capabilities = AgentCapabilities(streaming=False, pushNotifications=True)

    skill = AgentSkill(
        id="get_weather_alerts",
        name="Weather Alerts Reporter",
        description="Provides severe weather alerts for a city.",
        tags=["weather", "alerts", "severe", "warnings"],
        examples=["Are there any weather alerts in Dallas?", "Severe weather warnings in London?"]
    )

    agent_card = AgentCard(
        name="Weather Alerts Agent",
        description="Gives severe weather alerts for a given city.",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=WeatherAlertsAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=WeatherAlertsAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill]
    )

    notification_sender_auth = PushNotificationSenderAuth()
    notification_sender_auth.generate_jwk()

    server = A2AServer(
        agent_card=agent_card,
        task_manager=AgentTaskManager(agent=WeatherAlertsAgent(), notification_sender_auth=notification_sender_auth),
        host=host,
        port=port,
    )

    server.app.add_route(
        "/.well-known/jwks.json", notification_sender_auth.handle_jwks_endpoint, methods=["GET"]
    )

    logger.info(f"✅ WeatherAlertsAgent is live at http://{host}:{port}")
    server.start()

if __name__ == "__main__":
    main()