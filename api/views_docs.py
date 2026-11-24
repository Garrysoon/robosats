import os
import re
from pathlib import Path
import markdown

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import translation
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

DOCS_MAP = {
    "launch": {
        "title": _("Руководство по запуску и эксплуатации (Production Launch Guide)"),
        "tab_title": _("Инструкция по запуску"),
        "file": "coordinator_production_launch_guide",
        "icon": "rocket_launch",
    },
    "disputes": {
        "title": _("Регламент арбитража споров (Dispute Manual)"),
        "tab_title": _("Регламент арбитража"),
        "file": "coordinator_dispute_manual",
        "icon": "gavel",
    },
    "i18n": {
        "title": _("Руководство по локализации (i18n Guide)"),
        "tab_title": _("Локализация и i18n"),
        "file": "localization",
        "icon": "translate",
    },
}


@staff_member_required(login_url="/coordinator/login/")
def coordinator_docs_view(request, doc_id="launch"):
    if doc_id not in DOCS_MAP:
        doc_id = "launch"

    doc_info = DOCS_MAP[doc_id]
    base_file = doc_info["file"]

    lang = translation.get_language() or "ru"
    candidates = [
        settings.BASE_DIR / f"docs/{base_file}.{lang}.md",
        settings.BASE_DIR / f"docs/{base_file}.{lang.replace('-', '_')}.md",
        settings.BASE_DIR / f"docs/{base_file}.{lang.split('-')[0]}.md",
        settings.BASE_DIR / f"docs/{base_file}.md",
    ]
    file_path = candidates[-1]
    for cand in candidates:
        if cand.exists():
            file_path = cand
            break

    content = ""
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            raw_md = f.read()

        # Format alerts like > [!NOTE], > [!IMPORTANT], > [!WARNING]
        note_label = str(_("Примечание"))
        important_label = str(_("Важно"))
        warning_label = str(_("Предупреждение"))
        raw_md = re.sub(
            r"> \[!NOTE\]\s*(.*?)(?=\n\n|\n[^\>]|$)",
            rf'<div class="doc-alert doc-alert-note"><b>ℹ️ {note_label}:</b> \1</div>',
            raw_md,
            flags=re.DOTALL,
        )
        raw_md = re.sub(
            r"> \[!IMPORTANT\]\s*(.*?)(?=\n\n|\n[^\>]|$)",
            rf'<div class="doc-alert doc-alert-important"><b>⚠️ {important_label}:</b> \1</div>',
            raw_md,
            flags=re.DOTALL,
        )
        raw_md = re.sub(
            r"> \[!WARNING\]\s*(.*?)(?=\n\n|\n[^\>]|$)",
            rf'<div class="doc-alert doc-alert-warning"><b>🚨 {warning_label}:</b> \1</div>',
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
