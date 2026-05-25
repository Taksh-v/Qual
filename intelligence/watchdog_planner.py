import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from intelligence.llm_provider import generate_text
from ingestion.signal_monitor import SignalMonitor

logger = logging.getLogger(__name__)

WATCHDOG_PROMPT_TEMPLATE = """
You are the "Watchdog Planner" for a high-end financial intelligence system.
Your job is to update the "Mission Profiles" (the themes we are monitoring) based on the latest market developments.

CURRENT MISSION PROFILES:
{current_profiles}

LATEST MARKET HEADLINES (RAW SIGNAL):
{latest_headlines}

INSTRUCTIONS:
1. Analyze the headlines for any emerging themes, specific risks, or major shifts that aren't well-covered by the current profiles.
2. You can UPDATE an existing profile (improve its name, description, or keywords).
3. You can ADD a new profile if a major new theme has emerged (e.g., a specific regional crisis or a new tech paradigm).
4. Do NOT remove profiles unless they are completely obsolete.
5. Keep the total number of profiles between 4 and 8.
6. RETURN ONLY A JSON OBJECT matching the current format: {{"profiles": [...]}}

Note: Be specific. Instead of "Tech", use "Generative AI Monetization at Scale". Instead of "Risk", use "Commercial Real Estate Debt Contagion".
"""

class WatchdogPlanner:
    def __init__(self, profiles_path: str = "data/mission_profiles.json"):
        self.profiles_path = profiles_path
        self.monitor = SignalMonitor(profiles_path)

    def plan_updates(self) -> Optional[Dict[str, Any]]:
        """
        Gathers context and asks the LLM to propose updates to the mission profiles.
        """
        logger.info("Watchdog Planner: Analyzing market context...")
        
        # 1. Get current profiles
        with open(self.profiles_path, "r") as f:
            profiles_data = json.load(f)
        
        # 2. Get recent headlines as context
        # We only need the titles to save tokens
        articles = self.monitor.fetch_headlines_firehose()
        headlines = "\n".join([f"- {a['title']}" for a in articles[:30]])
        
        # 3. Prompt LLM
        prompt = WATCHDOG_PROMPT_TEMPLATE.format(
            current_profiles=json.dumps(profiles_data, indent=2),
            latest_headlines=headlines
        )
        
        try:
            response_text, provider = generate_text(prompt, temperature=0.2, max_tokens=1500)
            logger.info(f"Watchdog Planner: LLM ({provider}) proposed updates.")
            
            # Clean response if LLM included markdown blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            new_profiles = json.loads(response_text)
            return new_profiles
        except Exception as e:
            logger.error(f"Watchdog Planner failed: {e}")
            return None

    def apply_updates(self):
        """Execute the planning and save the results."""
        updates = self.plan_updates()
        if updates and "profiles" in updates:
            try:
                with open(self.profiles_path, "w") as f:
                    json.dump(updates, f, indent=2)
                logger.info("Watchdog Planner: Successfully updated mission profiles.")
                # Trigger a refresh in the monitor
                self.monitor.profiles = updates["profiles"]
                self.monitor.refresh_mission_embeddings()
            except Exception as e:
                logger.error(f"Failed to save updated profiles: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    planner = WatchdogPlanner()
    planner.apply_updates()
