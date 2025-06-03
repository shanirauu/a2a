from pydantic import BaseModel
from pathlib import Path
import os
from dotenv import load_dotenv
import sys
from typing import AsyncIterable, Dict, Any
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex, StorageContext, load_index_from_storage
import logging

logger = logging.getLogger(__name__)

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

root_dir = Path(__file__).resolve().parents[3]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

logger.info("Initializing JointlyQueryAgent...")

Settings.embed_model = OllamaEmbedding(
    model_name="nomic-embed-text",
    base_url="http://localhost:11434",
    request_timeout=600.0
)
Settings.llm = Ollama(
    model="qwen3:0.6b",
    base_url="http://localhost:11434",
    request_timeout=600.0
)


class ResponseFormat(BaseModel):
    status: str = "input_required"
    message: str

class JointlyQueryAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        logger.info("Initializing JointlyQueryAgent with LlamaIndex...")
        self.persist_dir = "./storage"
        try:
            if os.path.exists(self.persist_dir):
                storage_context = StorageContext.from_defaults(persist_dir=self.persist_dir)
                self.index = load_index_from_storage(storage_context)
                logger.info(f"Loaded existing index from {self.persist_dir}")
            else:
                logger.info("Loading documents from ./data...")
                # Explicitly load only universal_credit.txt or a small set of files
                input_files = [os.path.join("./data", f) for f in os.listdir("./data") if f.endswith(".txt")]
                if not input_files:
                    logger.error("No .txt files found in ./data")
                    raise FileNotFoundError("No .txt files found in ./data")
                logger.info(f"Selected files: {input_files}")
                documents = SimpleDirectoryReader(input_files=input_files).load_data()
                logger.info(f"Loaded {len(documents)} documents")
                for doc in documents:
                    logger.debug(f"Document ID: {doc.doc_id}, Metadata: {doc.metadata}")
                self.index = VectorStoreIndex.from_documents(documents, show_progress=True)
                self.index.storage_context.persist(persist_dir=self.persist_dir)
                logger.info(f"Created and saved new index to {self.persist_dir}")
            self.query_engine = self.index.as_query_engine()
        except Exception as e:
            logger.error(f"Failed to initialize index: {e}")
            raise

    async def invoke(self, query: str, session_id: str) -> dict:
        logger.info(f"invoke() called with query='{query}' and session_id='{session_id}'")
        try:
            response = await self.query_engine.aquery(query)
            response_text = str(response).strip()
            if not response_text:
                return {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": "No information found. Please clarify your query."
                }
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": response_text
            }
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "is_task_complete": False,
                "require_user_input": True,
                "content": f"Error: {str(e)}"
            }

    async def stream(self, query: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        logger.info(f"stream() called with query='{query}' and session_id='{session_id}'")
        try:
            yield {
                "is_task_complete": False,
                "require_user_input": False,
                "content": "Querying the document store..."
            }
            response = await self.query_engine.aquery(query)
            response_text = str(response).strip()
            yield {
                "is_task_complete": False,
                "require_user_input": False,
                "content": "Processing document results..."
            }
            if not response_text:
                yield {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": "No information found. Please clarify your query."
                }
            else:
                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": response_text
                }
        except Exception as e:
            logger.error(f"Error in stream: {e}")
            yield {
                "is_task_complete": False,
                "require_user_input": True,
                "content": f"Error: {str(e)}"
            }

logger.info("JointlyQueryAgent is fully initialized.")