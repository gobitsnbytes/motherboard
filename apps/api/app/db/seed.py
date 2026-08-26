"""
System configuration seeder for bnb-motherboard (bootstrap only).

Seeds contain NO operational data. Forks and team members are pulled live from
Notion (fork registry + team DB) at startup and via POST /api/sync/notion; user
identities arrive through Discord OAuth upserts. This module provides:

1. System Groups and Discord Role Mappings
2. Core permission registry
3. Section 8 Chart of Accounts structure with ZERO balances
4. 35 OKF Legal Rules covering IP assignment, minor safeguarding (POCSO/DPDP),
   non-profit tax exemption, and local fundraising limits.
"""

import json
import logging
import os
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. System Groups
# ---------------------------------------------------------------------------

SYSTEM_GROUPS: list[dict[str, Any]] = [
    {
        "slug": "sg_super_admin",
        "name": "Super Admin",
        "description": "Full platform access. Bypasses all permission checks.",
        "is_system": True,
        "color_hex": "#f1c40f",
    },
    {
        "slug": "sg_executive",
        "name": "Executive Leadership",
        "description": "HQ & Executive team. Full access to all forks and data.",
        "is_system": True,
        "color_hex": "#97192c",
    },
    {
        "slug": "sg_department_lead",
        "name": "Department Lead",
        "description": "Global track leadership. Cross-fork read & write.",
        "is_system": True,
        "color_hex": "#fc920d",
    },
    {
        "slug": "sg_hq",
        "name": "HQ",
        "description": "Bits&Bytes Foundation core members.",
        "is_system": True,
        "color_hex": "#f1c40f",
    },
    {
        "slug": "sg_fork_lead",
        "name": "Fork Lead",
        "description": "City fork leaders. Full local access to their fork.",
        "is_system": True,
        "color_hex": "#7289da",
    },
    {
        "slug": "sg_tech_lead",
        "name": "Tech Lead",
        "description": "Local tech track lead. Modify tech activities in their fork.",
        "is_system": True,
        "color_hex": "#1f8b4c",
    },
    {
        "slug": "sg_creative_lead",
        "name": "Creative Lead",
        "description": "Local creative track lead.",
        "is_system": True,
        "color_hex": "#ad1457",
    },
    {
        "slug": "sg_ops_lead",
        "name": "Ops Lead",
        "description": "Local operations track lead.",
        "is_system": True,
        "color_hex": "#11806a",
    },
    {
        "slug": "sg_outreach_lead",
        "name": "Outreach Lead",
        "description": "Local outreach track lead.",
        "is_system": True,
        "color_hex": "#a84300",
    },
    {
        "slug": "sg_contributor",
        "name": "Contributor",
        "description": "Base contributor. Auto-granted to all onboarded members.",
        "is_system": True,
        "color_hex": "#00ff94",
    },
    {
        "slug": "sg_track_tech",
        "name": "Tech Track",
        "description": "Global tech track contributor. Cross-fork view access.",
        "is_system": True,
        "color_hex": "#3498db",
    },
    {
        "slug": "sg_track_creative",
        "name": "Creative Track",
        "description": "Global creative track contributor.",
        "is_system": True,
        "color_hex": "#eb459e",
    },
    {
        "slug": "sg_track_ops",
        "name": "Ops Track",
        "description": "Global ops track contributor.",
        "is_system": True,
        "color_hex": "#eb459e",
    },
    {
        "slug": "sg_track_outreach",
        "name": "Outreach Track",
        "description": "Global outreach track contributor.",
        "is_system": True,
        "color_hex": "#e67e22",
    },
    {
        "slug": "sg_member",
        "name": "Community Member",
        "description": "City community role holder. Public view access only.",
        "is_system": True,
        "color_hex": "#5865f2",
    },
]

# ---------------------------------------------------------------------------
# 2. Core Permissions
# ---------------------------------------------------------------------------

