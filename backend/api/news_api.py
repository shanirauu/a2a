from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
import json

class QueryAPI:
    def __init__(self):
        """Initialize with OpenAI API credentials from .env file"""
        load_dotenv()
        self.api_key = os.environ.get("OPEN_API_KEY")
        if not self.api_key:
            raise ValueError("OPEN_API_KEY not found in .env file")
        
        self.model = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=self.api_key
        )

    def process_query(self, query):
        """
        Process any user query using OpenAI to generate a mock news response.

        Args:
            query (str): The user's raw query/topic

        Returns:
            dict: Formatted response with topic, headline, and summary
        """
        prompt = (
            f"Generate a brief news summary for the topic '{query}'. "
            "Return a JSON object with 'topic', 'headline', and 'summary' fields. "
            "The headline should start with 'Breaking:'. The summary should be 1-2 sentences. "
            "Ensure the response is valid JSON."
        )

        try:
            # Use JSON mode to ensure structured output
            
            response = self.model.invoke(
                prompt,
                response_format={"type": "json_object"}
            )
            result = response.content.strip()
            
            result_dict = json.loads(result)
            return {
                "topic": result_dict.get("topic", query),
                "headline": result_dict.get("headline", f"Breaking: News on {query.title()}!"),
                "summary": result_dict.get("summary", "No summary available.")
            }

        except Exception as e:
            print(f"OpenAI Error: {str(e)}")
            # Fallback: Generate plain text response
            try:
                fallback_prompt = (
                    f"Generate a brief news summary for the topic '{query}'. "
                    "Provide a headline starting with 'Breaking:' and a 1-2 sentence summary."
                )
                fallback_response = self.model.invoke(fallback_prompt)
                summary = fallback_response.content.strip()
                return {
                    "topic": query,
                    "headline": f"Breaking: News on {query.title()}!",
                    "summary": summary
                }
            except Exception as fallback_e:
                print(f"Fallback Error: {str(fallback_e)}")
                return {
                    "error": str(e),
                    "topic": query,
                    "headline": f"Error processing: {query}",
                    "summary": "Unable to process this query at this time."
                }