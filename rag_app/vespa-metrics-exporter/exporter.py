#!/usr/bin/env python3
"""
Tiny Vespa -> Prometheus metrics exporter.

Vespa exposes metrics as JSON at: http://vespa:19071/metrics/v2/values
Prometheus prefers text exposition format at: /metrics

This exporter fetches Vespa JSON on each scrape and exposes a single Gauge:

  vespa_metric_value{metric="...", stat="...", node="...", service="..."} <number>

To avoid high cardinality, set EXPORT_PATH_REGEX to filter metric names.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Iterable, List, Optional, Tuple

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest


VESPA_METRICS_URL = os.getenv("VESPA_METRICS_URL", "http://vespa:19071/metrics/v2/values")
EXPORT_PATH_REGEX = os.getenv("EXPORT_PATH_REGEX", "")
LISTEN_HOST = os.getenv("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("LISTEN_PORT", "9109"))
FETCH_TIMEOUT_SECONDS = float(os.getenv("FETCH_TIMEOUT_SECONDS", "2.5"))

_FILTER: Optional[re.Pattern[str]] = re.compile(EXPORT_PATH_REGEX, re.IGNORECASE) if EXPORT_PATH_REGEX else None


def _fetch_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8"))


def _iter_metric_objects(obj: Any, ctx: Dict[str, str]) -> Iterable[Tuple[Dict[str, str], Dict[str, Any]]]:
    """
    Traverse Vespa metrics JSON and yield (context_labels, metric_obj) for each object that looks like:
      { "values": { ... }, "dimensions": { ... } }

    Note: In Vespa /metrics/v2/values, the metric *names* are usually the keys inside the "values" dict, e.g.:
      { "values": { "query_latency.average": 181, "queries.rate": 0.1 }, "dimensions": {...} }
    """
    if isinstance(obj, dict):
        # enrich context when these keys exist
        for key, label in (("hostname", "node"), ("serviceId", "service"), ("service", "service")):
            v = obj.get(key)
            if isinstance(v, str) and v:
                ctx = {**ctx, label: v}

        # Vespa metrics objects typically look like: {"values": {...}, "dimensions": {...}}
        if "values" in obj and "dimensions" in obj and isinstance(obj["values"], dict) and isinstance(obj["dimensions"], dict):
            dims = obj.get("dimensions") or {}
            ctx2 = ctx
            # Pull the service id from the dimensions so we don't collapse multiple services into one series.
            if isinstance(dims, dict):
                sid = dims.get("serviceId") or dims.get("service")
                if isinstance(sid, str) and sid:
                    ctx2 = {**ctx2, "service": sid}
            yield ctx2, obj

        for v in obj.values():
            yield from _iter_metric_objects(v, ctx)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_metric_objects(item, ctx)


def _flatten_values(values: Dict[str, Any]) -> Iterable[Tuple[str, float]]:
    """
    Vespa values is a dict where keys are metric names and values are numbers, e.g.:
      {"query_latency.average": 181, "queries.rate": 0.1}
    """
    for k, v in values.items():
        if isinstance(v, (int, float)):
            yield k, float(v)


_KNOWN_STATS = {
    "average",
    "sum",
    "count",
    "max",
    "min",
    "rate",
    "last",
}


def _split_metric_and_stat(key: str) -> Tuple[str, str]:
    """
    Split "query_latency.average" -> ("query_latency", "average")
    If no known stat suffix exists, return (key, "value").
    """
    if "." in key:
        base, suffix = key.rsplit(".", 1)
        if suffix in _KNOWN_STATS:
            return base, suffix
    return key, "value"


def build_registry() -> CollectorRegistry:
    registry = CollectorRegistry()
    gauge = Gauge(
        "vespa_metric_value",
        "Vespa metric values exported from /metrics/v2/values",
        labelnames=["metric", "stat", "node", "service"],
        registry=registry,
    )

    try:
        payload = _fetch_json(VESPA_METRICS_URL)
    except Exception as e:
        # Expose an "up" style signal via stderr; Prometheus will see missing series.
        print(f"[exporter] ERROR fetching {VESPA_METRICS_URL}: {e}", file=sys.stderr)
        return registry

    for ctx, metric_obj in _iter_metric_objects(payload, ctx={"node": "", "service": ""}):
        values = metric_obj.get("values", {})
        if not isinstance(values, dict):
            continue
        for key, num in _flatten_values(values):
            # Filter on the full key (most specific), not the base metric.
            if _FILTER and not _FILTER.search(key):
                continue
            metric, stat = _split_metric_and_stat(key)
            gauge.labels(
                metric=metric,
                stat=stat,
                node=ctx.get("node", ""),
                service=ctx.get("service", ""),
            ).set(num)

    return registry


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return

        if self.path != "/metrics":
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"not found\n")
            return

        start = time.time()
        registry = build_registry()
        body = generate_latest(registry)

        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_LATEST)
        self.send_header("X-Exporter-Gen-Secs", f"{time.time() - start:.4f}")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        # keep logs quiet
        return


def main() -> int:
    print(f"[exporter] Vespa metrics URL: {VESPA_METRICS_URL}")
    print(f"[exporter] Export filter regex: {EXPORT_PATH_REGEX or '(none)'}")
    httpd = HTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(f"[exporter] Listening on http://{LISTEN_HOST}:{LISTEN_PORT}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



