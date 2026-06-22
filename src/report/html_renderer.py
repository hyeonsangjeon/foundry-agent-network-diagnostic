"""
Render a single, self-contained ``report.html`` dashboard.

Constraints:
  * One file, no external CDN/JS/fonts — must open in a closed/air-gapped network.
  * No JavaScript required; collapsible evidence uses native <details>.
  * Everything dynamic is HTML-escaped.

Layout: header → final verdict banner → status summary → 6 color-coded check cards
(Check 4 rendered as the official/observed/impact topology table) → copy-paste support block.
"""

from __future__ import annotations

import html
import json
from typing import Any

_STATUS_STYLE = {
    "PASS": ("#1a7f37", "#e6f4ea", "PASS"),
    "WARN": ("#9a6700", "#fff8e1", "WARN"),
    "FAIL": ("#cf222e", "#ffebe9", "FAIL"),
    "SKIPPED": ("#57606a", "#f6f8fa", "SKIPPED"),
    "INFO": ("#0969da", "#ddf4ff", "INFO"),
}

_VERDICT_STYLE = {
    "fail": ("#cf222e", "#fff0ef"),
    "warn": ("#9a6700", "#fff8e1"),
    "pass": ("#1a7f37", "#e9f7ee"),
    "unknown": ("#57606a", "#f1f3f5"),
}


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _status_chip(status: str) -> str:
    fg, bg, label = _STATUS_STYLE.get(status, _STATUS_STYLE["SKIPPED"])
    return (
        f'<span class="chip" style="color:{fg};background:{bg};'
        f'border:1px solid {fg}33">{_esc(label)}</span>'
    )


def _evidence_block(evidence: dict[str, Any]) -> str:
    if not evidence:
        return ""
    pretty = json.dumps(evidence, indent=2, ensure_ascii=False)
    return (
        '<details class="evidence"><summary>Evidence (raw)</summary>'
        f'<pre>{_esc(pretty)}</pre></details>'
    )


def _verdict_tone(checks: list[dict[str, Any]]) -> str:
    statuses = {c.get("status") for c in checks}
    if "FAIL" in statuses:
        return "fail"
    if "WARN" in statuses:
        return "warn"
    if statuses & {"PASS", "INFO"}:
        return "pass"
    return "unknown"


def _topology_table(rows: list[dict[str, Any]]) -> str:
    verdict_color = {"match": "#1a7f37", "diverge": "#cf222e", "unknown": "#9a6700"}
    out = [
        '<table class="topo"><thead><tr>',
        "<th>Dimension</th><th>Official (Template 16)</th>",
        "<th>Your environment</th><th>Impact</th></tr></thead><tbody>",
    ]
    for r in rows:
        vc = verdict_color.get(r.get("verdict", "unknown"), "#57606a")
        out.append(
            "<tr>"
            f'<td class="dim">{_esc(r.get("dimension",""))}</td>'
            f'<td>{_esc(r.get("official",""))}</td>'
            f'<td style="border-left:3px solid {vc}">'
            f'<strong style="color:{vc}">{_esc(r.get("verdict","").upper())}</strong> '
            f'— {_esc(r.get("observed",""))}</td>'
            f'<td class="impact">{_esc(r.get("impact",""))}</td>'
            "</tr>"
        )
    out.append("</tbody></table>")
    return "".join(out)


def _check_card(check: dict[str, Any]) -> str:
    fg, bg, _ = _STATUS_STYLE.get(check.get("status"), _STATUS_STYLE["SKIPPED"])
    body = [
        '<div class="card" style="border-left:6px solid ' + fg + '">',
        '<div class="card-head">',
        f'<h3>{_esc(check.get("name",""))}</h3>{_status_chip(check.get("status",""))}',
        "</div>",
        f'<p class="summary">{_esc(check.get("summary",""))}</p>',
    ]
    evidence = check.get("evidence") or {}
    if check.get("id") == "check4" and isinstance(evidence.get("rows"), list):
        body.append(_topology_table(evidence["rows"]))
        extra = {k: v for k, v in evidence.items() if k != "rows"}
        body.append(_evidence_block(extra))
    else:
        body.append(_evidence_block(evidence))
    if check.get("remediation"):
        body.append(f'<p class="fix"><strong>Suggested next step:</strong> {_esc(check["remediation"])}</p>')
    body.append("</div>")
    return "".join(body)


