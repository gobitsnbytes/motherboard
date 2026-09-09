"""Hardening tests: honest plugin telemetry (SSL/DNS/Minecraft metrics) and loader permission enforcement."""

import importlib.util
import socket
import ssl
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dns.resolver
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.db.models import Grant, User
from app.plugin_sdk.loader import PluginLoader
from app.plugin_sdk.types import PermissionDeclaration, PluginManifest, UiPanelDeclaration
from conftest import request_as

REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Plugin module loading helpers
# ---------------------------------------------------------------------------

def _load_plugin_module(plugin_id: str):
    main_path = REPO_ROOT / "plugins" / plugin_id / "api" / "main.py"
    module_name = f"plugin_{plugin_id}_hardening"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, main_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# SSL certificate expiry checks
# ---------------------------------------------------------------------------

def _generate_self_signed_cert(days_valid: int):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=days_valid))
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _free_tcp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def tls_server_port():
    key, cert = _generate_self_signed_cert(days_valid=25)
    with tempfile.TemporaryDirectory() as tmp:
        key_path = Path(tmp) / "key.pem"
        cert_path = Path(tmp) / "cert.pem"
        key_path.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(str(cert_path), str(key_path))

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(5)
        sock.settimeout(0.2)
        port = sock.getsockname()[1]

        stop = threading.Event()

        def _serve():
            while not stop.is_set():
                try:
                    conn, _ = sock.accept()
                except (socket.timeout, TimeoutError):
                    continue
                except OSError:
                    break
                conn.settimeout(5)
                try:
                    tls_conn = server_ctx.wrap_socket(conn, server_side=True)
                    try:
                        tls_conn.recv(1024)
                    finally:
                        try:
                            tls_conn.unwrap()
                        except Exception:
                            pass
                        tls_conn.close()
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass

        thread = threading.Thread(target=_serve, daemon=True)
        thread.start()
        yield port, cert.not_valid_after_utc
        stop.set()
        sock.close()
        thread.join(timeout=5)


@pytest.mark.asyncio
async def test_ssl_check_returns_real_positive_days(tls_server_port):
    email_plugin = _load_plugin_module("email_server")
    port, not_after = tls_server_port

    days_remaining, reachable = await email_plugin._check_ssl_cert_days("127.0.0.1", port)

    assert reachable is True
    expected_days = (not_after - datetime.now(timezone.utc)).days
    assert days_remaining == expected_days
    assert days_remaining > 0


@pytest.mark.asyncio
async def test_ssl_check_unreachable_host_returns_error_state():
    email_plugin = _load_plugin_module("email_server")
    dead_port = _free_tcp_port()

    days_remaining, reachable = await email_plugin._check_ssl_cert_days("127.0.0.1", dead_port)

    assert days_remaining is None
    assert reachable is False


# ---------------------------------------------------------------------------
# DNS validation against a mocked resolver
# ---------------------------------------------------------------------------

def _rrset(name: str, rdtype: str, *items):
    return dns.rrset.from_text_list(name, 300, "IN", rdtype, list(items))


class FakeResolver:
    def __init__(self, answers):
        self._answers = answers

    @staticmethod
    def _fqdn(name) -> str:
        text = str(name)
        return text if text.endswith(".") else f"{text}."

    def resolve(self, name, rdtype, *args, **kwargs):
        key = (self._fqdn(name), rdtype)
        if key not in self._answers:
            raise dns.resolver.NXDOMAIN(f"No answer for {name}/{rdtype}")
        return self._answers[key]


@pytest.mark.asyncio
async def test_dns_validator_all_matching_reports_valid():
    email_plugin = _load_plugin_module("email_server")
    base = f"{email_plugin.BASE_DOMAIN}."
    mail = f"{email_plugin.MAIL_DOMAIN}."
    admin = f"{email_plugin.ADMIN_DOMAIN}."
    answers = {
        (base, "MX"): _rrset(base, "MX", f"10 {mail}"),
        (base, "TXT"): _rrset(base, "TXT", f'"v=spf1 mx a:{email_plugin.MAIL_DOMAIN} ~all"'),
        (f"default._domainkey.{base}", "TXT"): _rrset(
            f"default._domainkey.{base}",
            "TXT",
            '"v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA"',
        ),
        (f"_dmarc.{base}", "TXT"): _rrset(
            f"_dmarc.{base}",
            "TXT",
            '"v=DMARC1; p=reject; rua=mailto:dmarc@gobitsnbytes.org"',
        ),
        (mail, "A"): _rrset(mail, "A", "203.0.113.10"),
        (admin, "A"): _rrset(admin, "A", "203.0.113.20"),
    }

    records = await email_plugin._collect_dns_records(FakeResolver(answers))

    assert len(records) == 6
    assert all(r.valid for r in records)


@pytest.mark.asyncio
async def test_dns_validator_reports_mismatch_and_missing_honestly():
    email_plugin = _load_plugin_module("email_server")
    base = f"{email_plugin.BASE_DOMAIN}."
    mail = f"{email_plugin.MAIL_DOMAIN}."
    answers = {
        (base, "MX"): _rrset(base, "MX", f"10 {mail}"),
        (base, "TXT"): _rrset(
            base, "TXT", '"v=spf1 include:_spf.example.com ~all"'
        ),
        (f"default._domainkey.{base}", "TXT"): _rrset(
            f"default._domainkey.{base}",
            "TXT",
            '"v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA"',
        ),
        (mail, "A"): _rrset(mail, "A", "203.0.113.10"),
    }

    records = await email_plugin._collect_dns_records(FakeResolver(answers))
    by_key = {(r.record_type, r.domain): r for r in records}

    spf = by_key[("SPF", email_plugin.BASE_DOMAIN)]
    assert spf.valid is False
    assert "include:_spf.example.com" in spf.actual

    dmarc = by_key[("DMARC", f"_dmarc.{email_plugin.BASE_DOMAIN}")]
    assert dmarc.valid is False
    assert dmarc.actual == "<unresolvable>"
    assert "DNS lookup failed" in dmarc.details

    admin_a = next(r for r in records if r.record_type == "A" and "admin" in r.domain)
    assert admin_a.valid is False

    assert any(not r.valid for r in records)


