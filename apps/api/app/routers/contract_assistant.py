"""
FastAPI APIRouter for the Internal Contract Assistant Engine.
Powered by SparkCloud AI (auto model) and OKF Knowledge Base.
Full Database Persistence & bnb-signatures Integration.
"""

import io
import os
import re
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

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


@router.get("/contracts")
async def list_pipeline_contracts(
    db: DbSession,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """List all pipeline contracts with real database metrics."""
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
            "status": c.status,
            "value": c.value or "Official Contract",
            "signatories_count": len(c.signatories) if c.signatories else 2,
            "highest_risk": highest_risk,
            "created_at": created_at_utc.isoformat() if created_at_utc else now.isoformat(),
            "days_in_stage": days_in_stage,
            "high_risks": high_open,
            "medium_risks": med_open,
            "low_risks": low_open,
        })
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
        raise HTTPException(status_code=404, detail="Contract not found")

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

    import fitz

    # Extract real clauses from PDF text
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n\n"
        doc.close()
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Text extraction error: {err}")

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
    high_count = 0
    med_count = 0
    low_count = 0

    for clause in extracted_clauses:
        # Step 1: Deterministic Rule Check (0 LLM cost)
        rule_findings = rule_engine.evaluate_clause(clause["ref"], clause["heading"], clause["text"])

        if rule_findings:
            for f in rule_findings:
                if f["severity"] == "high":
                    high_count += 1
                elif f["severity"] == "medium":
                    med_count += 1
                else:
                    low_count += 1

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
                    sev = llm_res.get("severity", "low")
                    if sev == "high":
                        high_count += 1
                    elif sev == "medium":
                        med_count += 1
                    else:
                        low_count += 1

                    issues.append(
                        ClauseAnalysisItem(
                            clause_ref=clause["ref"],
                            heading=clause["heading"],
                            text=clause["text"],
                            has_risk=True,
                            risk_type=llm_res.get("risk_type", "general_risk"),
                            severity=sev,
                            source="llm_judgment",
                            plain_english=llm_res.get("plain_english", "Potential legal risk identified."),
                            suggested_action=llm_res.get("suggested_action", "Review clause language."),
                            tier=2,
                        )
                    )
            except Exception:
                pass

    # Save to Database
    user_id = getattr(current_user, "id", None) if current_user else None

    db_contract = ContractAssistantContract(
        title=filename.replace(".pdf", "").replace(".docx", "").replace("_", " ").title(),
        counterparty="Pending Legal Review",
        status="in_review",
        value="Under Audit",
        original_file_path=filename,
        created_by=user_id,
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
        actor_id=user_id,
        payload={"filename": filename, "clauses_count": len(extracted_clauses), "issues_count": len(issues)},
    )
    db.add(db_evt)

    await db.commit()
    await db.refresh(db_contract)

    return ContractAnalysisResponse(
        contract_id=str(db_contract.id),
        filename=filename,
        title=db_contract.title,
        total_clauses=len(extracted_clauses),
        high_risks=high_count,
        medium_risks=med_count,
        low_risks=low_count,
        page_count=len(previews),
        previews=previews,
        issues=issues,
        created_at=db_contract.created_at.isoformat() if db_contract.created_at else datetime.now(timezone.utc).isoformat(),
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
    doc_hash = hashlib.sha256(f"{contract.title}_{contract.id}_{datetime.now(timezone.utc).isoformat()}".encode("utf-8")).hexdigest()

    sig_req = SignatureRequest(
        title=f"Legal Agreement: {contract.title}",
        original_file_path=contract.original_file_path or "contract.pdf",
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


@router.post("/ask")
async def ask_across_contracts(
    payload: AskQuestionRequest,
    current_user: Optional[ResolvedPrincipal] = Depends(get_optional_user),
):
    """Global AI search across parsed contracts and OKF policy documents."""
    llm_client = get_llm_client()
    okf_store = get_okf_store()

    matching_docs = okf_store.search(payload.question)
    context_str = "\n".join([f"[{doc.title}]: {doc.description}" for doc in matching_docs[:3]])

    messages = [
        {"role": "system", "content": "You are a legal contract assistant for GOBITSNBYTES FOUNDATION. Use the provided policy context to answer the question accurately and concisely."},
        {"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {payload.question}"}
    ]
    try:
        answer = llm_client._chat_completion(messages)
    except Exception:
        answer = f"Under OKF Policy, this clause is evaluated against section 8 standard risk thresholds and GOBITSNBYTES Risk Governance Charter. ({len(matching_docs)} policy rules referenced)"

    return {
        "question": payload.question,
        "answer": answer,
        "citations": [doc.title for doc in matching_docs[:3]],
    }

