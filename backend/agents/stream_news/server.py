import os
import logging
import click
from dotenv import load_dotenv
from pathlib import Path
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from common.server import A2AServer
from common.types import AgentCard, AgentCapabilities, AgentSkill
from common.utils.push_notification_auth import PushNotificationSenderAuth
from agents.stream_news.agent import StreamNewsAgent
from agents.stream_news.task_manager import AgentTaskManager

# Load environment variables
root_dir = Path(__file__).resolve().parents[3]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option("--host", default="localhost", help="Host to bind the StreamNewsAgent server.")
@click.option("--port", default=10014, help="Port to serve the StreamNewsAgent.")
@click.option("--push-notification-url", default="http://localhost:9000/notify", help="URL for push notifications.")
def main(host, port, push_notification_url):
    print(f"🚀 Starting StreamNewsAgent server at http://{host}:{port}")
    capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
    skill = AgentSkill(
        id="get_latest_news",
        name="Streaming News Fetcher",
        description="Fetches streaming news updates on a topic.",
        tags=["news", "streaming", "current events"],
        examples=["Stream live AI news updates"]
    )
    agent_card = AgentCard(
        name="Stream News Agent",
        description="Fetches streaming news updates on any topic.",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=StreamNewsAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=StreamNewsAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill]
    )
    notification_sender_auth = PushNotificationSenderAuth()
    notification_sender_auth.generate_jwk()
    server = A2AServer(
        agent_card=agent_card,
        task_manager=AgentTaskManager(agent=StreamNewsAgent(), notification_sender_auth=notification_sender_auth),
        host=host,
        port=port
    )
    server.app.add_route(
        "/.well-known/jwks.json", notification_sender_auth.handle_jwks_endpoint, methods=["GET"]
    )
    logger.info(f"✅ StreamNewsAgent is live at http://{host}:{port}")
    server.start()

if __name__ == "__main__":
    main()