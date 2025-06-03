from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, ToolMessage
from typing import AsyncIterable, Any, Dict, Literal
from pydantic import BaseModel
from pathlib import Path
import os
from dotenv import load_dotenv
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from api.currency_api import CurrencyAPI

logger.info("💵 Initializing CurrencyConversionAgent...")

# Load shared .env
root_dir = Path(__file__).resolve().parents[3]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

api_key = os.getenv("OPEN_API_KEY")
if not api_key:
    raise EnvironmentError(f"❌ OPEN_API_KEY not found in {dotenv_path}")
else:
    logger.info(f"✅ OPEN_API_KEY loaded from {dotenv_path}")

memory = MemorySaver()

@tool
def get_currency_conversion(amount: float = 100.0, from_currency: str = "USD", to_currency: str = "EUR") -> dict:
    """Fetches currency conversion for a given amount from one currency to another."""
    logger.info(f"💱 Tool called: get_currency_conversion for {amount} {from_currency} to {to_currency}")
    try:
        currency_api = CurrencyAPI()
        logger.info("🛠️ Calling CurrencyAPI.get_currency_conversion...")
        result = currency_api.get_currency_conversion(amount, from_currency, to_currency)
        logger.info(f"💱 Currency Conversion Tool result: {result}")
        return result
    except Exception as e:
        logger.error(f"💱 Currency Conversion Tool error: {str(e)}")
        return {
            "error": str(e),
            "from_currency": from_currency,
            "to_currency": to_currency,
            "amount": amount,
            "converted_amount": "Unable to fetch conversion rate."
        }

class ResponseFormat(BaseModel):
    status: Literal["input_required", "completed", "error"] = "input_required"
    message: str

class CurrencyConversionAgent:
    SYSTEM_INSTRUCTION = (
        "You are a currency conversion assistant. Use the 'get_currency_conversion' tool "
        "to convert an amount from one currency to another. "
        "If the user doesn't specify currencies, default to converting 100 USD to EUR. "
        "Set status to 'completed' when conversion is provided. "
        "Use 'input_required' if amount or currencies are unclear. Use 'error' for failures."
    )

    def __init__(self):
        logger.info("⚙️ Creating LangGraph ReAct agent for CurrencyConversionAgent...")
        self.model = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=api_key
        )
        self.tools = [get_currency_conversion]

        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat
        )

    def invoke(self, query: str, session_id: str) -> dict:
        logger.info(f"🧠 invoke() called with query='{query}' and session_id='{session_id}'")
        config = {"configurable": {"thread_id": session_id}}
        try:
            logger.info("📡 Invoking LangGraph agent...")
            response = self.graph.invoke({"messages": [("user", query)]}, config)
            logger.info(f"📡 LangGraph invoke response: {response}")
        except Exception as e:
            logger.error(f"❌ LangGraph invoke error: {str(e)}")
            return {
                "is_task_complete": False,
                "require_user_input": True,
                "content": f"Error: {str(e)}"
            }
        return self.get_agent_response(config)

    async def stream(self, query: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        logger.info(f"📡 stream() called with query='{query}' and session_id='{session_id}'")
        inputs = {"messages": [("user", query)]}
        config = {"configurable": {"thread_id": session_id}}

        async for item in self.graph.astream(inputs, config, stream_mode="values"):
            message = item["messages"][-1]
            if isinstance(message, AIMessage) and message.tool_calls:
                yield {"is_task_complete": False, "require_user_input": False, "content": "💱 Fetching currency conversion..."}
            elif isinstance(message, ToolMessage):
                yield {"is_task_complete": False, "require_user_input": False, "content": "🛠️ Analyzing conversion result..."}

        yield self.get_agent_response(config)

    def get_agent_response(self, config) -> dict:
        logger.info("🔍 Getting agent response...")
        state = self.graph.get_state(config)
        structured = state.values.get("structured_response")
        if isinstance(structured, ResponseFormat):
            logger.info(f"✅ Structured response received: {structured}")
            return {
                "is_task_complete": structured.status == "completed",
                "require_user_input": structured.status == "input_required",
                "content": structured.message
            }

        logger.warning("⚠️ No structured response. Returning fallback.")
        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "⚠️ Something went wrong. Please try again."
        }

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

logger.info("✅ CurrencyConversionAgent is fully initialized.")