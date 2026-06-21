# WebUI — AI Property Triage System

A Gradio-based web application with three tabs:

| Tab | Description |
|-----|-------------|
| 📝 Submit Listing | Upload a property description + images, submit to the n8n pipeline, and view the AI-generated triage report |
| 💬 AI Assistant | Chat with the real-estate AI assistant backed by a configurable API endpoint |
| ⚙️ Configuration | Set the n8n Webhook URL and AI Assistant API URL at runtime |

---

## Quick Start

### 1. Install dependencies

```bash
cd webui
pip install -r requirements.txt
```

### 2. (Optional) Set environment variables

Create a `.env` file or export variables before running:

```bash
export N8N_WEBHOOK_URL="https://your-n8n-instance.app.n8n.cloud/webhook/property-triage"
export AI_ASSISTANT_API_URL="http://<EC2-IP>:8001/chat"
```

Alternatively, configure them inside the app via the **⚙️ Configuration** tab.

### 3. Run

```bash
python app.py
```

The app will be available at `http://localhost:7860`.

To change the port:

```bash
PORT=8080 python app.py
```

---

## Docker

```bash
docker build -t webui .
docker run -p 7860:7860 \
  -e N8N_WEBHOOK_URL="https://..." \
  -e AI_ASSISTANT_API_URL="http://..." \
  webui
```

---

## Architecture

```
Browser
  └── Gradio (app.py)
        ├── Submit Listing  ──POST──▶  n8n Webhook
        │                   ◀─JSON──   Triage Report
        └── AI Assistant    ──POST──▶  AI Assistant Service (FastAPI)
                            ◀─JSON──   Chat Response
```

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `N8N_WEBHOOK_URL` | _(empty)_ | n8n webhook endpoint for property submissions |
| `AI_ASSISTANT_API_URL` | `http://localhost:8001/chat` | AI assistant chat backend |
| `PORT` | `7860` | Port the Gradio server listens on |
