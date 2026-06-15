from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import hashlib
import json
import os

from .config import AppConfig
from .storage import (
    TraderCommentaryDiscordCaptureItem,
    TraderCommentaryDiscordCaptureRun,
    TraderCommentaryRaw,
    count_rows_by_table,
    latest_trader_commentary_discord_capture_timestamp,
    list_trader_commentary_discord_capture_items,
    list_trader_commentary_discord_capture_runs,
    mark_trader_commentary_discord_capture_item_ingested,
    upsert_trader_commentary_discord_capture_item,
    upsert_trader_commentary_discord_capture_run,
    upsert_trader_commentary_raw,
)


DISCORD_API_BASE_URL = "https://discord.com/api/v10"
DISCORD_BOT_TOKEN_ENV = "DISCORD_BOT_TOKEN"


@dataclass(frozen=True)
class ParsedDiscordMessage:
    item_key: str
    channel_id: str | None
    guild_id: str | None
    message_id: str | None
    canonical_url: str | None
    author_id: str | None
    author_text: str | None
    content_text: str
    message_timestamp: str | None
    observed_at: str
    raw_excerpt: str | None
    attachment_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DiscordCaptureResult:
    run_id: str
    provider: str
    status: str
    raw_dir: Path
    item_count: int
    stored_count: int
    skipped_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DiscordCaptureIngestResult:
    imported_count: int
    skipped_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DiscordCaptureStatus:
    enabled: bool
    provider: str
    configured_channel_count: int
    token_present: bool
    capture_dir_exists: bool
    run_count: int
    item_count: int
    accepted_item_count: int
    uningested_item_count: int
    latest_run_timestamp: str | None
    latest_status: str | None
    latest_warnings: str | None


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _today() -> str:
    return date.today().isoformat()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_hash(*parts: str | None) -> str:
    return _hash_text("|".join(part or "" for part in parts))


def _warnings_text(warnings: tuple[str, ...]) -> str | None:
    seen: list[str] = []
    for warning in warnings:
        if warning and warning not in seen:
            seen.append(warning)
    return ", ".join(seen) if seen else None


