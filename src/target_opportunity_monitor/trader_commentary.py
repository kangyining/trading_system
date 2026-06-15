from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import date
import hashlib
from io import StringIO
from pathlib import Path
import re

from .config import AppConfig
from .commentary_onboarding import commentary_label_disposition_map
from .storage import (
    Price,
    Signal,
    StoredTraderCommentaryClaim,
    TraderCommentaryClaim,
    TraderCommentaryClaimOutcome,
    TraderCommentaryRaw,
    count_rows_by_table,
    list_assets,
    list_prices,
    list_trader_commentary_claim_outcomes,
    list_trader_commentary_claims,
    list_trader_commentary_raw,
    normalize_asset_role,
    normalize_ticker,
    trader_commentary_alias_map,
    trader_commentary_statuses,
    upsert_signal,
    upsert_trader_commentary_claim,
    upsert_trader_commentary_claim_outcome,
    upsert_trader_commentary_raw,
)


TRADER_COMMENTARY_HEADER = (
    "capture_date",
    "source",
    "source_author",
    "platform",
    "permission_scope",
    "language",
    "raw_text",
    "source_url",
    "capture_id",
    "text_file",
    "notes",
    "as_of_date",
    "effective_date",
)

HORIZONS = (1, 5, 20, 60)
CLAIM_VALIDATION_MODEL_VERSION = "trader_commentary_validation_mvp_v1"
TOKEN_EXCLUSIONS = {
    "A",
    "AI",
    "AM",
    "BUY",
    "CALL",
    "CPI",
    "ETF",
    "FOMC",
    "GDP",
    "HIGH",
    "IPO",
    "LOW",
    "LOWER",
    "NAV",
    "PUT",
    "SELL",
    "VIP",
}


@dataclass(frozen=True)
class TraderCommentaryInput:
    capture_date: str
    source: str
    source_author: str
    platform: str
    permission_scope: str
    language: str | None = None
    raw_text: str | None = None
    source_url: str | None = None
    capture_id: str | None = None
    text_file: str | None = None
    notes: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None
    data_warnings: str | None = None


@dataclass(frozen=True)
class TraderCommentaryLoadResult:
    loaded_count: int
    skipped_count: int
    warnings: tuple[str, ...]
    path: Path


@dataclass(frozen=True)
class TraderCommentaryTemplateResult:
    csv_path: Path
    text_path: Path


@dataclass(frozen=True)
class TraderCommentaryParseResult:
    parsed_count: int
    skipped_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class TraderCommentaryValidationItem:
    claim_key: str
    ticker: str | None
    claim_type: str
    status: str
    outcome_status: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class TraderCommentaryValidationResult:
    updated_count: int
    skipped_count: int
    warnings: tuple[str, ...]
    results: tuple[TraderCommentaryValidationItem, ...]


def ensure_trader_commentary_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(TRADER_COMMENTARY_HEADER)