CORE_PERMISSIONS: list[dict[str, Any]] = [
    # IAM
    {"key": "iam.users.read", "description": "View user profiles and account details."},
    {"key": "iam.users.write", "description": "Create, update, and deactivate users."},
    {"key": "iam.groups.read", "description": "View groups and their members."},
    {"key": "iam.groups.write", "description": "Create, edit, and delete groups."},
    {"key": "iam.memberships.write", "description": "Add or remove users from groups."},
    {"key": "iam.permissions.read", "description": "View the permission registry."},
    {"key": "iam.permissions.write", "description": "Register and manage permissions."},
    {"key": "iam.grants.read", "description": "View permission grants."},
    {"key": "iam.grants.write", "description": "Create, update, and revoke grants."},
    {"key": "iam.delegations.write", "description": "Delegate permissions to other users."},
    {"key": "iam.role_mappings.read", "description": "View Discord role -> group mappings."},
    {"key": "iam.role_mappings.write", "description": "Manage Discord role -> group mappings."},
    # Forks
    {"key": "forks.read", "description": "View all city forks and their metadata."},
    {"key": "forks.write", "description": "Create, update, and archive forks."},
    {"key": "forks.members.read", "description": "View fork member lists."},
    {"key": "forks.members.write", "description": "Add, update, and remove fork members."},
    # Provisioning
    {"key": "provisioning.sync.trigger", "description": "Manually trigger a Discord member sync."},
    {"key": "provisioning.sync.read", "description": "View sync run history and status."},
    # Plugins
    {"key": "plugins.read", "description": "View the plugin registry."},
    {"key": "plugins.write", "description": "Install, enable, disable, and configure plugins."},
    # Audit
    {"key": "audit.read", "description": "Read the audit log."},
    {"key": "audit.export", "description": "Export the audit log."},
    # Admin
    {"key": "admin.settings.read", "description": "View platform-wide settings."},
    {"key": "admin.settings.write", "description": "Change platform-wide settings."},
    # Finance
    {"key": "finance.accounts.read", "description": "View all virtual accounts and their balances."},
    {"key": "finance.accounts.create", "description": "Create new virtual accounts and assign owners."},
    {"key": "finance.accounts.manage", "description": "Edit, deactivate, and adjust balances on virtual accounts."},
    {"key": "finance.cards.read", "description": "View virtual cards across all accounts."},
    {"key": "finance.cards.create", "description": "Issue virtual cards for an account."},
    {"key": "finance.cards.manage", "description": "Deactivate or edit any virtual card."},
    {"key": "finance.requests.read", "description": "View all money requests."},
    {"key": "finance.requests.create", "description": "Submit a money request from pool or another account."},
    {"key": "finance.requests.approve", "description": "Approve or reject pending money requests."},
    {"key": "finance.admin", "description": "Full finance admin access — supersedes all individual finance permissions."},
    # Meetings
    {"key": "meetings.read", "description": "View scheduled meetings, transcripts, and preferences."},
    {"key": "meetings.write", "description": "Schedule, reschedule, start, stop, and configure meetings."},
]

# ---------------------------------------------------------------------------
# 3. Discord Role Mappings
# ---------------------------------------------------------------------------

DISCORD_ROLE_MAPPINGS: list[tuple[str, str, str, bool, int]] = [
    ("1480620981587279993", "admin", "sg_super_admin", True, 0),
    ("1506019032015310949", "Executive Leadership", "sg_executive", True, 0),
    ("1506323726223016149", "Department Leads", "sg_department_lead", True, 0),
    ("1509256369994203146", "hq", "sg_hq", True, 0),
    ("1509224755595841676", "tech-lead", "sg_tech_lead", True, 1),
    ("1509224757579616276", "creative-lead", "sg_creative_lead", True, 1),
    ("1509224760293195927", "ops-lead", "sg_ops_lead", True, 1),
    ("1509224762906247178", "outreach-lead", "sg_outreach_lead", True, 1),
    ("1490410901147488286", "fork-lead", "sg_fork_lead", True, 2),
    ("1506019068132462804", "Contributor", "sg_contributor", True, 3),
    ("1509224750663073865", "tech", "sg_track_tech", True, 4),
    ("1490412912420847646", "creative", "sg_track_creative", True, 4),
    ("1490413018830471332", "ops", "sg_track_ops", True, 4),
    ("1509224752747909351", "outreach", "sg_track_outreach", True, 4),
    ("1480624226414366924", "Builder", "sg_contributor", True, 5),
    ("1506019099999999999", "Community Member", "sg_member", True, 6),
]