def _relative_or_string(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _message_author_text(message: dict[str, object]) -> tuple[str | None, str | None]:
    author = message.get("author")
    if not isinstance(author, dict):
        return None, None
    author_id = str(author.get("id")) if author.get("id") is not None else None
    display = (
        author.get("global_name")
        or author.get("username")
        or author.get("display_name")
        or author_id
    )
    return author_id, str(display) if display is not None else None


def _canonical_message_url(
    guild_id: str | None,
    channel_id: str | None,
    message_id: str | None,
) -> str | None:
    if not channel_id or not message_id:
        return None
    if guild_id:
        return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
    return f"https://discord.com/channels/@me/{channel_id}/{message_id}"


def parse_discord_messages(
    payload: object,
    channel_id: str | None,
    observed_at: str | None = None,
) -> tuple[list[ParsedDiscordMessage], tuple[str, ...]]:
    observed = observed_at or _now_iso()
    warnings: list[str] = ["discord_official_api_capture", "discord_commentary_shadow_mode"]
    if isinstance(payload, dict):
        raw_messages = payload.get("messages", [])
    else:
        raw_messages = payload
    if not isinstance(raw_messages, list):
        return [], tuple(warnings + ["malformed_discord_payload"])

    items: list[ParsedDiscordMessage] = []
    for raw in raw_messages:
        if not isinstance(raw, dict):
            warnings.append("malformed_discord_message")
            continue
        message_id = str(raw.get("id")) if raw.get("id") is not None else None
        effective_channel_id = (
            str(raw.get("channel_id"))
            if raw.get("channel_id") is not None
            else channel_id
        )
        guild_id = str(raw.get("guild_id")) if raw.get("guild_id") is not None else None
        content_text = str(raw.get("content") or "").strip()
        attachments = raw.get("attachments")
        attachment_count = len(attachments) if isinstance(attachments, list) else 0
        item_warnings = list(warnings)
        if attachment_count:
            item_warnings.append("attachments_metadata_only")
        if not content_text:
            item_warnings.append("empty_discord_message_content")
            continue
        author_id, author_text = _message_author_text(raw)
        message_timestamp = (
            str(raw.get("timestamp")) if raw.get("timestamp") is not None else None
        )
        if message_id:
            item_key = f"discord:{effective_channel_id or 'unknown'}:{message_id}"
        else:
            item_key = (
                "discord_hash:"
                + _stable_hash(effective_channel_id, message_timestamp, author_text, content_text)[
                    :24
                ]
            )
            item_warnings.append("missing_discord_message_id")
        canonical_url = _canonical_message_url(guild_id, effective_channel_id, message_id)
        items.append(
            ParsedDiscordMessage(
                item_key=item_key,
                channel_id=effective_channel_id,
                guild_id=guild_id,
                message_id=message_id,
                canonical_url=canonical_url,
                author_id=author_id,
                author_text=author_text,
                content_text=content_text,
                message_timestamp=message_timestamp,
                observed_at=message_timestamp or observed,
                raw_excerpt=content_text[:500],
                attachment_count=attachment_count,
                warnings=tuple(dict.fromkeys(item_warnings)),
            )
        )
    if not items:
        warnings.append("no_discord_messages_with_text")
    return items, tuple(dict.fromkeys(warnings))


def _load_messages_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _fetch_discord_messages(
    channel_id: str,
    token: str,
    max_messages: int,
    timeout_seconds: int = 15,
) -> tuple[object | None, tuple[str, ...]]:
    query = urlencode({"limit": max(1, min(max_messages, 100))})
    url = f"{DISCORD_API_BASE_URL}/channels/{channel_id}/messages?{query}"
    request = Request(
        url,
        headers={
            "Authorization": f"Bot {token}",
            "Accept": "application/json",
            "User-Agent": "TargetOpportunityMonitor/0.1 DiscordCommentaryCapture",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8")
        return json.loads(text), ()
    except HTTPError as error:
        if error.code == 401:
            return None, ("discord_auth_failed",)
        if error.code == 403:
            return None, ("discord_channel_forbidden",)
        if error.code == 404:
            return None, ("discord_channel_not_found",)
        if error.code == 429:
            return None, ("discord_rate_limited",)
        return None, (f"discord_http_failed:{error.code}",)
    except URLError:
        return None, ("discord_http_failed",)
    except json.JSONDecodeError:
        return None, ("malformed_discord_response",)


def discord_capture_commentary(
    config: AppConfig,
    provider: str = "discord_gateway",
    channel_id: str | None = None,
    messages_json_file: Path | None = None,
    max_messages: int | None = None,
    acknowledge_permission: bool = False,
) -> DiscordCaptureResult:
    if provider != "discord_gateway":
        raise ValueError(f"Unsupported Discord commentary provider: {provider}")

    started_at = _now_iso()
    run_hash = _stable_hash(provider, channel_id, started_at)[:10]
    run_id = f"{provider}_{started_at.replace(':', '').replace('-', '')}_{run_hash}"
    run_date = _today()
    raw_dir = config.trader_commentary_discord_capture_dir / run_date / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    messages_path = raw_dir / "messages.json"
    raw_payload_path = raw_dir / "raw_payload.jsonl"
    metadata_path = raw_dir / "run_metadata.json"

    warnings: list[str] = []
    effective_channel_id = channel_id or (
        config.commentary_discord_capture_channel_ids[0]
        if config.commentary_discord_capture_channel_ids
        else None
    )
    token = os.environ.get(DISCORD_BOT_TOKEN_ENV, "")
    if not config.commentary_discord_capture_enabled:
        warnings.append("discord_capture_config_disabled")
    if config.commentary_discord_capture_require_operator_acknowledgement and not acknowledge_permission:
        warnings.append("discord_operator_acknowledgement_required")
    if not effective_channel_id:
        warnings.append("missing_discord_channel_id")
    if not token and messages_json_file is None:
        warnings.append("missing_discord_bot_token")

    blocked_warnings = {
        "discord_capture_config_disabled",
        "discord_operator_acknowledgement_required",
        "missing_discord_channel_id",
        "missing_discord_bot_token",
    }
    if any(warning in blocked_warnings for warning in warnings):
        status = "blocked"
        completed_at = _now_iso()
        _write_json(messages_path, [])
        _write_json(
            metadata_path,
            {
                "run_id": run_id,
                "provider": provider,
                "channel_id": effective_channel_id,
                "status": status,
                "started_at": started_at,
                "completed_at": completed_at,
                "warnings": list(dict.fromkeys(warnings)),
            },
        )
        upsert_trader_commentary_discord_capture_run(
            config.database_path,
            TraderCommentaryDiscordCaptureRun(
                run_id=run_id,
                provider=provider,
                channel_id=effective_channel_id,
                run_date=run_date,
                started_at=started_at,
                completed_at=completed_at,
                status=status,
                raw_dir=_relative_or_string(raw_dir, config.project_root),
                messages_path=_relative_or_string(messages_path, config.project_root),
                raw_payload_path=None,
                item_count=0,
                stored_count=0,
                skipped_count=0,
                warnings=_warnings_text(tuple(dict.fromkeys(warnings))),
                as_of_date=run_date,
                effective_date=run_date,
            ),
        )
        return DiscordCaptureResult(
            run_id=run_id,
            provider=provider,
            status=status,
            raw_dir=raw_dir,
            item_count=0,
            stored_count=0,
            skipped_count=0,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    if messages_json_file:
        raw_payload = _load_messages_json(messages_json_file)
        warnings.append("discord_messages_json_fixture_used")
    else:
        raw_payload, fetch_warnings = _fetch_discord_messages(
            str(effective_channel_id),
            token,
            max_messages or config.commentary_discord_capture_max_messages_per_run,
        )
        warnings.extend(fetch_warnings)
    if raw_payload is None:
        raw_payload = []

    _write_json(messages_path, raw_payload)
    if isinstance(raw_payload, list):
        raw_payload_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in raw_payload),
            encoding="utf-8",
        )

    upsert_trader_commentary_discord_capture_run(
        config.database_path,
        TraderCommentaryDiscordCaptureRun(
            run_id=run_id,
            provider=provider,
            channel_id=effective_channel_id,
            run_date=run_date,
            started_at=started_at,
            completed_at=None,
            status="running",
            raw_dir=_relative_or_string(raw_dir, config.project_root),
            messages_path=_relative_or_string(messages_path, config.project_root),
            raw_payload_path=(
                _relative_or_string(raw_payload_path, config.project_root)
                if raw_payload_path.exists()
                else None
            ),
            item_count=0,
            stored_count=0,
            skipped_count=0,
            warnings=_warnings_text(tuple(dict.fromkeys(warnings))),
            as_of_date=run_date,
            effective_date=run_date,
        ),
    )

    items, parse_warnings = parse_discord_messages(
        raw_payload,
        str(effective_channel_id) if effective_channel_id else None,
        observed_at=started_at,
    )
    warnings.extend(parse_warnings)
    stored_count = 0
    skipped_count = 0
    stored_payloads: list[dict[str, object]] = []
    for item in items:
        if not item.content_text.strip():
            skipped_count += 1
            continue
        data_warnings = _warnings_text(tuple(dict.fromkeys(item.warnings + tuple(warnings))))
        upsert_trader_commentary_discord_capture_item(
            config.database_path,
            TraderCommentaryDiscordCaptureItem(
                run_id=run_id,
                provider=provider,
                channel_id=item.channel_id,
                guild_id=item.guild_id,
                item_key=item.item_key,
                message_id=item.message_id,
                canonical_url=item.canonical_url,
                author_id=item.author_id,
                author_text=item.author_text,
                content_text=item.content_text,
                message_timestamp=item.message_timestamp,
                observed_at=item.observed_at,
                raw_excerpt=item.raw_excerpt,
                attachment_count=item.attachment_count,
                accepted_flag=1,
                data_warnings=data_warnings,
                as_of_date=run_date,
                effective_date=run_date,
            ),
        )
        stored_count += 1
        stored_payloads.append(
            {
                "item_key": item.item_key,
                "message_id": item.message_id,
                "channel_id": item.channel_id,
                "guild_id": item.guild_id,
                "canonical_url": item.canonical_url,
                "author_text": item.author_text,
                "content_text": item.content_text,
                "message_timestamp": item.message_timestamp,
                "observed_at": item.observed_at,
                "attachment_count": item.attachment_count,
                "warnings": data_warnings,
            }
        )

    status = "ok" if stored_count and not any(w.startswith("discord_") and w.endswith("failed") for w in warnings) else "partial"
    if any(
        warning
        in {
            "discord_auth_failed",
            "discord_channel_forbidden",
            "discord_channel_not_found",
            "discord_rate_limited",
            "malformed_discord_response",
        }
        for warning in warnings
    ):
        status = "partial"
    completed_at = _now_iso()
    _write_json(messages_path, stored_payloads)
    _write_json(
        metadata_path,
        {
            "run_id": run_id,
            "provider": provider,
            "channel_id": effective_channel_id,
            "status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            "item_count": len(items),
            "stored_count": stored_count,
            "skipped_count": skipped_count,
            "warnings": list(dict.fromkeys(warnings)),
        },
    )
    upsert_trader_commentary_discord_capture_run(
        config.database_path,
        TraderCommentaryDiscordCaptureRun(
            run_id=run_id,
            provider=provider,
            channel_id=effective_channel_id,
            run_date=run_date,
            started_at=started_at,
            completed_at=completed_at,
            status=status,
            raw_dir=_relative_or_string(raw_dir, config.project_root),
            messages_path=_relative_or_string(messages_path, config.project_root),
            raw_payload_path=(
                _relative_or_string(raw_payload_path, config.project_root)
                if raw_payload_path.exists()
                else None
            ),
            item_count=len(items),
            stored_count=stored_count,
            skipped_count=skipped_count,
            warnings=_warnings_text(tuple(dict.fromkeys(warnings))),
            as_of_date=run_date,
            effective_date=run_date,
        ),
    )
    return DiscordCaptureResult(
        run_id=run_id,
        provider=provider,
        status=status,
        raw_dir=raw_dir,
        item_count=len(items),
        stored_count=stored_count,
        skipped_count=skipped_count,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def ingest_discord_captured_commentary(
    config: AppConfig,
    provider: str = "discord_gateway",
) -> DiscordCaptureIngestResult:
    items = list_trader_commentary_discord_capture_items(
        config.database_path,
        accepted_only=True,
        uningested_only=True,
        provider=provider,
    )
    imported_count = 0
    skipped_count = 0
    warnings: list[str] = []
    ingested_at = _now_iso()
    for item in items:
        if not item.content_text.strip():
            skipped_count += 1
            continue
        capture_date = (
            (item.message_timestamp or item.observed_at)[:10]
            if (item.message_timestamp or item.observed_at)
            else _today()
        )
        identity_key = "discord_bot_capture:" + _stable_hash(
            item.item_key,
            item.message_id,
            item.content_text,
        )
        notes = f"discord_capture_run={item.run_id}; item_key={item.item_key}"
        commentary_id = upsert_trader_commentary_raw(
            config.database_path,
            TraderCommentaryRaw(
                identity_key=identity_key,
                capture_date=capture_date,
                source="discord_bot_capture",
                source_author=item.author_text or "unknown_discord_author",
                platform="discord",
                permission_scope="authorized_discord_bot_capture",
                language=None,
                raw_text=item.content_text,
                source_url=item.canonical_url,
                capture_id=f"discord_capture:{item.item_key}",
                text_file=None,
                notes=notes,
                data_warnings=item.data_warnings,
                as_of_date=capture_date,
                effective_date=capture_date,
            ),
        )
        if commentary_id:
            imported_count += 1
            mark_trader_commentary_discord_capture_item_ingested(
                config.database_path,
                item.item_key,
                ingested_at,
            )
    if not items:
        warnings.append("no_uningested_discord_capture_items")
    return DiscordCaptureIngestResult(
        imported_count=imported_count,
        skipped_count=skipped_count,
        warnings=tuple(warnings),
    )


def discord_capture_status(config: AppConfig) -> DiscordCaptureStatus:
    run_count = (
        count_rows_by_table(config.database_path, "trader_commentary_discord_capture_runs")
        if config.database_path.exists()
        else 0
    )
    item_count = (
        count_rows_by_table(config.database_path, "trader_commentary_discord_capture_items")
        if config.database_path.exists()
        else 0
    )
    items = (
        list_trader_commentary_discord_capture_items(config.database_path)
        if config.database_path.exists()
        else []
    )
    runs = (
        list_trader_commentary_discord_capture_runs(config.database_path)
        if config.database_path.exists()
        else []
    )
    latest = runs[0] if runs else None
    return DiscordCaptureStatus(
        enabled=config.commentary_discord_capture_enabled,
        provider=config.commentary_discord_capture_provider,
        configured_channel_count=len(config.commentary_discord_capture_channel_ids),
        token_present=bool(os.environ.get(DISCORD_BOT_TOKEN_ENV)),
        capture_dir_exists=config.trader_commentary_discord_capture_dir.exists(),
        run_count=run_count,
        item_count=item_count,
        accepted_item_count=sum(1 for item in items if item.accepted_flag),
        uningested_item_count=sum(1 for item in items if item.accepted_flag and not item.ingested_at),
        latest_run_timestamp=latest_trader_commentary_discord_capture_timestamp(
            config.database_path
        )
        if config.database_path.exists()
        else None,
        latest_status=latest.status if latest else None,
        latest_warnings=latest.warnings if latest else None,
    )


def build_discord_capture_status_text(config: AppConfig) -> str:
    status = discord_capture_status(config)
    lines = [
        "Trader Commentary Discord Capture Status",
        f"Enabled: {status.enabled}",
        f"Provider: {status.provider}",
        f"Configured channels: {status.configured_channel_count}",
        f"Bot token present: {status.token_present}",
        f"Capture directory: {_relative_or_string(config.trader_commentary_discord_capture_dir, config.project_root)}",
        f"Capture directory exists: {status.capture_dir_exists}",
        f"Run rows: {status.run_count}",
        f"Item rows: {status.item_count}",
        f"Accepted item rows: {status.accepted_item_count}",
        f"Uningested item rows: {status.uningested_item_count}",
        f"Latest run timestamp: {status.latest_run_timestamp or 'none'}",
        f"Latest run status: {status.latest_status or 'none'}",
        f"Latest warnings: {status.latest_warnings or 'none'}",
        "Boundary: Discord capture uses authorized bot/API access only; it does not use browser automation, scraping, or private-channel bypasses.",
    ]
    return "\n".join(lines)