def export_trader_commentary_template(config: AppConfig) -> TraderCommentaryTemplateResult:
    config.trader_commentary_exports_dir.mkdir(parents=True, exist_ok=True)
    csv_path = config.trader_commentary_exports_dir / "trader_commentary_template.csv"
    text_path = config.trader_commentary_exports_dir / "trader_commentary_capture_template.txt"
    text_path.write_text(
        "\n".join(
            (
                "Paste one authorized trader commentary capture here.",
                "Keep original wording where possible.",
                "Do not add prices, tickers, or claims that were not in the source.",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRADER_COMMENTARY_HEADER)
        writer.writeheader()
        writer.writerow(
            {
                "capture_date": _today(),
                "source": "user_paste",
                "source_author": "unknown_trader",
                "platform": "wechat_or_chat_capture",
                "permission_scope": "user_provided_private_capture",
                "language": "zh",
                "raw_text": "",
                "source_url": "",
                "capture_id": "capture_template_001",
                "text_file": text_path.name,
                "notes": "Replace this template row with a real authorized capture.",
                "as_of_date": _today(),
                "effective_date": _today(),
            }
        )
    return TraderCommentaryTemplateResult(csv_path=csv_path, text_path=text_path)


def _today() -> str:
    return date.today().isoformat()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _row_value(row: dict[str, str], name: str) -> str | None:
    for key, value in row.items():
        if key and key.strip().lower() == name.lower():
            cleaned = (value or "").strip()
            return cleaned or None
    return None


def _join(values: list[str] | tuple[str, ...]) -> str | None:
    cleaned: list[str] = []
    for value in values:
        for part in str(value).split(","):
            item = part.strip()
            if item and item not in cleaned:
                cleaned.append(item)
    return ",".join(cleaned) if cleaned else None


def _identity_key(row: TraderCommentaryInput) -> str:
    basis = "|".join(
        (
            row.capture_date,
            row.source,
            row.source_author,
            row.platform,
            row.permission_scope,
            row.source_url or "",
            row.capture_id or "",
            row.text_file or "",
            hashlib.sha256((row.raw_text or "").encode("utf-8")).hexdigest(),
        )
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _claim_key(parts: tuple[object, ...]) -> str:
    basis = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _read_text_file(config: AppConfig, csv_path: Path, text_file: str) -> tuple[str | None, str | None]:
    candidate = Path(text_file)
    candidates = [candidate] if candidate.is_absolute() else [
        csv_path.parent / candidate,
        config.trader_commentary_exports_dir / candidate,
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8-sig"), None
    return None, "missing_text_file"


def parse_trader_commentary_csv(
    text: str,
    config: AppConfig,
    path: Path | None = None,
) -> list[TraderCommentaryInput]:
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("Trader commentary CSV is missing a header row.")
    fieldnames = {field.strip().lower() for field in reader.fieldnames if field}
    required = {"capture_date", "source", "source_author", "platform", "permission_scope"}
    missing = required - fieldnames
    if missing:
        raise ValueError(
            "Trader commentary CSV missing required columns: "
            + ", ".join(sorted(missing))
        )

    rows: list[TraderCommentaryInput] = []
    csv_path = path or config.trader_commentary_path
    for row_number, row in enumerate(reader, start=2):
        warnings: list[str] = []
        capture_date = _row_value(row, "capture_date")
        source = _row_value(row, "source")
        source_author = _row_value(row, "source_author")
        platform = _row_value(row, "platform")
        permission_scope = _row_value(row, "permission_scope")
        if not all((capture_date, source, source_author, platform, permission_scope)):
            raise ValueError(f"Trader commentary CSV row {row_number} missing source metadata.")
        if _parse_date(capture_date) is None:
            raise ValueError(f"Trader commentary CSV row {row_number} has malformed capture_date.")

        raw_text = _row_value(row, "raw_text")
        text_file = _row_value(row, "text_file")
        source_url = _row_value(row, "source_url")
        capture_id = _row_value(row, "capture_id")
        if text_file:
            loaded_text, warning = _read_text_file(config, csv_path, text_file)
            if loaded_text:
                raw_text = loaded_text
            if warning:
                warnings.append(warning)
        if not any((raw_text, text_file, source_url, capture_id)):
            raise ValueError(
                f"Trader commentary CSV row {row_number} needs raw_text, text_file, "
                "source_url, or capture_id."
            )
        if not raw_text:
            warnings.append("missing_raw_text")

        rows.append(
            TraderCommentaryInput(
                capture_date=capture_date,
                source=source or "",
                source_author=source_author or "",
                platform=platform or "",
                permission_scope=permission_scope or "",
                language=_row_value(row, "language"),
                raw_text=raw_text,
                source_url=source_url,
                capture_id=capture_id,
                text_file=text_file,
                notes=_row_value(row, "notes"),
                as_of_date=_row_value(row, "as_of_date"),
                effective_date=_row_value(row, "effective_date") or capture_date,
                data_warnings=_join(warnings),
            )
        )
    return rows


def load_trader_commentary_csv(
    config: AppConfig,
    path: Path | None = None,
) -> TraderCommentaryLoadResult:
    commentary_path = path or config.trader_commentary_path
    ensure_trader_commentary_csv_header(commentary_path)
    config.trader_commentary_exports_dir.mkdir(parents=True, exist_ok=True)
    rows = parse_trader_commentary_csv(
        commentary_path.read_text(encoding="utf-8-sig"),
        config,
        commentary_path,
    )
    warnings: list[str] = []
    loaded = 0
    for row in rows:
        upsert_trader_commentary_raw(
            config.database_path,
            TraderCommentaryRaw(
                identity_key=_identity_key(row),
                capture_date=row.capture_date,
                source=row.source,
                source_author=row.source_author,
                platform=row.platform,
                permission_scope=row.permission_scope,
                language=row.language,
                raw_text=row.raw_text,
                source_url=row.source_url,
                capture_id=row.capture_id,
                text_file=row.text_file,
                notes=row.notes,
                data_warnings=row.data_warnings,
                as_of_date=row.as_of_date or _today(),
                effective_date=row.effective_date or row.capture_date,
            ),
        )
        loaded += 1
        if row.data_warnings:
            warnings.append(f"{row.capture_date}:{row.data_warnings}")
    if not rows:
        warnings.append("empty_trader_commentary")
    return TraderCommentaryLoadResult(
        loaded_count=loaded,
        skipped_count=0,
        warnings=tuple(warnings),
        path=commentary_path,
    )


def _segments(text: str) -> list[str]:
    return [
        segment.strip()
        for segment in re.split(r"[\n。！？!?；;]+", text)
        if segment.strip()
    ]


def _numbers(segment: str) -> list[float]:
    return [float(match) for match in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", segment)]


def _ranges(segment: str) -> list[tuple[float, float]]:
    ranges: list[tuple[float, float]] = []
    for left, right in re.findall(
        r"(\d+(?:\.\d+)?)\s*(?:-|~|到|至)\s*(\d+(?:\.\d+)?)",
        segment,
    ):
        low, high = sorted((float(left), float(right)))
        ranges.append((low, high))
    return ranges


def _extract_tickers(segment: str) -> list[str]:
    tickers: list[str] = []
    for match in re.findall(
        r"(?<![A-Za-z0-9])([A-Za-z]{1,5}(?:\.[A-Za-z])?)(?![A-Za-z0-9])",
        segment,
    ):
        ticker = normalize_ticker(match)
        if ticker in TOKEN_EXCLUSIONS:
            continue
        if ticker not in tickers:
            tickers.append(ticker)
    return tickers


def _instrument_label(segment: str) -> str | None:
    if "大盘" in segment:
        return "大盘"
    if re.search(r"\bmarket\b|\bindex\b", segment, re.IGNORECASE):
        return "market"
    return None


def _first_range_or_number(segment: str) -> tuple[float | None, float | None]:
    ranges = _ranges(segment)
    if ranges:
        return ranges[0]
    numbers = _numbers(segment)
    if numbers:
        return numbers[0], numbers[0]
    return None, None


def _last_range_or_number(segment: str) -> tuple[float | None, float | None]:
    ranges = _ranges(segment)
    if ranges:
        return ranges[-1]
    numbers = _numbers(segment)
    if numbers:
        return numbers[-1], numbers[-1]
    return None, None


def _claim_targets(segment: str) -> list[str | None]:
    tickers = _extract_tickers(segment)
    label = _instrument_label(segment)
    if tickers:
        return tickers
    return [label] if label else [None]


def _add_claim(
    claims: list[TraderCommentaryClaim],
    *,
    raw,
    segment: str,
    target: str | None,
    claim_type: str,
    direction: str | None,
    level_low: float | None = None,
    level_high: float | None = None,
    target_price: float | None = None,
    risk_level: float | None = None,
    strike_price: float | None = None,
    premium: float | None = None,
    warning: str | None = None,
) -> None:
    ticker = None
    instrument_label = None
    if target and re.match(r"^[A-Z]{1,5}(?:\.[A-Z])?$", target):
        ticker = target
    elif target:
        instrument_label = target
    elif _instrument_label(segment):
        instrument_label = _instrument_label(segment)
    warnings = [warning] if warning else []
    if instrument_label and ticker is None:
        warnings.append("unmapped_instrument")
    claim_key = _claim_key(
        (
            raw.commentary_id,
            claim_type,
            ticker,
            instrument_label,
            level_low,
            level_high,
            target_price,
            risk_level,
            strike_price,
            premium,
            segment[:220],
        )
    )
    claims.append(
        TraderCommentaryClaim(
            claim_key=claim_key,
            commentary_id=raw.commentary_id,
            claim_date=raw.capture_date,
            ticker=ticker,
            instrument_label=instrument_label,
            claim_type=claim_type,
            direction=direction,
            level_low=level_low,
            level_high=level_high,
            target_price=target_price,
            risk_level=risk_level,
            strike_price=strike_price,
            premium=premium,
            condition_text=segment[:500],
            raw_excerpt=segment[:500],
            parser_warnings=_join(warnings),
            source=raw.source,
            source_url=raw.source_url,
            model_version="trader_commentary_mvp_v1",
            as_of_date=_today(),
            effective_date=raw.capture_date,
        )
    )


def _parse_segment(raw, segment: str) -> list[TraderCommentaryClaim]:
    claims: list[TraderCommentaryClaim] = []
    targets = _claim_targets(segment)
    lower = segment.lower()
    ranges = _ranges(segment)
    numbers = _numbers(segment)

    sell_put_match = re.search(
        r"sell\s+put\s+([A-Za-z]{1,5}(?:\.[A-Za-z])?)\s*(\d+(?:\.\d+)?)?",
        segment,
        re.IGNORECASE,
    )
    if sell_put_match:
        ticker = normalize_ticker(sell_put_match.group(1))
        strike = float(sell_put_match.group(2)) if sell_put_match.group(2) else None
        premium = None
        if strike is not None:
            after_strike = [value for value in numbers if value != strike]
            premium = after_strike[0] if after_strike else None
        _add_claim(
            claims,
            raw=raw,
            segment=segment,
            target=ticker,
            claim_type="options_income_idea",
            direction="neutral",
            strike_price=strike,
            premium=premium,
            warning="options_proxy_only",
        )
        return claims

    if any(keyword in segment for keyword in ("支撑", "support")):
        low, high = _first_range_or_number(segment)
        for target in targets:
            _add_claim(
                claims,
                raw=raw,
                segment=segment,
                target=target,
                claim_type="technical_support_hold",
                direction="positive",
                level_low=low,
                level_high=high,
            )

    if any(keyword in segment for keyword in ("压力", "阻力", "resistance")):
        low, high = _first_range_or_number(segment)
        claim_type = (
            "market_resistance_breakout"
            if any(keyword in segment for keyword in ("突破", "break"))
            else "technical_resistance_watch"
        )
        for target in targets:
            _add_claim(
                claims,
                raw=raw,
                segment=segment,
                target=target,
                claim_type=claim_type,
                direction="positive" if claim_type.endswith("breakout") else "neutral",
                level_low=low,
                level_high=high,
            )

    if any(keyword in segment for keyword in ("目标", "target")) or re.search(r"看\s*\d", segment):
        low, high = _last_range_or_number(segment)
        target_price = high if high is not None else low
        for target in targets:
            _add_claim(
                claims,
                raw=raw,
                segment=segment,
                target=target,
                claim_type="ticker_price_target",
                direction="positive",
                level_low=low,
                level_high=high,
                target_price=target_price,
            )

    if (
        any(keyword in segment for keyword in ("回调", "跌幅", "跌到", "downside", "risk"))
        and "支撑" not in segment
    ):
        low, high = _last_range_or_number(segment)
        risk_level = low if low is not None else high
        for target in targets:
            _add_claim(
                claims,
                raw=raw,
                segment=segment,
                target=target,
                claim_type="downside_level_watch",
                direction="negative",
                risk_level=risk_level,
            )

    if any(keyword in segment for keyword in ("买进", "可以买", "buy", "加仓")):
        for target in targets:
            _add_claim(
                claims,
                raw=raw,
                segment=segment,
                target=target,
                claim_type="position_action",
                direction="positive",
            )

    if any(keyword in segment for keyword in ("减仓", "防守", "reduce", "trim")):
        for target in targets:
            _add_claim(
                claims,
                raw=raw,
                segment=segment,
                target=target,
                claim_type="risk_reduction_instruction",
                direction="negative",
            )

    if any(keyword in segment for keyword in ("板块", "sector", "rotation", "XLV", "XLF")):
        for target in targets:
            _add_claim(
                claims,
                raw=raw,
                segment=segment,
                target=target,
                claim_type="sector_rotation_view",
                direction="neutral",
            )

    if any(keyword in segment for keyword in ("CPI", "伊朗", "业绩", "会议", "catalyst")):
        for target in targets:
            _add_claim(
                claims,
                raw=raw,
                segment=segment,
                target=target,
                claim_type="catalyst_watch",
                direction="neutral",
            )

    if not claims and ranges and ("突破" in segment or "break" in lower):
        low, high = ranges[0]
        for target in targets:
            _add_claim(
                claims,
                raw=raw,
                segment=segment,
                target=target,
                claim_type="technical_resistance_watch",
                direction="positive",
                level_low=low,
                level_high=high,
            )
    return claims


def _score_for_claim(claim: StoredTraderCommentaryClaim) -> float:
    if claim.claim_type == "risk_reduction_instruction":
        return 40.0
    if claim.claim_type == "downside_level_watch":
        return 35.0
    if claim.claim_type == "options_income_idea":
        return 50.0
    if claim.direction == "positive":
        return 65.0
    if claim.direction == "negative":
        return 35.0
    return 50.0


def _direction_for_score(score: float) -> str:
    if score >= 60:
        return "positive"
    if score <= 40:
        return "negative"
    return "neutral"


def _write_shadow_signals(config: AppConfig, ticker: str) -> int:
    claims = list_trader_commentary_claims(config.database_path, ticker=ticker)
    if not claims:
        return 0
    latest_date = max(claim.claim_date for claim in claims)
    latest_claims = [claim for claim in claims if claim.claim_date == latest_date]
    claim_scores = [_score_for_claim(claim) for claim in latest_claims]
    composite = sum(claim_scores) / len(claim_scores) if claim_scores else 50.0
    warnings = ["trader_commentary_shadow_mode"]
    for claim in latest_claims:
        if claim.parser_warnings:
            warnings.extend(item for item in claim.parser_warnings.split(",") if item)
    by_name = {
        "trader_commentary.levels": [
            claim for claim in latest_claims if claim.level_low is not None or claim.target_price is not None
        ],
        "trader_commentary.direction": [
            claim for claim in latest_claims if claim.direction in {"positive", "negative"}
        ],
        "trader_commentary.action": [
            claim for claim in latest_claims if "action" in claim.claim_type or "instruction" in claim.claim_type
        ],
        "trader_commentary.composite": latest_claims,
    }
    written = 0
    for signal_name, signal_claims in by_name.items():
        if not signal_claims:
            continue
        score = (
            composite
            if signal_name.endswith("composite")
            else sum(_score_for_claim(claim) for claim in signal_claims) / len(signal_claims)
        )
        upsert_signal(
            config.database_path,
            Signal(
                ticker=ticker,
                signal_date=latest_date,
                signal_name=signal_name,
                signal_family="trader_commentary",
                value=score,
                score=score,
                direction=_direction_for_score(score),
                reason_code=",".join(sorted({claim.claim_type for claim in signal_claims})),
                source="trader_commentary",
                model_version=config.signals_trader_commentary_model_version,
                confidence=45.0,
                data_warnings=_join(warnings),
                notes=f"{len(signal_claims)} parsed commentary claims",
                as_of_date=_today(),
                effective_date=latest_date,
            ),
        )
        written += 1
    return written


def parse_trader_commentary_claims(
    config: AppConfig,
    commentary_id: int | None = None,
    ticker: str | None = None,
) -> TraderCommentaryParseResult:
    rows = list_trader_commentary_raw(config.database_path, commentary_id=commentary_id)
    wanted_ticker = normalize_ticker(ticker) if ticker else None
    warnings: list[str] = []
    parsed_count = 0
    skipped_count = 0
    affected_tickers: set[str] = set()
    for raw in rows:
        if not raw.raw_text:
            skipped_count += 1
            warnings.append(f"{raw.commentary_id}:missing_raw_text")
            continue
        raw_claims: list[TraderCommentaryClaim] = []
        recent_tickers: list[str] = []
        for segment in _segments(raw.raw_text):
            segment_tickers = _extract_tickers(segment)
            segment_claims = _parse_segment(raw, segment)
            if segment_claims and recent_tickers:
                inherited_claims: list[TraderCommentaryClaim] = []
                for claim in segment_claims:
                    if (
                        claim.ticker is None
                        and claim.instrument_label is None
                        and claim.claim_type
                        in {
                            "ticker_price_target",
                            "position_action",
                            "risk_reduction_instruction",
                            "downside_level_watch",
                            "technical_resistance_watch",
                            "market_resistance_breakout",
                            "technical_support_hold",
                        }
                    ):
                        inherited_ticker = recent_tickers[0]
                        inherited_claims.append(
                            replace(
                                claim,
                                ticker=inherited_ticker,
                                claim_key=_claim_key(
                                    (
                                        claim.commentary_id,
                                        claim.claim_type,
                                        inherited_ticker,
                                        claim.instrument_label,
                                        claim.level_low,
                                        claim.level_high,
                                        claim.target_price,
                                        claim.risk_level,
                                        claim.strike_price,
                                        claim.premium,
                                        (claim.raw_excerpt or "")[:220],
                                    )
                                ),
                            )
                        )
                    else:
                        inherited_claims.append(claim)
                segment_claims = inherited_claims
            raw_claims.extend(segment_claims)
            if segment_tickers:
                recent_tickers = segment_tickers
        if wanted_ticker:
            raw_claims = [claim for claim in raw_claims if claim.ticker == wanted_ticker]
        if not raw_claims:
            skipped_count += 1
            warnings.append(f"{raw.commentary_id}:no_structured_claims")
            continue
        for claim in raw_claims:
            upsert_trader_commentary_claim(config.database_path, claim)
            parsed_count += 1
            if claim.ticker:
                affected_tickers.add(claim.ticker)
            if claim.parser_warnings:
                warnings.append(f"{claim.claim_key[:8]}:{claim.parser_warnings}")
    for ticker_symbol in sorted(affected_tickers):
        _write_shadow_signals(config, ticker_symbol)
    return TraderCommentaryParseResult(
        parsed_count=parsed_count,
        skipped_count=skipped_count,
        warnings=tuple(warnings),
    )


def _price_value(price: Price) -> float | None:
    return price.adjusted_close if price.adjusted_close is not None else price.close


def _entry_price(claim: StoredTraderCommentaryClaim, prices: list[Price]) -> tuple[float | None, str | None, list[str]]:
    warnings: list[str] = []
    claim_date = _parse_date(claim.claim_date)
    if claim_date is None:
        warnings.append("malformed_claim_date")
        return None, None, warnings
    eligible = [
        price
        for price in prices
        if (price_date := _parse_date(price.price_date)) is not None
        and price_date <= claim_date
        and _price_value(price) is not None
    ]
    if not eligible:
        warnings.append("missing_entry_price")
        return None, claim.claim_date, warnings
    entry = eligible[-1]
    return _price_value(entry), entry.price_date, warnings


def _future_prices(prices: list[Price], entry_price_date: str | None) -> list[Price]:
    entry_date = _parse_date(entry_price_date)
    if entry_date is None:
        return []
    return [
        price
        for price in prices
        if (price_date := _parse_date(price.price_date)) is not None and price_date > entry_date
    ]


def _latest_price(prices: list[Price]) -> tuple[float | None, str | None]:
    priced = [price for price in prices if _price_value(price) is not None]
    if not priced:
        return None, None
    latest = priced[-1]
    return _price_value(latest), latest.price_date


def _horizon_returns(future_prices: list[Price], entry_price: float) -> tuple[dict[int, float | None], list[str], list[str]]:
    returns: dict[int, float | None] = {}
    completed: list[str] = []
    pending: list[str] = []
    priced = [price for price in future_prices if _price_value(price) is not None]
    for horizon in HORIZONS:
        label = f"{horizon}d"
        if len(priced) >= horizon:
            horizon_price = _price_value(priced[horizon - 1])
            returns[horizon] = horizon_price / entry_price - 1 if horizon_price is not None else None
            completed.append(label)
        else:
            returns[horizon] = None
            pending.append(label)
    return returns, completed, pending


def _outcome_status(completed: list[str], pending: list[str], entry_price: float | None) -> str:
    if entry_price is None:
        return "missing_entry"
    if not completed:
        return "pending"
    if pending:
        return "partial"
    return "completed"


def _level_hit(claim: StoredTraderCommentaryClaim, future_prices: list[Price]) -> tuple[int | None, str]:
    if not future_prices:
        return None, "pending"
    highs = [price.high for price in future_prices if price.high is not None]
    lows = [price.low for price in future_prices if price.low is not None]
    closes = [_price_value(price) for price in future_prices if _price_value(price) is not None]
    if claim.claim_type == "technical_support_hold" and claim.level_low is not None and lows:
        return (1, "hit") if min(lows) >= claim.level_low else (0, "miss")
    if claim.claim_type in {"technical_resistance_watch", "market_resistance_breakout"} and claim.level_high is not None:
        crossed = (highs and max(highs) >= claim.level_high) or (
            closes and max(closes) >= claim.level_high
        )
        return (1, "hit") if crossed else (0, "miss")
    if claim.claim_type == "ticker_price_target" and claim.target_price is not None:
        if claim.direction == "negative" and lows:
            return (1, "hit") if min(lows) <= claim.target_price else (0, "miss")
        if highs:
            return (1, "hit") if max(highs) >= claim.target_price else (0, "miss")
    if claim.claim_type == "downside_level_watch" and claim.risk_level is not None and lows:
        return (1, "hit") if min(lows) <= claim.risk_level else (0, "miss")
    return None, "not_applicable"


def _directional_hit(claim: StoredTraderCommentaryClaim, returns: dict[int, float | None], completed: list[str]) -> tuple[int | None, str]:
    if claim.direction not in {"positive", "negative"}:
        return None, "neutral"
    if not completed:
        return None, "pending"
    for horizon in (60, 20, 5, 1):
        value = returns.get(horizon)
        if value is not None:
            if claim.direction == "positive":
                return (1, "hit") if value > 0 else (0, "miss")
            return (1, "hit") if value < 0 else (0, "miss")
    return None, "pending"


def _evaluate_claim_outcome(
    claim: StoredTraderCommentaryClaim,
    prices: list[Price],
    asset_type: str | None,
) -> TraderCommentaryClaimOutcome:
    warnings: list[str] = []
    if asset_type == "etf":
        warnings.append("etf_trader_commentary_validation_gated")
    if claim.instrument_label and not claim.ticker:
        warnings.append("unmapped_instrument")
    if claim.claim_type == "options_income_idea":
        warnings.append("options_proxy_only")
    entry_price, entry_price_date, entry_warnings = _entry_price(claim, prices)
    warnings.extend(entry_warnings)
    latest_price, latest_price_date = _latest_price(prices)
    future = _future_prices(prices, entry_price_date)
    if not prices:
        warnings.append("missing_price_history")
    elif not future:
        warnings.append("pending_future_prices")
    returns = {horizon: None for horizon in HORIZONS}
    completed: list[str] = []
    pending = [f"{horizon}d" for horizon in HORIZONS]
    if entry_price not in (None, 0):
        returns, completed, pending = _horizon_returns(future, entry_price)
    level_flag, level_status = _level_hit(claim, future)
    directional_flag, directional_status = _directional_hit(claim, returns, completed)
    hit_status = level_status if level_status != "not_applicable" else directional_status
    return TraderCommentaryClaimOutcome(
        claim_id=claim.claim_id,
        claim_key=claim.claim_key,
        ticker=claim.ticker,
        instrument_label=claim.instrument_label,
        claim_type=claim.claim_type,
        claim_date=claim.claim_date,
        outcome_date=_today(),
        outcome_status=_outcome_status(completed, pending, entry_price),
        entry_price=entry_price,
        entry_price_date=entry_price_date,
        latest_price=latest_price,
        latest_price_date=latest_price_date,
        completed_horizons=_join(completed),
        pending_horizons=_join(pending),
        return_1d=returns[1],
        return_5d=returns[5],
        return_20d=returns[20],
        return_60d=returns[60],
        level_hit_flag=level_flag,
        directional_hit_flag=directional_flag,
        hit_status=hit_status,
        data_warnings=_join(warnings),
        model_version=CLAIM_VALIDATION_MODEL_VERSION,
        source="trader_commentary_validation",
        as_of_date=_today(),
        effective_date=latest_price_date,
    )


def _skipped_claim_outcome(
    claim: StoredTraderCommentaryClaim,
    warnings: tuple[str, ...],
) -> TraderCommentaryClaimOutcome:
    return TraderCommentaryClaimOutcome(
        claim_id=claim.claim_id,
        claim_key=claim.claim_key,
        ticker=claim.ticker,
        instrument_label=claim.instrument_label,
        claim_type=claim.claim_type,
        claim_date=claim.claim_date,
        outcome_date=_today(),
        outcome_status="skipped",
        completed_horizons=None,
        pending_horizons=_join([f"{horizon}d" for horizon in HORIZONS]),
        hit_status="not_applicable",
        data_warnings=_join(warnings),
        model_version=CLAIM_VALIDATION_MODEL_VERSION,
        source="trader_commentary_validation",
        as_of_date=_today(),
        effective_date=claim.claim_date,
    )


def validate_trader_commentary_claims(
    config: AppConfig,
    ticker: str | None = None,
) -> TraderCommentaryValidationResult:
    wanted_ticker = normalize_ticker(ticker) if ticker else None
    assets = {
        asset.ticker: (asset.asset_type or "equity").lower()
        for asset in list_assets(config.database_path)
        if asset.active_flag == 1
    }
    aliases = trader_commentary_alias_map(config.database_path)
    claims = list_trader_commentary_claims(config.database_path, ticker=wanted_ticker)
    results: list[TraderCommentaryValidationItem] = []
    warnings: list[str] = []
    updated = 0
    skipped = 0
    for claim in claims:
        if claim.ticker is None:
            alias = aliases.get((claim.instrument_label or "").strip().lower())
            if alias is not None:
                mapped_ticker = normalize_ticker(alias.canonical_ticker)
                asset_type = assets.get(mapped_ticker)
                if asset_type is not None:
                    mapped_claim = replace(claim, ticker=mapped_ticker)
                    outcome = _evaluate_claim_outcome(
                        mapped_claim,
                        list_prices(config.database_path, mapped_ticker),
                        asset_type,
                    )
                    existing_warnings = [
                        item.strip()
                        for item in (outcome.data_warnings or "").split(",")
                        if item.strip()
                    ]
                    outcome = replace(
                        outcome,
                        data_warnings=", ".join(
                            dict.fromkeys(existing_warnings + ["alias_mapped_instrument"])
                        ),
                    )
                    upsert_trader_commentary_claim_outcome(config.database_path, outcome)
                    updated += 1
                    warnings.append(f"{mapped_ticker}:alias_mapped_instrument")
                    results.append(
                        TraderCommentaryValidationItem(
                            claim_key=claim.claim_key,
                            ticker=mapped_ticker,
                            claim_type=claim.claim_type,
                            status="updated",
                            outcome_status=outcome.outcome_status,
                            warnings=tuple(existing_warnings + ["alias_mapped_instrument"]),
                        )
                    )
                    continue
                warnings.append(f"{mapped_ticker}:alias_ticker_not_active_or_missing_asset")
            skipped += 1
            warning_tuple = ("unmapped_instrument",)
            warnings.append(f"{claim.claim_key[:8]}:unmapped_instrument")
            upsert_trader_commentary_claim_outcome(
                config.database_path,
                _skipped_claim_outcome(claim, warning_tuple),
            )
            results.append(
                TraderCommentaryValidationItem(
                    claim_key=claim.claim_key,
                    ticker=None,
                    claim_type=claim.claim_type,
                    status="skipped",
                    outcome_status="skipped",
                    warnings=warning_tuple,
                )
            )
            continue
        asset_type = assets.get(claim.ticker)
        if asset_type is None:
            skipped += 1
            warning_tuple = ("ticker_not_active_or_missing_asset",)
            warnings.append(f"{claim.ticker}:ticker_not_active_or_missing_asset")
            upsert_trader_commentary_claim_outcome(
                config.database_path,
                _skipped_claim_outcome(claim, warning_tuple),
            )
            results.append(
                TraderCommentaryValidationItem(
                    claim_key=claim.claim_key,
                    ticker=claim.ticker,
                    claim_type=claim.claim_type,
                    status="skipped",
                    outcome_status="skipped",
                    warnings=warning_tuple,
                )
            )
            continue
        outcome = _evaluate_claim_outcome(
            claim,
            list_prices(config.database_path, claim.ticker),
            asset_type,
        )
        upsert_trader_commentary_claim_outcome(config.database_path, outcome)
        updated += 1
        warning_tuple = tuple(
            item.strip()
            for item in (outcome.data_warnings or "").split(",")
            if item.strip()
        )
        warnings.extend(f"{claim.ticker}:{warning}" for warning in warning_tuple)
        results.append(
            TraderCommentaryValidationItem(
                claim_key=claim.claim_key,
                ticker=claim.ticker,
                claim_type=claim.claim_type,
                status="updated",
                outcome_status=outcome.outcome_status,
                warnings=warning_tuple,
            )
        )
    return TraderCommentaryValidationResult(
        updated_count=updated,
        skipped_count=skipped,
        warnings=tuple(warnings),
        results=tuple(results),
    )


def build_trader_commentary_parse_review(config: AppConfig) -> str:
    raw_rows = list_trader_commentary_raw(config.database_path)
    claims = list_trader_commentary_claims(config.database_path)
    assets = {
        asset.ticker: asset
        for asset in list_assets(config.database_path)
        if asset.active_flag == 1
    }
    asset_types = {ticker: (asset.asset_type or "equity").lower() for ticker, asset in assets.items()}
    raw_ids_with_claims = {claim.commentary_id for claim in claims}
    raw_without_claims = [
        str(raw.commentary_id)
        for raw in raw_rows
        if raw.commentary_id not in raw_ids_with_claims
    ]
    label_dispositions = commentary_label_disposition_map(config)
    ticker_claims = [claim for claim in claims if claim.ticker]
    unresolved_claims = [
        claim
        for claim in claims
        if not claim.ticker
        and (
            claim.instrument_label or "unmapped_context"
        ).strip().lower()
        in label_dispositions
    ]
    unmapped_claims = [
        claim
        for claim in claims
        if not claim.ticker
        and (
            claim.instrument_label or "unmapped_context"
        ).strip().lower()
        not in label_dispositions
    ]
    intentionally_unresolved_claims = [
        claim
        for claim in unresolved_claims
        if label_dispositions[
            (claim.instrument_label or "unmapped_context").strip().lower()
        ].disposition
        == "intentionally_unresolved_ambiguous"
    ]
    ignored_non_instrument_claims = [
        claim
        for claim in unresolved_claims
        if label_dispositions[
            (claim.instrument_label or "unmapped_context").strip().lower()
        ].disposition
        == "ignored_non_instrument_context"
    ]
    unsupported_claims = [
        claim for claim in ticker_claims if claim.ticker not in asset_types
    ]
    reference_claims = [
        claim
        for claim in ticker_claims
        if claim.ticker in assets
        and normalize_asset_role(assets[claim.ticker].asset_role) != "scoreable"
    ]
    etf_claims = [
        claim for claim in ticker_claims if asset_types.get(claim.ticker) == "etf"
    ]
    options_claims = [
        claim for claim in claims if claim.claim_type == "options_income_idea"
    ]
    warning_counts: dict[str, int] = {}
    reviewed_warning_counts: dict[str, int] = {}
    claim_type_counts: dict[str, int] = {}
    for claim in claims:
        claim_type_counts[claim.claim_type] = claim_type_counts.get(claim.claim_type, 0) + 1
        for warning in (claim.parser_warnings or "").split(","):
            warning = warning.strip()
            if warning:
                label_key = (
                    (claim.instrument_label or "unmapped_context").strip().lower()
                    if not claim.ticker
                    else ""
                )
                if warning == "unmapped_instrument" and label_key in label_dispositions:
                    reviewed_warning_counts[warning] = (
                        reviewed_warning_counts.get(warning, 0) + 1
                    )
                else:
                    warning_counts[warning] = warning_counts.get(warning, 0) + 1
    unsupported_tickers = sorted({claim.ticker or "" for claim in unsupported_claims})
    unmapped_labels = sorted(
        {claim.instrument_label or "unmapped_context" for claim in unmapped_claims}
    )
    intentionally_unresolved_labels = sorted(
        {
            claim.instrument_label or "unmapped_context"
            for claim in intentionally_unresolved_claims
        }
    )
    ignored_non_instrument_labels = sorted(
        {
            claim.instrument_label or "unmapped_context"
            for claim in ignored_non_instrument_claims
        }
    )
    option_tickers = sorted({claim.ticker or claim.instrument_label or "unmapped" for claim in options_claims})
    lines = [
        "Trader Commentary Parse Review",
        f"Raw commentary rows: {len(raw_rows)}",
        f"Parsed claims: {len(claims)}",
        f"Ticker-mapped claims: {len(ticker_claims)}",
        f"Unmapped instrument claims: {len(unmapped_claims)}",
        f"Intentionally unresolved instrument claims: {len(intentionally_unresolved_claims)}",
        f"Ignored non-instrument claims: {len(ignored_non_instrument_claims)}",
        f"Unsupported ticker claims: {len(unsupported_claims)}",
        f"Unsupported but onboardable ticker claims: {len(unsupported_claims)}",
        f"Reference-instrument ticker claims: {len(reference_claims)}",
        f"ETF-gated ticker claims: {len(etf_claims)}",
        f"Options proxy claims: {len(options_claims)}",
        f"Raw rows without parsed claims: {', '.join(raw_without_claims) if raw_without_claims else 'none'}",
        f"Unmapped instruments: {', '.join(unmapped_labels) if unmapped_labels else 'none'}",
        "Intentionally unresolved labels: "
        + (
            ", ".join(intentionally_unresolved_labels)
            if intentionally_unresolved_labels
            else "none"
        ),
        "Ignored non-instrument labels: "
        + (
            ", ".join(ignored_non_instrument_labels)
            if ignored_non_instrument_labels
            else "none"
        ),
        f"Unsupported tickers: {', '.join(unsupported_tickers) if unsupported_tickers else 'none'}",
        f"Options proxy tickers: {', '.join(option_tickers) if option_tickers else 'none'}",
    ]
    if claim_type_counts:
        lines.append("Claim type counts:")
        for claim_type, count in sorted(claim_type_counts.items()):
            lines.append(f"- {claim_type}: {count}")
    else:
        lines.append("Claim type counts: none")
    if warning_counts:
        lines.append("Parser warnings:")
        for warning, count in sorted(warning_counts.items()):
            lines.append(f"- {warning}: {count}")
    else:
        lines.append("Parser warnings: none")
    if reviewed_warning_counts:
        lines.append("Reviewed disposition warnings:")
        for warning, count in sorted(reviewed_warning_counts.items()):
            lines.append(f"- {warning}: {count}")
    if unsupported_claims:
        lines.append("Unsupported ticker details:")
        for claim in unsupported_claims[:25]:
            lines.append(
                f"- {claim.ticker}: {claim.claim_type} "
                f"@{claim.claim_date} ({claim.raw_excerpt or ''})"
            )
    if unmapped_claims:
        lines.append("Unmapped instrument details:")
        for claim in unmapped_claims[:25]:
            lines.append(
                f"- {claim.instrument_label or 'unmapped_context'}: {claim.claim_type} "
                f"@{claim.claim_date} ({claim.raw_excerpt or ''})"
            )
    if intentionally_unresolved_claims:
        lines.append("Intentionally unresolved label details:")
        for claim in intentionally_unresolved_claims[:25]:
            disposition = label_dispositions[
                (claim.instrument_label or "unmapped_context").strip().lower()
            ]
            lines.append(
                f"- {claim.instrument_label or 'unmapped_context'}: {claim.claim_type} "
                f"@{claim.claim_date} ({disposition.disposition}; {claim.raw_excerpt or ''})"
            )
    if ignored_non_instrument_claims:
        lines.append("Ignored non-instrument label details:")
        for claim in ignored_non_instrument_claims[:25]:
            disposition = label_dispositions[
                (claim.instrument_label or "unmapped_context").strip().lower()
            ]
            lines.append(
                f"- {claim.instrument_label or 'unmapped_context'}: {claim.claim_type} "
                f"@{claim.claim_date} ({disposition.disposition}; {claim.raw_excerpt or ''})"
            )
    return "\n".join(lines)


def build_trader_commentary_status_text(config: AppConfig) -> str:
    raw_count = count_rows_by_table(config.database_path, "trader_commentary_raw")
    claim_count = count_rows_by_table(config.database_path, "trader_commentary_claims")
    outcome_count = count_rows_by_table(
        config.database_path, "trader_commentary_claim_outcomes"
    )
    statuses = trader_commentary_statuses(config.database_path)
    lines = [
        "Trader Commentary Status",
        f"Raw rows: {raw_count}",
        f"Parsed claims: {claim_count}",
        f"Claim outcomes: {outcome_count}",
    ]
    if not statuses:
        lines.append("No ticker-mapped commentary claims yet.")
    else:
        lines.append(
            "Ticker | Claims | Latest Claim | Direction | Validation | Hit | Warnings"
        )
        for status in statuses:
            lines.append(
                f"{status.ticker} | {status.claim_count} | "
                f"{status.latest_claim_type or 'none'}@{status.latest_claim_date or 'none'} | "
                f"{status.latest_direction or 'neutral'} | "
                f"{status.latest_outcome_status or 'missing'}@{status.latest_outcome_date or 'none'} | "
                f"{status.latest_hit_status or 'none'} | {status.data_warnings or ''}"
            )
    return "\n".join(lines)


def build_trader_commentary_validation_report(config: AppConfig) -> str:
    outcomes = list_trader_commentary_claim_outcomes(config.database_path)
    lines = ["Trader Commentary Validation Report"]
    if not outcomes:
        lines.append("No commentary claim outcomes yet.")
        return "\n".join(lines)
    completed = [item for item in outcomes if item.outcome_status in {"partial", "completed"}]
    pending = [item for item in outcomes if item.outcome_status == "pending"]
    hits = [item for item in completed if item.hit_status == "hit"]
    misses = [item for item in completed if item.hit_status == "miss"]
    lines.extend(
        [
            f"Outcome rows: {len(outcomes)}",
            f"Pending rows: {len(pending)}",
            f"Completed/partial rows: {len(completed)}",
            f"Directional or level hit rate: {len(hits)}/{len(hits) + len(misses)}"
            if hits or misses
            else "Directional or level hit rate: not enough matured evidence",
            "",
            "Ticker | Claim | Claim Date | Outcome | Hit | 1d | 5d | 20d | 60d | Warnings",
        ]
    )
    for outcome in outcomes[:50]:
        lines.append(
            f"{outcome.ticker or outcome.instrument_label or 'unmapped'} | "
            f"{outcome.claim_type} | {outcome.claim_date} | "
            f"{outcome.outcome_status or 'none'} | {outcome.hit_status or 'none'} | "
            f"{_fmt_pct(outcome.return_1d)} | {_fmt_pct(outcome.return_5d)} | "
            f"{_fmt_pct(outcome.return_20d)} | {_fmt_pct(outcome.return_60d)} | "
            f"{outcome.data_warnings or ''}"
        )
    return "\n".join(lines)


def _fmt_pct(value: float | None) -> str:
    return f"{value:.2%}" if value is not None else "none"