# ---------------------------------------------------------------------------
CHART_OF_ACCOUNTS: list[dict[str, Any]] = [
    {
        "name": "Grant Revenue",
        "description": "Section 8 institutional and government grant receipts account.",
        "account_number": "GOBN-8001-GRANT",
        "balance_paise": 0,  # zero-start: real balances accrue only from recorded operations
        "ifsc": "GOBN0001001",
    },
    {
        "name": "Event Operations",
        "description": "Hackathons, meetups, workshops and regional event operations account.",
        "account_number": "GOBN-8002-EVNT",
        "balance_paise": 0,
        "ifsc": "GOBN0001001",
    },
    {
        "name": "Dev Squad Grants",
        "description": "Micro-grants and stipend pool for student dev squads and open source contributors.",
        "account_number": "GOBN-8003-DSQD",
        "balance_paise": 0,
        "ifsc": "GOBN0001001",
    },
    {
        "name": "Administrative Overhead",
        "description": "Legal, accounting, compliance, software SaaS infrastructure and operational overhead.",
        "account_number": "GOBN-8004-ADMIN",
        "balance_paise": 0,
        "ifsc": "GOBN0001001",
    },
    {
        "name": "Reserve Account",
        "description": "Section 8 non-profit capital reserve and emergency liquidity account.",
        "account_number": "GOBN-8005-RESERV",
        "balance_paise": 0,
        "ifsc": "GOBN0001001",
    },
]

# ---------------------------------------------------------------------------
# 7. 35 OKF Legal Rules Definitions
# ---------------------------------------------------------------------------

