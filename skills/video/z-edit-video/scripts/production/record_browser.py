#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.49,<2"]
# ///
"""Record each browser recording in edit.json and write its path.

    uv run scripts/production/record_browser.py
    uv run scripts/production/record_browser.py --name install-docs
    uv run scripts/production/record_browser.py --zoom 2

The page is loaded before its `open` is on screen, including a later `open`.
A one-click banner is cleared before the page is on screen.
--zoom 2 lays the page out at half the frame size and scales the recording
up, so text is readable at 4K. The default zoom is 2 when resolution is
4K, and 1 otherwise.

Requires ffmpeg and ffprobe on PATH, and Playwright's Chromium:
    uv run --no-project --with playwright python -m playwright install chromium
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from plan_model import load_plan, parse_tc


# ==================================================
# Page actions
# ==================================================

# Load finishes before the recording clock. These waits are not on that clock.
PAGE_LOAD_TIMEOUT_MS = 45000
PAGE_LOAD_EVENT_MS = 15000
PAGE_TEXT_WAIT_MS = 5000
BANNER_WAIT_S = 3.0

INIT_SCROLL = """
const nativeAttachShadow = Element.prototype.attachShadow;
Element.prototype.attachShadow = function (init) {
  const next = Object.assign({}, init, { mode: "open" });
  return nativeAttachShadow.call(this, next);
};
const style = document.createElement("style");
style.setAttribute("data-browser-recording", "scroll");
style.textContent = "html, body, * { scroll-behavior: auto !important; }";
const parent = document.documentElement || document.head;
if (parent) parent.appendChild(style);
"""

INSTALL_PAGE = r"""() => {
  if (window.__browserReady) return;
  window.__browserReady = true;
  const style = document.createElement("style");
  style.setAttribute("data-browser-recording", "");
  style.textContent = "html, body, * { scroll-behavior: auto !important; } mark.browser-highlight{background:#ffe14a !important;color:#1a1a1a !important;border-radius:0.12em;padding:0.02em 0.14em;box-decoration-break:clone;-webkit-box-decoration-break:clone;}";
  (document.head || document.documentElement).appendChild(style);

  function findRange(text) {
    const needle = String(text || "").replace(/\s+/g, " ").trim().toLowerCase();
    if (!needle || !document.body) return null;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        const tag = parent.tagName;
        if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT") {
          return NodeFilter.FILTER_REJECT;
        }
        const computed = getComputedStyle(parent);
        if (computed.display === "none" || computed.visibility === "hidden") {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    let norm = "";
    const map = [];
    let node;
    while ((node = walker.nextNode())) {
      const value = node.textContent || "";
      for (let i = 0; i < value.length; i++) {
        const ch = value[i];
        if (/\s/.test(ch)) {
          if (!norm || norm.endsWith(" ")) continue;
          norm += " ";
          map.push([node, i]);
        } else {
          norm += ch.toLowerCase();
          map.push([node, i]);
        }
      }
    }
    const idx = norm.indexOf(needle);
    if (idx < 0) return null;
    const start = map[idx];
    const end = map[idx + needle.length - 1];
    if (!start || !end) return null;
    const range = document.createRange();
    range.setStart(start[0], start[1]);
    range.setEnd(end[0], end[1] + 1);
    return range;
  }

  function rootScroller() {
    return document.scrollingElement || document.documentElement;
  }

  function isRoot(scroller) {
    const root = rootScroller();
    return scroller === root || scroller === document.documentElement || scroller === document.body;
  }

  function scrollParent(node) {
    let el = node && node.nodeType === 1 ? node : node && node.parentElement;
    while (el) {
      const computed = getComputedStyle(el);
      const overflow = computed.overflowY;
      if (
        (overflow === "auto" || overflow === "scroll" || overflow === "overlay")
        && el.scrollHeight > el.clientHeight + 2
      ) {
        return el;
      }
      el = el.parentElement;
    }
    return rootScroller();
  }

  // The document element's rect origin moves with scrollTop. The visible top is the viewport.
  function portOf(scroller) {
    if (isRoot(scroller)) {
      const root = rootScroller();
      const height = root.clientHeight || window.innerHeight;
      return { top: 0, bottom: height, height: height, scrollHeight: root.scrollHeight };
    }
    const box = scroller.getBoundingClientRect();
    const top = box.top + scroller.clientTop;
    const height = scroller.clientHeight;
    return { top: top, bottom: top + height, height: height, scrollHeight: scroller.scrollHeight };
  }

  function readScroll(scroller) {
    if (isRoot(scroller)) return rootScroller().scrollTop || window.scrollY || 0;
    return scroller.scrollTop;
  }

  function writeScroll(scroller, top) {
    const y = Math.max(0, top);
    const target = isRoot(scroller) ? rootScroller() : scroller;
    target.style.setProperty("scroll-behavior", "auto", "important");
    try {
      target.scrollTo({ top: y, left: target.scrollLeft || 0, behavior: "instant" });
    } catch (error) {
      target.scrollTop = y;
    }
    if (Math.abs(target.scrollTop - y) > 1) target.scrollTop = y;
  }

  function desiredScroll(scroller, range) {
    const rect = range.getBoundingClientRect();
    const port = portOf(scroller);
    const delta = rect.top - port.top - port.height * 0.28;
    const max = Math.max(0, port.scrollHeight - port.height);
    return Math.max(0, Math.min(readScroll(scroller) + delta, max));
  }

  function ensureStyle() {
    if (!style.isConnected) (document.head || document.documentElement).appendChild(style);
  }

  function armLazy(scroller) {
    const port = portOf(scroller);
    const root = isRoot(scroller) ? document : scroller;
    for (const img of root.querySelectorAll("img")) {
      const box = img.getBoundingClientRect();
      if (box.bottom < port.top - port.height) continue;
      if (box.top > port.bottom + port.height * 2) continue;
      const dataSrc = img.getAttribute("data-src");
      if (dataSrc && !img.getAttribute("src")) img.setAttribute("src", dataSrc);
      if (img.loading === "lazy") img.loading = "eager";
    }
  }

  function shiftingImages(scroller) {
    const port = portOf(scroller);
    const root = isRoot(scroller) ? document : scroller;
    const found = [];
    for (const img of root.querySelectorAll("img")) {
      if (img.complete && img.naturalWidth > 0) continue;
      const computed = getComputedStyle(img);
      const reserved =
        (img.hasAttribute("width") && img.hasAttribute("height"))
        || (computed.aspectRatio && computed.aspectRatio !== "auto");
      if (reserved) continue;
      const box = img.getBoundingClientRect();
      if (box.bottom < port.top - port.height) continue;
      if (box.top > port.bottom + 40) continue;
      found.push(img);
      if (found.length >= 12) break;
    }
    return found;
  }

  function waitForImages(imgs, budgetMs) {
    return new Promise((resolve) => {
      let settled = false;
      let left = 0;
      const timer = setTimeout(finish, Math.max(16, budgetMs));
      function finish() {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve();
      }
      for (const img of imgs) {
        if (img.complete) continue;
        left += 1;
        const done = () => {
          left -= 1;
          if (left <= 0) finish();
        };
        img.addEventListener("load", done, { once: true });
        img.addEventListener("error", done, { once: true });
      }
      if (left === 0) finish();
    });
  }

  async function settleOn(text, scroller) {
    const deadline = performance.now() + 220;
    let stable = 0;
    while (performance.now() < deadline) {
      ensureStyle();
      armLazy(scroller);
      const pending = shiftingImages(scroller);
      if (pending.length) {
        stable = 0;
        await waitForImages(pending, Math.min(120, Math.max(16, deadline - performance.now())));
      }
      const range = findRange(text);
      if (!range) return false;
      const dest = desiredScroll(scroller, range);
      if (Math.abs(dest - readScroll(scroller)) < 2) {
        stable += 1;
        if (stable >= 2 && shiftingImages(scroller).length === 0) return true;
      } else {
        stable = 0;
        writeScroll(scroller, dest);
      }
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    const range = findRange(text);
    if (!range) return false;
    writeScroll(scroller, desiredScroll(scroller, range));
    return true;
  }

  window.__browserScroll = async (text, durationMs) => {
    ensureStyle();
    const range = findRange(text);
    if (!range) return false;
    const scroller = scrollParent(range.startContainer);
    armLazy(scroller);
    const start = readScroll(scroller);
    const dest = desiredScroll(scroller, range);
    if (Math.abs(dest - start) < 2 || durationMs < 16) {
      writeScroll(scroller, dest);
      return settleOn(text, scroller);
    }
    const t0 = performance.now();
    await new Promise((resolve) => {
      const timer = setTimeout(resolve, durationMs + 150);
      function step(now) {
        const p = Math.min(1, (now - t0) / durationMs);
        const eased = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
        writeScroll(scroller, start + (dest - start) * eased);
        if (p < 1) requestAnimationFrame(step);
        else {
          clearTimeout(timer);
          resolve();
        }
      }
      requestAnimationFrame(step);
    });
    return settleOn(text, scroller);
  };

  function walk(scope, out) {
    if (!scope || !scope.querySelectorAll) return out;
    for (const el of scope.querySelectorAll("*")) {
      out.push(el);
      if (el.shadowRoot) walk(el.shadowRoot, out);
    }
    return out;
  }

  function shown(el) {
    const style = getComputedStyle(el);
    if (
      style.display === "none"
      || style.visibility === "hidden"
      || Number(style.opacity) === 0
      || style.pointerEvents === "none"
    ) {
      return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width >= 8 && rect.height >= 8;
  }

  function covers(el) {
    const rect = el.getBoundingClientRect();
    const vw = window.innerWidth || 1;
    const vh = window.innerHeight || 1;
    const area = rect.width * rect.height;
    const big = area > vw * vh * 0.08;
    const bar = rect.width > vw * 0.45
      && rect.height > 32
      && rect.height < vh * 0.7
      && (rect.top < vh * 0.4 || rect.bottom > vh * 0.6);
    return big || bar;
  }

  function labelOf(el) {
    const aria = el.getAttribute("aria-label") || "";
    const value = "value" in el ? el.value || "" : "";
    const title = el.getAttribute("title") || "";
    const text = el.innerText || el.textContent || "";
    return (aria || text || value || title).replace(/\s+/g, " ").trim().toLowerCase();
  }

  function denied(name) {
    return /\b(manage|customize|customise|settings|setting|preferences|preference|sign in|log in|login|learn more|more info|more options|privacy policy|cookie policy)\b/.test(name);
  }

  function rank(name) {
    if (!name || denied(name)) return -1;
    const phrases = [
      "accept all",
      "agree",
      "allow all",
      "got it",
      "okay",
      "ok",
      "accept",
      "reject all",
      "decline",
      "close",
    ];
    for (let i = 0; i < phrases.length; i++) {
      const body = phrases[i].replace(/ /g, "\\s+");
      if (new RegExp("\\b" + body + "\\b").test(name)) return i;
    }
    if (name === "×" || name === "✕" || name === "x") return phrases.length;
    return -1;
  }

  function findDismiss(scope) {
    let best = null;
    let bestRank = 999;
    for (const el of walk(scope, [])) {
      const tag = el.tagName;
      const role = (el.getAttribute("role") || "").toLowerCase();
      const type = (el.getAttribute("type") || "").toLowerCase();
      const clickable = tag === "BUTTON"
        || role === "button"
        || (tag === "INPUT" && (type === "button" || type === "submit"))
        || tag === "A";
      if (!clickable || !shown(el)) continue;
      const score = rank(labelOf(el));
      if (score >= 0 && score < bestRank) {
        best = el;
        bestRank = score;
      }
    }
    return best;
  }

  function isOverlay(el) {
    if (el === document.body || el === document.documentElement) return false;
    if (!shown(el) || !covers(el)) return false;
    const role = (el.getAttribute("role") || "").toLowerCase();
    if (role === "dialog" || role === "alertdialog" || el.getAttribute("aria-modal") === "true") {
      return true;
    }
    const style = getComputedStyle(el);
    if (style.position !== "fixed" && style.position !== "sticky") return false;
    const text = (el.innerText || "").replace(/\s+/g, " ").toLowerCase();
    return /cookie|consent|gdpr|accept all|reject all/.test(text);
  }

  function findOverlay() {
    const candidates = walk(document, []).filter(isOverlay);
    const withButton = candidates.filter((el) => findDismiss(el));
    const pool = withButton.length ? withButton : candidates;
    pool.sort((a, b) => {
      const ra = a.getBoundingClientRect();
      const rb = b.getBoundingClientRect();
      return ra.width * ra.height - rb.width * rb.height;
    });
    return pool[0] || null;
  }

  window.__browserDismissTarget = () => {
    const overlay = findOverlay();
    if (!overlay) return { state: "clear" };
    const button = findDismiss(overlay);
    if (!button) return { state: "open" };
    const rect = button.getBoundingClientRect();
    return {
      state: "ready",
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    };
  };

  window.__browserBannerOpen = () => findOverlay() !== null;

  window.__browserHighlight = async (text) => {
    const range = findRange(text);
    if (!range) return "missing";
    const scroller = scrollParent(range.startContainer);
    const rect = range.getBoundingClientRect();
    const port = portOf(scroller);
    const inView = rect.top >= port.top - 1 && rect.bottom <= port.bottom + 1 && rect.height > 0;
    if (!inView) {
      const scrolled = await window.__browserScroll(text, 700);
      if (!scrolled) return "missing";
    }
    const live = findRange(text);
    if (!live) return "missing";
    const mark = document.createElement("mark");
    mark.className = "browser-highlight";
    mark.appendChild(live.extractContents());
    live.insertNode(mark);
    return "ok";
  };

  const root = rootScroller();
  root.style.setProperty("scroll-behavior", "auto", "important");
  if (document.body) document.body.style.setProperty("scroll-behavior", "auto", "important");
  try {
    root.scrollTo({ top: root.scrollTop, left: root.scrollLeft || 0, behavior: "instant" });
  } catch (error) {}
}"""


# ==================================================
# Record
# ==================================================


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("edit/edit.json"),
        help="edit.json to read and update (default: edit/edit.json)",
    )
    parser.add_argument(
        "--name",
        action="append",
        default=[],
        help="Re-record this browser recording. Repeat for more than one",
    )
    parser.add_argument(
        "--zoom",
        type=float,
        default=None,
        help=(
            "Page zoom. 2 lays the page out at half the frame size and scales "
            "the recording up. Default is 2 when resolution is 4K, and 1 otherwise"
        ),
    )
    args = parser.parse_args()

    plan_path = args.plan
    model = load_plan(plan_path)
    sources = model["sources"]
    if not isinstance(sources, dict):
        sources = {}

    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for scene in model["scenes"]:
        for card in scene["cards"]:
            if card["type"] != "browser":
                continue
            name = str(card["source"])
            if name not in groups:
                order.append(name)
                groups[name] = []
            groups[name].append(card)

    if args.name:
        unknown = [name for name in args.name if name not in groups]
        if unknown:
            sys.exit("not a browser recording layer: " + ", ".join(unknown))
        selected = set(args.name)
    else:
        selected = set()
        for name in order:
            record = sources.get(name)
            if not isinstance(record, dict):
                record = {}
            path = record.get("path")
            if isinstance(path, str) and path.strip() and (Path.cwd() / path).is_file():
                continue
            if isinstance(path, str) and path.strip() and Path(path).is_file():
                continue
            selected.add(name)

    todo = [name for name in order if name in selected]
    if not todo:
        print("no browser recordings")
        return

    settings = model["video_settings"]
    if not isinstance(settings, dict):
        settings = {}
    orientation = str(settings.get("orientation") or "").strip().lower()
    resolution = str(settings.get("resolution") or "").strip().upper()
    if orientation == "portrait":
        output_w, output_h = (2160, 3840) if resolution == "4K" else (1080, 1920)
    elif orientation == "landscape":
        output_w, output_h = (3840, 2160) if resolution == "4K" else (1920, 1080)
    else:
        sys.exit("video_settings.orientation must be landscape or portrait")
    fps = settings.get("fps") or 30
    fps_text = str(int(fps)) if isinstance(fps, float) and fps == int(fps) else str(fps)
    if args.zoom is None:
        zoom = 2.0 if resolution == "4K" else 1.0
    else:
        zoom = float(args.zoom)
    if not zoom > 0:
        sys.exit("--zoom must be greater than 0")

    out_dir = plan_path.parent / "browser"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
    except Exception as error:
        sys.exit(
            "Playwright could not launch Chromium. Run: "
            "uv run --no-project --with playwright python -m playwright install chromium\n"
            f"{error}"
        )

    try:
        for name in todo:
            record = sources.get(name)
            if not isinstance(record, dict):
                sys.exit(f"sources.{name}: missing")
            raw_actions = record.get("actions")
            if not isinstance(raw_actions, list):
                sys.exit(f"sources.{name}.actions: expected an array")
            parse_errors: list[str] = []
            timed: list[tuple[float, int, dict]] = []
            for index, action in enumerate(raw_actions):
                if not isinstance(action, dict):
                    sys.exit(f"sources.{name}.actions[{index}]: expected an object")
                at = parse_tc(
                    action.get("at"),
                    f"sources.{name}.actions[{index}].at",
                    parse_errors,
                )
                if at is None:
                    sys.exit("\n".join(parse_errors))
                timed.append((at, index, action))
            timed.sort()

            group = sorted(groups[name], key=lambda card: card["start"])
            duration = float(group[-1]["end"] - group[0]["start"])
            if duration <= 0:
                sys.exit(f"sources.{name}: recording duration must be greater than 0")
            frame = group[0]["frame"]
            if frame == "full":
                width, height = output_w, output_h
            elif isinstance(frame, str) and frame in {"top", "bottom"}:
                width, height = output_w, max(2, (output_h // 2) // 2 * 2)
            elif isinstance(frame, dict):
                width = max(2, int(round(output_w * float(frame["w"]))) // 2 * 2)
                height = max(2, int(round(output_h * float(frame["h"]))) // 2 * 2)
            else:
                sys.exit(
                    f"sources.{name}: frame must be full, top, bottom, or x, y, w, and h"
                )

            appearance = order.index(name) + 1
            out_path = out_dir / f"{appearance}-browser-{name}.mp4"
            view_w = max(2, int(round(width / zoom)) // 2 * 2)
            view_h = max(2, int(round(height / zoom)) // 2 * 2)
            print(
                f"recording {name} → {out_path} ({duration:.2f}s, zoom {zoom:g})"
            )

            with tempfile.TemporaryDirectory() as tmp:
                context = browser.new_context(
                    viewport={"width": view_w, "height": view_h},
                    record_video_dir=tmp,
                    record_video_size={"width": view_w, "height": view_h},
                    device_scale_factor=1,
                    locale="en-US",
                    bypass_csp=True,
                )
                context.add_init_script(INIT_SCROLL)
                page = context.new_page()
                video_path = Path(page.video.path()) if page.video else None
                recording_started = time.monotonic()
                origin = recording_started
                lead = 0.0
                hidden: list[tuple[float, float]] = []
                seen_open = False

                def wait_until(at: float, label: str) -> None:
                    delay = at - (time.monotonic() - origin)
                    if delay > 0.02:
                        page.wait_for_timeout(int(round(delay * 1000)))
                        return
                    if delay < -0.25:
                        sys.exit(f"sources.{name}: {label} was {-delay:.2f}s late")

                try:
                    for at, action_index, action in timed:
                        kind = action.get("type")
                        if kind == "open":
                            target = str(action.get("url") or "").strip()
                            if not target.startswith(("http://", "https://")):
                                sys.exit(
                                    f"sources.{name}.actions[{action_index}].url: "
                                    "expected an http or https url"
                                )
                            cut_from = None
                            if seen_open:
                                wait_until(at, "open")
                                cut_from = time.monotonic()
                            try:
                                page.goto(
                                    target,
                                    wait_until="domcontentloaded",
                                    timeout=PAGE_LOAD_TIMEOUT_MS,
                                )
                            except PlaywrightTimeout:
                                sys.exit(f"sources.{name}: opening {target} timed out")
                            try:
                                page.wait_for_load_state(
                                    "load", timeout=PAGE_LOAD_EVENT_MS
                                )
                            except PlaywrightTimeout:
                                pass
                            page.evaluate(INSTALL_PAGE)
                            try:
                                page.wait_for_function(
                                    """() => {
                                      const text = document.body && document.body.innerText
                                        ? document.body.innerText.trim()
                                        : "";
                                      return text.length > 0;
                                    }""",
                                    timeout=PAGE_TEXT_WAIT_MS,
                                )
                            except PlaywrightTimeout:
                                pass
                            page.evaluate(
                                """() => Promise.race([
                                  document.fonts ? document.fonts.ready : Promise.resolve(),
                                  new Promise((resolve) => setTimeout(resolve, 3000))
                                ]).then(() => new Promise((resolve) => {
                                  requestAnimationFrame(() => requestAnimationFrame(resolve));
                                }))"""
                            )
                            deadline = time.monotonic() + BANNER_WAIT_S
                            banner_clicks = 0
                            while time.monotonic() < deadline:
                                found = page.evaluate(
                                    "() => window.__browserDismissTarget()"
                                )
                                state = found.get("state") if isinstance(found, dict) else ""
                                if state == "ready" and banner_clicks < 2:
                                    page.mouse.click(
                                        min(max(float(found["x"]), 1), view_w - 1),
                                        min(max(float(found["y"]), 1), view_h - 1),
                                    )
                                    banner_clicks += 1
                                    page.wait_for_timeout(400)
                                    continue
                                if state != "clear":
                                    break
                                page.wait_for_timeout(200)
                            if page.evaluate("() => window.__browserBannerOpen()"):
                                sys.exit(
                                    f"sources.{name}: a banner still covers {target}"
                                )
                            if banner_clicks:
                                print(f"cleared {banner_clicks} banner(s) on {target}")
                            now = time.monotonic()
                            if not seen_open:
                                origin = now
                                lead = origin - recording_started
                                seen_open = True
                            else:
                                origin = origin + (now - cut_from)
                                hidden.append(
                                    (
                                        cut_from - recording_started,
                                        now - recording_started,
                                    )
                                )
                            continue
                        if not seen_open:
                            sys.exit(
                                f"sources.{name}: the first action is open at 00:00:00.00"
                            )
                        wait_until(at, str(kind))
                        if kind == "scroll":
                            found = page.evaluate(
                                "(text) => window.__browserScroll(text, 700)",
                                action.get("to"),
                            )
                            if not found:
                                sys.exit(
                                    f"sources.{name}: scroll text not on the page: "
                                    f"{action.get('to')}"
                                )
                        elif kind == "highlight":
                            found = page.evaluate(
                                "(text) => window.__browserHighlight(text)",
                                action.get("text"),
                            )
                            if found != "ok":
                                sys.exit(
                                    f"sources.{name}: highlight text not on the page: "
                                    f"{action.get('text')}"
                                )
                        else:
                            sys.exit(f"sources.{name}: unknown action {kind}")
                    wait_until(duration, "the end of the recording")
                finally:
                    context.close()

                if video_path is None or not video_path.is_file():
                    sys.exit(f"sources.{name}: Playwright did not write a video")

                probed = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        str(video_path),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                video_duration = 0.0
                if probed.returncode == 0:
                    try:
                        video_duration = float(probed.stdout.decode().strip())
                    except ValueError:
                        video_duration = 0.0
                if video_duration > 0.2:
                    lead = min(lead, max(0.0, video_duration - 0.05))
                    kept_hidden = []
                    for start, end in hidden:
                        start = min(max(start, lead), video_duration)
                        end = min(max(end, start), video_duration)
                        if end - start > 0.02:
                            kept_hidden.append((start, end))
                    hidden = kept_hidden

                pieces: list[tuple[float, float | None]] = []
                cursor = lead
                for start, end in hidden:
                    if start - cursor > 0.02:
                        pieces.append((cursor, start))
                    cursor = max(cursor, end)
                pieces.append((cursor, None))

                if len(pieces) == 1:
                    vf = (
                        f"trim=start={lead:.3f},setpts=PTS-STARTPTS,"
                        f"tpad=stop_mode=clone:stop_duration={duration:.3f},"
                        f"trim=duration={duration:.3f},"
                        f"scale={width}:{height}:flags=lanczos,fps={fps_text}"
                    )
                    filter_args = ["-vf", vf]
                else:
                    segments = []
                    labels = []
                    for index, (start, end) in enumerate(pieces):
                        label = f"v{index}"
                        if end is None:
                            segments.append(
                                f"[0:v]trim=start={start:.3f},setpts=PTS-STARTPTS[{label}]"
                            )
                        else:
                            segments.append(
                                f"[0:v]trim=start={start:.3f}:end={end:.3f},"
                                f"setpts=PTS-STARTPTS[{label}]"
                            )
                        labels.append(f"[{label}]")
                    graph = (
                        ";".join(segments)
                        + ";"
                        + "".join(labels)
                        + f"concat=n={len(pieces)}:v=1:a=0[joined];"
                        + f"[joined]tpad=stop_mode=clone:stop_duration={duration:.3f},"
                        + f"trim=duration={duration:.3f},setpts=PTS-STARTPTS,"
                        + f"scale={width}:{height}:flags=lanczos,fps={fps_text}[out]"
                    )
                    filter_args = ["-filter_complex", graph, "-map", "[out]"]
                proc = subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(video_path),
                        *filter_args,
                        "-an",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "fast",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                        "-movflags",
                        "+faststart",
                        str(out_path),
                    ],
                    stderr=subprocess.PIPE,
                )
                if proc.returncode != 0:
                    err = proc.stderr.decode("utf-8", errors="replace")
                    sys.exit(f"sources.{name}: ffmpeg failed\n{err[-2000:]}")

            rel = os.path.relpath(out_path, Path.cwd()).replace("\\", "/")
            fresh = json.loads(plan_path.read_text())
            fresh_sources = fresh.get("sources")
            if not isinstance(fresh_sources, dict) or name not in fresh_sources:
                sys.exit(f"sources.{name}: missing from {plan_path}")
            fresh_sources[name]["path"] = rel
            plan_path.write_text(json.dumps(fresh, indent=2, ensure_ascii=False) + "\n")
            print(f"browser recording {name} → {rel}")
    finally:
        browser.close()
        playwright.stop()


if __name__ == "__main__":
    main()
