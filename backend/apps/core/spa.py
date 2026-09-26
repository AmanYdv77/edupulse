"""
Single Page Application (SPA) view for serving the built React frontend.
Provides index.html fallback for client-side routing at /app/.
"""

import logging
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse, HttpResponseServerError
from django.views import View

logger = logging.getLogger(__name__)


class SPAIndexView(View):
    """
    Serves the production index.html built by Vite in frontend/dist.
    Acts as a catch-all view for client-side routes under /app/*.
    """

    def get(self, request, *args, **kwargs):
        repo_dir = getattr(settings, "REPO_DIR", settings.BASE_DIR.parent)
        dist_dir = getattr(settings, "FRONTEND_DIST_DIR", repo_dir / "frontend" / "dist")
        index_file = dist_dir / "index.html"

        if not index_file.is_file():
            logger.warning("SPA index.html not found at %s", index_file)
            fallback_html = (
                "<!DOCTYPE html><html><head><title>EduPulse</title></head>"
                "<body style='font-family:sans-serif;background:#0b0f19;color:#f9fafb;padding:2rem;text-align:center;'>"
                "<h1>EduPulse Frontend</h1>"
                "<p style='color:#9ca3af;'>Frontend distribution build not found. Please run <code>npm run build</code> inside the <code>frontend/</code> directory.</p>"
                "</body></html>"
            )
            response = HttpResponse(fallback_html, content_type="text/html; charset=utf-8", status=200)
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return response

        try:
            content = index_file.read_text(encoding="utf-8")
            response = HttpResponse(content, content_type="text/html; charset=utf-8", status=200)
            # Ensure the HTML shell is never cached so users get updated JS/CSS bundles immediately
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return response
        except Exception as e:
            logger.error("Error reading SPA index.html: %s", e)
            return HttpResponseServerError("Failed to load SPA index file.")
