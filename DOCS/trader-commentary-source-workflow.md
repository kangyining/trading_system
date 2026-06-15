# Trader Commentary Source Workflow

Phase 10H lets TOM ingest trader commentary as a shadow-only input. It is meant
for user-authorized text capture, not scraping.

## Accepted Inputs

Use `data/signals/manual/trader_commentary.csv`.

Required columns:

```text
capture_date, source, source_author, platform, permission_scope
```

Each row must include at least one of:

```text
raw_text, text_file, source_url, capture_id
```

Use `raw_text` for short pasted notes. Use `text_file` for longer UTF-8 files
stored beside the CSV or under:

```text
data/signals/source_exports/trader_commentary/
```

For private or VIP content, use a stable `capture_id` instead of a public URL.
Do not add automated scraping for private groups.

## Templates And Seeded Captures

Generate a ready-to-fill CSV and text-file template with:

```powershell
python -m target_opportunity_monitor export-trader-commentary-template
```

The template is written under:

```text
data/signals/source_exports/trader_commentary/
```

Phase 10H.1 also seeds the user-provided Chinese examples as local authorized
captures in that same directory. The rows in
`data/signals/manual/trader_commentary.csv` use:

```text
source = user_paste
source_author = unknown_trader
platform = wechat_or_chat_capture
permission_scope = user_provided_private_capture
capture_id = local user_paste_* ids
```

These rows intentionally use capture IDs instead of public URLs because the
source is a user-provided private capture.

## X Browser Capture Fallback

Phase 10H.2 adds an opt-in fallback for public X pages, lists, or search URLs
when a paid X API is not available. This is not a scraper hidden inside TOM.
Codex Browser or the operator provides rendered visible text artifacts; TOM
stores, dedupes, and ingests those artifacts.

Default config:

```toml
[commentary_browser_capture]
enabled = false
provider = "x_browser"
target_urls = []
max_scroll_batches = 3
min_seconds_between_runs = 900
require_operator_acknowledgement = true
```

Default artifact path:

```text
data/signals/browser_captures/trader_commentary/YYYY-MM-DD/run-id/
```

Each run writes:

```text
dom_text.txt
page.html optional
items.json
run_metadata.json
```

Commands:

```powershell
python -m target_opportunity_monitor browser-capture-commentary-status
python -m target_opportunity_monitor browser-capture-commentary --provider x_browser --target-url URL --acknowledge-terms-risk --dom-text-file PATH
python -m target_opportunity_monitor ingest-browser-captured-commentary
python -m target_opportunity_monitor parse-trader-commentary-claims
python -m target_opportunity_monitor trader-commentary-parse-review
python -m target_opportunity_monitor validate-trader-commentary-claims
```

Run boundaries:

- Capture only rendered visible text from user-configured public X targets.
- Do not bypass login, captchas, rate limits, paywalls, or technical blocks.
- If X shows a login wall, captcha, rate limit, or generic block page, record a
  partial/failed run and stop.
- Use a low cadence, such as every 15-30 minutes, only after manual verification
  works.
- Do not use aggressive scrolling; keep `max_scroll_batches` small.
- The stored warnings intentionally include `browser_capture_fragile`,
  `x_api_not_used`, `manual_auth_required`, `capture_may_be_incomplete`, or
  `terms_risk_acknowledgement_required` when relevant.

Discord is not handled through browser automation. Use the Phase 10H.5 official
bot/API workflow below. WeChat browser capture is not part of the current plan.

## Discord Official Bot/API Capture

Phase 10H.5 adds disabled-by-default Discord capture for channels where your bot
has permission to read messages. TOM reads the token from:

```text
DISCORD_BOT_TOKEN
```

Never store the token in TOM config files, CSVs, reports, dashboard output, or
test fixtures.

Default config:

```toml
[commentary_discord_capture]
enabled = false
provider = "discord_gateway"
channel_ids = []
max_messages_per_run = 100
min_seconds_between_runs = 900
require_operator_acknowledgement = true
```

Default artifact path:

```text
data/signals/discord_captures/trader_commentary/YYYY-MM-DD/run-id/
```

Each run writes:

```text
messages.json
raw_payload.jsonl optional
run_metadata.json
```

Commands:

```powershell
python -m target_opportunity_monitor discord-capture-commentary-status
python -m target_opportunity_monitor discord-capture-commentary --provider discord_gateway --channel-id CHANNEL_ID --acknowledge-permission
python -m target_opportunity_monitor ingest-discord-captured-commentary
python -m target_opportunity_monitor parse-trader-commentary-claims
python -m target_opportunity_monitor trader-commentary-parse-review
python -m target_opportunity_monitor validate-trader-commentary-claims
```