# ---------------------------------------------------------------------------
# Minecraft metrics honesty
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_minecraft_metrics_failure_has_no_fabricated_numbers(monkeypatch):
    mc_plugin = _load_plugin_module("minecraft_server")

    async def failing_ssh(ssh_host, cmd, timeout=8.0):
        return -1, "", "ssh: connect to host bnb-mc-server port 22: Connection timed out"

    monkeypatch.setattr(mc_plugin, "_run_ssh_command", failing_ssh)

    response = await mc_plugin._collect_server_metrics()

    assert response.available is False
    assert response.error
    assert "bnb-mc-server" in response.error
    assert response.tps is None
    assert response.cpu_usage_pct is None
    assert response.ram_used_mb is None
    assert response.ram_max_mb is None
    assert response.disk_used_gb is None
    assert response.uptime is None


@pytest.mark.asyncio
async def test_minecraft_metrics_success_parses_without_fakes(monkeypatch):
    mc_plugin = _load_plugin_module("minecraft_server")

    async def scripted_ssh(ssh_host, cmd, timeout=8.0):
        if "tps" in cmd or "rcon-cli" in cmd:
            return 0, "TPS from last 1m, 5m, 15m: 19.98, 20.0, 20.0", ""
        return (
            0,
            "CPU: 7.2\nRAM: 1500/8192\nDISK: 12/80\nUPTIME: up 3 days",
            "",
        )

    monkeypatch.setattr(mc_plugin, "_run_ssh_command", scripted_ssh)

    response = await mc_plugin._collect_server_metrics()

    assert response.available is True
    assert response.error is None
    assert response.tps == pytest.approx(19.98)
    assert response.cpu_usage_pct == pytest.approx(7.2)
    assert response.ram_used_mb == pytest.approx(1500.0)
    assert response.ram_max_mb == pytest.approx(8192.0)
    assert response.disk_used_gb == pytest.approx(12.0)
    assert response.uptime == "up 3 days"


# ---------------------------------------------------------------------------
# Loader permission enforcement
# ---------------------------------------------------------------------------

def _session_factory(session: AsyncSession):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory():
        yield session

    return _factory


def _build_gated_manifest(permission_key: str | None) -> tuple[PluginManifest, APIRouter]:
    gated_router = APIRouter()

    @gated_router.get("/gated")
    async def gated_endpoint():
        return {"ok": True}

    ui_panels = []
    if permission_key:
        ui_panels.append(
            UiPanelDeclaration(
                id="gate-panel",
                title="Gate Panel",
                route_segment="gate",
                placement="sidebar",
                required_permission=permission_key,
                icon="Shield",
            )
        )

    manifest = PluginManifest(
        id="hardening_gate_plugin",
        name="Hardening Gate Plugin",
        version="1.0.0",
        description="Loader enforcement test plugin",
        router=gated_router,
        permissions=[
            PermissionDeclaration(key="hardening.gate.read", description="Gate read access")
        ]
        if permission_key
        else [],
        ui_panels=ui_panels,
    )
    return manifest, gated_router


@pytest.mark.asyncio
async def test_loader_enforces_manifest_permission(db_session: AsyncSession, super_admin: User):
    manifest, _router = _build_gated_manifest("hardening.gate.read")

    test_app = FastAPI()

    async def _override_session():
        yield db_session

    test_app.dependency_overrides[get_session] = _override_session

    loader = PluginLoader(test_app, _session_factory(db_session))
    await loader.load_plugin(manifest)

    route_path = "/api/plugins/hardening_gate_plugin/gated"
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        anon = await ac.get(route_path)
        assert anon.status_code == 401, anon.text

        regular = User(display_name="No Perm Regular", is_super_admin=False)
        db_session.add(regular)
        await db_session.commit()

        denied = await request_as(ac, regular.id, "GET", route_path)
        assert denied.status_code == 403, denied.text
        assert "hardening.gate.read" in denied.json()["detail"]

        allowed = await request_as(ac, super_admin.id, "GET", route_path)
        assert allowed.status_code == 200, allowed.text
        assert allowed.json() == {"ok": True}

        grant = Grant(
            id=uuid.uuid4(),
            principal_type="user",
            principal_id=regular.id,
            permission_key="hardening.gate.read",
        )
        db_session.add(grant)
        await db_session.commit()

        granted = await request_as(ac, regular.id, "GET", route_path)
        assert granted.status_code == 200, granted.text


@pytest.mark.asyncio
async def test_loader_without_panel_permission_keeps_auth_only(db_session: AsyncSession, super_admin: User):
    manifest, _router = _build_gated_manifest(None)

    test_app = FastAPI()

    async def _override_session():
        yield db_session

    test_app.dependency_overrides[get_session] = _override_session

    loader = PluginLoader(test_app, _session_factory(db_session))
    await loader.load_plugin(manifest)

    route_path = "/api/plugins/hardening_gate_plugin/gated"
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        anon = await ac.get(route_path)
        assert anon.status_code == 401

        regular = User(display_name="Auth Only Regular", is_super_admin=False)
        db_session.add(regular)
        await db_session.commit()

        ok = await request_as(ac, regular.id, "GET", route_path)
        assert ok.status_code == 200
