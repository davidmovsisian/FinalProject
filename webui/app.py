import gradio as gr
import requests
import json
import os
import base64
import mimetypes

# ─────────────────────────────────────────────
#  Configuration (read from env or defaults)
# ─────────────────────────────────────────────
N8N_WEBHOOK_URL_DEFAULT = os.getenv("N8N_WEBHOOK_URL", "http://n8n:5678/webhook-test/real-estate-assistant")
AI_ASSISTANT_API_URL_DEFAULT = os.getenv("AI_ASSISTANT_API_URL", "http://assistant_service:8000/general_answer")
ASSISTANT_SERVICE_BASE_URL_DEFAULT = os.getenv("ASSISTANT_SERVICE_BASE_URL", "http://assistant_service:8000")

# ─────────────────────────────────────────────
#  State helpers
# ─────────────────────────────────────────────
_config = {
    "n8n_webhook_url": N8N_WEBHOOK_URL_DEFAULT,
    "ai_assistant_api_url": AI_ASSISTANT_API_URL_DEFAULT,
    "assistant_service_base_url": ASSISTANT_SERVICE_BASE_URL_DEFAULT,
}

# Holds the most recent listing submission response:
# { "listing_id": str, "passed": bool, "reason": str, "safe_text": str }
_listing_context = {
    "listing_id": "",
    "passed": None,
    "reason": "",
    "safe_text": "",
}

def save_config(n8n_webhook_url: str, ai_assistant_api_url: str):
    _config["n8n_webhook_url"] = n8n_webhook_url.strip()
    _config["ai_assistant_api_url"] = ai_assistant_api_url.strip()
    base = ai_assistant_api_url.strip().rsplit("/general_answer", 1)[0]
    if base:
        _config["assistant_service_base_url"] = base
    return "✅ Configuration saved successfully."


# ─────────────────────────────────────────────
#  AI Assistant chat
# ─────────────────────────────────────────────
def chat_with_assistant(message: str, history: list, listing_question: bool):
    """Send message to the AI assistant service and stream/return the reply.

    If `listing_question` is checked, the request is routed to the
    `/answer-with-listing` endpoint using the listing_id stored in
    `_listing_context` from the most recent listing submission. Otherwise
    it goes to `/general_answer` as before.
    """
    if not message.strip():
        return history, ""

    clean_history = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]

    if listing_question:
        listing_id = (_listing_context.get("listing_id") or "").strip()
        if not listing_id:
            reply = "⚠️ Listing should be submitted before."
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": reply},
            ]
            return history, ""

        base_url = _config.get("assistant_service_base_url", "").strip()
        if not base_url:
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": "⚠️ AI Assistant API URL is not configured. Please set it in the Configuration tab."},
            ]
            return history, ""

        api_url = f"{base_url}/answer-with-listing"
        payload = {
            "question": message,
            "listing_id": listing_id,
        }
    else:
        api_url = _config.get("ai_assistant_api_url", "").strip()
        if not api_url:
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": "⚠️ AI Assistant API URL is not configured. Please set it in the Configuration tab."},
            ]
            return history, ""

        payload = {
            "message": message,
            "history": clean_history,
        }

    try:
        print(f"Sending request to {api_url} with payload: {payload}")
        response = requests.post(api_url, json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()
        print(f"Data:{data}")
        reply = data.get("response") or data.get("message") or data.get("answer") or str(data)
    except requests.exceptions.ConnectionError:
        reply = "⚠️ Could not connect to the AI assistant service. Please check the API URL in Configuration."
    except requests.exceptions.Timeout:
        reply = "⚠️ The AI assistant service timed out. Please try again."
    except Exception as exc:
        reply = f"⚠️ Error: {exc}"

    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]
    return history, ""


