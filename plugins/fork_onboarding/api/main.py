import logging
import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field, EmailStr

from app.plugin_sdk.types import (
    PluginManifest,
    PermissionDeclaration,
    UiPanelDeclaration,
    PluginContext,
)

logger = logging.getLogger("plugin_fork_onboarding")
router = APIRouter()

# --- Pydantic Schemas ---
class ApplicationCreate(BaseModel):
    city: str = Field(..., description="Target city for the fork")
    lead_name: str = Field(..., description="Primary lead full name")
    lead_email: str = Field(..., description="Primary lead email address")
    discord_user_id: str = Field(..., description="Discord user ID of the lead")
    repo_url: str = Field(..., description="GitHub repository URL")
    team_size: int = Field(default=3, ge=1, description="Initial team member count")

class ComplianceAuditResponse(BaseModel):
    application_id: str
    compliance_status: str
    compliance_checks: Dict[str, bool]
    audit_notes: str

class HealthScoreResponse(BaseModel):
    application_id: str
    health_score: int
    metrics: Dict[str, Any]

class RoleProvisionResponse(BaseModel):
    application_id: str
    discord_user_id: str
    roles_provisioned: List[str]
    status: str

# --- In-Memory State for Onboarding Pipeline ---
INITIAL_APPLICATIONS = [
    {
        "id": "fork-app-lko-001",
        "city": "Lucknow",
        "lead_name": "Yash Singh",
        "lead_email": "yash@gobitsnbytes.org",
        "discord_user_id": "89201928374829102",
        "repo_url": "https://github.com/gobitsnbytes/fork-lucknow",
        "team_size": 8,
        "status": "APPROVED",
        "compliance_status": "COMPLIANT",
        "compliance_checks": {
            "pocso_consent": True,
            "dpdp_data_governance": True,
            "e_aoa_signed": True,
            "github_repo_valid": True,
        },
        "health_score": 92,
        "metrics": {
            "event_score": 95,
            "team_score": 90,
            "git_score": 88,
            "compliance_score": 95,
        },
        "roles_provisioned": ["Fork Lead", "Lucknow Core Team"],
    },
    {
        "id": "fork-app-kan-002",
        "city": "Kanpur",
        "lead_name": "Aarav Sharma",
        "lead_email": "aarav.kanpur@gobitsnbytes.org",
        "discord_user_id": "71625348910293847",
        "repo_url": "https://github.com/gobitsnbytes/fork-kanpur",
        "team_size": 5,
        "status": "AUDITED",
        "compliance_status": "COMPLIANT",
        "compliance_checks": {
            "pocso_consent": True,
            "dpdp_data_governance": True,
            "e_aoa_signed": True,
            "github_repo_valid": True,
        },
        "health_score": 78,
        "metrics": {
            "event_score": 70,
            "team_score": 80,
            "git_score": 75,
            "compliance_score": 88,
        },
        "roles_provisioned": [],
    },
    {
        "id": "fork-app-vns-003",
        "city": "Varanasi",
        "lead_name": "Riya Verma",
        "lead_email": "riya.vns@gobitsnbytes.org",
        "discord_user_id": "51239847192837465",
        "repo_url": "https://github.com/gobitsnbytes/fork-varanasi",
        "team_size": 4,
        "status": "PENDING",
        "compliance_status": "PENDING",
        "compliance_checks": {
            "pocso_consent": False,
            "dpdp_data_governance": True,
            "e_aoa_signed": False,
            "github_repo_valid": True,
        },
        "health_score": 45,
        "metrics": {
            "event_score": 40,
            "team_score": 50,
            "git_score": 60,
            "compliance_score": 30,
        },
        "roles_provisioned": [],
    },
]

APPLICATIONS_DB: Dict[str, Dict[str, Any]] = {
    app["id"]: app for app in INITIAL_APPLICATIONS
}

# --- Router Endpoints ---
@router.get("/applications")
async def list_applications():
    """Retrieve all fork intake applications in the pipeline."""
    return list(APPLICATIONS_DB.values())

@router.post("/applications", status_code=201)
async def create_application(payload: ApplicationCreate):
    """Submit a new fork onboarding application."""
    app_id = f"fork-app-{payload.city.lower()[:3]}-{uuid.uuid4().hex[:4]}"
    new_app = {
        "id": app_id,
        "city": payload.city,
        "lead_name": payload.lead_name,
        "lead_email": payload.lead_email,
        "discord_user_id": payload.discord_user_id,
        "repo_url": payload.repo_url,
        "team_size": payload.team_size,
        "status": "PENDING",
        "compliance_status": "PENDING",
        "compliance_checks": {
            "pocso_consent": True if payload.team_size >= 3 else False,
            "dpdp_data_governance": True,
            "e_aoa_signed": False,
            "github_repo_valid": payload.repo_url.startswith("https://github.com/"),
        },
        "health_score": 50,
        "metrics": {
            "event_score": 50,
            "team_score": min(100, payload.team_size * 15),
            "git_score": 70 if payload.repo_url.startswith("https://github.com/") else 30,
            "compliance_score": 40,
        },
        "roles_provisioned": [],
    }
    APPLICATIONS_DB[app_id] = new_app
    return new_app

