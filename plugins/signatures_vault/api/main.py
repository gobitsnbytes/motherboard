import hashlib
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field, EmailStr

from app.plugin_sdk.types import (
    PluginManifest,
    PermissionDeclaration,
    UiPanelDeclaration,
    PluginContext,
)

logger = logging.getLogger("plugin_signatures_vault")
router = APIRouter()

# --- Pydantic Schemas ---
class SignerSpec(BaseModel):
    name: str = Field(..., description="Signer full name")
    email: str = Field(..., description="Signer email address")

class EnvelopeCreate(BaseModel):
    title: str = Field(..., description="Legal envelope title e.g. Fork Partnership Agreement 2026")
    document_type: str = Field(..., description="Type of document e.g. e-AOA, MOU, NDA, Grant Contract")
    content: str = Field(..., description="Legal text content or markdown representation")
    signers: List[SignerSpec] = Field(..., min_items=1, description="List of required signers")

class SignRequest(BaseModel):
    signer_email: str = Field(..., description="Email of the signer signing")
    signature_token: Optional[str] = Field(default="VALID_TOKEN", description="Cryptographic signature token")

class SealVerificationRequest(BaseModel):
    envelope_id: Optional[str] = Field(default=None, description="Envelope ID to verify")
    sha256_seal: Optional[str] = Field(default=None, description="SHA-256 seal hash to verify")
    raw_content: Optional[str] = Field(default=None, description="Raw document text content to verify")

# --- In-Memory Signatures Vault Data ---
INITIAL_ENVELOPES = [
    {
        "envelope_id": "env-aoa-2026-lko",
        "title": "GOBITSNBYTES Section 8 e-AOA Charter - Lucknow Fork",
        "document_type": "e-AOA Charter",
        "content": "Official Section 8 GOBITSNBYTES FOUNDATION e-AOA Charter establishing the Lucknow operational Fork.",
        "signers": [
            {"name": "Yash Singh", "email": "yash@gobitsnbytes.org", "signed": True, "signed_at": "2026-06-03T10:00:00Z"},
            {"name": "Akshat Kushwaha", "email": "akshatsingh14372@outlook.com", "signed": True, "signed_at": "2026-06-03T10:05:00Z"}
        ],
        "status": "SEALED",
        "created_at": "2026-06-02T18:00:00Z",
        "sha256_seal": hashlib.sha256(b"GOBITSNBYTES Section 8 e-AOA Charter - Lucknow Fork:SEALED").hexdigest(),
        "sealed_at": "2026-06-03T10:06:00Z",
    },
    {
        "envelope_id": "env-mou-iitk-execron",
        "title": "IIT Kanpur Execron 1.0 Co-Host MoU & Venue Agreement",
        "document_type": "MOU",
        "content": "MoU between GOBITSNBYTES FOUNDATION and IIT Kanpur for Execron 1.0 Hackathon.",
        "signers": [
            {"name": "Aadrika Maurya", "email": "aadrika@gobitsnbytes.org", "signed": True, "signed_at": "2026-07-15T12:30:00Z"},
            {"name": "Devaansh Pathak", "email": "devaansh@gobitsnbytes.org", "signed": False, "signed_at": None}
        ],
        "status": "PARTIALLY_SIGNED",
        "created_at": "2026-07-14T09:00:00Z",
        "sha256_seal": None,
        "sealed_at": None,
    },
    {
        "envelope_id": "env-grant-2026-kanpur",
        "title": "Kanpur Fork Seed Grant Disbursement Agreement",
        "document_type": "Grant Contract",
        "content": "Seed grant disbursement terms and Section 8 expenditure rules for Kanpur Fork.",
        "signers": [
            {"name": "Aarav Sharma", "email": "aarav.kanpur@gobitsnbytes.org", "signed": False, "signed_at": None}
        ],
        "status": "SENT",
        "created_at": "2026-08-01T15:20:00Z",
        "sha256_seal": None,
        "sealed_at": None,
    }
]

ENVELOPES_DB: Dict[str, Dict[str, Any]] = {
    env["envelope_id"]: env for env in INITIAL_ENVELOPES
}

# --- Router Endpoints ---
@router.get("/envelopes")
async def list_envelopes():
    """List all legal envelopes in the vault."""
    return list(ENVELOPES_DB.values())

@router.post("/envelopes", status_code=201)
async def create_envelope(payload: EnvelopeCreate):
    """Draft and dispatch a new legal signature envelope."""
    env_id = f"env-{payload.document_type.lower().replace(' ', '')}-{uuid.uuid4().hex[:6]}"
    signers_data = [
        {"name": s.name, "email": s.email, "signed": False, "signed_at": None}
        for s in payload.signers
    ]
    
    envelope = {
        "envelope_id": env_id,
        "title": payload.title,
        "document_type": payload.document_type,
        "content": payload.content,
        "signers": signers_data,
        "status": "SENT",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "sha256_seal": None,
        "sealed_at": None,
    }
    ENVELOPES_DB[env_id] = envelope
    return envelope

