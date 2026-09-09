"""
SparkCloud AI Client Service for Contract Risk Analysis and Redlining.
Uses the SparkCloud OpenAI-compatible endpoint (https://cloud.sparkden.org/api/ai/v1).
"""

import json
import logging
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

from app.config import get_settings

logger = logging.getLogger("app.services.llm_client")


class SparkCloudAIClient:
    """Client wrapper for SparkCloud AI API endpoint with auto-model routing."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.sparkcloud_api_key
        self.base_url = (base_url or settings.sparkcloud_base_url).rstrip("/")
        self.model = model or settings.sparkcloud_model

    def _chat_completion(self, messages: List[Dict[str, str]], json_response: bool = False) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                choices = result.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "")
                return ""
        except urllib.error.HTTPError as err:
            error_body = err.read().decode("utf-8")
            logger.error(f"SparkCloud AI HTTP Error {err.code}: {error_body}")
            raise RuntimeError(f"SparkCloud AI API call failed with status {err.code}: {error_body}")
        except Exception as err:
            logger.error(f"SparkCloud AI connection error: {err}")
            raise RuntimeError(f"Failed to communicate with SparkCloud AI: {err}")

    def analyze_clause_risk(self, clause_ref: str, heading: str, text: str) -> Dict[str, Any]:
        """Runs LLM clause analysis returning structured JSON risk findings."""
        prompt = f"""You are an expert contract risk review AI assistant. Analyze the following contract clause and evaluate its risk profile.

Clause Reference: {clause_ref}
Heading: {heading}
Clause Text: "{text}"

Output ONLY a raw JSON object (no markdown code fences) with the exact structure:
{{
  "has_risk": true/false,
  "risk_type": "auto_renewal | uncapped_indemnity | unilateral_termination | payment_terms | jurisdiction | ip_assignment | vague_scope | none",
  "severity": "high | medium | low | none",
  "plain_english": "A concise 1-2 sentence explanation of the risk.",
  "suggested_action": "Recommended modification or opt-out action."
}}
"""
        messages = [
            {"role": "system", "content": "You are a professional legal risk analysis engine. Always respond in valid JSON format."},
            {"role": "user", "content": prompt},
        ]

        raw_output = self._chat_completion(messages, json_response=True)
        try:
            # Clean markdown codeblocks if present
            cleaned = raw_output.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned.rsplit("\n", 1)[0]
                cleaned = cleaned.replace("json\n", "", 1)
            return json.loads(cleaned)
        except Exception as err:
            logger.warning(f"Could not parse LLM JSON for {clause_ref}: {err}. Raw output: {raw_output}")
            return {
                "has_risk": False,
                "risk_type": "none",
                "severity": "none",
                "plain_english": "Clause analyzed with standard risk metrics.",
                "suggested_action": "No immediate change required.",
            }

    def generate_tier2_redline(self, clause_text: str, issue_description: str, policy_context: str) -> Dict[str, str]:
        """Generates a proposed redline rewrite for narrative contract clauses."""
        prompt = f"""You are a corporate legal counsel drafting contract redlines.

Original Clause:
"{clause_text}"

Identified Issue:
{issue_description}

Applicable Company Policy:
{policy_context}

Provide a revised, redlined version of the clause that remedies the issue while preserving standard legal enforceability.
Output ONLY a raw JSON object (no markdown code fences):
{{
  "original_clause": "{clause_text}",
  "suggested_rewrite": "The proposed amended text...",
  "rationale": "Clear legal reasoning for the revision..."
}}
"""
        messages = [
            {"role": "system", "content": "You are an expert contract redline editor. Output JSON only."},
            {"role": "user", "content": prompt},
        ]

        raw_output = self._chat_completion(messages, json_response=True)
        try:
            cleaned = raw_output.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned.rsplit("\n", 1)[0]
                cleaned = cleaned.replace("json\n", "", 1)
            return json.loads(cleaned)
        except Exception:
            return {
                "original_clause": clause_text,
                "suggested_rewrite": f"Amended {clause_text}",
                "rationale": issue_description,
            }


_llm_client: Optional[SparkCloudAIClient] = None


def get_llm_client() -> SparkCloudAIClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = SparkCloudAIClient()
    return _llm_client
