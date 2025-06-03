import os
import logging
from dotenv import load_dotenv
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
import click
from pathlib import Path
from common.server import A2AServer
from common.types import AgentCard, AgentCapabilities, AgentSkill
from common.utils.push_notification_auth import PushNotificationSenderAuth
from agents.jointly_query.agent import JointlyQueryAgent
from agents.jointly_query.task_manager import AgentTaskManager

# Load environment variables
root_dir = Path(__file__).resolve().parents[3]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option("--host", default="localhost", help="Host to bind the JointlyQueryAgent server.")
@click.option("--port", default=10013, help="Port to serve the JointlyQueryAgent.")
def main(host, port):
    print(f"🚀 Starting JointlyQueryAgent server at http://{host}:{port}")

    # Define agent capabilities
    capabilities = AgentCapabilities(streaming=False, pushNotifications=True)

    # Define agent skill
    skill = AgentSkill(
        id="query_document_store",
        name="Document Query",
        description="Answers queries based on document data using LlamaIndex.",
        tags=["documents", "information retrieval", "universal credit", "social security", "benefits", "query"],
        examples=["What is Universal Credit?", "How does Universal Credit work?", "Explain social security benefits"]
    )

    # Define agent card
    agent_card = AgentCard(
        name="Jointly Query Agent",
        description="Provides answers to queries using a document-based LlamaIndex query engine.",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=JointlyQueryAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=JointlyQueryAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill]
    )

    # Setup push notification signing
    notification_sender_auth = PushNotificationSenderAuth()
    notification_sender_auth.generate_jwk()

    # Create the A2A server
    server = A2AServer(
        agent_card=agent_card,
        task_manager=AgentTaskManager(agent=JointlyQueryAgent(), notification_sender_auth=notification_sender_auth),
        host=host,
        port=port,
    )

    # Add route for push notification key discovery
    server.app.add_route(
        "/.well-known/jwks.json", notification_sender_auth.handle_jwks_endpoint, methods=["GET"]
    )

    logger.info(f"✅ JointlyQueryAgent is live at http://{host}:{port}")
    server.start()

if __name__ == "__main__":
    main()