OKF_LEGAL_RULES: list[dict[str, Any]] = [
    # IP Assignment (1-8)
    {
        "file_name": "okf-rule-01-ip-assignment-foundational.md",
        "title": "Foundational IP Assignment Policy",
        "description": "All software, documentation, and technical assets created by team members or dev squads are assigned to GOBITSNBYTES FOUNDATION.",
        "tags": ["legal", "ip", "assignment", "policy"],
        "content": "All code, documentation, designs, and intellectual property developed by members or contributors during Foundation activities shall vest exclusively with GOBITSNBYTES FOUNDATION.",
    },
    {
        "file_name": "okf-rule-02-ip-licensing-open-source.md",
        "title": "Open Source Code Licensing Standard",
        "description": "Public repositories and dev squad outputs must be licensed under MIT or Apache 2.0 held by the Foundation.",
        "tags": ["legal", "ip", "license", "open-source"],
        "content": "All open source projects released under bits&bytes branding must utilize approved OSI licenses (MIT/Apache 2.0) with GOBITSNBYTES FOUNDATION as copyright holder.",
    },
    {
        "file_name": "okf-rule-03-ip-trademark-protection.md",
        "title": "Trademark & Brand Assets Protection Rule",
        "description": "bits&bytes™ wordmark, isometric B-cube logo, and associated visual kit are registered trademarks.",
        "tags": ["legal", "ip", "trademark", "branding"],
        "content": "The bits&bytes wordmark and isometric cube logo are legally protected trademarks. Unauthorized commercial usage or modification is strictly prohibited.",
    },
    {
        "file_name": "okf-rule-04-ip-contributor-license-agreement.md",
        "title": "Contributor License Agreement (CLA) Requirement",
        "description": "External contributors must sign the OKF CLA before code merges into core repositories.",
        "tags": ["legal", "ip", "cla", "contributor"],
        "content": "PR authors and external code contributors must execute the bits&bytes Contributor License Agreement to grant non-exclusive operational rights.",
    },
    {
        "file_name": "okf-rule-05-ip-fork-branding-limits.md",
        "title": "City Fork Brand Licensing Boundaries",
        "description": "Local city forks hold a conditional non-exclusive brand license strictly for non-profit student events.",
        "tags": ["legal", "ip", "fork", "branding"],
        "content": "Recognized City Forks receive a revocable, non-transferable license to use bits&bytes branding solely for sanctioned community hackathons and workshops.",
    },
    {
        "file_name": "okf-rule-06-ip-moral-rights-attribution.md",
        "title": "Student Author Moral Rights & Attribution",
        "description": "Student creators retain moral credit while legal copyright resides with the Foundation.",
        "tags": ["legal", "ip", "attribution", "moral-rights"],
        "content": "The Foundation preserves creator attribution rights across showcase sites while retaining institutional copyright ownership.",
    },
    {
        "file_name": "okf-rule-07-ip-commercial-exploitation-ban.md",
        "title": "Prohibition of Unapproved Commercialization",
        "description": "No team member or fork lead may commercialize Foundation IP without Board written consent.",
        "tags": ["legal", "ip", "commercial", "governance"],
        "content": "Commercial exploitation, sublicensing, or sale of bits&bytes proprietary technology or branding without Board resolution is illegal.",
    },
    {
        "file_name": "okf-rule-08-ip-derivative-works.md",
        "title": "Derivative Work Rights & Assignment",
        "description": "Proprietary software extensions built on Foundation infra belong to GOBITSNBYTES FOUNDATION.",
        "tags": ["legal", "ip", "derivative", "ownership"],
        "content": "Any derivative software modules, internal tools, or bots created for network operations remain sole property of GOBITSNBYTES FOUNDATION.",
    },
    # Minor Safeguarding (9-16)
    {
        "file_name": "okf-rule-09-safeguarding-pocso-compliance.md",
        "title": "POCSO Act Mandatory Safeguarding Policy",
        "description": "Zero-tolerance safeguarding policy strictly complying with POCSO Act 2012 for all minor participants.",
        "tags": ["legal", "safeguarding", "pocso", "minors"],
        "content": "All Foundation events and Discord interactions strictly enforce zero tolerance for harm or exploitation, adhering to the Protection of Children from Sexual Offences (POCSO) Act 2012.",
    },
    {
        "file_name": "okf-rule-10-safeguarding-dpdp-parental-consent.md",
        "title": "DPDP Act Verified Parental Consent Rule",
        "description": "Mandatory parental consent for minor data processing under DPDP Act 2023.",
        "tags": ["legal", "safeguarding", "dpdp", "privacy"],
        "content": "Processing personal data of participants under 18 years requires verifiable consent from parent or lawful guardian as mandated by Digital Personal Data Protection (DPDP) Act 2023.",
    },
    {
        "file_name": "okf-rule-11-safeguarding-background-checks.md",
        "title": "Adult Mentor & Staff Vetting Mandate",
        "description": "Adult organizers, mentors, and judges interacting with student builders must be background-checked.",
        "tags": ["legal", "safeguarding", "vetting", "mentors"],
        "content": "All adult volunteers, mentors, and event staff must complete identity verification and safeguarding orientation before accessing minor spaces.",
    },
    {
        "file_name": "okf-rule-12-safeguarding-two-adult-rule.md",
        "title": "Dual Adult Supervision Rule in All Sessions",
        "description": "Online workshops and in-person hack nights require at least two vetted adult supervisors present.",
        "tags": ["legal", "safeguarding", "supervision", "safety"],
        "content": "No single adult organizer may engage in 1-on-1 isolated physical or private online sessions with minor participants; dual adult presence is mandatory.",
    },
    {
        "file_name": "okf-rule-13-safeguarding-photo-consent.md",
        "title": "Minor Media Release & Photography Consent",
        "description": "Parental signed release form required for taking or publishing photographs of minors.",
        "tags": ["legal", "safeguarding", "media", "consent"],
        "content": "Event media coverage featuring minor attendees requires prior written parental release forms explicitly authorizing photography and video recording.",
    },
    {
        "file_name": "okf-rule-14-safeguarding-incident-reporting.md",
        "title": "24-Hour Mandatory Incident Escalation Protocol",
        "description": "Immediate 24-hour reporting path to the Board Safeguarding Lead for any safety concern.",
        "tags": ["legal", "safeguarding", "incident", "escalation"],
        "content": "Any reported safety violation or harassment involving minors must be escalated to the Board Safeguarding Officer within 24 hours.",
    },
    {
        "file_name": "okf-rule-15-safeguarding-curfew-overnight-ban.md",
        "title": "Overnight Hackathon Minor Safety & Curfew Policy",
        "description": "Strict curfew, separate minor resting zones, and parental chaperones required for overnight hackathons.",
        "tags": ["legal", "safeguarding", "overnight", "events"],
        "content": "24-hour hackathons hosting minors must enforce physical perimeter security, gender-segregated resting areas, and designated minor chaperones.",
    },
    {
        "file_name": "okf-rule-16-safeguarding-data-minimization.md",
        "title": "Minor Personal Data Minimization & Retention",
        "description": "Minor participant PII must be encrypted, access-restricted, and purged post-event.",
        "tags": ["legal", "safeguarding", "data", "retention"],
        "content": "PII collected from minor registrants is restricted to operational necessity, encrypted at rest, and purged 90 days post-event completion.",
    },
    # Non-Profit Tax Exemption & Statutory Compliance (17-23)
    {
        "file_name": "okf-rule-17-tax-section8-nonprofit-status.md",
        "title": "Section 8 Non-Profit Corporate Governance Status",
        "description": "GOBITSNBYTES FOUNDATION is incorporated under Section 8 of the Companies Act 2013.",
        "tags": ["legal", "tax", "section8", "governance"],
        "content": "GOBITSNBYTES FOUNDATION is a non-profit company registered under Section 8 of the Companies Act 2013, dedicated solely to technology education.",
    },
    {
        "file_name": "okf-rule-18-tax-12a-registration.md",
        "title": "Section 12A/12AB Income Tax Exemption Policy",
        "description": "Foundation income and grant revenues are tax-exempt under Section 12A of the Income Tax Act.",
        "tags": ["legal", "tax", "12a", "exemption"],
        "content": "All grant funding and educational contributions are exempt from income tax under Section 12A/12AB registration.",
    },
    {
        "file_name": "okf-rule-19-tax-80g-donor-deductions.md",
        "title": "Section 80G Donor Tax Deduction Exemption",
        "description": "Indian donors receive 50% income tax deduction benefits under Section 80G.",
        "tags": ["legal", "tax", "80g", "donations"],
        "content": "Official donation receipts issued by the Foundation include Section 80G registration credentials for donor tax deductibility.",
    },
    {
        "file_name": "okf-rule-20-tax-no-profit-distribution.md",
        "title": "Non-Distribution Constraint of Surplus Funds",
        "description": "Zero profit distribution to directors, members, or officers; 100% reinvestment into mission.",
        "tags": ["legal", "tax", "nonprofit", "compliance"],
        "content": "No income, surplus, or asset of the Foundation shall be paid or transferred by way of dividend or bonus to any director or officer.",
    },
    {
        "file_name": "okf-rule-21-tax-fcra-foreign-funding-ban.md",
        "title": "FCRA Foreign Contribution Restriction Policy",
        "description": "Foreign currency donations prohibited without Ministry of Home Affairs FCRA approval.",
        "tags": ["legal", "tax", "fcra", "foreign-funding"],
        "content": "Direct receipt of foreign currency contributions is strictly prohibited pending formal FCRA registration with the Ministry of Home Affairs.",
    },
    {
        "file_name": "okf-rule-22-tax-gst-compliance.md",
        "title": "Statutory GST Educational Exemption Rule",
        "description": "Educational student hackathons and non-profit workshops operated under GST statutory limits.",
        "tags": ["legal", "tax", "gst", "compliance"],
        "content": "Student event activities operate within statutory non-profit GST threshold exemptions; commercial GST invoices require CFO sign-off.",
    },
    {
        "file_name": "okf-rule-23-tax-annual-mca-returns.md",
        "title": "Annual MCA Statutory Filings & Audit Compliance",
        "description": "Mandatory filing of AOC-4, MGT-7, and audited balance sheets with Registrar of Companies.",
        "tags": ["legal", "tax", "mca", "audit"],
        "content": "The CFO shall ensure annual financial statements, statutory audits, AOC-4, and MGT-7 filings are submitted to MCA before due dates.",
    },
    # Local Fundraising Limits & Financial Governance (24-30)
    {
        "file_name": "okf-rule-24-fundraising-local-city-cap.md",
        "title": "Local City Fork Sponsorship Authorization Cap",
        "description": "Local city forks cannot independently sign sponsorship deals exceeding ₹50,000.",
        "tags": ["legal", "fundraising", "fork", "limits"],
        "content": "City Forks may raise local event sponsorships up to ₹50,000 per event. Deals above ₹50,000 require HQ CFO approval.",
    },
    {
        "file_name": "okf-rule-25-fundraising-cash-prohibition.md",
        "title": "Absolute Ban on Physical Cash Transactions",
        "description": "All funds must flow directly to official Foundation bank accounts via UPI/NEFT; cash is strictly forbidden.",
        "tags": ["legal", "fundraising", "cash", "banking"],
        "content": "Collection of physical cash for registrations or sponsorships is forbidden. All receipts must route through official RazorpayX accounts.",
    },
    {
        "file_name": "okf-rule-26-fundraising-sponsor-deliverables.md",
        "title": "Sponsorship Agreement Legal Execution Policy",
        "description": "Sponsorship agreements must be signed by authorized corporate officers.",
        "tags": ["legal", "fundraising", "contracts", "signatures"],
        "content": "Sponsorship contracts and MOUs are legally valid only when executed by authorized Executive Officers or Board Signatories.",
    },
    {
        "file_name": "okf-rule-27-fundraising-grant-disbursement.md",
        "title": "Itemized Event Budget Disbursement Rule",
        "description": "Event budget advances disbursed against itemized receipts verified by CFO.",
        "tags": ["legal", "fundraising", "disbursement", "budget"],
        "content": "Event funds are released to City Leads in tranches based on approved itemized budgets and submitted vendor invoices.",
    },
    {
        "file_name": "okf-rule-28-fundraising-crypto-ban.md",
        "title": "Unregulated Cryptocurrency Funding Restrictions",
        "description": "Cryptocurrency and token donations restricted without prior legal compliance review.",
        "tags": ["legal", "fundraising", "crypto", "compliance"],
        "content": "Receipt of crypto assets or token grants requires prior legal review to ensure RBI and tax compliance.",
    },
    {
        "file_name": "okf-rule-29-fundraising-quid-pro-quo-limit.md",
        "title": "Corporate Sponsor Ethics & Data Privacy Rule",
        "description": "Sponsor perks restricted to branding/speaking; selling participant contact PII is illegal.",
        "tags": ["legal", "fundraising", "ethics", "privacy"],
        "content": "Sponsors receive logo placement, booths, and mentor access; selling or sharing participant personal contact data is prohibited.",
    },
    {
        "file_name": "okf-rule-30-fundraising-crowdfunding-escrow.md",
        "title": "Public Crowdfunding Campaign Escrow Mandate",
        "description": "Community crowdfunding campaigns must route funds directly into Foundation escrow.",
        "tags": ["legal", "fundraising", "crowdfunding", "escrow"],
        "content": "Community crowdfunding campaigns for squads or hackathons must use Foundation-managed verified escrow pages.",
    },
    # General Governance & Operational Policy (31-35)
    {
        "file_name": "okf-rule-31-liability-cap-ceiling.md",
        "title": "Contractual Liability Ceiling Policy",
        "description": "Liability in vendor or partner contracts strictly capped at contract value or ₹100,000.",
        "tags": ["legal", "governance", "liability", "policy"],
        "content": "All Foundation agreements must include a limitation of liability clause capping aggregate liability at fees paid or ₹100,000.",
    },
    {
        "file_name": "okf-rule-32-payment-terms-net30.md",
        "title": "Standard Vendor Payment Term (Net 30) Policy",
        "description": "Standard vendor payment terms are Net 30 days upon invoice receipt; Net 60+ requires CFO waiver.",
        "tags": ["legal", "governance", "payment", "policy"],
        "content": "Invoices are payable within Net 30 days upon delivery. Payment windows exceeding Net 45 days require written CFO approval.",
    },
    {
        "file_name": "okf-rule-33-jurisdiction-lucknow-court.md",
        "title": "Governing Law & Exclusive Lucknow Jurisdiction",
        "description": "All legal agreements are governed by laws of India subject to exclusive jurisdiction of Lucknow courts.",
        "tags": ["legal", "governance", "jurisdiction", "disputes"],
        "content": "All contracts entered into by the Foundation are governed by Indian law with exclusive jurisdiction in Lucknow, Uttar Pradesh.",
    },
    {
        "file_name": "okf-rule-34-auto-renewal-notice-window.md",
        "title": "Auto-Renewal Notice Window & Non-Renewal Terms",
        "description": "Auto-renewing vendor contracts require 30 days maximum cancellation notice.",
        "tags": ["legal", "governance", "renewal", "contracts"],
        "content": "Vendor agreements with automatic renewal must allow cancellation by written notice submitted at least 30 days prior to term end.",
    },
    {
        "file_name": "okf-rule-35-authority-matrix-signatory.md",
        "title": "Corporate Authority Matrix & Dual Signatory Rule",
        "description": "Financial commitments exceeding ₹100,000 require joint signature of CEO and CFO.",
        "tags": ["legal", "governance", "authority", "signatures"],
        "content": "Contracts, disbursements, or legal obligations exceeding ₹100,000 require dual signature of Chief Executive Officer and Chief Financial Officer.",
    },
]

