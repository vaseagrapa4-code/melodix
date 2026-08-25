"""
Tiny keep-alive HTTP server.

Some free hosts (e.g. Render's free Web Service) require the app to listen on a
port, and they put the app to sleep without HTTP traffic. This module starts a
minimal web server that answers health checks, so:
  * the platform sees an open port and considers the deploy healthy;
  * an external pinger (e.g. UptimeRobot) can hit "/" every few minutes to keep
    the instance awake.

It only runs when a PORT environment variable is present, so it does nothing on
platforms/worker types that don't need it (or when running locally).
"""

import logging
import os

from aiohttp import web

logger = logging.getLogger(__name__)


async def _health(request: web.Request) -> web.Response:
    return web.Response(text="Melodix bot is alive")


async def start_keepalive() -> web.AppRunner | None:
    """Start the health server if a PORT is provided. Returns the runner."""
    port = os.getenv("PORT")
    if not port:
        return None  # nothing to do (worker mode / local)

    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(port))
    await site.start()
    logger.info("Keep-alive HTTP server listening on port %s", port)
    return runner