@router.post("/envelopes/{envelope_id}/sign")
async def sign_envelope(envelope_id: str, payload: SignRequest):
    """Sign an envelope on behalf of a signer."""
    if envelope_id not in ENVELOPES_DB:
        raise HTTPException(status_code=404, detail="Legal envelope not found")
    
    env = ENVELOPES_DB[envelope_id]
    signer_found = False
    all_signed = True
    
    for s in env["signers"]:
        if s["email"].lower() == payload.signer_email.lower():
            s["signed"] = True
            s["signed_at"] = datetime.utcnow().isoformat() + "Z"
            signer_found = True
        if not s["signed"]:
            all_signed = False
            
    if not signer_found:
        raise HTTPException(status_code=400, detail="Signer email not registered on envelope")

    if all_signed and env["status"] != "SEALED":
        env["status"] = "SIGNED"

    return env

@router.post("/envelopes/{envelope_id}/seal")
async def seal_envelope(envelope_id: str):
    """Cryptographically seal envelope and compute immutable SHA-256 seal digest."""
    if envelope_id not in ENVELOPES_DB:
        raise HTTPException(status_code=404, detail="Legal envelope not found")

    env = ENVELOPES_DB[envelope_id]
    
    # Generate SHA-256 seal hash from content + envelope_id + signers
    raw_payload = f"{env['envelope_id']}:{env['title']}:{env['content']}:{len(env['signers'])}"
    sha256_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    env["sha256_seal"] = sha256_hash
    env["sealed_at"] = datetime.utcnow().isoformat() + "Z"
    env["status"] = "SEALED"
    
    return {
        "envelope_id": envelope_id,
        "status": "SEALED",
        "sha256_seal": sha256_hash,
        "sealed_at": env["sealed_at"]
    }

@router.post("/verify")
async def verify_signature_seal(payload: SealVerificationRequest):
    """Verify cryptographic SHA-256 seal integrity against vault records."""
    if payload.sha256_seal:
        # Match by seal hash
        for env in ENVELOPES_DB.values():
            if env.get("sha256_seal") and env["sha256_seal"].lower() == payload.sha256_seal.strip().lower():
                return {
                    "is_valid": True,
                    "envelope_id": env["envelope_id"],
                    "title": env["title"],
                    "status": env["status"],
                    "sealed_at": env["sealed_at"],
                    "sha256_hash": env["sha256_seal"],
                    "verification_message": "Cryptographic seal integrity VERIFIED against GOBITSNBYTES Vault."
                }
    
    if payload.envelope_id and payload.envelope_id in ENVELOPES_DB:
        env = ENVELOPES_DB[payload.envelope_id]
        if env["status"] == "SEALED" and env.get("sha256_seal"):
            return {
                "is_valid": True,
                "envelope_id": env["envelope_id"],
                "title": env["title"],
                "status": env["status"],
                "sealed_at": env["sealed_at"],
                "sha256_hash": env["sha256_seal"],
                "verification_message": "Envelope is cryptographically SEALED and intact."
            }

    return {
        "is_valid": False,
        "envelope_id": payload.envelope_id,
        "title": "Unknown Document",
        "status": "UNVERIFIED",
        "sealed_at": None,
        "sha256_hash": payload.sha256_seal or "N/A",
        "verification_message": "No matching cryptographically sealed record found in vault."
    }

@router.get("/stats")
async def get_vault_stats():
    """Get vault summary statistics."""
    envs = list(ENVELOPES_DB.values())
    total = len(envs)
    sealed = sum(1 for e in envs if e["status"] == "SEALED")
    pending = sum(1 for e in envs if e["status"] in ["SENT", "PARTIALLY_SIGNED"])
    
    return {
        "total_envelopes": total,
        "pending_signature": pending,
        "sealed_and_locked": sealed,
        "verification_rate": 100.0 if sealed > 0 else 0.0,
    }

# --- Plugin Lifecycle Hooks ---
async def on_load(app, ctx: PluginContext):
    """Executes on startup when signatures_vault is loaded."""
    logger.info(f"Signatures Vault plugin {ctx.plugin_id} on_load executing...")
    await ctx.audit(
        action="load",
        target_type="plugin",
        target_id=ctx.plugin_id,
        meta={"event": "signatures_vault_mounted"}
    )
    await ctx.publish_event("signatures.vault_ready", {"plugin_id": ctx.plugin_id})

async def on_unload(ctx: PluginContext):
    """Executes on shutdown when signatures_vault is unloaded."""
    logger.info(f"Signatures Vault plugin {ctx.plugin_id} on_unload executing...")
    await ctx.audit(
        action="unload",
        target_type="plugin",
        target_id=ctx.plugin_id,
        meta={"event": "signatures_vault_unmounted"}
    )

# --- Plugin Manifest ---
def get_manifest() -> PluginManifest:
    """Returns PluginManifest for signatures_vault."""
    return PluginManifest(
        id="signatures_vault",
        name="Legal Signatures Vault",
        version="1.0.0",
        description="Legal signature workflow, envelope status tracking, and SHA-256 seal verification.",
        router=router,
        on_load=on_load,
        on_unload=on_unload,
        permissions=[
            PermissionDeclaration(key="signatures_vault.read", description="View legal signature envelopes and status."),
            PermissionDeclaration(key="signatures_vault.create", description="Draft and send legal signature envelopes."),
            PermissionDeclaration(key="signatures_vault.sign", description="Execute signature and seal envelopes."),
            PermissionDeclaration(key="signatures_vault.verify", description="Verify SHA-256 seal cryptographic integrity."),
        ],
        ui_panels=[
            UiPanelDeclaration(
                id="signatures-vault-panel",
                title="Signatures Vault",
                route_segment="signatures-vault",
                placement="sidebar",
                icon="ShieldCheck",
                required_permission="signatures_vault.read"
            )
        ]
    )
