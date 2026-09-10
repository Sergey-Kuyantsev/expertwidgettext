"""FastAPI proxy for Эксперт Новострой text chat widget (Yandex AI Studio)."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "").strip()
YANDEX_PROJECT = os.getenv("YANDEX_PROJECT", "").strip()
YANDEX_PROMPT_ID = os.getenv("YANDEX_PROMPT_ID", "").strip()
YANDEX_BASE_URL = os.getenv(
    "YANDEX_BASE_URL", "https://ai.api.cloud.yandex.net/v1"
).strip()
BITRIX_MCP_URL = os.getenv("BITRIX_MCP_URL", "").strip()
BITRIX_MCP_LABEL = os.getenv("BITRIX_MCP_LABEL", "expertbitrix24").strip()
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "").strip()
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").strip()
WELCOME_PROMPT = os.getenv(
    "WELCOME_PROMPT",
    "Посетитель открыл чат на сайте компании «Эксперт Новострой». "
    "Поприветствуй кратко и по-деловому на русском. "
    "Представься как ИИ-консультант компании «Эксперт Новострой». "
    "Предложи помочь с приёмкой, стоимостью или заявкой. Не используй markdown.",
).strip()

sessions: dict[str, str] = {}

app = FastAPI(title="Эксперт Новострой Text Chat")

_origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
if _origins == ["*"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class ChatRequest(BaseModel):
    sessionId: str = Field(min_length=1)
    message: str = Field(min_length=1)


class WelcomeRequest(BaseModel):
    sessionId: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str
    sessionId: str


def _require_config() -> None:
    missing = [
        name
        for name, value in (
            ("YANDEX_API_KEY", YANDEX_API_KEY),
            ("YANDEX_PROJECT", YANDEX_PROJECT),
            ("YANDEX_PROMPT_ID", YANDEX_PROMPT_ID),
        )
        if not value
    ]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Server misconfigured: missing {', '.join(missing)}",
        )


def _build_tools() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    if BITRIX_MCP_URL and BITRIX_MCP_URL not in ("*",):
        tools.append(
            {
                "type": "mcp",
                "server_label": BITRIX_MCP_LABEL or "expertbitrix24",
                "server_url": BITRIX_MCP_URL,
                "server_description": "",
                "require_approval": "never",
            }
        )
    # Ignore empty / placeholder values (e.g. "*" mistaken from CORS_ORIGINS)
    vs_id = VECTOR_STORE_ID.strip()
    if vs_id and vs_id not in ("*", "none", "null") and len(vs_id) >= 8:
        tools.append(
            {
                "type": "file_search",
                "vector_store_ids": [vs_id],
                "max_num_results": 5,
            }
        )
    return tools


def _get_client() -> OpenAI:
    return OpenAI(
        api_key=YANDEX_API_KEY,
        base_url=YANDEX_BASE_URL,
        project=YANDEX_PROJECT,
    )


def _call_yandex(session_id: str, message: str) -> ChatResponse:
    _require_config()
    previous_response_id = sessions.get(session_id)
    create_kwargs: dict[str, Any] = {
        "prompt": {"id": YANDEX_PROMPT_ID},
        "input": message.strip(),
    }
    tools = _build_tools()
    if tools:
        create_kwargs["tools"] = tools
    if previous_response_id:
        create_kwargs["previous_response_id"] = previous_response_id

    try:
        client = _get_client()
        response = client.responses.create(**create_kwargs)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Yandex API error: {exc}",
        ) from exc

    reply = (getattr(response, "output_text", None) or "").strip()
    new_id = getattr(response, "id", None)
    if not reply:
        raise HTTPException(status_code=502, detail="Empty reply from Yandex API")
    if not new_id:
        raise HTTPException(
            status_code=502, detail="Missing response id from Yandex API"
        )

    sessions[session_id] = new_id
    return ChatResponse(reply=reply, sessionId=session_id)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "expertwidgettext",
        "status": "ok",
        "health": "/api/health",
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/welcome", response_model=ChatResponse)
def welcome(body: WelcomeRequest) -> ChatResponse:
    if body.sessionId in sessions:
        raise HTTPException(status_code=409, detail="Session already started")
    return _call_yandex(body.sessionId, WELCOME_PROMPT)


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    return _call_yandex(body.sessionId, body.message)


@app.delete("/api/chat/{session_id}")
def reset_session(session_id: str) -> dict[str, str]:
    sessions.pop(session_id, None)
    return {"status": "ok", "sessionId": session_id}