def render_html(report: dict[str, Any]) -> str:
    checks = report.get("checks", [])
    verdict = report.get("verdict", {})
    counts = report.get("summary_counts", {})
    tone = _verdict_tone(checks)
    v_fg, v_bg = _VERDICT_STYLE.get(tone, _VERDICT_STYLE["unknown"])

    summary_chips = "".join(
        f'<span class="count" style="color:{_STATUS_STYLE[s][0]}">'
        f'{counts.get(s,0)} {s}</span>'
        for s in ("PASS", "WARN", "FAIL", "SKIPPED", "INFO")
        if counts.get(s, 0)
    )

    cards = "".join(_check_card(c) for c in checks)
    support = _esc(report.get("support_block", ""))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Foundry Agent Network Diagnostic — Report</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         color:#1f2328; background:#f6f8fa; line-height:1.5; }}
  .wrap {{ max-width:980px; margin:0 auto; padding:28px 20px 64px; }}
  header.top {{ display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px; }}
  header.top h1 {{ font-size:20px; margin:0; }}
  .meta {{ color:#57606a; font-size:13px; }}
  .banner {{ margin:18px 0 22px; padding:18px 20px; border-radius:12px;
            background:{v_bg}; border:1px solid {v_fg}55; }}
  .banner .lbl {{ font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:{v_fg}; font-weight:700; }}
  .banner h2 {{ margin:6px 0 6px; font-size:19px; color:{v_fg}; }}
  .banner p {{ margin:4px 0; }}
  .counts {{ display:flex; gap:14px; flex-wrap:wrap; margin:0 0 18px; font-weight:600; font-size:13px; }}
  .count {{ background:#fff; border:1px solid #d0d7de; border-radius:20px; padding:3px 12px; }}
  .card {{ background:#fff; border:1px solid #d0d7de; border-radius:12px; padding:16px 18px; margin:0 0 14px; }}
  .card-head {{ display:flex; justify-content:space-between; align-items:center; gap:12px; }}
  .card-head h3 {{ margin:0; font-size:15.5px; }}
  .chip {{ font-size:12px; font-weight:700; padding:2px 10px; border-radius:20px; white-space:nowrap; }}
  .summary {{ margin:8px 0 6px; }}
  .fix {{ margin:8px 0 0; font-size:14px; color:#1f2328; background:#f6f8fa; border-radius:8px; padding:8px 10px; }}
  details.evidence {{ margin-top:8px; }}
  details.evidence summary {{ cursor:pointer; color:#0969da; font-size:13px; }}
  pre {{ background:#0d1117; color:#e6edf3; padding:12px; border-radius:8px; overflow:auto; font-size:12px;
        font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  table.topo {{ width:100%; border-collapse:collapse; margin:10px 0 4px; font-size:13px; }}
  table.topo th, table.topo td {{ text-align:left; vertical-align:top; padding:8px 10px; border-bottom:1px solid #eaeef2; }}
  table.topo th {{ background:#f6f8fa; font-size:12px; text-transform:uppercase; letter-spacing:.03em; color:#57606a; }}
  table.topo td.dim {{ font-weight:600; white-space:nowrap; }}
  table.topo td.impact {{ color:#57606a; }}
  .support h2 {{ font-size:16px; margin:26px 0 8px; }}
  textarea.support-box {{ width:100%; min-height:200px; font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
        font-size:12.5px; padding:12px; border:1px solid #d0d7de; border-radius:10px; background:#fff; color:#1f2328; }}
  footer {{ color:#57606a; font-size:12px; margin-top:28px; text-align:center; }}
  .ro {{ display:inline-block; background:#e6f4ea; color:#1a7f37; border:1px solid #1a7f3733;
        border-radius:20px; padding:2px 10px; font-size:12px; font-weight:700; }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>Foundry Agent Network Diagnostic</h1>
    <div class="meta">
      <span class="ro">READ-ONLY</span>
      &nbsp;mode: <strong>{_esc(report.get("mode",""))}</strong>
      &nbsp;·&nbsp; {_esc(report.get("generated_utc",""))}
      &nbsp;·&nbsp; v{_esc(report.get("version",""))}
    </div>
  </header>

  <section class="banner">
    <div class="lbl">Root-cause verdict</div>
    <h2>{_esc(verdict.get("headline","Undetermined"))}</h2>
    <p>{_esc(verdict.get("detail",""))}</p>
    <p><em>{_esc(verdict.get("corroboration",""))}</em></p>
  </section>

  <div class="counts">{summary_chips}</div>

  {cards}

  <section class="support">
    <h2>Support case summary (copy &amp; paste)</h2>
    <textarea class="support-box" readonly>{support}</textarea>
  </section>

  <footer>
    Generated by foundry-agent-network-diagnostic · read-only · no resources were modified.<br>
    Author: Hyeonsang Jeon · Microsoft Global Black Belt AI Apps
  </footer>
</div>
</body>
</html>
"""


def write_html(report: dict[str, Any], path: str) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_html(report))
    return path