# ---------------------------------------------------------------------------
# Seeding Functions
# ---------------------------------------------------------------------------

async def seed_system_groups(session: AsyncSession) -> None:
    """Insert system groups — idempotent on slug conflict."""
    for g in SYSTEM_GROUPS:
        await session.execute(
            text(
                """
                INSERT INTO groups (id, slug, name, description, is_system, color_hex)
                VALUES (:id, :slug, :name, :description, :is_system, :color_hex)
                ON CONFLICT (slug) DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "slug": g["slug"],
                "name": g["name"],
                "description": g.get("description"),
                "is_system": g.get("is_system", False),
                "color_hex": g.get("color_hex"),
            },
        )
    logger.info("Seeded %d system groups.", len(SYSTEM_GROUPS))


async def seed_core_permissions(session: AsyncSession) -> None:
    """Insert core permissions — idempotent on key conflict."""
    for p in CORE_PERMISSIONS:
        await session.execute(
            text(
                """
                INSERT INTO permissions (id, key, description, plugin_id)
                VALUES (:id, :key, :description, NULL)
                ON CONFLICT (key) DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "key": p["key"],
                "description": p.get("description"),
            },
        )
    logger.info("Seeded %d core permissions.", len(CORE_PERMISSIONS))


async def seed_discord_role_mappings(session: AsyncSession) -> None:
    """Insert Discord role -> group mappings — idempotent on discord_role_id conflict."""
    for discord_role_id, discord_role_name, group_slug, sync_enabled, priority in DISCORD_ROLE_MAPPINGS:
        await session.execute(
            text(
                """
                INSERT INTO discord_role_mappings
                    (id, discord_role_id, discord_role_name, group_id, sync_enabled, priority)
                SELECT
                    :id,
                    :discord_role_id,
                    :discord_role_name,
                    g.id,
                    :sync_enabled,
                    :priority
                FROM groups g
                WHERE g.slug = :group_slug
                ON CONFLICT (discord_role_id) DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "discord_role_id": discord_role_id,
                "discord_role_name": discord_role_name,
                "group_slug": group_slug,
                "sync_enabled": sync_enabled,
                "priority": priority,
            },
        )
    logger.info("Seeded %d Discord role mappings.", len(DISCORD_ROLE_MAPPINGS))


async def seed_chart_of_accounts(session: AsyncSession) -> None:
    """Insert Section 8 Chart of Accounts into virtual_accounts."""
    # Find an owner user ID (CEO or super admin)
    res = await session.execute(text("SELECT id FROM users ORDER BY is_super_admin DESC, created_at ASC LIMIT 1"))
    owner_row = res.fetchone()
    if not owner_row:
        logger.warning("No user found to assign as virtual account owner. Skipping chart of accounts seed.")
        return
    owner_id = owner_row[0]

    for acc in CHART_OF_ACCOUNTS:
        await session.execute(
            text(
                """
                INSERT INTO virtual_accounts
                    (id, owner_id, name, description, balance_paise, account_number, ifsc, is_active, metadata)
                VALUES
                    (:id, :owner_id, :name, :description, :balance_paise, :account_number, :ifsc, true, '{}')
                ON CONFLICT (account_number) DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "owner_id": owner_id,
                "name": acc["name"],
                "description": acc["description"],
                "balance_paise": acc["balance_paise"],
                "account_number": acc["account_number"],
                "ifsc": acc["ifsc"],
            },
        )
    logger.info("Seeded %d Section 8 virtual accounts.", len(CHART_OF_ACCOUNTS))


