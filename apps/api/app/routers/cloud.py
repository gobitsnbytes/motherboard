"""
SparkCloud Verification & Access Router
Handles applicant form submissions, forwards interactive embeds to Discord,
and dispatches decision emails upon approval/denial by admins.
"""

import logging
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Header, UploadFile, status
from pydantic import BaseModel, EmailStr

from app.config import Settings, get_settings
from app.routers.meetings import send_smtp_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cloud", tags=["cloud"])


class CloudDecisionRequest(BaseModel):
    action: str  # "approve" or "deny"
    email: EmailStr
    name: str
    reason: Optional[str] = None
    reviewer: Optional[str] = None


@router.post("/apply", status_code=status.HTTP_201_CREATED)
async def apply_for_cloud_access(
    name: str = Form(...),
    email: str = Form(...),
    github: str = Form(...),
    linkedin: str = Form(...),
    id_file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
):
    """
    Receives cloud verification application with uploaded ID document.
    Validates form data and dispatches an interactive Discord webhook with
    Approve / Deny component buttons.
    """
    name = name.strip()
    email = email.strip()
    github = github.strip()
    linkedin = linkedin.strip()

    if not name or not email or not github or not linkedin:
        raise HTTPException(status_code=400, detail="All text fields are required.")

    # Read uploaded ID file
    file_bytes = await id_file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded ID file is empty.")

    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="ID file size must be less than 10MB.")

    webhook_url = settings.discord_cloud_approval_webhook_url
    if not webhook_url:
        logger.warning("[CLOUD_AUTH] DISCORD_CLOUD_APPROVAL_WEBHOOK_URL is not set. Webhook notification skipped.")
        return {"status": "success", "message": "Application received (webhook pending configuration)."}

    # Prepare Discord Webhook payload with Interactive Components
    payload_json = {
        "embeds": [
            {
                "title": "☁️ NEW SPARKCLOUD ACCESS REQUEST",
                "description": "A student builder has submitted their details & ID for SparkCloud access verification.",
                "color": 16552461,  # #fc920d Orange
                "fields": [
                    {"name": "👤 Full Name", "value": name, "inline": True},
                    {"name": "📧 Email", "value": email, "inline": True},
                    {"name": "🐙 GitHub Profile", "value": github, "inline": False},
                    {"name": "💼 LinkedIn Profile", "value": linkedin, "inline": False},
                    {"name": "🆔 ID Document", "value": f"`{id_file.filename}` (attached)", "inline": True},
                ],
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "footer": {"text": "bits&bytes™ SparkCloud Anti-Abuse System"},
            }
        ],
        "components": [
            {
                "type": 1,  # Action Row
                "components": [
                    {
                        "type": 2,  # Button
                        "style": 3,  # Success (Green)
                        "label": "Approve Access",
                        "custom_id": "cloud_approve",
                        "emoji": {"name": "✅"},
                    },
                    {
                        "type": 2,  # Button
                        "style": 4,  # Danger (Red)
                        "label": "Deny Access",
                        "custom_id": "cloud_deny",
                        "emoji": {"name": "❌"},
                    },
                ],
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            files = {
                "files[0]": (id_file.filename, file_bytes, id_file.content_type or "application/octet-stream"),
            }
            data = {"payload_json": httpx.json.dumps(payload_json)}

            # 1. Try sending via Discord Bot API to guarantee button components render
            sent_via_bot = False
            if settings.discord_bot_token:
                try:
                    # Get channel_id from webhook info
                    webhook_info_res = await client.get(webhook_url)
                    if webhook_info_res.status_code == 200:
                        channel_id = webhook_info_res.json().get("channel_id")
                        if channel_id:
                            bot_headers = {"Authorization": f"Bot {settings.discord_bot_token}"}
                            bot_post_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
                            bot_res = await client.post(bot_post_url, headers=bot_headers, data=data, files=files)
                            if bot_res.status_code in (200, 201):
                                sent_via_bot = True
                                logger.info(f"[CLOUD_AUTH] Interactive review message sent via Bot API to channel {channel_id}")
                except Exception as bot_err:
                    logger.warning(f"[CLOUD_AUTH] Failed to send via Bot API, falling back to Webhook: {bot_err}")

            # 2. Fallback to Webhook if Bot API message wasn't sent
            if not sent_via_bot:
                res = await client.post(webhook_url, data=data, files=files)
                if res.status_code not in (200, 204):
                    logger.error(f"[CLOUD_AUTH] Webhook dispatch failed: {res.status_code} - {res.text}")
                    raise HTTPException(status_code=502, detail="Failed to dispatch review request to Discord.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CLOUD_AUTH] Error posting to Discord: {e}")
        raise HTTPException(status_code=500, detail="Internal server error sending review request.")

    return {"status": "success", "message": "Application submitted successfully for review."}


@router.post("/send-decision")
async def send_cloud_decision(
    req: CloudDecisionRequest,
    x_api_secret: Optional[str] = Header(None, alias="X-API-Secret"),
    settings: Settings = Depends(get_settings),
):
    """
    Triggered by Discord Bot when an admin approves or denies a request.
    Sends automated email notification with SparkCloud access link or rejection reason.
    """

    if settings.api_internal_secret and x_api_secret != settings.api_internal_secret:
        # If internal secret is configured, log warning if missing/mismatched
        logger.warning("[CLOUD_AUTH] Unauthorized attempt to send cloud decision email.")

    email = req.email
    name = req.name
    reason = req.reason or "No specific reason provided."

    if req.action == "approve":
        subject = "Your SparkCloud Access Request Has Been Approved! ☁️"
        join_url = settings.sparkcloud_join_url
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #120F0A; color: #FFFFFF; margin: 0; padding: 24px; }}
            .card {{ max-width: 600px; margin: 0 auto; background-color: #1A1612; border: 3px solid #97192C; padding: 32px; box-shadow: 6px 6px 0px 0px #97192C; }}
            .header {{ font-size: 24px; font-weight: 900; text-transform: uppercase; color: #FC920D; margin-bottom: 16px; border-bottom: 2px solid #332B22; padding-bottom: 12px; }}
            .text {{ font-size: 15px; line-height: 1.6; color: #D0CFCE; margin-bottom: 20px; }}
            .btn {{ display: inline-block; background-color: #FC920D; color: #120F0A; font-weight: 900; font-size: 16px; text-transform: uppercase; text-decoration: none; padding: 14px 28px; border: 2px solid #FFFFFF; margin-top: 12px; margin-bottom: 24px; }}
            .note-box {{ background-color: #241F1A; border-left: 4px solid #FC920D; padding: 12px 16px; margin-bottom: 20px; font-size: 14px; font-style: italic; color: #FED39E; }}
            .footer {{ font-size: 12px; color: #716F6C; margin-top: 32px; border-top: 1px solid #332B22; padding-top: 16px; font-family: monospace; }}
          </style>
        </head>
        <body>
          <div class="card">
            <div class="header">SparkCloud Access Approved</div>
            <p class="text">Hi <strong>{name}</strong>,</p>
            <p class="text">Great news! Your verification details have been reviewed and approved by the bits&bytes™ operations team. You now have full access to complimentary SparkCloud development spaces.</p>
            
            <div class="note-box">
              <strong>Reviewer Note:</strong> {reason}
            </div>

            <p class="text">Click the button below to join the GOBITSNBYTES organization on SparkCloud and spin up your containers:</p>
            
            <a href="{join_url}" class="btn" target="_blank">Access SparkCloud Space &rarr;</a>

            <p class="text" style="font-size: 13px; color: #A09F9D;">
              <em>Reminder: Your account is subject to Sparkden's Code of Conduct and Acceptable Use Policies. Complimentary access is strictly reserved for non-commercial student projects.</em>
            </p>

            <div class="footer">
              bits&bytes™ Student Builder Network &bull; GOBITSNBYTES FOUNDATION
            </div>
          </div>
        </body>
        </html>
        """
    else:
        subject = "Update Regarding Your SparkCloud Access Request"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #120F0A; color: #FFFFFF; margin: 0; padding: 24px; }}
            .card {{ max-width: 600px; margin: 0 auto; background-color: #1A1612; border: 3px solid #EF4444; padding: 32px; box-shadow: 6px 6px 0px 0px #EF4444; }}
            .header {{ font-size: 24px; font-weight: 900; text-transform: uppercase; color: #EF4444; margin-bottom: 16px; border-bottom: 2px solid #332B22; padding-bottom: 12px; }}
            .text {{ font-size: 15px; line-height: 1.6; color: #D0CFCE; margin-bottom: 20px; }}
            .reason-box {{ background-color: #2D1A1A; border-left: 4px solid #EF4444; padding: 14px 16px; margin-bottom: 20px; font-size: 14px; color: #FCA5A5; }}
            .footer {{ font-size: 12px; color: #716F6C; margin-top: 32px; border-top: 1px solid #332B22; padding-top: 16px; font-family: monospace; }}
          </style>
        </head>
        <body>
          <div class="card">
            <div class="header">SparkCloud Request Update</div>
            <p class="text">Hi <strong>{name}</strong>,</p>
            <p class="text">Thank you for applying for SparkCloud access. After reviewing your verification submission, we are currently unable to approve your application due to the following reason:</p>
            
            <div class="reason-box">
              <strong>Reason:</strong> {reason}
            </div>

            <p class="text">If you believe this was in error or wish to provide updated verification documents (such as a clear photo of your student ID), please feel free to submit a new application on our website or reach out in our Discord community.</p>

            <div class="footer">
              bits&bytes™ Student Builder Network &bull; GOBITSNBYTES FOUNDATION
            </div>
          </div>
        </body>
        </html>
        """

    try:
        send_smtp_email(settings, [email], subject, html_body)
        logger.info(f"[CLOUD_AUTH] Decision email ('{req.action}') dispatched to {email}")
        return {"status": "success", "message": f"Decision email sent to {email}"}
    except Exception as e:
        logger.error(f"[CLOUD_AUTH] Failed to send decision email to {email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send decision email: {str(e)}")
