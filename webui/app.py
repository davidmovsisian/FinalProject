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
AI_ASSISTANT_API_URL_DEFAULT = os.getenv("AI_ASSISTANT_API_URL", "http://assistant_service:8000")

# ─────────────────────────────────────────────
#  State helpers
# ─────────────────────────────────────────────
_config = {
    "n8n_webhook_url": N8N_WEBHOOK_URL_DEFAULT,
    "ai_assistant_api_url": AI_ASSISTANT_API_URL_DEFAULT,
}

def save_config(n8n_webhook_url: str, ai_assistant_api_url: str):
    _config["n8n_webhook_url"] = n8n_webhook_url.strip()
    _config["ai_assistant_api_url"] = ai_assistant_api_url.strip()
    return "✅ Configuration saved successfully."


# ─────────────────────────────────────────────
#  AI Assistant chat
# ─────────────────────────────────────────────
def chat_with_assistant(message: str, history: list, listing_related: bool, listing_state: dict):
    """Send message to the AI assistant service.

    Routes to /answer-with-listing when 'Listing Related Question' is checked
    and a listing has already been submitted (listing_id present in state).
    Otherwise routes to /general_answer.
    """
    if not message.strip():
        return history, "", gr.update(visible=False)

    base_url = _config.get("ai_assistant_api_url", "").strip().rstrip("/")

    if not base_url:
        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": "⚠️ AI Assistant API URL is not configured. Please set it in the Configuration tab."},
        ]
        return history, "", gr.update(visible=False)

    # ── Route decision ───────────────────────────────────────────────────────
    if listing_related:
        listing_id = (listing_state or {}).get("listing_id", "")
        if not listing_id:
            # Listing not yet submitted — show inline error, do NOT send request
            return history, message, gr.update(
                visible=True,
                value="⚠️ Listing should be submitted before asking listing-related questions."
            )

        # Validate payload matches ListingQuestionRequest
        # (listing_id: str min_length=1, question: str min_length=1, k: int|None default=5)
        if not message.strip():
            return history, message, gr.update(
                visible=True,
                value="⚠️ Question must not be empty."
            )

        api_url = f"{base_url}/answer-with-listing"
        payload = {
            "listing_id": listing_id,          # str, min_length=1  ✓
            "question": message.strip()        # str, min_length=1  ✓
        }
        print(f"[answer-with-listing] POST {api_url}  listing_id={listing_id!r}  question={message!r}")

    else:
        # Validate payload matches ChatRequest
        # (message: Optional[str], history: Optional[List[HistoryMessage]])
        valid_history = [
            {"role": m["role"], "content": m["content"]}
            for m in (history or [])
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        api_url = f"{base_url}/general_answer"
        payload = {
            "message": message,                 # Optional[str]  ✓
            "history": valid_history,           # Optional[List[HistoryMessage]]  ✓
        }
        print(f"[general_answer] POST {api_url}  message={message!r}  history_len={len(valid_history)}")

    # ── Send request ─────────────────────────────────────────────────────────
    try:
        response = requests.post(api_url, json=payload, timeout=3600)
        response.raise_for_status()
        data = response.json()
        print(f"Response data: {data}")
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
    return history, "", gr.update(visible=False)


# ─────────────────────────────────────────────
#  Listing submission
# ─────────────────────────────────────────────
def submit_listing(
    agent_name: str,
    description: str,
    image_urls: str,
    images,            # file-upload list
):
    """POST the listing to the n8n webhook and return the structured report.

    On success the response JSON  { listing_id, passed, reason, safe_text }
    is stored in the listing_state gr.State component so the AI Assistant tab
    can use it for listing-related questions.
    """
    webhook_url = _config.get("n8n_webhook_url", "").strip()

    if not webhook_url:
        return (
            gr.update(visible=False),
            gr.update(visible=True, value="⚠️ n8n Webhook URL is not configured. Please set it in the Configuration tab."),
            {},  # empty listing_state
        )

    if not description.strip():
        return (
            gr.update(visible=False),
            gr.update(visible=True, value="⚠️ Property description is required."),
            {},  # empty listing_state
        )

    # Build image URL list
    url_list = [u.strip() for u in image_urls.split(",") if u.strip()] if image_urls else []

    # Attach uploaded files
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
        response = requests.post(webhook_url, json=payload, timeout=3600)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.ConnectionError:
        return (
            gr.update(visible=False),
            gr.update(visible=True, value="⚠️ Could not connect to n8n. Please check the Webhook URL in Configuration."),
            {}, 
        )
    except requests.exceptions.Timeout:
        return (
            gr.update(visible=False),
            gr.update(visible=True, value="⚠️ The n8n workflow timed out. Please try again."),
            {}, 
        )
    except Exception as exc:
        return (
            gr.update(visible=False),
            gr.update(visible=True, value=f"⚠️ Submission error: {exc}"),
            {}, 
        )

    # ── Store listing response in state ──────────────────────────────────────
    # Expected shape: { "listing_id": str, "passed": bool, "reason": str, "safe_text": str }

    listing_id = str(data.get("listing_id") or "").strip()
    passed = data.get("passed")
    reason = str(data.get("reason") or "")
    safe_text = str(data.get("safe_text") or "")

    listing_state = {
        "listing_id": listing_id,
        "passed":     passed,
        "reason":     reason,
        "safe_text":  safe_text,
    }
    print(f"[submit_listing] Stored listing_state: listing_id={listing_state['listing_id']!r}  passed={listing_state['passed']}")

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
        listing_state,
        []
    )


