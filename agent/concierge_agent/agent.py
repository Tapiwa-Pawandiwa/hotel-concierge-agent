from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

root_agent = Agent(
    model=LiteLlm(model="anthropic/claude-haiku-4-5-20251001"),
    name="concierge_agent",
    description="A concierge assistant for a hotel.",
    instruction="You are a helpful, warm hotel concierge. For now, just chat naturally — tools come in a later step.",
)