def seed_okf_rules() -> None:
    """Write 35 OKF Legal Rules to data/company-knowledge/legal/rules/ and refresh store."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    repo_rules_dir = os.path.join(base_dir, "data", "company-knowledge", "legal", "rules")
    cwd_rules_dir = os.path.join(os.getcwd(), "data", "company-knowledge", "legal", "rules")

    rules_dir = repo_rules_dir if os.path.exists(os.path.dirname(repo_rules_dir)) else cwd_rules_dir
    os.makedirs(rules_dir, exist_ok=True)

    for rule in OKF_LEGAL_RULES:
        filepath = os.path.join(rules_dir, rule["file_name"])
        content = f"""---
type: Policy Rule
title: {rule["title"]}
description: {rule["description"]}
tags: {json.dumps(rule["tags"])}
timestamp: 2026-08-04T00:00:00Z
---

# {rule["title"]}

{rule["content"]}
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    logger.info("Seeded %d OKF Legal Rules in %s.", len(OKF_LEGAL_RULES), rules_dir)

    # Refresh OKF Knowledge Store in memory if initialized
    try:
        from app.services.okf_engine import get_okf_store
        store = get_okf_store()
        store.load_bundle()
    except Exception as err:
        logger.debug("OKF store reload skipped: %s", err)


async def run_seeds(session: AsyncSession) -> None:
    """Seed system configuration only (groups, permissions, role mappings,
    chart-of-accounts structure, OKF rules). Operational data (forks, team)
    is pulled live from Notion via app.provisioning.notion_sync — never seeded."""
    logger.info("Running system configuration seeds…")
    await seed_system_groups(session)
    await seed_core_permissions(session)
    await seed_discord_role_mappings(session)
    await seed_chart_of_accounts(session)
    seed_okf_rules()
    await session.commit()
    logger.info("System configuration seeds completed successfully.")
