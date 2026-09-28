#!/usr/bin/env python3
"""Generate a distinct, searchable technology PDF from each canonical Markdown guide.

Usage:
  python deployment/technology-guides/publish_pdfs.py
  python deployment/technology-guides/publish_pdfs.py --only 03
  python deployment/technology-guides/publish_pdfs.py --browser "C:\\...\\chrome.exe"

Requires: Python 3.10+, Markdown 3.10, Chrome/Edge with headless PDF printing.
Optional: pypdf for text/page-content validation.
Never use PDF files as documentation sources; edit and re-run the Markdown.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
PDF_DIR = HERE / "pdf"
NUMBERED = re.compile(r"^\d\d-.+\.md$")
PRIVATE_PEM = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def browser_binary(explicit: str | None) -> Path:
    options = [
        explicit,
        shutil.which("chrome"),
        shutil.which("msedge"),
        shutil.which("chromium"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for option in options:
        if option and Path(option).is_file():
            return Path(option)
    raise SystemExit("Chrome or Edge not found: use --browser PATH")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="One numbered guide prefix, e.g. 03, or README")
    parser.add_argument("--browser", help="Full path to Chrome or Edge executable")
    args = parser.parse_args()
    try:
        import markdown
    except ImportError:
        raise SystemExit("Install source renderer: python -m pip install markdown==3.10")

    browser = browser_binary(args.browser)
    sources = [HERE / "00-README.md", *(f for f in sorted(HERE.glob("[0-2][0-9]-*.md")) if f.name != "00-README.md")]
    sources = [f for f in sources if f.name == "00-README.md" or NUMBERED.fullmatch(f.name)]
    if args.only:
        sources = [
            f for f in sources
            if f.name.startswith(args.only + "-") or
               (args.only.upper() == "README" and f.name == "00-README.md")
        ]
    if not sources:
        raise SystemExit("No matching guides")
    PDF_DIR.mkdir(exist_ok=True)
    results = []
    errors = []
    with tempfile.TemporaryDirectory(prefix="lorawan-technology-pdf-") as work:
        temp = Path(work)
        for source in sources:
            text = source.read_text(encoding="utf-8")
            if PRIVATE_PEM.search(text):
                raise SystemExit(f"Refusing to publish embedded private key: {source.name}")
            label = source.stem
            title = next(
                (ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("# ")),
                label,
            )
            body = markdown.markdown(
                text,
                extensions=["fenced_code", "tables", "sane_lists", "toc"],
                output_format="html5",
            )
            appendix_sources = []
            if label != "00-README":
                # Include linked implementation/recovery runbooks so an exported PDF
                # remains useful even without navigating the source repository.
                for relative in dict.fromkeys(re.findall(r"\]\((\.\./[^)#]+\.md)(?:#[^)]*)?\)", text)):
                    reference = (HERE / relative).resolve()
                    if not reference.is_file() or HERE not in reference.parents:
                        # Internal deployment manuals may live outside the guide folder.
                        if not reference.is_file() or HERE.parent.parent not in reference.parents:
                            continue
                    runbook_text = reference.read_text(encoding="utf-8")
                    # Fail closed on key blocks; never publish credential-bearing text.
                    if PRIVATE_PEM.search(runbook_text):
                        raise SystemExit(f"Private key detected in supporting runbook: {reference.name}")
                    runbook_text = runbook_text.replace("jervis128662120269", "[REDACTED: obtain from authorized secret store]")
                    appendix_sources.append({"path": reference, "sha256": sha256(reference)})
                    body += ('<section class="appendix"><h1>Supporting runbook: ' +
                             html.escape(reference.name) + "</h1>" +
                             '<p class="appendix-notice">This is the original project runbook. ' +
                             "Check the current documentation baseline and actual host state " +
                             "before applying historical steps or changing a live system.</p>" +
                             markdown.markdown(runbook_text, extensions=["fenced_code", "tables", "sane_lists", "toc"], output_format="html5") +
                             "</section>")
            # In the published collection, numbered local guide links point to PDFs.
            body = re.sub(
                r'href="(\d\d-[^"#?]+)\.md(#[^"]*)?"',
                lambda m: 'href="' + m.group(1) + '.pdf' + (m.group(2) or "") + '"',
                body,
            )
            generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            document = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>""" + html.escape(title) + """</title><style>
@page {size: A4; margin: 16mm 15mm 16mm 15mm}
:root {font-family: Arial, Helvetica, sans-serif; color: #243343}
body {font-size: 9.8pt; line-height: 1.43; overflow-wrap: anywhere}
h1,h2,h3,h4 {color: #102b42; line-height: 1.2; break-after: avoid}
h1 {font-size: 21pt; padding-bottom: 7pt; border-bottom: 3px solid #296d9d}\n.appendix {break-before: page}\n.appendix-notice {padding: 8pt; background: #fff0cd; border-left: 3px solid #b68d27}
h2 {font-size: 14pt; margin-top: 20pt; padding-bottom: 4pt; border-bottom: 1px solid #cad8e4}
h3 {font-size: 11.5pt; margin-top: 13pt}
p,li {orphans: 2; widows: 2}
li {margin: 3pt 0}
pre {white-space: pre-wrap; overflow-wrap: anywhere; word-break: break-word;
 background: #f1f4f7; border-left: 3px solid #728da5; padding: 8pt;
 font-size: 8.0pt; line-height: 1.26; font-family: Consolas, 'Courier New', monospace;
 break-inside: auto}
code {font-family: Consolas, 'Courier New', monospace; font-size: .9em;
 overflow-wrap: anywhere}
pre code {font-size: inherit}
table {border-collapse: collapse; width: 100%; table-layout: fixed;
 margin: 10pt 0; font-size: 8.1pt; break-inside: auto}
th,td {border: 1px solid #cbd6e0; padding: 5pt; text-align: left;
 vertical-align: top; overflow-wrap: anywhere}
th {background: #e8f0f5; color: #102b42}
tr {break-inside: avoid}
blockquote {padding: 0 9pt; border-left: 3px solid #aac2d5; color: #3c5164}
a {color: #245c87; text-decoration: underline}
hr {border: 0; border-top: 1px solid #cbd6e0; margin: 16pt 0}
.kicker {color: #486b85; font-size: 8.3pt; margin-bottom: 16pt}
.source {font-size: 8pt; color: #516779; margin-top: 19pt; border-top: 1px solid #cbd6e0;
 padding-top: 6pt}
</style></head><body>
<div class="kicker">LORAWAN INFRASTRUCTURE · TECHNOLOGY GUIDE · """ + html.escape(generated) + """</div>
""" + body + """
<div class="source">Canonical source: deployment/technology-guides/""" + html.escape(source.name) + """.
For any mutable production-status statement, check the dated baseline and verified live state.</div>
</body></html>"""
            html_file = temp / (label + ".html")
            html_file.write_text(document, encoding="utf-8")
            output = PDF_DIR / (label + ".pdf")
            if output.exists():
                output.unlink()
            profile = temp / ("profile-" + label)
            cmd = [
                str(browser), "--headless=new", "--disable-gpu",
                "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--no-pdf-header-footer",
                "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=2000",
                "--user-data-dir=" + str(profile),
                "--print-to-pdf=" + str(output),
                html_file.resolve().as_uri(),
            ]
            try:
                process = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=95, check=False
                )
            except subprocess.TimeoutExpired:
                errors.append(f"{source.name}: browser PDF timeout")
                continue
            if process.returncode != 0 or not output.exists() or output.stat().st_size < 1000:
                errors.append(
                    f"{source.name}: failed ({process.returncode}) " +
                    (process.stderr or "")[-400:]
                )
                continue
            if output.open("rb").read(5) != b"%PDF-":
                errors.append(f"{source.name}: output is not a PDF")
                continue
            pages = None
            try:
                from pypdf import PdfReader
                pdf = PdfReader(str(output))
                pages = len(pdf.pages)
                excerpt = (pdf.pages[0].extract_text() or "").lower()
                if pages < 1 or (title[:20].lower() not in excerpt and label not in excerpt):
                    errors.append(f"{source.name}: PDF text/page verification failed")
            except ImportError:
                pass
            results.append({
                "source": source.name,
                "source_sha256": sha256(source),
                "included_runbooks": [{"source": str(item["path"].relative_to(HERE.parent.parent)), "sha256": item["sha256"]} for item in appendix_sources],
                "pdf": output.name,
                "pdf_sha256": sha256(output),
                "pages": pages,
                "bytes": output.stat().st_size,
            })
            print(f"PDF {output.name}: pages={pages} bytes={output.stat().st_size}", flush=True)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical": "Markdown in deployment/technology-guides",
        "browser": browser.name,
        "publications": results,
        "errors": errors,
    }
    (PDF_DIR / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"PUB_COUNT={len(results)} ERROR_COUNT={len(errors)}")
    for error in errors:
        print("ERROR", error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
