"""
Open Knowledge Format (OKF) Engine for Contract Due Diligence & Rule Engine.
Parses OKF markdown bundles with YAML frontmatter from data/company-knowledge/.
Provides zero-cost deterministic rule checking and OKF template linking.
"""

import os
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("app.services.okf_engine")


@dataclass
class OKFConcept:
    file_path: str
    concept_type: str  # "Policy Rule", "Template", "Playbook Note", "Precedent"
    title: str
    description: str
    tags: List[str]
    metadata: Dict[str, Any]
    content: str


class OKFKnowledgeStore:
    """Loader and indexer for Open Knowledge Format (OKF) markdown bundles."""

    def __init__(self, knowledge_dir: Optional[str] = None):
        if not knowledge_dir:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            repo_knowledge = os.path.join(base_dir, "data", "company-knowledge")
            cwd_knowledge = os.path.join(os.getcwd(), "data", "company-knowledge")
            knowledge_dir = repo_knowledge if os.path.exists(repo_knowledge) else cwd_knowledge
        self.knowledge_dir = knowledge_dir
        self.concepts: List[OKFConcept] = []
        self.load_bundle()

    def load_bundle(self):
        """Recursively parses all .md files in the OKF bundle directory."""
        self.concepts.clear()
        if not os.path.exists(self.knowledge_dir):
            logger.warning(f"OKF knowledge directory does not exist: {self.knowledge_dir}")
            return

        for root, _, files in os.walk(self.knowledge_dir):
            for file in files:
                if file.endswith(".md") and file != "index.md":
                    full_path = os.path.join(root, file)
                    concept = self._parse_okf_file(full_path)
                    if concept:
                        self.concepts.append(concept)

        logger.info(f"Loaded {len(self.concepts)} OKF concepts into knowledge store.")

    def _parse_okf_file(self, file_path: str) -> Optional[OKFConcept]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read()

            # Parse frontmatter bounded by ---
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw_text, re.DOTALL)
            if not match:
                return None

            frontmatter_str, content = match.group(1), match.group(2)
            metadata = {}
            tags = []
            concept_type = "Policy Rule"
            title = os.path.basename(file_path).replace(".md", "")
            description = ""

            for line in frontmatter_str.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip()
                    val = val.strip()

                    if key == "type":
                        concept_type = val
                    elif key == "title":
                        title = val
                    elif key == "description":
                        description = val
                    elif key == "tags":
                        # parse list [tag1, tag2]
                        cleaned_tags = val.strip("[]").split(",")
                        tags = [t.strip() for t in cleaned_tags if t.strip()]
                    else:
                        metadata[key] = val

            rel_path = os.path.relpath(file_path, self.knowledge_dir).replace("\\", "/")
            return OKFConcept(
                file_path=rel_path,
                concept_type=concept_type,
                title=title,
                description=description,
                tags=tags,
                metadata=metadata,
                content=content.strip(),
            )
        except Exception as err:
            logger.error(f"Error parsing OKF file {file_path}: {err}")
            return None

    def get_rules(self) -> List[OKFConcept]:
        return [c for c in self.concepts if c.concept_type == "Policy Rule"]

    def get_templates(self) -> List[OKFConcept]:
        return [c for c in self.concepts if c.concept_type == "Template"]

    def get_template_by_tag(self, tag: str) -> Optional[OKFConcept]:
        for c in self.concepts:
            if c.concept_type == "Template" and tag.lower() in [t.lower() for t in c.tags]:
                return c
        return None


class DeterministicRuleEngine:
    """Fast, 0-LLM-cost rule check engine matching extracted terms against Policy Rules."""

    def __init__(self, store: OKFKnowledgeStore):
        self.store = store

    def evaluate_clause(self, clause_ref: str, heading: str, text: str) -> List[Dict[str, Any]]:
        findings = []
        lower_text = text.lower()

        # 1. Check Liability Cap Rules
        if "liability" in lower_text or "indemn" in lower_text:
            if "uncapped" in lower_text or "unlimited liability" in lower_text or "without limit" in lower_text:
                template = self.store.get_template_by_tag("liability")
                findings.append({
                    "rule_id": "rule_liability_uncapped",
                    "source": "rule_engine",
                    "severity": "high",
                    "clause_ref": clause_ref,
                    "title": "Uncapped Liability / Unlimited Indemnity Forbidden",
                    "description": "Contract contains uncapped liability or unlimited indemnity, violating OKF Liability Cap Ceiling Policy.",
                    "policy_link": "/legal/playbook/liability-caps.md",
                    "template_fix": template.content if template else None,
                    "tier": 1,
                })

        # 2. Check Payment Terms Rules
        if "payment" in lower_text or "net " in lower_text or "invoice" in lower_text:
            if any(term in lower_text for term in ["net 60", "net 90", "net 120", "net 180", "120 days", "90 days"]):
                template = self.store.get_template_by_tag("payment")
                findings.append({
                    "rule_id": "rule_payment_terms_exceeded",
                    "source": "rule_engine",
                    "severity": "medium",
                    "clause_ref": clause_ref,
                    "title": "Excessive Payment Term Window (Exceeds Net 30/45)",
                    "description": "Payment terms exceed company standard Net 30 policy threshold.",
                    "policy_link": "/legal/playbook/payment-terms.md",
                    "template_fix": template.content if template else None,
                    "tier": 1,
                })

        # 3. Check Auto Renewal Cancellation Windows
        if "renew" in lower_text or "auto-renew" in lower_text or "term" in lower_text:
            if any(term in lower_text for term in ["90 days notice", "120 days notice", "automatically renews"]):
                findings.append({
                    "rule_id": "rule_auto_renewal_window",
                    "source": "rule_engine",
                    "severity": "high",
                    "clause_ref": clause_ref,
                    "title": "Strict Auto-Renewal Notice Window Detected",
                    "description": "Auto-renewal clause requires 90+ days advance cancellation notice.",
                    "policy_link": "/legal/playbook/liability-caps.md",
                    "template_fix": "Contract shall renew for successive 1-year terms unless either party gives written notice of non-renewal at least 30 days prior to end of term.",
                    "tier": 1,
                })

        return findings


_okf_store: Optional[OKFKnowledgeStore] = None


def get_okf_store() -> OKFKnowledgeStore:
    global _okf_store
    if _okf_store is None:
        _okf_store = OKFKnowledgeStore()
    return _okf_store
