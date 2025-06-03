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

# 🧠 Local agent and task manager for Currency Conversion
from agents.currency.agent import CurrencyConversionAgent
from agents.currency.task_manager import AgentTaskManager

# 🌍 Load .env from project root
root_dir = Path(__file__).resolve().parents[3]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option("--host", default="localhost", help="Host to bind the CurrencyConversionAgent server.")
@click.option("--port", default=10012, help="Port to serve the CurrencyConversionAgent.")
def main(host, port):
    print(f"💵 Starting CurrencyConversionAgent server at http://{host}:{port}")

    capabilities = AgentCapabilities(streaming=False, pushNotifications=True)

    skill = AgentSkill(
        id="get_currency_conversion",
        name="Currency Converter",
        description="Converts an amount from one currency to another.",
        tags=["currency", "conversion", "finance", "exchange"],
        examples=["Convert 100 USD to EUR", "What is 50 GBP in JPY?"]
    )

    agent_card = AgentCard(
        name="Currency Conversion Agent",
        description="Converts amounts between different currencies.",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=CurrencyConversionAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=CurrencyConversionAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill]
    )

    notification_sender_auth = PushNotificationSenderAuth()
    notification_sender_auth.generate_jwk()

    server = A2AServer(
        agent_card=agent_card,
        task_manager=AgentTaskManager(agent=CurrencyConversionAgent(), notification_sender_auth=notification_sender_auth),
        host=host,
        port=port,
    )

    server.app.add_route(
        "/.well-known/jwks.json", notification_sender_auth.handle_jwks_endpoint, methods=["GET"]
    )

    logger.info(f"✅ CurrencyConversionAgent is live at http://{host}:{port}")
    server.start()

if __name__ == "__main__":
    main()