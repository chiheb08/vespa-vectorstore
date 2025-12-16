from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="rag-api", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# Minimal OpenAI-compatible model list so OpenWebUI can connect.
@app.get("/v1/models")
def list_models() -> dict:
    return {
        "object": "list",
        "data": [
            {
                "id": "rag-ollama",
                "object": "model",
                "owned_by": "rag_app",
            }
        ],
    }


# Minimal OpenAI-compatible response (stub). We'll implement real RAG next.
@app.post("/v1/chat/completions")
def chat_completions(payload: dict) -> dict:
    user_text = ""
    for m in payload.get("messages", []) or []:
        if m.get("role") == "user":
            user_text = m.get("content", "") or ""
            break

    content = (
        "rag-api is up, but full RAG is not implemented yet.\n"
        "You sent: " + user_text
    )

    return {
        "id": "chatcmpl-stub",
        "object": "chat.completion",
        "created": 0,
        "model": payload.get("model", "rag-ollama"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


