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

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from api.weather_api import WeatherAPI

print("🌤️ Initializing WeatherAgent...")

# Load shared .env
root_dir = Path(__file__).resolve().parents[3]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

api_key = os.getenv("OPEN_API_KEY")
if not api_key:
    raise EnvironmentError(f"❌ OPEN_API_KEY not found in {dotenv_path}")
else:
    print(f"✅ OPEN_API_KEY loaded from {dotenv_path}")

memory = MemorySaver()

@tool
def get_weather(city: str = "New York") -> dict:
    """Fetches real-time weather report for a given city."""
    print(f"🌡️ Tool called: get_weather for city='{city}'")
    weather_api = WeatherAPI()
    result = weather_api.get_weather(city)
    print(f"🌡️ Weather Tool result: {result}")
    return result

class ResponseFormat(BaseModel):
    status: Literal["input_required", "completed", "error"] = "input_required"
    message: str

class WeatherAgent:
    SYSTEM_INSTRUCTION = (
        "You are a weather assistant. Use the 'get_weather' tool "
        "to provide weather information for a given city. "
        "If the user doesn't specify a city, default to 'New York'. "
        "Set status to 'completed' when weather is provided. "
        "Use 'input_required' if city is unclear. Use 'error' for failures."
    )

    def __init__(self):
        print("⚙️ Creating LangGraph ReAct agent for WeatherAgent...")
        self.model = ChatOpenAI(
            model="gpt-4o-mini",  # Changed to gpt-4o-mini for consistency
            temperature=0.7,
            api_key=api_key
        )
        self.tools = [get_weather]

        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat
        )

    def invoke(self, query: str, session_id: str) -> dict:
        print(f"🧠 invoke() called with query='{query}' and session_id='{session_id}'")
        config = {"configurable": {"thread_id": session_id}}
        self.graph.invoke({"messages": [("user", query)]}, config)
        print("=============")
        return self.get_agent_response(config)

    async def stream(self, query: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        print(f"📡 stream() called with query='{query}' and session_id='{session_id}'")
        inputs = {"messages": [("user", query)]}
        config = {"configurable": {"thread_id": session_id}}

        async for item in self.graph.astream(inputs, config, stream_mode="values"):
            message = item["messages"][-1]
            if isinstance(message, AIMessage) and message.tool_calls:
                yield {"is_task_complete": False, "require_user_input": False, "content": "🌧️ Fetching weather data..."}
            elif isinstance(message, ToolMessage):
                yield {"is_task_complete": False, "require_user_input": False, "content": "🛠️ Analyzing weather report..."}

        yield self.get_agent_response(config)

    def get_agent_response(self, config) -> dict:
        state = self.graph.get_state(config)
        structured = state.values.get("structured_response")
        if isinstance(structured, ResponseFormat):
            print(f"✅ Structured response received: {structured}")
            return {
                "is_task_complete": structured.status == "completed",
                "require_user_input": structured.status == "input_required",
                "content": structured.message
            }

        print("⚠️ No structured response. Returning fallback.")
        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "⚠️ Something went wrong. Please try again."
        }

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

print("✅ WeatherAgent is fully initialized.")