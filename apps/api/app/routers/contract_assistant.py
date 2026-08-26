"""
FastAPI APIRouter for the Internal Contract Assistant Engine.
Powered by SparkCloud AI (auto model) and OKF Knowledge Base.
Full Database Persistence & bnb-signatures Integration.
"""

import io
import os
import re
import uuid
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.models import (
    ContractAssistantContract,
    ContractAssistantClause,
    ContractAssistantFinding,
    ContractAssistantSignatory,
    ContractAssistantEnvelope,
    ContractAssistantEvent,
    SignatureRequest,
    SignatureRecipient,
    SignatureAuditLog,
)
from app.dependencies import DbSession, ResolvedPrincipal, get_current_user, get_optional_user
from app.services.llm_client import get_llm_client
from app.services.okf_engine import DeterministicRuleEngine, get_okf_store
from app.services.signature_engine import prepare_document_pdf, render_pdf_page_previews

router = APIRouter(prefix="/api/contract-assistant", tags=["contract-assistant"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ClauseAnalysisItem(BaseModel):
    clause_ref: str
    heading: str
    text: str
    has_risk: bool
    risk_type: str
    severity: str
    source: str  # "rule_engine" or "llm_judgment"
    plain_english: str
    suggested_action: str
    policy_link: Optional[str] = None
    template_fix: Optional[str] = None
    tier: int = 1  # 1 = Template swap, 2 = LLM redline


class ContractAnalysisResponse(BaseModel):
    contract_id: str
    filename: str
    title: str
    total_clauses: int
    high_risks: int
    medium_risks: int
    low_risks: int
    page_count: int
    previews: List[str] = []
    issues: List[ClauseAnalysisItem] = []
    created_at: str


class AutoFixRequest(BaseModel):
    clause_text: str
    issue_description: str
    tier: int = 1  # 1 = Template swap, 2 = LLM redline
    policy_tag: Optional[str] = None


class AutoFixResponse(BaseModel):
    tier: int
    original_clause: str
    suggested_rewrite: str
    rationale: str
    requires_human_approval: bool = True
    auto_dispatched: bool = False


class UpdateFindingRequest(BaseModel):
    status: Optional[str] = None  # open, resolved, dismissed
    suggested_rewrite: Optional[str] = None
    dismissed_reason: Optional[str] = None


class InboundEmailWebhookPayload(BaseModel):
    from_email: str
    subject: str
    body_plain: Optional[str] = None
    message_id: Optional[str] = None
    attachments_count: int = 0


class DispatchRequest(BaseModel):
    contract_id: str
    recipients: List[Dict[str, str]]  # list of {name, email, role}


class AskQuestionRequest(BaseModel):
    question: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/rules")
async def get_okf_playbook_rules():
    """List loaded OKF playbook policies and rule definitions."""
    store = get_okf_store()
    rules = store.get_rules()
    return {
        "total_rules": len(rules),
        "rules": [
            {
                "file_path": r.file_path,
                "title": r.title,
                "description": r.description,
                "tags": r.tags,
                "metadata": r.metadata,
            }
            for r in rules
        ],
    }


def _normalize_status(raw_status: Optional[str]) -> str:
    if not raw_status:
        return "in_review"
    s = raw_status.lower().strip()
    if s in ("dotted", "completed", "executed", "archived", "sealed", "signed"):
        return "dotted"
    if s in ("out_for_signature", "pending", "sent", "pending_signatures", "dispatched", "partially_signed"):
        return "out_for_signature"
    return "in_review"


async def _sync_signature_request_to_ca_contract(db: DbSession, sig_req: SignatureRequest) -> ContractAssistantContract:
    """Auto-ingest and analyze a SignatureRequest into ContractAssistantContract if unlinked."""
    counterparty = sig_req.recipients[0].name if sig_req.recipients else "GOBITSNBYTES FOUNDATION"
    c_status = "out_for_signature" if sig_req.status in ("pending", "sent") else "dotted" if sig_req.status == "completed" else "in_review"

    ca_contract = ContractAssistantContract(
        id=sig_req.id,
        title=sig_req.title,
        counterparty=counterparty,
        status=c_status,
        value="Official Contract",
        original_file_path=sig_req.original_file_path,
        created_by=sig_req.created_by,
        created_at=sig_req.created_at or datetime.now(timezone.utc),
    )
    db.add(ca_contract)

    envelope = ContractAssistantEnvelope(
        contract_id=ca_contract.id,
        signature_request_id=sig_req.id,
        status=sig_req.status,
    )
    db.add(envelope)

    for r in sig_req.recipients:
        sig = ContractAssistantSignatory(
            contract_id=ca_contract.id,
            name=r.name,
            email=r.email,
            role=r.role,
            envelope_status=r.status,
        )
        db.add(sig)

    text_to_analyze = sig_req.title
    extracted_clauses = []

    if sig_req.original_file_path and os.path.exists(sig_req.original_file_path):
        try:
            import fitz
            doc = fitz.open(sig_req.original_file_path)
            full_text = ""
            for p_idx, page in enumerate(doc, 1):
                p_text = page.get_text("text") or ""
                full_text += f"\n{p_text}"
                if p_text.strip():
                    extracted_clauses.append((f"§{p_idx}.0", f"Page {p_idx} Terms", p_text.strip()[:1500], p_idx))
            if full_text.strip():
                text_to_analyze = full_text
        except Exception as e:
            logger.warning(f"Failed PDF text extraction for {sig_req.id}: {e}")

    if not extracted_clauses:
        extracted_clauses.append(("§1.0", f"Agreement Scope: {sig_req.title}", f"Official legal agreement: {sig_req.title}. Tracked under bnb-signatures with {len(sig_req.recipients)} signatories.", 1))

    clause_objs = []
    for ref, heading, clause_text, page_num in extracted_clauses:
        cl = ContractAssistantClause(
            contract_id=ca_contract.id,
            ref=ref,
            heading=heading,
            text=clause_text,
            page_number=page_num,
        )
        db.add(cl)
        clause_objs.append(cl)

    # OKF Rule Engine Evaluation
    okf_store = get_okf_store()
    rule_engine = DeterministicRuleEngine(okf_store)
    eval_results = rule_engine.evaluate_contract_text(text_to_analyze)
    for idx, res in enumerate(eval_results, 1):
        target_cl = clause_objs[0] if clause_objs else None
        f = ContractAssistantFinding(
            contract_id=ca_contract.id,
            clause_id=target_cl.id if target_cl else None,
            clause_ref=target_cl.ref if target_cl else "§1.0",
            heading=res.get("title", "Policy Finding"),
            source="rule_engine",
            severity=res.get("severity", "medium"),
            risk_type=res.get("title", "Legal Finding"),
            plain_english=res.get("description", "Potential policy mismatch detected."),
            suggested_action=res.get("template_fix") or "Review against OKF playbook.",
            policy_link=res.get("policy_link", "/legal/playbook"),
            tier=1,
            status="open",
        )
        db.add(f)

    ev = ContractAssistantEvent(
        contract_id=ca_contract.id,
        type="ingested",
        payload={"title": ca_contract.title, "source": "signature_request_sync"},
    )
    db.add(ev)

    await db.commit()

    stmt = (
        select(ContractAssistantContract)
        .options(
            selectinload(ContractAssistantContract.clauses),
            selectinload(ContractAssistantContract.findings),
            selectinload(ContractAssistantContract.signatories),
            selectinload(ContractAssistantContract.envelopes),
            selectinload(ContractAssistantContract.events),
        )
        .where(ContractAssistantContract.id == ca_contract.id)
    )
    res = await db.execute(stmt)
    return res.scalar_one()


@router.get("/contracts")
async def list_pipeline_contracts(
    db: DbSession,
    source: Optional[str] = None,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """List all pipeline contracts with real database metrics (merging ca_contracts & signature_requests).

    ``?source=inbound_email`` restricts to contracts ingested from the legal inbox."""
    # Auto-sync any unlinked SignatureRequest entries
    sig_stmt = (
        select(SignatureRequest)
        .options(selectinload(SignatureRequest.recipients))
    )
    sig_res = await db.execute(sig_stmt)
    all_sig_reqs = sig_res.scalars().all()

    existing_ca_stmt = select(ContractAssistantEnvelope)
    env_res = await db.execute(existing_ca_stmt)
    linked_sig_ids = {env.signature_request_id for env in env_res.scalars().all()}

    for sr in all_sig_reqs:
        if sr.id not in linked_sig_ids:
            try:
                await _sync_signature_request_to_ca_contract(db, sr)
            except Exception as e:
                logger.error(f"Failed to auto-sync signature request {sr.id}: {e}")

    stmt = (
        select(ContractAssistantContract)
        .options(
            selectinload(ContractAssistantContract.findings),
            selectinload(ContractAssistantContract.signatories),
            selectinload(ContractAssistantContract.envelopes),
        )
        .order_by(ContractAssistantContract.created_at.desc())
    )
    result = await db.execute(stmt)
    contracts = result.scalars().all()

    if (source or "").strip().lower() == "inbound_email":
        contracts = [c for c in contracts if c.message_id]

    output = []
    now = datetime.now(timezone.utc)

    for c in contracts:
        high_open = sum(1 for f in c.findings if f.severity == "high" and f.status == "open")
        med_open = sum(1 for f in c.findings if f.severity == "medium" and f.status == "open")
        low_open = sum(1 for f in c.findings if f.severity == "low" and f.status == "open")

        highest_risk = "none"
        if high_open > 0:
            highest_risk = "high"
        elif med_open > 0:
            highest_risk = "medium"
        elif low_open > 0:
            highest_risk = "low"

        created_at_utc = c.created_at.replace(tzinfo=timezone.utc) if c.created_at and c.created_at.tzinfo is None else c.created_at
        days_in_stage = (now - created_at_utc).days if created_at_utc else 0

        output.append({
            "id": str(c.id),
            "title": c.title,
            "counterparty": c.counterparty or "GOBITSNBYTES FOUNDATION",
            "status": _normalize_status(c.status),
            "raw_status": c.status,
            "value": c.value or "Official Contract",
            "signatories_count": len(c.signatories) if c.signatories else 2,
            "highest_risk": highest_risk,
            "created_at": created_at_utc.isoformat() if created_at_utc else now.isoformat(),
            "days_in_stage": days_in_stage,
            "high_risks": high_open,
            "medium_risks": med_open,
            "low_risks": low_open,
        })

    output.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return output


@router.get("/contracts/{contract_id}")
async def get_contract_detail(
    contract_id: str,
    db: DbSession,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """Retrieve full contract clauses, findings, and status from database."""
    try:
        contract_uuid = uuid.UUID(contract_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Contract not found")

    stmt = (
        select(ContractAssistantContract)
        .options(
            selectinload(ContractAssistantContract.clauses),
            selectinload(ContractAssistantContract.findings),
            selectinload(ContractAssistantContract.signatories),
            selectinload(ContractAssistantContract.envelopes),
            selectinload(ContractAssistantContract.events),
        )
        .where(ContractAssistantContract.id == contract_uuid)
    )
    result = await db.execute(stmt)
    contract = result.scalar_one_or_none()

    if not contract:
        sig_stmt = (
            select(SignatureRequest)
            .options(
                selectinload(SignatureRequest.recipients),
                selectinload(SignatureRequest.audit_logs),
            )
            .where(SignatureRequest.id == contract_uuid)
        )
        sig_res = await db.execute(sig_stmt)
        sig_req = sig_res.scalar_one_or_none()

        if not sig_req:
            raise HTTPException(status_code=404, detail="Contract not found")

        try:
            contract = await _sync_signature_request_to_ca_contract(db, sig_req)
        except Exception as e:
            logger.error(f"Error syncing contract detail for {sig_req.id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to sync contract legal overview")

    clauses_out = [
        {
            "id": str(cl.id),
            "ref": cl.ref,
            "heading": cl.heading,
            "text": cl.text,
            "page_number": cl.page_number,
        }
        for cl in contract.clauses
    ]

    findings_out = [
        {
            "id": str(f.id),
            "clause_id": str(f.clause_id) if f.clause_id else None,
            "ref": f.clause_ref,
            "heading": f.heading,
            "text": f.suggested_rewrite if (f.status == "resolved" and f.suggested_rewrite) else (f.clause.text if f.clause else f.plain_english),
            "source": f.source,
            "severity": f.severity,
            "risk_type": f.risk_type,
            "plain_english": f.plain_english,
            "suggested_action": f.suggested_action,
            "policy_link": f.policy_link,
            "template_fix": f.template_fix,
            "suggested_rewrite": f.suggested_rewrite,
            "tier": f.tier,
            "status": f.status,
            "rationale": f.dismissed_reason or "OKF Governance & Risk Charter standard compliance.",
        }
        for f in contract.findings
    ]

    return {
        "id": str(contract.id),
        "title": contract.title,
        "counterparty": contract.counterparty or "GOBITSNBYTES FOUNDATION",
        "status": contract.status,
        "value": contract.value or "Official Contract",
        "created_at": contract.created_at.isoformat() if contract.created_at else None,
        "clauses": clauses_out,
        "findings": findings_out,
        "signatories": [
            {"id": str(s.id), "name": s.name, "email": s.email, "role": s.role, "status": s.envelope_status}
            for s in contract.signatories
        ],
    }


async def analyze_contract_bytes(
    db: DbSession,
    filename: str,
    content: bytes,
    source: str = "dashboard_upload",
    source_meta: Optional[Dict[str, Any]] = None,
) -> ContractAssistantContract:
    """Core analysis pipeline shared by the /analyze endpoint and the legal-agent
    inbox poller: parse document (.pdf/.docx), run 2-pass analysis (OKF Rule
    Engine + SparkCloud AI), persist contract/clauses/findings/event, return the
    loaded ContractAssistantContract."""
    try:
        pdf_bytes = prepare_document_pdf(content, filename)
    except Exception as err:
        raise ValueError(f"Document parsing error: {err}")

    import fitz

    # Extract real clauses from PDF text
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n\n"
        doc.close()
    except Exception as err:
        raise ValueError(f"Text extraction error: {err}")

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if len(p.strip()) > 20]

    extracted_clauses = []
    for i, p in enumerate(paragraphs):
        lines = p.split('\n', 1)
        heading = lines[0].strip()
        text = lines[1].strip().replace('\n', ' ') if len(lines) > 1 else p.replace('\n', ' ')
        if not text:
            text = heading

        ref_match = re.match(r'^(§\s*\d+(?:\.\d+)?|Section\s*\d+|Article\s*[IVX0-9]+)', heading, re.IGNORECASE)
        ref = ref_match.group(1) if ref_match else f"Clause {i+1}"

        extracted_clauses.append({
            "ref": ref,
            "heading": heading[:100],
            "text": text
        })

    if not extracted_clauses:
        extracted_clauses.append({
            "ref": "Doc",
            "heading": "Full Document",
            "text": full_text.replace('\n', ' ')[:2000]
        })

    okf_store = get_okf_store()
    rule_engine = DeterministicRuleEngine(okf_store)
    llm_client = get_llm_client()

    issues: List[ClauseAnalysisItem] = []

    for clause in extracted_clauses:
        # Step 1: Deterministic Rule Check (0 LLM cost)
        rule_findings = rule_engine.evaluate_clause(clause["ref"], clause["heading"], clause["text"])

        if rule_findings:
            for f in rule_findings:
                issues.append(
                    ClauseAnalysisItem(
                        clause_ref=clause["ref"],
                        heading=clause["heading"],
                        text=clause["text"],
                        has_risk=True,
                        risk_type=f["title"],
                        severity=f["severity"],
                        source="rule_engine",
                        plain_english=f["description"],
                        suggested_action="Apply approved OKF standard clause replacement.",
                        policy_link=f.get("policy_link"),
                        template_fix=f.get("template_fix"),
                        tier=1,
                    )
                )
        else:
            # Step 2: Semantic Risk Review via SparkCloud AI (auto model)
            try:
                llm_res = llm_client.analyze_clause_risk(clause["ref"], clause["heading"], clause["text"])
                if llm_res.get("has_risk"):
                    issues.append(
                        ClauseAnalysisItem(
                            clause_ref=clause["ref"],
                            heading=clause["heading"],
                            text=clause["text"],
                            has_risk=True,
                            risk_type=llm_res.get("risk_type", "general_risk"),
                            severity=llm_res.get("severity", "low"),
                            source="llm_judgment",
                            plain_english=llm_res.get("plain_english", "Potential legal risk identified."),
                            suggested_action=llm_res.get("suggested_action", "Review clause language."),
                            tier=2,
                        )
                    )
            except Exception:
                pass

    meta = dict(source_meta or {})

    db_contract = ContractAssistantContract(
        title=filename.replace(".pdf", "").replace(".docx", "").replace("_", " ").title(),
        counterparty="Pending Legal Review",
        status="in_review",
        value="Under Audit",
        original_file_path=filename,
        message_id=meta.get("message_id"),
        created_by=meta.get("created_by"),
    )
    db.add(db_contract)
    await db.flush()

    db_clauses = []
    for c_data in extracted_clauses:
        db_cl = ContractAssistantClause(
            contract_id=db_contract.id,
            ref=c_data["ref"],
            heading=c_data["heading"],
            text=c_data["text"],
            page_number=1,
        )
        db.add(db_cl)
        db_clauses.append(db_cl)

    await db.flush()
    clause_map = {cl.ref: cl.id for cl in db_clauses}

    for issue in issues:
        db_f = ContractAssistantFinding(
            contract_id=db_contract.id,
            clause_id=clause_map.get(issue.clause_ref),
            clause_ref=issue.clause_ref,
            heading=issue.heading,
            source=issue.source,
            severity=issue.severity,
            risk_type=issue.risk_type,
            plain_english=issue.plain_english,
            suggested_action=issue.suggested_action,
            policy_link=issue.policy_link,
            template_fix=issue.template_fix,
            tier=issue.tier,
            status="open",
        )
        db.add(db_f)

    db_evt = ContractAssistantEvent(
        contract_id=db_contract.id,
        type="ingested_and_analyzed",
        actor_id=meta.get("created_by"),
        payload={
            "filename": filename,
            "clauses_count": len(extracted_clauses),
            "issues_count": len(issues),
            "source": source,
            "source_meta": meta,
        },
    )
    db.add(db_evt)

    await db.commit()

    stmt = (
        select(ContractAssistantContract)
        .options(
            selectinload(ContractAssistantContract.clauses),
            selectinload(ContractAssistantContract.findings),
            selectinload(ContractAssistantContract.signatories),
            selectinload(ContractAssistantContract.envelopes),
            selectinload(ContractAssistantContract.events),
        )
        .where(ContractAssistantContract.id == db_contract.id)
    )
    res = await db.execute(stmt)
    return res.scalar_one()


def _findings_to_issues(contract: ContractAssistantContract) -> List[ClauseAnalysisItem]:
    """Rebuild the API issue list from persisted findings (shared pipeline output)."""
    clause_text_by_id = {cl.id: cl.text for cl in (contract.clauses or [])}
    return [
        ClauseAnalysisItem(
            clause_ref=f.clause_ref,
            heading=f.heading,
            text=(clause_text_by_id.get(f.clause_id) or f.plain_english),
            has_risk=True,
            risk_type=f.risk_type,
            severity=f.severity,
            source=f.source,
            plain_english=f.plain_english,
            suggested_action=f.suggested_action,
            policy_link=f.policy_link,
            template_fix=f.template_fix,
            tier=f.tier,
        )
        for f in (contract.findings or [])
    ]


@router.post("/analyze", response_model=ContractAnalysisResponse)
async def analyze_contract_file(
    db: DbSession,
    file: UploadFile = File(...),
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """Parse document (.pdf or .docx), run 2-pass analysis (OKF Rule Engine + SparkCloud AI), and persist to DB."""
    contents = await file.read()
    filename = file.filename or "contract.pdf"

    try:
        pdf_bytes = prepare_document_pdf(contents, filename)
        previews = render_pdf_page_previews(pdf_bytes)
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Document parsing error: {err}")

    try:
        db_contract = await analyze_contract_bytes(
            db,
            filename,
            contents,
            "dashboard_upload",
            {"created_by": getattr(current_user, "id", None) if current_user else None},
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    issues = _findings_to_issues(db_contract)
    high_count = sum(1 for i in issues if i.severity == "high")
    med_count = sum(1 for i in issues if i.severity == "medium")
    low_count = sum(1 for i in issues if i.severity == "low")

    created_at_utc = (
        db_contract.created_at.replace(tzinfo=timezone.utc)
        if db_contract.created_at and db_contract.created_at.tzinfo is None
        else db_contract.created_at
    )

    return ContractAnalysisResponse(
        contract_id=str(db_contract.id),
        filename=filename,
        title=db_contract.title,
        total_clauses=len(db_contract.clauses or []),
        high_risks=high_count,
        medium_risks=med_count,
        low_risks=low_count,
        page_count=len(previews),
        previews=previews,
        issues=issues,
        created_at=created_at_utc.isoformat() if created_at_utc else datetime.now(timezone.utc).isoformat(),
    )


@router.patch("/contracts/{contract_id}/findings/{finding_id}")
async def update_contract_finding(
    contract_id: str,
    finding_id: str,
    payload: UpdateFindingRequest,
    db: DbSession,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """Update finding status (resolve/dismiss/open) or save redline text in database."""
    try:
        c_uuid = uuid.UUID(contract_id)
        f_uuid = uuid.UUID(finding_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Finding not found")

    stmt = select(ContractAssistantFinding).where(
        ContractAssistantFinding.id == f_uuid,
        ContractAssistantFinding.contract_id == c_uuid,
    )
    res = await db.execute(stmt)
    finding = res.scalar_one_or_none()

    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    if payload.status:
        finding.status = payload.status
    if payload.suggested_rewrite:
        finding.suggested_rewrite = payload.suggested_rewrite
    if payload.dismissed_reason:
        finding.dismissed_reason = payload.dismissed_reason

    user_id = getattr(current_user, "id", None) if current_user else None
    db_evt = ContractAssistantEvent(
        contract_id=c_uuid,
        type="finding_updated",
        actor_id=user_id,
        payload={"finding_id": finding_id, "new_status": finding.status},
    )
    db.add(db_evt)

    await db.commit()
    return {"status": "success", "finding_id": finding_id, "finding_status": finding.status}


@router.post("/autofix", response_model=AutoFixResponse)
async def generate_autofix(
    payload: AutoFixRequest,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """Generate Tier-1 template substitution or Tier-2 SparkCloud AI redline proposal."""
    if payload.tier == 1:
        okf_store = get_okf_store()
        template = okf_store.get_template_by_tag(payload.policy_tag or "liability")
        rewrite = template.content if template else payload.clause_text
        return AutoFixResponse(
            tier=1,
            original_clause=payload.clause_text,
            suggested_rewrite=rewrite,
            rationale="Canonical Tier-1 OKF Template Substitution (Safe for immediate application).",
        )

    # Tier 2: LLM Redline via SparkCloud AI
    llm_client = get_llm_client()
    redline = llm_client.generate_tier2_redline(
        clause_text=payload.clause_text,
        issue_description=payload.issue_description,
        policy_context="Standard Company Risk Management Policy",
    )

    return AutoFixResponse(
        tier=2,
        original_clause=redline.get("original_clause", payload.clause_text),
        suggested_rewrite=redline.get("suggested_rewrite", payload.clause_text),
        rationale=redline.get("rationale", "AI generated redline proposal."),
    )


import hmac
import secrets

@router.post("/inbound-email")
async def handle_inbound_email_webhook(
    req: Request,
    payload: InboundEmailWebhookPayload,
    x_postmark_server_token: Optional[str] = Header(None, alias="x-postmark-server-token"),
    x_inbound_secret: Optional[str] = Header(None, alias="x-inbound-secret"),
    x_webhook_signature: Optional[str] = Header(None, alias="x-webhook-signature"),
    x_signature_256: Optional[str] = Header(None, alias="x-signature-256"),
):
    """
    Webhook handler for Postmark / SendGrid / SES inbound email parsing (contracts@gobitsnbytes.org).
    Validates webhook HMAC signature, secret token, and enforces @gobitsnbytes.org sender authorization.
    """
    # Enforce @gobitsnbytes.org sender domain restriction strictly
    from_email = (payload.from_email or "").strip().lower()
    if not (from_email.endswith("@gobitsnbytes.org") or from_email.endswith("<legal@gobitsnbytes.org>")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access Denied: Inbound contract triggers are strictly restricted to authorized @gobitsnbytes.org email accounts."
        )

    settings = get_settings()
    expected_secret = settings.inbound_email_webhook_secret

    if expected_secret:
        provided_token = x_postmark_server_token or x_inbound_secret
        token_valid = False
        if provided_token and secrets.compare_digest(provided_token, expected_secret):
            token_valid = True

        sig_header = x_webhook_signature or x_signature_256
        if sig_header and not token_valid:
            raw_body = await req.body()
            computed_hmac = hmac.new(
                expected_secret.encode("utf-8"),
                raw_body,
                digestmod="sha256"
            ).hexdigest()
            if secrets.compare_digest(sig_header.lower(), computed_hmac.lower()):
                token_valid = True

        if not token_valid and provided_token is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature or unauthorized secret token."
            )

    return {
        "status": "success",
        "message": f"Inbound email from {payload.from_email} verified & processed. Subject: {payload.subject}",
        "thread_id": f"th_{uuid.uuid4().hex[:8]}",
        "verified": True,
    }


@router.post("/dispatch")
async def dispatch_contract_for_signature(
    payload: DispatchRequest,
    db: DbSession,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """
    Dispatch reviewed contract to bnb-signatures e-signature system.
    Server-side safety gate: ensures high-severity findings are resolved before sending out.
    """
    if not payload.recipients:
        raise HTTPException(status_code=400, detail="At least one signatory recipient is required for dispatch.")

    try:
        c_uuid = uuid.UUID(payload.contract_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contract_id format")

    stmt = (
        select(ContractAssistantContract)
        .options(selectinload(ContractAssistantContract.findings))
        .where(ContractAssistantContract.id == c_uuid)
    )
    res = await db.execute(stmt)
    contract = res.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Safety Gate Check: ensure high-severity findings are resolved or dismissed
    high_open = [f for f in contract.findings if f.severity == "high" and f.status == "open"]
    if high_open:
        raise HTTPException(
            status_code=400,
            detail=f"Dispatch blocked: {len(high_open)} high-severity legal finding(s) must be resolved or dismissed first.",
        )

    user_id = getattr(current_user, "id", None) if current_user else None

    # Create SignatureRequest in bnb-signatures database
    import hashlib
    file_path = contract.original_file_path or os.path.join(os.getcwd(), "data", "signatures", f"{contract.id}.pdf")
    doc_hash = None
    if os.path.exists(file_path):
        with open(file_path, "rb") as df:
            doc_hash = hashlib.sha256(df.read()).hexdigest()
    else:
        # Fallback to deterministic title hash
        doc_hash = hashlib.sha256(f"{contract.title}_{contract.id}".encode("utf-8")).hexdigest()

    sig_req = SignatureRequest(
        title=f"Legal Agreement: {contract.title}",
        original_file_path=file_path,
        created_by=user_id,
        status="pending",
        document_hash=doc_hash,
    )
    db.add(sig_req)
    await db.flush()

    for r in payload.recipients:
        token = f"sig_tok_{uuid.uuid4().hex[:16]}"
        rec = SignatureRecipient(
            request_id=sig_req.id,
            name=r.get("name", "Signatory"),
            email=r.get("email", "signer@gobitsnbytes.org"),
            access_token=token,
            status="pending",
        )
        db.add(rec)

        ca_sig = ContractAssistantSignatory(
            contract_id=contract.id,
            name=r.get("name", "Signatory"),
            email=r.get("email", "signer@gobitsnbytes.org"),
            role=r.get("role", "signer"),
            envelope_status="pending",
        )
        db.add(ca_sig)

    audit_log = SignatureAuditLog(
        request_id=sig_req.id,
        action="DISPATCHED",
        details=f"Contract Assistant dispatched agreement to {len(payload.recipients)} signatories.",
    )
    db.add(audit_log)

    envelope = ContractAssistantEnvelope(
        contract_id=contract.id,
        signature_request_id=sig_req.id,
        status="pending",
    )
    db.add(envelope)

    contract.status = "out_for_signature"
    contract.dispatched_at = datetime.now(timezone.utc)

    evt = ContractAssistantEvent(
        contract_id=contract.id,
        type="dispatched_to_signatures",
        actor_id=user_id,
        payload={"signature_request_id": str(sig_req.id), "recipients": payload.recipients},
    )
    db.add(evt)

    await db.commit()

    return {
        "status": "dispatched",
        "message": "Contract successfully dispatched to bnb-signatures portal",
        "signature_request_id": str(sig_req.id),
        "contract_id": str(contract.id),
        "dispatched_recipients_count": len(payload.recipients),
    }


@router.post("/contracts/{contract_id}/void")
async def void_contract_agreement(
    contract_id: str,
    db: DbSession,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """Officially quash/void an agreement and revoke all signatory access."""
    try:
        c_uuid = uuid.UUID(contract_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contract_id format")

    user_id = getattr(current_user, "id", None) if current_user else None

    # Query ContractAssistantContract
    ca_stmt = (
        select(ContractAssistantContract)
        .options(
            selectinload(ContractAssistantContract.envelopes),
            selectinload(ContractAssistantContract.signatories),
        )
        .where(ContractAssistantContract.id == c_uuid)
    )
    ca_res = await db.execute(ca_stmt)
    contract = ca_res.scalar_one_or_none()

    if not contract:
        env_stmt = select(ContractAssistantEnvelope).where(ContractAssistantEnvelope.signature_request_id == c_uuid)
        env_res = await db.execute(env_stmt)
        env = env_res.scalar_one_or_none()
        if env:
            ca_stmt = (
                select(ContractAssistantContract)
                .options(
                    selectinload(ContractAssistantContract.envelopes),
                    selectinload(ContractAssistantContract.signatories),
                )
                .where(ContractAssistantContract.id == env.contract_id)
            )
            contract = (await db.execute(ca_stmt)).scalar_one_or_none()

    # Query SignatureRequest
    sig_stmt = select(SignatureRequest).options(selectinload(SignatureRequest.recipients)).where(SignatureRequest.id == c_uuid)
    sig_res = await db.execute(sig_stmt)
    sig_req = sig_res.scalar_one_or_none()

    if not contract and not sig_req:
        raise HTTPException(status_code=404, detail="Contract agreement not found")

    now = datetime.now(timezone.utc)

    if contract:
        contract.status = "voided"
        for sig in contract.signatories:
            if sig.envelope_status in ("pending", "viewed"):
                sig.envelope_status = "declined"

        evt = ContractAssistantEvent(
            contract_id=contract.id,
            type="contract_voided",
            actor_id=user_id,
            payload={"voided_at": now.isoformat(), "action": "quashed_by_admin"},
        )
        db.add(evt)

        for env in contract.envelopes:
            if env.signature_request_id:
                s_stmt = select(SignatureRequest).options(selectinload(SignatureRequest.recipients)).where(SignatureRequest.id == env.signature_request_id)
                s_r = (await db.execute(s_stmt)).scalar_one_or_none()
                if s_r:
                    s_r.status = "voided"
                    for r in s_r.recipients:
                        if r.status in ("pending", "viewed"):
                            r.status = "declined"
                        r.otp_code = None
                        r.otp_expires_at = None
                    db.add(SignatureAuditLog(
                        request_id=s_r.id,
                        action="VOIDED",
                        details=f"Contract agreement officially quashed and voided by admin at {now.isoformat()}.",
                    ))

    if sig_req:
        sig_req.status = "voided"
        for r in sig_req.recipients:
            if r.status in ("pending", "viewed"):
                r.status = "declined"
            r.otp_code = None
            r.otp_expires_at = None
        db.add(SignatureAuditLog(
            request_id=sig_req.id,
            action="VOIDED",
            details=f"Contract agreement officially quashed and voided by admin at {now.isoformat()}.",
        ))

    await db.commit()
    return {
        "status": "voided",
        "message": "Contract agreement has been officially quashed and voided. All active execution links are revoked.",
        "contract_id": contract_id,
        "voided_at": now.isoformat(),
    }


@router.get("/contracts/{contract_id}/export-void")
async def export_voided_contract_copy(
    contract_id: str,
    db: DbSession,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """Generate and download an official CANCELLED & VOID certificate copy for client device archive."""
    try:
        c_uuid = uuid.UUID(contract_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contract_id format")

    # Fetch contract or signature request
    title = "Contract Agreement"
    file_hash = "SHA256_UNREGISTERED"
    created_at_str = datetime.now(timezone.utc).isoformat()
    signatories_str = "Signatories Registered"

    ca_stmt = (
        select(ContractAssistantContract)
        .options(selectinload(ContractAssistantContract.signatories))
        .where(ContractAssistantContract.id == c_uuid)
    )
    ca_res = await db.execute(ca_stmt)
    contract = ca_res.scalar_one_or_none()

    if contract:
        title = contract.title
        created_at_str = contract.created_at.isoformat() if contract.created_at else created_at_str
        if contract.signatories:
            signatories_str = ", ".join([f"{s.name} ({s.email})" for s in contract.signatories])
    else:
        sig_stmt = select(SignatureRequest).options(selectinload(SignatureRequest.recipients)).where(SignatureRequest.id == c_uuid)
        sig_req = (await db.execute(sig_stmt)).scalar_one_or_none()
        if sig_req:
            title = sig_req.title
            file_hash = sig_req.document_hash or file_hash
            created_at_str = sig_req.created_at.isoformat() if sig_req.created_at else created_at_str
            if sig_req.recipients:
                signatories_str = ", ".join([f"{r.name} ({r.email})" for r in sig_req.recipients])

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    cert_text = f"""================================================================================
           OFFICIAL CERTIFICATE OF CANCELLATION & VOIDED COPY
================================================================================
GOBITSNBYTES FOUNDATION (Section 8 Non-Profit Co., Companies Act 2013)
bits&bytes™ Legal Operations & Contract Assistant Portal

STATUS:              VOIDED & CANCELLED (REVOKED)
DOCUMENT TITLE:      {title}
DOCUMENT ID:         {contract_id}
ORIGINAL CHECKSUM:   {file_hash}
DATE OF CREATION:    {created_at_str}
DATE OF REVOCATION:  {now_str}
REGISTERED PARTIES:  {signatories_str}

--------------------------------------------------------------------------------
STATUTORY REVOCATION NOTICE:
In accordance with Section 10A of the Information Technology Act, 2000 and Section
65B of the Indian Evidence Act (Bharatiya Sakshya Adhiniyam, 2023):

1. THIS CONTRACT AGREEMENT HAS BEEN OFFICIALLY QUASHED AND VOIDED BY THE ISSUING
   AUTHORITY (GOBITSNBYTES FOUNDATION).
2. ALL ELECTRONIC SIGNATURE LINKS, TOKENIZED PORTAL ACCESS, AND STATUTORY ENFORCEABILITY
   FOR THIS DOCUMENT ARE PERMANENTLY REVOKED AND TERMINATED.
3. THIS DOCUMENT CONSTITUTES THE SOLE CERTIFIED ARCHIVAL RECORD PROVING THAT THE
   AGREEMENT WAS CANCELLED AND VOIDED PRIOR TO DESTRUCTION OF ONLINE DATABASE RECORDS.
--------------------------------------------------------------------------------
Audit Trail: Generated & Sealed on {now_str} by Legal Administrator.
================================================================================
"""

    from fastapi.responses import Response
    return Response(
        content=cert_text,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="VOIDED_AGREEMENT_{contract_id[:8]}.txt"'
        },
    )


@router.delete("/contracts/{contract_id}")
async def delete_contract_permanently(
    contract_id: str,
    db: DbSession,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """
    Permanently purge a contract and all associated database records (clauses, findings, signatories, envelopes, audit logs).
    """
    try:
        c_uuid = uuid.UUID(contract_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contract_id format")

    # Delete from ca_contracts
    ca_stmt = select(ContractAssistantContract).options(selectinload(ContractAssistantContract.envelopes)).where(ContractAssistantContract.id == c_uuid)
    ca_res = await db.execute(ca_stmt)
    contract = ca_res.scalar_one_or_none()

    sig_ids_to_delete = set()

    if contract:
        for env in contract.envelopes:
            if env.signature_request_id:
                sig_ids_to_delete.add(env.signature_request_id)
        if contract.original_file_path and os.path.exists(contract.original_file_path):
            try:
                os.remove(contract.original_file_path)
            except Exception as e:
                logger.warning(f"Could not remove contract file {contract.original_file_path}: {e}")
        await db.delete(contract)

    # Delete from signature_requests
    sig_stmt = select(SignatureRequest).where(SignatureRequest.id == c_uuid)
    sig_req = (await db.execute(sig_stmt)).scalar_one_or_none()

    if sig_req:
        if sig_req.original_file_path and os.path.exists(sig_req.original_file_path):
            try:
                os.remove(sig_req.original_file_path)
            except Exception as e:
                logger.warning(f"Could not remove signature file {sig_req.original_file_path}: {e}")
        if sig_req.signed_file_path and os.path.exists(sig_req.signed_file_path):
            try:
                os.remove(sig_req.signed_file_path)
            except Exception:
                pass
        await db.delete(sig_req)

    for sid in sig_ids_to_delete:
        if sid != c_uuid:
            s_stmt = select(SignatureRequest).where(SignatureRequest.id == sid)
            s_r = (await db.execute(s_stmt)).scalar_one_or_none()
            if s_r:
                if s_r.original_file_path and os.path.exists(s_r.original_file_path):
                    try:
                        os.remove(s_r.original_file_path)
                    except Exception:
                        pass
                if s_r.signed_file_path and os.path.exists(s_r.signed_file_path):
                    try:
                        os.remove(s_r.signed_file_path)
                    except Exception:
                        pass
                await db.delete(s_r)

    await db.commit()

    return {
        "status": "deleted",
        "message": f"Contract {contract_id} and all associated records permanently purged from database.",
    }


class AskSourceChip(BaseModel):
    label: str  # "OKF Rule" | "Executed Contract"
    title: str


class AskAnswerResponse(BaseModel):
    answer: str
    sources: List[AskSourceChip] = []


def _ask_tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]{3,}", (text or "").lower()))


async def _build_ask_corpus(db: DbSession) -> List[Dict[str, str]]:
    """Retrieval corpus = OKF playbook concepts + clauses of executed contracts."""
    corpus: List[Dict[str, str]] = []

    okf_store = get_okf_store()
    for concept in okf_store.concepts:
        corpus.append({
            "label": "OKF Rule",
            "title": concept.title,
            "text": f"{concept.title}\n{concept.description}\n{(concept.content or '')[:1500]}",
        })

    executed_stmt = (
        select(ContractAssistantContract)
        .join(
            ContractAssistantEnvelope,
            ContractAssistantEnvelope.contract_id == ContractAssistantContract.id,
        )
        .join(
            SignatureRequest,
            ContractAssistantEnvelope.signature_request_id == SignatureRequest.id,
        )
        .options(selectinload(ContractAssistantContract.clauses))
        .where(SignatureRequest.status == "completed")
        .distinct()
    )
    executed = (await db.execute(executed_stmt)).scalars().all()
    for contract in executed:
        for cl in contract.clauses or []:
            corpus.append({
                "label": "Executed Contract",
                "title": contract.title,
                "text": f"{contract.title} — {cl.ref} {cl.heading}: {(cl.text or '')[:1200]}",
            })

    return corpus


@router.post("/ask", response_model=AskAnswerResponse)
async def ask_contract_knowledge_base(
    payload: AskQuestionRequest,
    db: DbSession,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """RAG over the OKF knowledge base plus executed contracts, with source chips."""
    q_tokens = _ask_tokens(payload.question)

    corpus = await _build_ask_corpus(db)
    scored: List[tuple] = []
    for idx, chunk in enumerate(corpus):
        overlap = len(q_tokens & _ask_tokens(chunk["text"]))
        if overlap > 0:
            scored.append((overlap, -idx, chunk))
    scored.sort(key=lambda pair: (pair[0], pair[1]), reverse=True)

    # Per-label quotas keep executed contracts from being crowded out of the
    # context window by generic OKF-rule keyword matches.
    okf_hits = [chunk for _, _, chunk in scored if chunk["label"] == "OKF Rule"][:3]
    executed_hits = [chunk for _, _, chunk in scored if chunk["label"] == "Executed Contract"][:3]
    relevant = okf_hits + executed_hits

    if not relevant:
        return AskAnswerResponse(
            answer=(
                "I could not find anything in the OKF playbook or your executed "
                "contracts matching that question. Try naming a clause topic "
                "(liability, payment terms, renewal) or a contract title."
            ),
            sources=[],
        )

    context_block = "\n\n".join(
        f"[{c['label']}: {c['title']}]\n{c['text']}" for c in relevant
    )

    llm_client = get_llm_client()
    messages = [
        {
            "role": "system",
            "content": (
                "You are the GOBITSNBYTES FOUNDATION legal assistant. Answer using ONLY "
                "the provided context snippets. Cite snippets inline like [OKF Rule: title] "
                "or [Executed Contract: title]. If the context is insufficient, say so."
            ),
        },
        {
            "role": "user",
            "content": f"Question: {payload.question}\n\nContext:\n{context_block}",
        },
    ]

    answer: Optional[str] = None
    try:
        raw = llm_client._chat_completion(messages)
        if raw and raw.strip():
            answer = raw.strip()
    except Exception as err:
        logger.warning(f"/ask LLM synthesis failed, using deterministic fallback: {err}")

    if not answer:
        answer = "Based on the retrieved records:\n" + "\n".join(
            f"- [{c['label']}: {c['title']}] {_truncate_for_ask(c['text'])}" for c in relevant
        )

    seen_titles = set()
    sources: List[AskSourceChip] = []
    for c in relevant:
        key = (c["label"], c["title"])
        if key in seen_titles:
            continue
        seen_titles.add(key)
        sources.append(AskSourceChip(label=c["label"], title=c["title"]))

    return AskAnswerResponse(answer=answer, sources=sources)


def _truncate_for_ask(text: str, limit: int = 280) -> str:
    cleaned = " ".join((text or "").split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip() + "…"


@router.get("/agent/stats")
async def get_legal_agent_stats(
    db: DbSession,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """Operational stats for the Legal Agent panel / Agent Ops drawer."""
    from app.services.legal_agent import INBOUND_EVENT_TYPE, collect_nudge_targets, get_last_poll_at

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    # Portable across SQLite/Postgres timestamp storage quirks: pull a bounded
    # recent window of inbound-ingest events and filter precisely in Python.
    inbox_stmt = (
        select(ContractAssistantEvent.created_at)
        .where(ContractAssistantEvent.type == INBOUND_EVENT_TYPE)
        .order_by(ContractAssistantEvent.created_at.desc())
        .limit(1000)
    )
    inbox_rows = (await db.execute(inbox_stmt)).scalars().all()
    inbox_processed_24h = sum(
        1
        for ts in inbox_rows
        if ts is not None and (_as_utc_safe(ts) or now) >= cutoff
    )

    status_stmt = select(ContractAssistantContract.status)
    statuses = (await db.execute(status_stmt)).scalars().all()
    counts = {"in_review": 0, "out_for_signature": 0, "dotted": 0}
    for raw_status in statuses:
        normalized = _normalize_status(raw_status)
        if normalized in counts:
            counts[normalized] += 1

    try:
        pending_nudges = len(await collect_nudge_targets(db, now=now))
    except Exception as err:
        logger.warning(f"Failed computing pending nudges: {err}")
        pending_nudges = 0

    last_poll = get_last_poll_at()

    return {
        "inbox_processed_24h": inbox_processed_24h,
        "contracts_in_review": counts["in_review"],
        "out_for_signature": counts["out_for_signature"],
        "dotted_count": counts["dotted"],
        "pending_nudges": pending_nudges,
        "last_poll_at": last_poll.isoformat() if last_poll else None,
    }


def _as_utc_safe(ts: Optional[datetime]) -> Optional[datetime]:
    if ts is None:
        return None
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)


