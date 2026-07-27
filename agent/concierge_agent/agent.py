from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

from .tools import lookup_guest_profile, retrieve_hotel_policy

root_agent = Agent(
    model=LiteLlm(model="anthropic/claude-haiku-4-5-20251001"),
    name="concierge_agent",
    description="A concierge assistant for a hotel.",
    instruction="""
    You are a helpful, warm hotel concierge.
Use retrieve_hotel_policy for quetions about hotel rules, check-in/out, cancellation, pets, breakfast or parking.
   Use lookup_guest_profile when you know the guest's ID and want to personalize your answer based on their stay. 
   Be concise and friendly. 
    """,
    tools=[retrieve_hotel_policy, lookup_guest_profile],
)
