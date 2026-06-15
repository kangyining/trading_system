from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from pathlib import Path
import hashlib
import json
import re

from .config import AppConfig
from .storage import (
    TraderCommentaryBrowserCaptureItem,
    TraderCommentaryBrowserCaptureRun,
    TraderCommentaryRaw,
    count_rows_by_table,
    latest_trader_commentary_browser_capture_timestamp,
    list_trader_commentary_browser_capture_items,
    list_trader_commentary_browser_capture_runs,
    mark_trader_commentary_browser_capture_item_ingested,
    upsert_trader_commentary_browser_capture_item,
    upsert_trader_commentary_browser_capture_run,
    upsert_trader_commentary_raw,
)


X_STATUS_RE = re.compile(
    r"https?://(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]+)/status/([0-9]+)",
    re.IGNORECASE,
)
HANDLE_RE = re.compile(r"@([A-Za-z0-9_]{1,20})")
BLOCK_PAGE_PATTERNS = (
    "captcha",
    "automated requests",
    "unusual traffic",
    "rate limit",
    "sign in to x",
    "log in to x",
    "login to x",
    "something went wrong",
    "try again",
)
BASE_WARNINGS = (
    "browser_capture_fragile",
    "x_api_not_used",
    "capture_may_be_incomplete",
)


@dataclass(frozen=True)
class ParsedBrowserItem:
    item_key: str
    content_text: str
    observed_at: str
    target_url: str | None
    external_id: str | None = None
    canonical_url: str | None = None
    author_text: str | None = None
    created_at_text: str | None = None
    raw_excerpt: str | None = None
    warnings: tuple[str, ...] = BASE_WARNINGS


@dataclass(frozen=True)
class BrowserCaptureResult:
    run_id: str
    provider: str
    status: str
    raw_dir: Path
    item_count: int
    stored_count: int
    skipped_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class BrowserCaptureIngestResult:
    imported_count: int
    skipped_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class BrowserCaptureStatus:
    run_count: int
    item_count: int
    accepted_item_count: int
    uningested_item_count: int
    latest_run_timestamp: str | None
    latest_status: str | None
    latest_warnings: str | None
    capture_dir_exists: bool


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _today() -> str:
    return date.today().isoformat()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_hash(*parts: str | None) -> str:
    return _hash_text("|".join(part or "" for part in parts))


