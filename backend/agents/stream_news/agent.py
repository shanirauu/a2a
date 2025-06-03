from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, ToolMessage
from typing import List, Dict, Literal, Any
from pydantic import BaseModel
from pathlib import Path
import os
import asyncio
import json
import logging
from dotenv import load_dotenv
import sys
import re

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from api.news_api import QueryAPI

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

logger.info("Initializing StreamNewsAgent...")

# Load shared .env from root
root_dir = Path(__file__).resolve().parents[3]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

api_key = os.getenv("OPEN_API_KEY")
if not api_key:
    raise EnvironmentError(f"❌ OPEN_API_KEY not found in {dotenv_path}")
else:
    logger.info(f"✅ OPEN_API_KEY loaded from {dotenv_path}")

# Memory for threading
memory = MemorySaver()

# 🛠️ Tool - returns a list of news updates
@tool
async def get_latest_news(topic: str = "AI") -> List[str]:
    """Fetches the latest news for a given topic, returning a list of JSON strings."""
    logger.info(f"📰 Tool called: get_latest_news with topic='{topic}'")
    results = []
    try:
        query_api = QueryAPI()
        # Define topic-specific subtopics
        subtopic_map = {
            "ai": ["ai in healthcare", "ai ethics", "ai automation"],
            "sports": ["sports injuries", "sports technology", "sports events"],
            "politics": ["political elections", "political policy", "political scandals"],
            "technology": ["tech startups", "cybersecurity", "tech regulations"],
            "health": ["public health", "medical research", "healthcare policy"]
        }
        # Use specific subtopics if available, else generate generic ones
        subtopics = subtopic_map.get(topic.lower(), [
            f"{topic} trends",
            f"{topic} innovations",
            f"{topic} events"
        ])
        logger.debug(f"Generated subtopics: {subtopics}")
        articles = []
        for subtopic in subtopics:
            try:
                result = query_api.process_query(subtopic)
                logger.debug(f"📰 News Tool result for {subtopic}: {result}")
                if isinstance(result, dict) and 'headline' in result and 'summary' in result:
                    articles.append({
                        "title": result.get('headline', f"Breaking: News on {subtopic.title()}!"),
                        "description": result.get('summary', "No summary available.")
                    })
                else:
                    logger.warning(f"⚠️ Invalid QueryAPI result for {subtopic}: {result}")
                    articles.append({
                        "title": f"Error Fetching {subtopic.title()} News",
                        "description": f"Failed to fetch news: Invalid response format"
                    })
            except Exception as e:
                logger.error(f"❌ Error fetching news for {subtopic}: {str(e)}")
                articles.append({
                    "title": f"Error Fetching {subtopic.title()} News",
                    "description": f"Failed to fetch news: {str(e)}"
                })
        logger.info(f"✅ Collected {len(articles)} articles")
        # Collect results
        for i, article in enumerate(articles[:3], 1):
            chunk = {
                "headline": article.get('title', f"News update {i} on {topic}"),
                "summary": article.get('description', f"Summary {i}: Latest news on {topic}..."),
                "index": i
            }
            logger.debug(f"📰 Collecting chunk {i}: {chunk}")
            results.append(json.dumps(chunk))
    except Exception as e:
        logger.error(f"❌ Fatal error in get_latest_news: {str(e)}")
        # Return error chunks for all three
        for i in range(1, 4):
            chunk = {
                "headline": f"Error Fetching News {i}",
                "summary": f"Failed to fetch news: {str(e)}",
                "index": i
            }
            logger.debug(f"📰 Collecting error chunk {i}: {chunk}")
            results.append(json.dumps(chunk))
    return results

# 🧾 Format for response
class ResponseFormat(BaseModel):
    status: Literal["input_required", "completed", "error"] = "input_required"
    message: str

