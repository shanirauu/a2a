import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv
import os
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
root_dir = Path(__file__).resolve().parents[3]
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

api_key = os.getenv("OPEN_API_KEY")
if not api_key:
    raise EnvironmentError(f"❌ OPEN_API_KEY not found in {dotenv_path}")
else:
    logger.info(f"✅ OPEN_API_KEY loaded from {dotenv_path}")

class QueryAPI:
    def __init__(self):
        logger.info("Initializing QueryAPI...")
        self.client = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=api_key
        )
        self.prompt = PromptTemplate(
            input_variables=["topic"],
            template="""
            You are a news generator. Generate a concise news article about a specific, realistic, and recent advancement or event related to {topic}.
            Ensure the content is unique, avoiding overlap with other news on the same topic.
            Include credible details like organizations, locations, or dates where relevant.
            Return the response in JSON format with the following structure:
            {
                "topic": "{topic}",
                "headline": "Breaking: [Short, attention-grabbing headline starting with 'Breaking:']",
                "summary": "[1-2 sentence summary of the news, specific and informative]"
            }
            """
        )
        self.parser = JsonOutputParser()

    def process_query(self, topic: str) -> dict:
        logger.info(f"Processing query for topic: {topic}")
        try:
            print("+++")
            chain = self.prompt | self.client | self.parser
            result = chain.invoke({"topic": topic})
            logger.debug(f"QueryAPI result: {result}")
            print(f"--- {result}")
            return result
        except Exception as e:
            logger.error(f"OpenAI Error: {str(e)}")
            return {
                "topic": topic,
                "headline": f"Error: News on {topic}",
                "summary": f"Failed to generate news: {str(e)}"
            }

logger.info("✅ QueryAPI is fully initialized.")