def _relative_or_string(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def _html_to_text(html_text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_text)
    text = re.sub(r"(?s)<br\s*/?>", "\n", text)
    text = re.sub(r"(?s)</p>|</div>|</article>|</span>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _warnings_text(warnings: tuple[str, ...]) -> str | None:
    seen: list[str] = []
    for warning in warnings:
        if warning and warning not in seen:
            seen.append(warning)
    return ", ".join(seen) if seen else None


def _detect_block_warnings(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    warnings: list[str] = []
    if any(pattern in lowered for pattern in BLOCK_PAGE_PATTERNS):
        warnings.append("manual_auth_required")
        warnings.append("capture_may_be_incomplete")
    if "captcha" in lowered or "automated requests" in lowered:
        warnings.append("browser_capture_blocked")
    if "rate limit" in lowered:
        warnings.append("browser_capture_rate_limited")
    return tuple(dict.fromkeys(warnings))


def _clean_content_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    blocked_prefixes = (
        "reply",
        "repost",
        "like",
        "view",
        "views",
        "show more",
        "translate post",
    )
    for line in lines:
        value = line.strip()
        if not value:
            continue
        if X_STATUS_RE.search(value):
            continue
        if value.lower() in blocked_prefixes:
            continue
        if value not in cleaned:
            cleaned.append(value)
    return cleaned


def _extract_items_from_lines(
    lines: list[str],
    target_url: str | None,
    observed_at: str,
) -> list[ParsedBrowserItem]:
    matches: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(lines):
        match = X_STATUS_RE.search(line)
        if match:
            matches.append((index, match))

    items: list[ParsedBrowserItem] = []
    for match_index, (line_index, match) in enumerate(matches):
        next_index = matches[match_index + 1][0] if match_index + 1 < len(matches) else len(lines)
        start_index = max(0, line_index - 4)
        window = lines[start_index:next_index]
        content_lines = _clean_content_lines(window)
        if not content_lines:
            content_lines = [match.group(0)]
        content_text = "\n".join(content_lines).strip()
        author = f"@{match.group(1)}"
        for candidate in reversed(lines[start_index : line_index + 1]):
            handle_match = HANDLE_RE.search(candidate)
            if handle_match:
                author = f"@{handle_match.group(1)}"
                break
        external_id = match.group(2)
        canonical_url = f"https://x.com/{match.group(1)}/status/{external_id}"
        item_key = f"x_browser:{external_id}"
        items.append(
            ParsedBrowserItem(
                item_key=item_key,
                content_text=content_text,
                observed_at=observed_at,
                target_url=target_url,
                external_id=external_id,
                canonical_url=canonical_url,
                author_text=author,
                raw_excerpt=content_text[:500],
            )
        )
    return items


def extract_x_browser_items(
    rendered_text: str,
    target_url: str | None,
    observed_at: str | None = None,
) -> tuple[list[ParsedBrowserItem], tuple[str, ...]]:
    observed = observed_at or _now_iso()
    normalized_text = "\n".join(line.strip() for line in rendered_text.splitlines() if line.strip())
    warnings = tuple(dict.fromkeys(BASE_WARNINGS + _detect_block_warnings(normalized_text)))
    if "browser_capture_blocked" in warnings:
        return [], warnings
    lines = normalized_text.splitlines()
    items = _extract_items_from_lines(lines, target_url, observed)
    if not items and normalized_text:
        warnings = warnings + ("no_post_url_detected",)
    deduped: dict[str, ParsedBrowserItem] = {}
    for item in items:
        key = item.item_key or f"x_browser:{_stable_hash(target_url, item.content_text)[:16]}"
        deduped[key] = item
    return list(deduped.values()), warnings


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def browser_capture_commentary(
    config: AppConfig,
    provider: str = "x_browser",
    target_url: str | None = None,
    dom_text_file: Path | None = None,
    page_html_file: Path | None = None,
    acknowledge_terms_risk: bool = False,
) -> BrowserCaptureResult:
    if provider != "x_browser":
        raise ValueError(f"Unsupported commentary browser capture provider: {provider}")

    started_at = _now_iso()
    run_hash = _stable_hash(provider, target_url, started_at)[:10]
    run_id = f"{provider}_{started_at.replace(':', '').replace('-', '')}_{run_hash}"
    run_date = _today()
    raw_dir = config.trader_commentary_browser_capture_dir / run_date / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    dom_text_path = raw_dir / "dom_text.txt"
    page_html_path = raw_dir / "page.html"
    items_path = raw_dir / "items.json"
    metadata_path = raw_dir / "run_metadata.json"

    warnings: list[str] = []
    if not config.commentary_browser_capture_enabled:
        warnings.append("browser_capture_config_disabled")
    if config.commentary_browser_capture_require_operator_acknowledgement and not acknowledge_terms_risk:
        warnings.append("terms_risk_acknowledgement_required")
        status = "blocked"
        completed_at = _now_iso()
        _write_json(items_path, [])
        _write_json(
            metadata_path,
            {
                "run_id": run_id,
                "provider": provider,
                "target_url": target_url,
                "status": status,
                "started_at": started_at,
                "completed_at": completed_at,
                "warnings": warnings,
            },
        )
        upsert_trader_commentary_browser_capture_run(
            config.database_path,
            TraderCommentaryBrowserCaptureRun(
                run_id=run_id,
                provider=provider,
                target_url=target_url,
                run_date=run_date,
                started_at=started_at,
                completed_at=completed_at,
                status=status,
                raw_dir=_relative_or_string(raw_dir, config.project_root),
                dom_text_path=None,
                page_html_path=None,
                item_count=0,
                stored_count=0,
                skipped_count=0,
                warnings=_warnings_text(tuple(warnings)),
                as_of_date=run_date,
                effective_date=run_date,
            ),
        )
        return BrowserCaptureResult(
            run_id=run_id,
            provider=provider,
            status=status,
            raw_dir=raw_dir,
            item_count=0,
            stored_count=0,
            skipped_count=0,
            warnings=tuple(warnings),
        )

    configured_targets = config.commentary_browser_capture_target_urls
    effective_target_url = target_url or (configured_targets[0] if configured_targets else None)
    if not effective_target_url:
        warnings.append("missing_target_url")

    rendered_text = ""
    html_text = ""
    if dom_text_file:
        rendered_text = dom_text_file.read_text(encoding="utf-8-sig")
    if page_html_file:
        html_text = page_html_file.read_text(encoding="utf-8-sig")
        if not rendered_text:
            rendered_text = _html_to_text(html_text)

    if not rendered_text:
        warnings.extend(("manual_auth_required", "external_browser_artifact_required"))

    dom_text_path.write_text(rendered_text, encoding="utf-8")
    if html_text:
        page_html_path.write_text(html_text, encoding="utf-8")

    upsert_trader_commentary_browser_capture_run(
        config.database_path,
        TraderCommentaryBrowserCaptureRun(
            run_id=run_id,
            provider=provider,
            target_url=effective_target_url,
            run_date=run_date,
            started_at=started_at,
            completed_at=None,
            status="running",
            raw_dir=_relative_or_string(raw_dir, config.project_root),
            dom_text_path=_relative_or_string(dom_text_path, config.project_root),
            page_html_path=(
                _relative_or_string(page_html_path, config.project_root)
                if html_text
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

    items, parse_warnings = extract_x_browser_items(
        rendered_text,
        effective_target_url,
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
        upsert_trader_commentary_browser_capture_item(
            config.database_path,
            TraderCommentaryBrowserCaptureItem(
                run_id=run_id,
                provider=provider,
                target_url=effective_target_url,
                item_key=item.item_key,
                external_id=item.external_id,
                canonical_url=item.canonical_url,
                author_text=item.author_text,
                content_text=item.content_text,
                created_at_text=item.created_at_text,
                observed_at=item.observed_at,
                raw_excerpt=item.raw_excerpt,
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
                "external_id": item.external_id,
                "canonical_url": item.canonical_url,
                "author_text": item.author_text,
                "content_text": item.content_text,
                "observed_at": item.observed_at,
                "warnings": data_warnings,
            }
        )

    status = "ok" if stored_count else "partial"
    if "manual_auth_required" in warnings or "external_browser_artifact_required" in warnings:
        status = "partial"
    completed_at = _now_iso()
    _write_json(items_path, stored_payloads)
    _write_json(
        metadata_path,
        {
            "run_id": run_id,
            "provider": provider,
            "target_url": effective_target_url,
            "status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            "item_count": len(items),
            "stored_count": stored_count,
            "skipped_count": skipped_count,
            "warnings": list(dict.fromkeys(warnings)),
        },
    )
    upsert_trader_commentary_browser_capture_run(
        config.database_path,
        TraderCommentaryBrowserCaptureRun(
            run_id=run_id,
            provider=provider,
            target_url=effective_target_url,
            run_date=run_date,
            started_at=started_at,
            completed_at=completed_at,
            status=status,
            raw_dir=_relative_or_string(raw_dir, config.project_root),
            dom_text_path=_relative_or_string(dom_text_path, config.project_root),
            page_html_path=(
                _relative_or_string(page_html_path, config.project_root)
                if html_text
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
    return BrowserCaptureResult(
        run_id=run_id,
        provider=provider,
        status=status,
        raw_dir=raw_dir,
        item_count=len(items),
        stored_count=stored_count,
        skipped_count=skipped_count,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def ingest_browser_captured_commentary(
    config: AppConfig,
    provider: str = "x_browser",
) -> BrowserCaptureIngestResult:
    items = list_trader_commentary_browser_capture_items(
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
        capture_date = item.observed_at[:10] if item.observed_at else _today()
        identity_key = "x_browser_capture:" + _stable_hash(item.item_key, item.content_text)
        notes = f"browser_capture_run={item.run_id}; item_key={item.item_key}"
        commentary_id = upsert_trader_commentary_raw(
            config.database_path,
            TraderCommentaryRaw(
                identity_key=identity_key,
                capture_date=capture_date,
                source="x_browser_capture",
                source_author=item.author_text or "unknown_x_author",
                platform="x",
                permission_scope="public_browser_capture",
                language=None,
                raw_text=item.content_text,
                source_url=item.canonical_url or item.target_url,
                capture_id=f"browser_capture:{item.item_key}",
                text_file=None,
                notes=notes,
                data_warnings=item.data_warnings,
                as_of_date=capture_date,
                effective_date=capture_date,
            ),
        )
        if commentary_id:
            imported_count += 1
            mark_trader_commentary_browser_capture_item_ingested(
                config.database_path,
                item.item_key,
                ingested_at,
            )
    if not items:
        warnings.append("no_uningested_browser_capture_items")
    return BrowserCaptureIngestResult(
        imported_count=imported_count,
        skipped_count=skipped_count,
        warnings=tuple(warnings),
    )


def browser_capture_status(config: AppConfig) -> BrowserCaptureStatus:
    run_count = (
        count_rows_by_table(config.database_path, "trader_commentary_browser_capture_runs")
        if config.database_path.exists()
        else 0
    )
    item_count = (
        count_rows_by_table(config.database_path, "trader_commentary_browser_capture_items")
        if config.database_path.exists()
        else 0
    )
    items = (
        list_trader_commentary_browser_capture_items(config.database_path)
        if config.database_path.exists()
        else []
    )
    runs = (
        list_trader_commentary_browser_capture_runs(config.database_path)
        if config.database_path.exists()
        else []
    )
    latest = runs[0] if runs else None
    return BrowserCaptureStatus(
        run_count=run_count,
        item_count=item_count,
        accepted_item_count=sum(1 for item in items if item.accepted_flag),
        uningested_item_count=sum(1 for item in items if item.accepted_flag and not item.ingested_at),
        latest_run_timestamp=latest_trader_commentary_browser_capture_timestamp(
            config.database_path
        )
        if config.database_path.exists()
        else None,
        latest_status=latest.status if latest else None,
        latest_warnings=latest.warnings if latest else None,
        capture_dir_exists=config.trader_commentary_browser_capture_dir.exists(),
    )


def build_browser_capture_status_text(config: AppConfig) -> str:
    status = browser_capture_status(config)
    lines = [
        "Trader Commentary Browser Capture Status",
        f"Enabled: {config.commentary_browser_capture_enabled}",
        f"Provider: {config.commentary_browser_capture_provider}",
        f"Target URLs: {', '.join(config.commentary_browser_capture_target_urls) if config.commentary_browser_capture_target_urls else 'none'}",
        f"Capture directory: {_relative_or_string(config.trader_commentary_browser_capture_dir, config.project_root)}",
        f"Capture directory exists: {status.capture_dir_exists}",
        f"Run rows: {status.run_count}",
        f"Item rows: {status.item_count}",
        f"Accepted item rows: {status.accepted_item_count}",
        f"Uningested item rows: {status.uningested_item_count}",
        f"Latest run timestamp: {status.latest_run_timestamp or 'none'}",
        f"Latest run status: {status.latest_status or 'none'}",
        f"Latest warnings: {status.latest_warnings or 'none'}",
        "Boundary: X browser capture is opt-in, low-frequency, and never bypasses login, captcha, rate limits, or technical restrictions.",
        "Discord boundary: use an official bot/Gateway route later; browser capture is not used for Discord.",
    ]
    return "\n".join(lines)