def _format_report(data: dict) -> str:
    """Convert the n8n response JSON into readable Markdown.

    "safe_text" already arrives as fully-formed Markdown (headings, bold
    metadata lines, bullet lists, summary paragraph), so it's rendered
    as-is rather than re-wrapped in another header.
    """
    if not isinstance(data, dict):
        return f"## 📋 Property Triage Report\n\n{data}"

    listing_id = data.get("listing_id", "—")
    passed = data.get("passed")
    reason = data.get("reason", "")
    safe_text = data.get("safe_text", "")

    if safe_text:
        return safe_text

    # Fallback when there's no safe_text to show.
    status_badge = "✅ **Passed**" if passed else "❌ **Not Passed**"
    lines = [
        "## 📋 Property Triage Report",
        "",
        f"**Listing ID:** {listing_id}  ",
        f"**Status:** {status_badge}  ",
    ]
    if reason:
        lines += ["", f"**Reason:** {reason}"]

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
.gr-group {
    border-radius: 10px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07) !important;
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

/* ── Listing-related checkbox ─────────────── */
#listing-related-cb {
    margin-top: 10px;
    padding: 10px 14px;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
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

/* ── Error box ────────────────────────────── */
#error-box {
    background: #fff1f2;
    border: 1px solid #fda4af;
    border-radius: 8px;
    padding: 14px 16px;
    color: #be123c;
}

/* ── Chat error box ───────────────────────── */
#chat-error-box {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-radius: 8px;
    padding: 10px 14px;
    color: #9a3412;
    font-size: 0.9rem;
}
"""

def build_ui():
    with gr.Blocks(title="AI Property Triage System", css=CUSTOM_CSS) as demo:

        # ── Shared state: stores the last listing submission response ────────
        # Shape: { listing_id: str, passed: bool|None, reason: str, safe_text: str }
        listing_state = gr.State({})

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

            # ─────────────────────────────────────────
            #  TAB 2 — AI Assistant
            # ─────────────────────────────────────────
            with gr.TabItem("💬 AI Assistant"):
                with gr.Row():
                    with gr.Column(scale=4):
                        chatbot = gr.Chatbot(
                            label="Real Estate AI Assistant",
                            height=480,
                            elem_id="chat-box"
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

                        # ── Listing Related Question checkbox ────────────────
                        # Placed at the bottom of the chat column as requested.
                        listing_related_cb = gr.Checkbox(
                            label="📋 Listing Related Question",
                            value=False,
                            elem_id="listing-related-cb",
                            info=(
                                "When checked, your question is sent to the assistant "
                                "with full context of the last submitted listing. "
                                "A listing must be submitted first."
                            ),
                        )

                        # Inline error shown when checkbox is on but no listing_id exists
                        chat_error = gr.Markdown(
                            value="",
                            elem_id="chat-error-box",
                            visible=False,
                        )

                # Wire up both Send button and Enter key
                send_btn.click(
                    fn=chat_with_assistant,
                    inputs=[chat_input, chatbot, listing_related_cb, listing_state],
                    outputs=[chatbot, chat_input, chat_error],
                )
                chat_input.submit(
                    fn=chat_with_assistant,
                    inputs=[chat_input, chatbot, listing_related_cb, listing_state],
                    outputs=[chatbot, chat_input, chat_error],
                )

            # ─────────────────────────────────────────
            #  TAB 3 — Configuration
            # ─────────────────────────────────────────
            with gr.TabItem("⚙️ Configuration"):
                gr.Markdown("### Service Configuration")

                with gr.Column(elem_id="config-card"):
                    n8n_url_input = gr.Textbox(
                        label="n8n Webhook URL",
                        placeholder="https://your-n8n-instance.app.n8n.cloud/webhook/property-triage",
                        value=N8N_WEBHOOK_URL_DEFAULT,
                        info="The n8n webhook endpoint that receives listing submissions.",
                    )
                    ai_api_url_input = gr.Textbox(
                        label="AI Assistant API Base URL",
                        placeholder="http://<EC2-IP>:8000",
                        value=AI_ASSISTANT_API_URL_DEFAULT,
                        info=(
                            "Base URL for the AI assistant service "
                            "(routes /general_answer and /answer-with-listing are appended automatically)."
                        ),
                    )

                    save_btn = gr.Button("💾 Save Configuration", variant="primary")
                    save_status = gr.Markdown("")

                save_btn.click(
                    fn=save_config,
                    inputs=[n8n_url_input, ai_api_url_input],
                    outputs=[save_status],
                )

        # submit_listing now also writes to listing_state
        submit_btn.click(
            fn=submit_listing,
            inputs=[agent_name_input, description_input, image_urls_input, image_upload],
            outputs=[report_output, error_output, listing_state, chatbot], # Added chatbot here to receive the cleared list
        )
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
    )