import os

def fix_env_file():
    path = "/opt/bnb-api/.env"
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")

    if not os.path.exists(path):
        print(f".env file not found at {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = []
    for line in content.splitlines():
        clean_line = line.replace("\\", "").replace("EOF", "").strip()
        if clean_line and not any(k in clean_line for k in ["SPARKCLOUD", "INBOUND_EMAIL_WEBHOOK_SECRET"]):
            lines.append(clean_line)

    lines.append('SPARKCLOUD_API_KEY="sc-ai-KOQa19ciMSNINRR089UcKXQjbp77krMJ"')
    lines.append('SPARKCLOUD_BASE_URL="https://cloud.sparkden.org/api/ai/v1"')
    lines.append('SPARKCLOUD_MODEL="auto"')
    lines.append('INBOUND_EMAIL_WEBHOOK_SECRET="inbound_sec_8f9a2b4c1d3e5f6g"')

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("Successfully sanitized and updated .env file!")

if __name__ == "__main__":
    fix_env_file()