# ─────────────────────────────────────────────
#  Listing submission
# ─────────────────────────────────────────────
def submit_listing(
    agent_name: str,
    description: str,
    image_urls: str,
    images,            # file-upload list
):
    """POST the listing to the n8n webhook and return the structured report."""
    webhook_url = _config.get("n8n_webhook_url", "").strip()

    if not webhook_url:
        return (
            gr.update(visible=False),
            gr.update(visible=True, value="⚠️ n8n Webhook URL is not configured. Please set it in the Configuration tab."),
        )

    if not description.strip():
        return (
            gr.update(visible=False),
            gr.update(visible=True, value="⚠️ Property description is required."),
        )

    # Build image URL list
    url_list = [u.strip() for u in image_urls.split(",") if u.strip()] if image_urls else []

    # Attach uploaded files.
    uploaded_images = []
    if images:
        for img in images:
            path = img["path"] if isinstance(img, dict) else img
            name = img.get("orig_name", os.path.basename(path)) if isinstance(img, dict) else os.path.basename(path)
            if path and os.path.isfile(path):
                mime_type, _ = mimetypes.guess_type(path)
                mime_type = mime_type or "application/octet-stream"
                with open(path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                uploaded_images.append({
                    "filename": name,
                    "mime_type": mime_type,
                    "data": encoded,
                })

    payload = {
        "agent_name": agent_name.strip(),
        "description": description.strip(),
        "image_urls": url_list,
        "uploaded_images": uploaded_images,
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=420)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.ConnectionError:
        return (
            gr.update(visible=False),
            gr.update(visible=True, value="⚠️ Could not connect to n8n. Please check the Webhook URL in Configuration."),
        )
    except requests.exceptions.Timeout:
        return (
            gr.update(visible=False),
            gr.update(visible=True, value="⚠️ The n8n workflow timed out. Please try again."),
        )
    except Exception as exc:
        return (
            gr.update(visible=False),
            gr.update(visible=True, value=f"⚠️ Submission error: {exc}"),
        )

    # Expected shape: { listing_id, passed, reason, safe_text }
    if not isinstance(data, dict):
        return (
            gr.update(visible=False),
            gr.update(visible=True, value=f"⚠️ Unexpected response from server: {data}"),
        )

    listing_id = str(data.get("listing_id") or "").strip()
    passed = data.get("passed")
    reason = str(data.get("reason") or "")
    safe_text = str(data.get("safe_text") or "")

    # Store whatever we got, so later listing-related questions can reference it.
    _listing_context["listing_id"] = listing_id
    _listing_context["passed"] = bool(passed)
    _listing_context["reason"] = reason
    _listing_context["safe_text"] = safe_text

    if not listing_id:
        return (
            gr.update(visible=False),
            gr.update(visible=True, value="⚠️ Listing submission failed: no listing ID was returned."),
        )

    if not passed:
        error_msg = "⚠️ Listing did not pass validation."
        if reason:
            error_msg += f" Reason: {reason}"
        return (
            gr.update(visible=False),
            gr.update(visible=True, value=error_msg),
        )

    report_md = _format_report(data)
    return (
        gr.update(visible=True, value=f"✅ Listing submitted successfully!\n\n{report_md}"),
        gr.update(visible=False),
    )


def _format_report(data: dict) -> str:
    """Convert the n8n response JSON into readable Markdown."""
    if not isinstance(data, dict):
        return f"## 📋 Property Triage Report\n\n{data}"

    listing_id = data.get("listing_id", "—")
    passed = data.get("passed")
    reason = data.get("reason", "")
    safe_text = data.get("safe_text", "")

    status_badge = "✅ **Passed**" if passed else "❌ **Not Passed**"

    lines = [
        "## 📋 Property Triage Report",
        "",
        f"**Listing ID:** {listing_id}  ",
        f"**Status:** {status_badge}  ",
    ]

    if reason:
        lines += ["", f"**Reason:** {reason}"]

    if safe_text:
        lines += ["", "---", "### 📝 Listing Text", "", safe_text]

    return "\n".join(lines)

# ─────────────────────────────────────────────
#  Build the Gradio UI
# ─────────────────────────────────────────────
CUSTOM_CSS = """
/* ── Global ───────────────────────────────── */
body, .gradio-container {
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif !important;
    background: #f8fafc !important;
}

/* ── Header banner ────────────────────────── */
#header-banner {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
    border-radius: 12px;
    padding: 28px 32px 20px;
    margin-bottom: 8px;
    color: white;
}
#header-banner h1 {
    font-size: 1.8rem;
    font-weight: 700;
    margin: 0 0 4px;
    color: white !important;
}
#header-banner p {
    margin: 0;
    opacity: 0.85;
    font-size: 0.95rem;
    color: white !important;
}

/* ── Tabs ─────────────────────────────────── */
.tab-nav button {
    font-weight: 600 !important;
    font-size: 0.92rem !important;
}

/* ── Cards ────────────────────────────────── */
.card {
    background: white;
    border-radius: 10px;
    padding: 20px 22px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    margin-bottom: 12px;
}

/* ── Submit button ────────────────────────── */
#submit-btn {
    background: linear-gradient(135deg, #1e3a5f, #2d6a9f) !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    border-radius: 8px !important;
    padding: 10px 24px !important;
}
#submit-btn:hover {
    opacity: 0.9 !important;
}

/* ── Report box ───────────────────────────── */
#report-box {
    background: #f0f7ff;
    border: 1px solid #b3d4f5;
    border-radius: 10px;
    padding: 18px;
}

/* ── Chat ─────────────────────────────────── */
#chat-box .message.bot {
    background: #e8f4fd !important;
    border-radius: 10px !important;
}

/* ── Config section ───────────────────────── */
#config-card {
    background: #fff;
    border-radius: 10px;
    padding: 20px 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}

/* ── Status badges ────────────────────────── */
.status-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
}
.status-pill.green { background:#dcfce7; color:#166534; }
.status-pill.red   { background:#fee2e2; color:#991b1b; }

/* ── Sidebar info box ─────────────────────── */
#info-box {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    padding: 14px 16px;
    font-size: 0.85rem;
    color: #1e40af;
}

/* ── Error box ────────────��───────────────── */
#error-box {
    background: #fff1f2;
    border: 1px solid #fda4af;
    border-radius: 8px;
    padding: 14px 16px;
    color: #be123c;
}
"""

def build_ui():
    with gr.Blocks(title="AI Property Triage System") as demo:

        # ── Header ──────────────────────────────────
        gr.HTML("""
        <div id="header-banner">
          <h1>🏠 AI Property Triage System</h1>
          <p>Automated real-estate listing intake &amp; evaluation powered by AI</p>
        </div>
        """)

        # ── Tabs ─────────────────────────────────────
        with gr.Tabs():

            # ─────────────────────────────────────────
            #  TAB 1 — Property Submission
            # ─────────────────────────────────────────
            with gr.TabItem("📝 Submit Listing"):
                # gr.Markdown(
                #     "Fill in the property details below and click **Submit Listing** to start the AI triage pipeline.",
                #     elem_classes="card",
                # )

                with gr.Row():
                    with gr.Column(scale=3):
                        agent_name_input = gr.Textbox(
                            label="Listing Agent Name",
                            placeholder="e.g. Sarah Cohen",
                            max_lines=1,
                        )
                        description_input = gr.Textbox(
                            label="Property Description ✱",
                            placeholder="Describe the property in detail — type, size, location, condition, features …",
                            lines=8,
                        )
                        image_urls_input = gr.Textbox(
                            label="Image URLs (comma-separated)",
                            placeholder="https://example.com/img1.jpg, https://example.com/img2.jpg",
                            lines=2,
                        )
                        image_upload = gr.File(
                            label="Or upload images directly",
                            file_count="multiple",
                            file_types=["image"],
                        )

                        submit_btn = gr.Button(
                            "🚀 Submit Listing",
                            variant="primary",
                            elem_id="submit-btn",
                        )

                    # with gr.Column(scale=2):
                    #     gr.HTML("""
                    #     <div id="info-box">
                    #       <strong>ℹ️ How it works</strong><br><br>
                    #       1. Your submission is validated by the <b>Guardrails</b> service.<br><br>
                    #       2. An AI extractor identifies property type, rooms, price, and key features.<br><br>
                    #       3. Each image is classified by room type and given a <b>condition score (1–5)</b>.<br><br>
                    #       4. Similar past listings are retrieved from the <b>knowledge base</b>.<br><br>
                    #       5. A final <b>listing brief</b> is generated and the listing is routed to the correct team.
                    #     </div>
                    #     """)

                # Results area
                with gr.Row():
                    with gr.Column():
                        report_output = gr.Markdown(
                            label="Triage Report",
                            elem_id="report-box",
                            visible=False,
                        )
                        error_output = gr.Markdown(
                            label="",
                            elem_id="error-box",
                            visible=False,
                        )

                submit_btn.click(
                    fn=submit_listing,
                    inputs=[agent_name_input, description_input, image_urls_input, image_upload],
                    outputs=[report_output, error_output],
                )

            # ─────────────────────────────────────────
            #  TAB 2 — AI Assistant
            # ─────────────────────────────────────────
            with gr.TabItem("💬 AI Assistant"):
                with gr.Row():
                    with gr.Column(scale=4):
                        chatbot = gr.Chatbot(
                            label="Real Estate AI Assistant",
                            height=480,
                            elem_id="chat-box",
                        )
                        with gr.Row():
                            chat_input = gr.Textbox(
                                label="",
                                placeholder="Ask about property market trends, valuations, investment advice …",
                                scale=5,
                                max_lines=3,
                                show_label=False,
                            )
                            send_btn = gr.Button("Send ➤", scale=1, variant="primary")

                        gr.Examples(
                            examples=[
                                ["What are the current real estate market trends?"],
                                ["How do I evaluate a property's condition score?"],
                                ["What makes a good listing description?"],
                                ["What is the difference between residential and commercial listings?"],
                                ["What renovation tips would improve a property's value?"],
                            ],
                            inputs=chat_input,
                            label="Example questions",
                        )

                    # with gr.Column(scale=1):
                    #     gr.HTML("""
                    #     <div id="info-box">
                    #       <strong>🤖 AI Assistant</strong><br><br>
                    #       Your knowledgeable real-estate assistant is ready to help.<br><br>
                    #       Ask about:<br>
                    #       • Market trends &amp; valuations<br>
                    #       • Property types &amp; features<br>
                    #       • Investment advice<br>
                    #       • Listing best practices<br><br>
                    #       <em>The assistant stays on real-estate topics and will politely decline off-topic requests.</em>
                    #     </div>
                    #     """)

                send_btn.click(
                    fn=chat_with_assistant,
                    inputs=[chat_input, chatbot],
                    outputs=[chatbot, chat_input],
                )
                chat_input.submit(
                    fn=chat_with_assistant,
                    inputs=[chat_input, chatbot],
                    outputs=[chatbot, chat_input],
                )

            # ─────────────────────────────────────────
            #  TAB 3 — Configuration
            # ─────────────────────────────────────────
            with gr.TabItem("⚙️ Configuration"):
                gr.Markdown("### Service Configuration")
                # gr.Markdown(
                #     "Configure the URLs for backend services. Changes take effect immediately without restarting.",
                #     elem_classes="card",
                # )

                with gr.Column(elem_id="config-card"):
                    n8n_url_input = gr.Textbox(
                        label="n8n Webhook URL",
                        placeholder="https://your-n8n-instance.app.n8n.cloud/webhook/property-triage",
                        value=N8N_WEBHOOK_URL_DEFAULT,
                        info="The n8n webhook endpoint that receives listing submissions.",
                    )
                    ai_api_url_input = gr.Textbox(
                        label="AI Assistant API URL",
                        placeholder="http://<EC2-IP>:8001/chat",
                        value=AI_ASSISTANT_API_URL_DEFAULT,
                        info="The backend endpoint for the conversational AI assistant.",
                    )

                    save_btn = gr.Button("💾 Save Configuration", variant="primary")
                    save_status = gr.Markdown("")

                save_btn.click(
                    fn=save_config,
                    inputs=[n8n_url_input, ai_api_url_input],
                    outputs=[save_status],
                )

#                 gr.Markdown("""---
# ### Environment Variables

# You can also pre-set configuration via environment variables before launching:

# | Variable | Description |
# |---|---|
# | `N8N_WEBHOOK_URL` | n8n webhook endpoint for listing submissions |
# | `AI_ASSISTANT_API_URL` | Backend URL for the AI assistant chat service |
# """)

    return demo


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", 7860)),
        share=False,
        css=CUSTOM_CSS,
    )