For testing or audited provider exports, use:

```powershell
python -m target_opportunity_monitor discord-capture-commentary --provider discord_gateway --channel-id CHANNEL_ID --messages-json-file PATH --acknowledge-permission
```

Run boundaries:

- Capture only channels the bot is authorized to read.
- Do not bypass Discord permissions, private-channel restrictions, rate limits,
  captchas, or technical blocks.
- Attachments are stored as metadata counts only in this MVP; TOM does not OCR
  images or parse audio/video.
- Accepted messages are deduped by Discord message ID and ingested into
  `trader_commentary_raw` with `source = "discord_bot_capture"` and
  `platform = "discord"`.
- `refresh-data --daily` ingests already captured Discord items but does not
  fetch Discord by itself.
- Captured Discord commentary remains shadow-only.

## Parser Scope

The Phase 10H parser is deterministic and bilingual. It extracts:

- tickers and ETF symbols written in Latin characters,
- unmapped instrument labels such as `大盘`,
- support and resistance zones,
- breakout or breakdown conditions,
- price targets and downside/risk levels,
- buy/add/reduce/sell-style action comments,
- sector-rotation references,
- catalyst or event references,
- sell-put ideas as underlying-price proxy claims.

If a sentence omits the ticker but follows a sentence with an explicit ticker,
TOM may inherit that recent ticker for target/action/risk claims. Unmapped market
labels remain unmapped and are not forced to SPY or QQQ.

Review parser output with:

```powershell
python -m target_opportunity_monitor trader-commentary-parse-review
```

The review separates ticker-mapped claims, unmapped context such as `大盘`,
unsupported tickers that are not active TOM assets, ETF-gated claims, option
proxy claims, and parser warnings. Unsupported tickers are not automatically
added to TOM; add them through the normal asset workflow if you want priced
validation.

## Commentary Onboarding And Aliases

Phase 10H.3 turns unsupported commentary tickers into explicit onboarding
candidates. The default role is `commentary_validation`, meaning TOM can ingest
prices and validate commentary claims for that instrument, while scoring,
alerts, range notifications, portfolio guidance, and `verify-universe` continue
to use only `scoreable` assets.

Commands:

```powershell
python -m target_opportunity_monitor commentary-onboarding-plan
python -m target_opportunity_monitor commentary-onboarding-status
python -m target_opportunity_monitor export-commentary-onboarding-template
python -m target_opportunity_monitor apply-commentary-onboarding --file PATH
python -m target_opportunity_monitor apply-commentary-onboarding --file PATH --confirm
python -m target_opportunity_monitor load-commentary-instrument-aliases
```

`apply-commentary-onboarding` is a dry run unless `--confirm` is supplied. Use
the dry run first, inspect the generated rows, and promote to `scoreable` only
when you truly want the instrument to enter the full valuation, score, alert,
range, and portfolio workflow.

Instrument aliases live at:

```text
data/signals/manual/trader_commentary_instrument_aliases.csv
```

Required alias columns:

```text
instrument_label, canonical_ticker
```

Optional columns:

```text
asset_type, asset_role, source, notes, as_of_date, effective_date
```

Aliases are explicit. Broad labels such as `大盘` remain unmapped until you add a
row yourself; TOM does not force them to SPY, QQQ, or any other proxy.

Current Phase 10H.4 reference instruments:

```text
BRK.B, HOOD, KORU, SOXL, TSLA, XLF, XLV
```

These are active only for price loading and commentary validation. They are not
scoreable assets and should not appear in `verify-universe`, score computation,
alerts, range notifications, or portfolio guidance unless promoted later.

## Validation Scope

TOM validates commentary only with local stored prices. It tracks:

- 1d, 5d, 20d, and 60d forward returns,
- support-hold and support-breach checks,
- resistance-breakout checks,
- target-hit checks,
- downside/risk-level breaches,
- pending horizons when not enough future prices exist.

Options commentary such as `sell put KORU 600, 100 premium` is stored as an
`options_income_idea`, but Phase 10H validates only the underlying price proxy.
It does not calculate option P&L, assignment risk, Greeks, margin, or execution.

## Boundaries

Commentary remains shadow-only:

- no score impact,
- no alert impact,
- no range override,
- no portfolio guidance impact,
- no notifications beyond existing local visibility surfaces,
- no broker writes,
- no execution.

Use the validation results to decide whether a commentary source is useful over
time, not as a direct trading instruction.
