from app.core.config import get_settings

DESTRUCTIVE_CAPABILITIES = {
    "file_delete", "database_drop", "database_delete",
    "system_registry_write", "firewall_change", "service_install"
}
EXTERNAL_WRITE_CAPABILITIES = {
    "external_write", "git_push", "publish", "send_message", "upload"
}

def requires_approval(
    risk_level: int,
    capability: str = "",
    server_trust_level: str = "UNTRUSTED",
    allow_read_without_prompt: bool = False,
    allow_write_without_prompt: bool = False,
) -> bool:
    cap = (capability or "").lower()
    trust = (server_trust_level or "UNTRUSTED").upper()

    if cap in DESTRUCTIVE_CAPABILITIES:
        return True
    if cap in EXTERNAL_WRITE_CAPABILITIES:
        return True
    if trust == "UNTRUSTED":
        return True

    if risk_level == 0 and allow_read_without_prompt:
        return False
    if risk_level <= 1 and allow_write_without_prompt and trust in {"TRUSTED","SYSTEM"}:
        return False

    return risk_level > get_settings().auto_approve_risk_level

def approval_payload(
    action: str,
    summary: str,
    risk_level: int,
    payload: dict,
    capability: str = "",
    server_trust_level: str = "UNTRUSTED",
) -> dict:
    return {
        "action": action,
        "summary": summary,
        "risk_level": risk_level,
        "capability": capability,
        "server_trust_level": server_trust_level,
        "payload": payload,
        "choices": ["approve", "reject"]
    }