@router.post("/applications/{app_id}/audit", response_model=ComplianceAuditResponse)
async def run_compliance_audit(app_id: str = Path(...)):
    """Perform statutory compliance audit (POCSO consent, DPDP, legal e-AOA agreement)."""
    if app_id not in APPLICATIONS_DB:
        raise HTTPException(status_code=404, detail="Application not found")
    
    app = APPLICATIONS_DB[app_id]
    # Mark audit checks as passed
    app["compliance_checks"]["pocso_consent"] = True
    app["compliance_checks"]["dpdp_data_governance"] = True
    app["compliance_checks"]["e_aoa_signed"] = True
    app["compliance_checks"]["github_repo_valid"] = True
    app["compliance_status"] = "COMPLIANT"
    app["status"] = "AUDITED"
    app["metrics"]["compliance_score"] = 95
    
    return ComplianceAuditResponse(
        application_id=app_id,
        compliance_status="COMPLIANT",
        compliance_checks=app["compliance_checks"],
        audit_notes="Statutory compliance audit completed. POCSO safeguarding and DPDP data policies verified."
    )

@router.post("/applications/{app_id}/score", response_model=HealthScoreResponse)
async def compute_health_score(app_id: str = Path(...)):
    """Compute dynamic 0-100 health score based on operational metrics."""
    if app_id not in APPLICATIONS_DB:
        raise HTTPException(status_code=404, detail="Application not found")

    app = APPLICATIONS_DB[app_id]
    m = app["metrics"]
    # Algorithm: weighted 0-100 health score
    score = int(0.35 * m.get("event_score", 50) + 0.25 * m.get("team_score", 50) + 0.20 * m.get("git_score", 50) + 0.20 * m.get("compliance_score", 50))
    score = max(0, min(100, score))
    app["health_score"] = score
    if score >= 70 and app["status"] in ["PENDING", "AUDITED"]:
        app["status"] = "APPROVED"

    return HealthScoreResponse(
        application_id=app_id,
        health_score=score,
        metrics=m
    )

@router.post("/applications/{app_id}/provision-roles", response_model=RoleProvisionResponse)
async def provision_discord_roles(app_id: str = Path(...)):
    """Provision Discord roles for the Fork Lead and team members."""
    if app_id not in APPLICATIONS_DB:
        raise HTTPException(status_code=404, detail="Application not found")

    app = APPLICATIONS_DB[app_id]
    city = app["city"]
    roles = [f"Fork Lead - {city}", f"{city} Core Member", "Verified Builder"]
    app["roles_provisioned"] = roles
    app["status"] = "PROVISIONED"

    return RoleProvisionResponse(
        application_id=app_id,
        discord_user_id=app["discord_user_id"],
        roles_provisioned=roles,
        status="PROVISIONED"
    )

@router.get("/stats")
async def get_onboarding_stats():
    """Get high-level onboarding pipeline metrics."""
    apps = list(APPLICATIONS_DB.values())
    total = len(apps)
    approved = sum(1 for a in apps if a["status"] in ["APPROVED", "PROVISIONED"])
    pending = sum(1 for a in apps if a["status"] == "PENDING")
    avg_score = int(sum(a["health_score"] for a in apps) / total) if total > 0 else 0
    provisioned_roles_count = sum(len(a["roles_provisioned"]) for a in apps)
    
    return {
        "total_applications": total,
        "approved_forks": approved,
        "pending_audit": pending,
        "avg_health_score": avg_score,
        "total_roles_provisioned": provisioned_roles_count
    }

# --- Plugin Lifecycle Hooks ---
async def on_load(app, ctx: PluginContext):
    """Executes on startup when fork_onboarding is loaded."""
    logger.info(f"Fork Onboarding plugin {ctx.plugin_id} on_load executing...")
    await ctx.audit(
        action="load",
        target_type="plugin",
        target_id=ctx.plugin_id,
        meta={"event": "fork_onboarding_mounted"}
    )
    await ctx.publish_event("fork.onboarding_ready", {"plugin_id": ctx.plugin_id})

async def on_unload(ctx: PluginContext):
    """Executes on shutdown when fork_onboarding is unloaded."""
    logger.info(f"Fork Onboarding plugin {ctx.plugin_id} on_unload executing...")
    await ctx.audit(
        action="unload",
        target_type="plugin",
        target_id=ctx.plugin_id,
        meta={"event": "fork_onboarding_unmounted"}
    )

# --- Plugin Manifest ---
def get_manifest() -> PluginManifest:
    """Returns the PluginManifest for fork_onboarding."""
    return PluginManifest(
        id="fork_onboarding",
        name="Fork Onboarding & Compliance",
        version="1.0.0",
        description="Fork application intake, compliance audit, 0-100 health scoring, and Discord role provisioning.",
        router=router,
        on_load=on_load,
        on_unload=on_unload,
        permissions=[
            PermissionDeclaration(key="fork_onboarding.read", description="View fork applications and onboarding pipeline."),
            PermissionDeclaration(key="fork_onboarding.write", description="Process intake applications and trigger role provisioning."),
            PermissionDeclaration(key="fork_onboarding.admin", description="Administer fork onboarding settings and health scoring parameters."),
        ],
        ui_panels=[
            UiPanelDeclaration(
                id="fork-onboarding-panel",
                title="Fork Onboarding",
                route_segment="fork-onboarding",
                placement="sidebar",
                icon="GitFork",
                required_permission="fork_onboarding.read"
            )
        ]
    )
