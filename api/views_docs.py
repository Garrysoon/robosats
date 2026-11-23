import os
import re
from pathlib import Path
import markdown

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

DOCS_MAP = {
    "launch": {
        "title": "Руководство по запуску и эксплуатации (Production Launch Guide)",
        "file": "docs/coordinator_production_launch_guide.md",
        "icon": "rocket_launch",
    },
    "disputes": {
        "title": "Регламент арбитража споров (Dispute Manual)",
        "file": "docs/coordinator_dispute_manual.md",
        "icon": "gavel",
    },
    "i18n": {
        "title": "Руководство по локализации (i18n Guide)",
        "file": "docs/localization.md",
        "icon": "translate",
    },
}


@staff_member_required(login_url="/coordinator/login/")
def coordinator_docs_view(request, doc_id="launch"):
    if doc_id not in DOCS_MAP:
        doc_id = "launch"

    doc_info = DOCS_MAP[doc_id]
    file_path = settings.BASE_DIR / doc_info["file"]

    content = ""
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            raw_md = f.read()

        # Format alerts like > [!NOTE], > [!IMPORTANT], > [!WARNING]
        raw_md = re.sub(
            r"> \[!NOTE\]\s*(.*?)(?=\n\n|\n[^\>]|$)",
            r'<div class="doc-alert doc-alert-note"><b>ℹ️ Примечание:</b> \1</div>',
            raw_md,
            flags=re.DOTALL,
        )
        raw_md = re.sub(
            r"> \[!IMPORTANT\]\s*(.*?)(?=\n\n|\n[^\>]|$)",
            r'<div class="doc-alert doc-alert-important"><b>⚠️ Важно:</b> \1</div>',
            raw_md,
            flags=re.DOTALL,
        )
        raw_md = re.sub(
            r"> \[!WARNING\]\s*(.*?)(?=\n\n|\n[^\>]|$)",
            r'<div class="doc-alert doc-alert-warning"><b>🚨 Предупреждение:</b> \1</div>',
            raw_md,
            flags=re.DOTALL,
        )

        content = markdown.markdown(
            raw_md,
            extensions=["tables", "fenced_code", "toc"],
        )

    admin_context = admin.site.each_context(request)
    context = {
        **admin_context,
        "title": doc_info["title"],
        "doc_id": doc_id,
        "docs_map": DOCS_MAP,
        "content": mark_safe(content),
        "is_nav_sidebar_enabled": True,
        "has_permission": True,
    }
    return render(request, "admin/coordinator_docs.html", context)
