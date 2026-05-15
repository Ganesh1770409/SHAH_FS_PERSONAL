"""Central logging: stdout for Render (real-time) + rotating files locally."""
from __future__ import annotations

import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, g, request

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(app: Flask) -> None:
    level_name = (app.config.get("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    log_dir = Path(app.config.get("LOG_DIR") or "logs")
    on_render = os.environ.get("RENDER") == "true"
    log_to_file = app.config.get("LOG_TO_FILE")
    if log_to_file is None:
        log_to_file = not on_render

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_to_file:
        log_dir.mkdir(parents=True, exist_ok=True)
        max_bytes = int(app.config.get("LOG_MAX_BYTES", 5 * 1024 * 1024))
        backup_count = int(app.config.get("LOG_BACKUP_COUNT", 5))

        app_handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        app_handler.setFormatter(formatter)
        app_handler.setLevel(level)
        root.addHandler(app_handler)

        error_handler = RotatingFileHandler(
            log_dir / "error.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.WARNING)
        root.addHandler(error_handler)

    for name in ("werkzeug", "gunicorn", "gunicorn.error", "gunicorn.access"):
        logging.getLogger(name).setLevel(level)

    app.logger.handlers.clear()
    app.logger.propagate = True
    app.logger.setLevel(level)

    env_label = "render" if on_render else "local"
    targets = "stdout" + (f", {log_dir}/" if log_to_file else "")
    app.logger.info("Logging started env=%s level=%s targets=%s", env_label, level_name, targets)

    _register_request_logging(app)


def _register_request_logging(app: Flask) -> None:
    @app.before_request
    def _log_request_start() -> None:
        g._req_start = time.perf_counter()

    @app.after_request
    def _log_request_end(response):
        duration_ms = (time.perf_counter() - g.get("_req_start", time.perf_counter())) * 1000
        user_id = "-"
        try:
            from flask_login import current_user

            if current_user.is_authenticated:
                user_id = str(current_user.id)
        except Exception:
            pass
        log_fn = app.logger.info if response.status_code < 400 else app.logger.warning
        if response.status_code >= 500:
            log_fn = app.logger.error
        log_fn(
            "%s %s %s | %d | %.0fms | user=%s",
            request.method,
            request.path,
            request.remote_addr or "-",
            response.status_code,
            duration_ms,
            user_id,
        )
        return response