# 🧠 StreamNewsAgent powered by LangGraph + OpenAI
class StreamNewsAgent:
    SYSTEM_INSTRUCTION = (
        "You are a streaming news assistant. For any query requesting news updates (e.g., 'Stream live [topic] news updates'), "
        "extract the topic from the query and call the 'get_latest_news' tool with that topic to fetch and stream incremental news updates. "
        "Do not generate news summaries yourself; rely solely on the 'get_latest_news' tool. "
        "Stream each update as received. If no topic is specified, default to 'AI'. "
        "Set status to 'completed' after streaming all updates, 'error' if the tool fails."
    )

    def __init__(self):
        logger.info("⚙️ Creating LangGraph ReAct agent for StreamNewsAgent...")
        self.model = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=api_key
        )
        self.tools = [get_latest_news]
        self.graph = create_react_agent(
            model=self.model,
            tools=self.tools,
            checkpointer=memory,
            state_modifier=self.SYSTEM_INSTRUCTION
        )

    def _extract_topic(self, query: str) -> str:
        """Extracts the topic from a query like 'Stream live [topic] news updates'."""
        logger.debug(f"Extracting topic from query: {query}")
        try:
            # Simplified extraction without regex flags to avoid errors
            pattern = r"(?:stream\s+live\s+)?([\w\s]+?)(?:\s+news\s*(?:updates)?|$)"
            logger.debug(f"Using regex pattern: {pattern}")
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                topic = match.group(1).strip().lower()
                logger.info(f"Extracted topic: {topic}")
                return topic
            logger.warning("No topic found in query. Defaulting to 'AI'.")
            return "AI"
        except Exception as e:
            logger.error(f"Error extracting topic: {str(e)}. Defaulting to 'AI'.")
            return "AI"

    async def invoke(self, query: str, session_id: str) -> dict:
        logger.info(f"🧠 invoke() called with query='{query}' and session_id='{session_id}'")
        config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}
        topic = self._extract_topic(query)
        await self.graph.ainvoke({"messages": [("user", query)]}, config)
        return self.get_agent_response(config)

    async def stream(self, query: str, session_id: str) -> Dict[str, Any]:
        logger.info(f"📡 stream() called with query='{query}' and session_id='{session_id}'")
        config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}
        update_count = 0
        max_updates = 3  # Limit to three news updates
        try:
            topic = self._extract_topic(query)
            # Ensure query is a string
            stream_query = f"Fetch news on {topic}"
            logger.debug(f"Streaming with query: {stream_query}")
            async for item in self.graph.astream({"messages": [("user", stream_query)]}, config, stream_mode="updates"):
                logger.debug(f"Stream event: {item}")
                for node, state in item.items():
                    if "messages" in state and state["messages"]:
                        message = state["messages"][-1]
                        logger.debug(f"Processing message: {type(message).__name__}, content={getattr(message, 'content', None)}")
                        if isinstance(message, AIMessage) and message.tool_calls:
                            yield {
                                "is_task_complete": False,
                                "require_user_input": False,
                                "content": "🔍 Fetching the latest news...",
                                "index": 0
                            }
                        elif isinstance(message, ToolMessage):
                            try:
                                # Parse tool response (list of JSON strings)
                                content = message.content
                                logger.debug(f"Tool message content: {content}")
                                if not content or not isinstance(content, (str, list)):
                                    logger.warning(f"Invalid tool message content: {content}")
                                    chunk = {
                                        "headline": "Error Processing News",
                                        "summary": "Invalid tool response format",
                                        "index": 0
                                    }
                                    yield {
                                        "is_task_complete": False,
                                        "require_user_input": False,
                                        "content": f"📰 Update: {chunk['headline']}\n{chunk['summary']}",
                                        "index": chunk['index']
                                    }
                                    continue
                                # Handle list of JSON strings
                                if isinstance(content, str):
                                    content = json.loads(content) if content else []
                                for chunk_str in content:
                                    try:
                                        chunk = json.loads(chunk_str)
                                        logger.debug(f"Streaming chunk: {chunk}")
                                        yield {
                                            "is_task_complete": False,
                                            "require_user_input": False,
                                            "content": f"📰 Update: {chunk['headline']}\n{chunk['summary']}",
                                            "index": chunk.get('index', 0)
                                        }
                                        update_count += 1
                                        await asyncio.sleep(1)  # Reduced delay
                                        if update_count >= max_updates:
                                            logger.info("Reached max updates. Terminating stream.")
                                            # Force completion
                                            yield {
                                                "is_task_complete": True,
                                                "require_user_input": False,
                                                "content": "All news updates completed.",
                                                "index": 0
                                            }
                                            return  # Exit the stream
                                    except json.JSONDecodeError as e:
                                        logger.error(f"⚠️ Error parsing chunk: {chunk_str}, error: {e}")
                                        yield {
                                            "is_task_complete": False,
                                            "require_user_input": False,
                                            "content": f"⚠️ Error processing news: Invalid chunk format: {str(e)}",
                                            "index": 0
                                        }
                            except Exception as e:
                                logger.error(f"⚠️ Error processing tool message: {e}, content={content}")
                                yield {
                                    "is_task_complete": False,
                                    "require_user_input": False,
                                    "content": f"⚠️ Error processing news: {str(e)}",
                                    "index": 0
                                }
            # Send final response if not already sent
            if update_count < max_updates:
                final_response = self.get_agent_response(config)
                logger.debug(f"Final response: {final_response}")
                yield {
                    "is_task_complete": final_response["is_task_complete"],
                    "require_user_input": final_response["require_user_input"],
                    "content": final_response["content"],
                    "index": 0
                }
        except Exception as e:
            logger.error(f"❌ Stream error: {str(e)}")
            yield {
                "is_task_complete": False,
                "require_user_input": False,
                "content": f"Unable to fetch news: {str(e)}",
                "index": 0
            }

    def get_agent_response(self, config) -> dict:
        state = self.graph.get_state(config)
        structured = state.values.get("structured_response")
        if isinstance(structured, ResponseFormat):
            logger.debug(f"✅ Structured response: {structured}")
            return {
                "is_task_complete": structured.status == "completed",
                "require_user_input": structured.status == "input_required",
                "content": structured.message
            }
        logger.warning("⚠️ No structured response. Returning fallback.")
        return {
            "is_task_complete": True,
            "require_user_input": False,
            "content": "All news updates completed."
        }

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

logger.info("✅ StreamNewsAgent is fully initialized.")