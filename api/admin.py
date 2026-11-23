from statistics import median

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, User
from django.db.models import F
from django.urls import reverse
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from django_admin_relation_links import AdminChangeLinksMixin
from rest_framework.authtoken.admin import TokenAdmin
from rest_framework.authtoken.models import TokenProxy
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from api.logics import Logics
from api.models import (
    Currency,
    LNPayment,
    MarketTick,
    OnchainPayment,
    Order,
    Robot,
    CoordinatorNode,
    CoordinatorCheckLog,
    TaprootEscrowContract,
    EmailInboxConfig,
)
from api.utils import render_order_logs
from api.tasks import send_notification

admin.site.unregister(Group)
admin.site.unregister(User)
admin.site.unregister(TokenProxy)


class RobotInline(admin.StackedInline):
    model = Robot
    can_delete = False
    show_change_link = True


@admin.register(User)
class EUserAdmin(AdminChangeLinksMixin, UserAdmin):
    inlines = [RobotInline]
    list_display = (
        "id",
        "robot_link",
        "username",
        "last_login",
        "date_joined",
        "is_staff",
    )
    list_display_links = ("id", "username")
    change_links = ("robot",)
    ordering = ("-id",)


# extended tokens with raw id fields
@admin.register(TokenProxy)
class ETokenAdmin(AdminChangeLinksMixin, TokenAdmin):
    raw_id_fields = ["user"]
    list_display = (
        "key",
        "user_link",
    )
    list_display_links = ("key",)
    change_links = ("user",)


class LNPaymentInline(admin.StackedInline):
    model = LNPayment
    can_delete = True
    fields = (
        "payment_hash",
        "num_satoshis",
        "status",
        "routing_budget_sats",
        "description",
    )
    readonly_fields = (
        "payment_hash",
        "num_satoshis",
        "status",
        "routing_budget_sats",
        "description",
    )
    show_change_link = True
    show_full_result_count = True
    extra = 0


@admin.register(Order)
class OrderAdmin(AdminChangeLinksMixin, ModelAdmin):
    inlines = [LNPaymentInline]
    list_display = (
        "order_badge",
        "parties_display",
        "amount_display",
        "status_badge",
        "evidence_display",
        "verdict_display",
        "quick_actions",
    )
    list_display_links = ("order_badge",)
    ordering = ("-is_disputed", "-id")
    change_links = (
        "maker",
        "taker",
        "currency",
        "payout_tx",
        "payout",
        "maker_bond",
        "taker_bond",
        "trade_escrow",
    )
    raw_id_fields = (
        "maker",
        "taker",
        "payout_tx",
        "payout",
        "maker_bond",
        "taker_bond",
        "trade_escrow",
    )
    list_filter = (
        "is_disputed",
        "is_fiat_sent",
        "is_swap",
        "type",
        "currency",
        "status",
    )
    search_fields = [
        "id",
        "reference",
        "maker__username",
        "taker__username",
        "amount",
        "payout__payment_hash",
        "maker_bond__payment_hash",
        "taker_bond__payment_hash",
        "trade_escrow__payment_hash",
        "payout_tx__txid",
        "payout_tx__address",
        "min_amount",
        "max_amount",
    ]
    readonly_fields = ("dispute_cockpit", "reference", "_logs")

    fieldsets = (
        (
            _("🚨 ПУЛЬТ АРБИТРАЖА СПОРА (DISPUTE COCKPIT)"),
            {
                "fields": ("dispute_cockpit",),
            },
        ),
        (
            _("Параметры сделки"),
            {
                "fields": (
                    "status",
                    "type",
                    "currency",
                    "amount",
                    "satoshis",
                    "payment_method",
                    "reference",
                    "maker",
                    "taker",
                ),
            },
        ),
        (
            _("Заявления сторон спора"),
            {
                "fields": (
                    "is_disputed",
                    "is_fiat_sent",
                    "maker_statement",
                    "taker_statement",
                ),
            },
        ),
        (
            _("Залоги и платежи эскроу"),
            {
                "fields": (
                    "maker_bond",
                    "taker_bond",
                    "trade_escrow",
                    "payout",
                    "payout_tx",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Логи аудита"),
            {
                "fields": ("_logs",),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description=_("Сделка"), ordering="id")
    def order_badge(self, obj):
        change_url = reverse("admin:api_order_change", args=[obj.id])
        type_style = (
            "background:#064e3b;color:#34d399;border:1px solid #059669;"
            if obj.type == 0
            else "background:#1e3a5f;color:#60a5fa;border:1px solid #2563eb;"
        )
        type_label = _("ПОКУПКА") if obj.type == 0 else _("ПРОДАЖА")
        created_str = obj.created_at.strftime("%d.%m %H:%M") if obj.created_at else ""
        return mark_safe(
            f'<div style="font-size:12px;line-height:1.3;">'
            f'  <div style="display:flex;align-items:center;gap:6px;">'
            f'    <a href="{change_url}" style="font-weight:700;font-size:13px;color:#c084fc;text-decoration:none;">#{obj.id}</a>'
            f'    <span style="padding:1px 6px;border-radius:4px;font-size:10px;font-weight:700;{type_style}">{type_label}</span>'
            f'  </div>'
            f'  <div style="color:#64748b;font-size:11px;margin-top:3px;white-space:nowrap;">{created_str}</div>'
            f'</div>'
        )

    @admin.display(description=_("Стороны (Покупатель / Продавец)"))
    def parties_display(self, obj):
        maker_is_buyer = Logics.is_buyer(obj, obj.maker) if obj.maker else True
        if maker_is_buyer:
            buyer = obj.maker
            buyer_role = "Мейкер"
            seller = obj.taker
            seller_role = "Тейкер"
        else:
            buyer = obj.taker
            buyer_role = "Тейкер"
            seller = obj.maker
            seller_role = "Мейкер"

        if buyer:
            buyer_url = reverse("admin:api_robot_change", args=[buyer.id])
            buyer_html = f'<a href="{buyer_url}" style="color:#f8fafc;font-weight:600;text-decoration:none;">{buyer.username}</a> <span style="color:#64748b;font-size:10px;">({buyer_role})</span>'
        else:
            buyer_html = '<span style="color:#64748b;">— Ожидает —</span>'

        if seller:
            seller_url = reverse("admin:api_robot_change", args=[seller.id])
            seller_html = f'<a href="{seller_url}" style="color:#f8fafc;font-weight:600;text-decoration:none;">{seller.username}</a> <span style="color:#64748b;font-size:10px;">({seller_role})</span>'
        else:
            seller_html = '<span style="color:#64748b;">— Ожидает —</span>'

        return mark_safe(
            f'<div style="font-size:12px;line-height:1.4;">'
            f'  <div style="display:flex;align-items:center;gap:4px;white-space:nowrap;">'
            f'    <span style="color:#10b981;font-weight:700;">🟢 Покупатель:</span> {buyer_html}'
            f'  </div>'
            f'  <div style="display:flex;align-items:center;gap:4px;white-space:nowrap;margin-top:2px;">'
            f'    <span style="color:#f43f5e;font-weight:700;">🔴 Продавец:</span> {seller_html}'
            f'  </div>'
            f'</div>'
        )

    @admin.display(description=_("Сумма и объем"), ordering="amount")
    def amount_display(self, obj):
        curr = str(obj.currency) if obj.currency else ""
        try:
            amt_val = f"{float(obj.amount):,.1f}".replace(",", " ").replace(".", ",")
        except Exception:
            amt_val = str(obj.amount)

        sats_html = ""
        sats = obj.satoshis or obj.t0_satoshis
        if sats:
            try:
                sats_val = f"{int(sats):,}".replace(",", " ")
            except Exception:
                sats_val = str(sats)
            sats_html = f'<div style="color:#fbbf24;font-size:11px;font-weight:600;margin-top:1px;white-space:nowrap;">⚡ {sats_val} sat</div>'

        method_html = ""
        if obj.payment_method:
            method_html = f'<div style="color:#94a3b8;font-size:10px;margin-top:1px;white-space:nowrap;">💳 {obj.payment_method}</div>'

        return mark_safe(
            f'<div style="font-size:12px;line-height:1.3;">'
            f'  <div style="font-weight:700;font-size:13px;color:#f8fafc;white-space:nowrap;">{amt_val} {curr}</div>'
            f'  {sats_html}'
            f'  {method_html}'
            f'</div>'
        )

    @admin.display(description=_("Статус и фиат"), ordering="status")
    def status_badge(self, obj):
        if obj.is_disputed:
            st_html = '<span style="display:inline-block;padding:2px 8px;border-radius:6px;background:#7f1d1d;color:#fca5a5;font-weight:700;font-size:11px;border:1px solid #ef4444;white-space:nowrap;">🚨 В СПОРЕ</span>'
        else:
            st_name = obj.get_status_display()
            st_html = f'<span style="display:inline-block;padding:2px 8px;border-radius:6px;background:#1e293b;color:#cbd5e1;font-weight:600;font-size:11px;border:1px solid #334155;white-space:nowrap;">{st_name}</span>'

        fiat_html = (
            '<div style="color:#34d399;font-size:11px;font-weight:600;margin-top:2px;white-space:nowrap;">💸 Фиат отправлен</div>'
            if obj.is_fiat_sent
            else '<div style="color:#64748b;font-size:11px;margin-top:2px;white-space:nowrap;">⏳ Ожидание фиата</div>'
        )

        f2f_html = ""
        if obj.check_is_f2f():
            f2f_html = '<div style="color:#f59e0b;font-size:11px;font-weight:600;margin-top:1px;white-space:nowrap;">🤝 F2F (Наличные)</div>'

        return mark_safe(
            f'<div style="font-size:12px;line-height:1.3;">'
            f'  {st_html}'
            f'  {fiat_html}'
            f'  {f2f_html}'
            f'</div>'
        )

    @admin.display(description=_("Банковский чек (DKIM/PDF)"))
    def evidence_display(self, obj):
        if not obj.is_disputed:
            return mark_safe("<span style='color:#64748b;font-size:11px;'>—</span>")
        try:
            from api.dkim_verifier import validate_receipt_for_order
            for st in [obj.taker_statement, obj.maker_statement]:
                if st and ("DKIM-Signature:" in st or "From:" in st or "%PDF" in st):
                    raw_b = st.encode("utf-8") if isinstance(st, str) else st
                    valid, msg, receipt = validate_receipt_for_order(obj, raw_b)
                    if valid:
                        pdf_icon = (
                            " +PDF"
                            if receipt.get("pdf_attachments_count", 0) > 0 or receipt.get("is_standalone_pdf")
                            else ""
                        )
                        return mark_safe(
                            f'<div style="font-size:12px;line-height:1.3;">'
                            f'  <div style="display:inline-block;padding:2px 8px;border-radius:6px;background:#064e3b;color:#6ee7b7;font-weight:600;font-size:11px;border:1px solid #059669;white-space:nowrap;">✓ {receipt.get("domain")}{pdf_icon} PASS</div>'
                            f'  <div style="color:#94a3b8;font-size:10px;margin-top:2px;white-space:nowrap;">Чек: {receipt.get("amount")} {receipt.get("currency")}</div>'
                            f'</div>'
                        )
                    elif receipt.get("is_trusted_bank"):
                        return mark_safe(
                            f'<div style="display:inline-block;padding:2px 8px;border-radius:6px;background:#451a03;color:#fdba74;font-size:11px;border:1px solid #d97706;white-space:nowrap;">⚠ {receipt.get("domain")} (FAIL)</div>'
                        )
        except Exception:
            pass

        if obj.check_is_f2f():
            pin_state = "PIN активен" if obj.f2f_release_secret_hash else "Ожидание PIN"
            both = " | Оба прибыли" if (obj.f2f_arrived_maker and obj.f2f_arrived_taker) else ""
            return mark_safe(
                f'<div style="display:inline-block;padding:2px 8px;border-radius:6px;background:#172554;color:#93c5fd;font-size:11px;border:1px solid #2563eb;white-space:nowrap;">🤝 F2F ({pin_state}{both})</div>'
            )

        return mark_safe("<span style='color:#64748b;font-size:11px;'>— Чек не загружен</span>")

    @admin.display(description=_("Вердикт авто-арбитража"))
    def verdict_display(self, obj):
        if not obj.is_disputed:
            return mark_safe("<span style='color:#64748b;font-size:11px;'>—</span>")
        try:
            from api.dispute_automation import DisputeRecommendationEngine
            rec = DisputeRecommendationEngine.analyze_order(obj)
            conf_pct = int(rec.confidence * 100)
            if rec.action == "successful_trade":
                return mark_safe(
                    f'<div style="font-size:12px;line-height:1.3;">'
                    f'  <div style="display:inline-block;padding:3px 8px;border-radius:6px;background:#064e3b;color:#34d399;font-weight:700;font-size:11px;border:1px solid #10b981;white-space:nowrap;" title="{rec.reason}">🤖 {conf_pct}% Выплата покупателю</div>'
                    f'  <div style="color:#94a3b8;font-size:10px;margin-top:2px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="{rec.reason}">{rec.reason}</div>'
                    f'</div>'
                )
            elif rec.action in ["maker_wins", "taker_wins"]:
                role = "мейкера" if rec.action == "maker_wins" else "тейкера"
                return mark_safe(
                    f'<div style="font-size:12px;line-height:1.3;">'
                    f'  <div style="display:inline-block;padding:3px 8px;border-radius:6px;background:#1e3a5f;color:#60a5fa;font-weight:700;font-size:11px;border:1px solid #3b82f6;white-space:nowrap;" title="{rec.reason}">⏱️ {conf_pct}% Победа {role}</div>'
                    f'  <div style="color:#94a3b8;font-size:10px;margin-top:2px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="{rec.reason}">{rec.reason}</div>'
                    f'</div>'
                )
            elif rec.action == "return_everything":
                return mark_safe(
                    f'<div style="font-size:12px;line-height:1.3;">'
                    f'  <div style="display:inline-block;padding:3px 8px;border-radius:6px;background:#3b0764;color:#c084fc;font-weight:700;font-size:11px;border:1px solid #a855f7;white-space:nowrap;" title="{rec.reason}">↩️ {conf_pct}% Возврат средств</div>'
                    f'  <div style="color:#94a3b8;font-size:10px;margin-top:2px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="{rec.reason}">{rec.reason}</div>'
                    f'</div>'
                )
            else:
                return mark_safe(
                    f'<div style="font-size:12px;line-height:1.3;">'
                    f'  <div style="display:inline-block;padding:3px 8px;border-radius:6px;background:#1e293b;color:#cbd5e1;font-weight:600;font-size:11px;border:1px solid #475569;white-space:nowrap;" title="{rec.reason}">👤 Ручное рассмотрение</div>'
                    f'  <div style="color:#94a3b8;font-size:10px;margin-top:2px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="{rec.reason}">{rec.reason}</div>'
                    f'</div>'
                )
        except Exception:
            return mark_safe("<span style='color:#64748b;font-size:11px;'>—</span>")

    @admin.display(description=_("Решение"))
    def quick_actions(self, obj):
        change_url = reverse("admin:api_order_change", args=[obj.id])
        if obj.is_disputed:
            return mark_safe(
                f'<a href="{change_url}" style="display:inline-flex;align-items:center;gap:4px;padding:5px 12px;border-radius:6px;background:#7e22ce;color:#ffffff;font-size:12px;font-weight:700;text-decoration:none;white-space:nowrap;box-shadow:0 1px 2px rgba(0,0,0,0.3);transition:background 0.2s;" onmouseover="this.style.background=\'#9333ea\'" onmouseout="this.style.background=\'#7e22ce\'">'
                f'  🚨 Пульт спора →'
                f'</a>'
            )
        else:
            return mark_safe(
                f'<a href="{change_url}" style="display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:6px;background:#1e293b;color:#94a3b8;font-size:11px;font-weight:600;text-decoration:none;border:1px solid #334155;white-space:nowrap;transition:color 0.2s;" onmouseover="this.style.color=\'#f8fafc\'" onmouseout="this.style.color=\'#94a3b8\'">'
                f'  Карточка →'
                f'</a>'
            )

    @admin.display(description=_("🚨 Dispute Cockpit"))
    def dispute_cockpit(self, obj):
        if not obj:
            return ""

        # 1. AI / Rules Recommendation Badge
        rec_html = ""
        try:
            from api.dispute_automation import DisputeRecommendationEngine
            rec = DisputeRecommendationEngine.analyze_order(obj)
            conf_pct = int(rec.confidence * 100)
            rec_html = f"""
            <div style="background: #1e293b; color: #f8fafc; padding: 14px 18px; border-radius: 8px; margin-bottom: 14px; border-left: 4px solid #38bdf8;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: #94a3b8;">🤖 Рекомендация Авто-Арбитража</span>
                    <span style="background: #0284c7; color: white; padding: 2px 8px; border-radius: 9999px; font-weight: 700; font-size: 12px;">Уверенность: {conf_pct}%</span>
                </div>
                <div style="font-size: 15px; font-weight: 700; color: #38bdf8; margin-bottom: 4px;">⚡ Вердикт: {rec.action.upper().replace('_', ' ')}</div>
                <div style="font-size: 13px; color: #cbd5e1; line-height: 1.4;">Обоснование: {rec.reason}</div>
            </div>
            """
        except Exception:
            rec_html = ""

        # 2. Bank DKIM Receipt Card
        receipt_html = ""
        try:
            from api.dkim_verifier import validate_receipt_for_order
            for st in [obj.taker_statement, obj.maker_statement]:
                if st and ("DKIM-Signature:" in st or "From:" in st or "%PDF" in st):
                    raw_b = st.encode("utf-8") if isinstance(st, str) else st
                    valid, msg, receipt = validate_receipt_for_order(obj, raw_b)
                    if valid:
                        pdf_txt = " +PDF Вложение" if receipt.get("pdf_attachments_count", 0) > 0 or receipt.get("is_standalone_pdf") else ""
                        receipt_html = f"""
                        <div style="background: #064e3b; color: #ecfdf5; padding: 14px 18px; border-radius: 8px; margin-bottom: 14px; border-left: 4px solid #10b981;">
                            <div style="font-weight: 700; font-size: 14px; margin-bottom: 4px; color: #34d399;">✓ БАНКОВСКИЙ ЧЕК ВЕРИФИЦИРОВАН (DKIM PASS{pdf_txt})</div>
                            <div style="font-size: 13px; line-height: 1.5;">
                                Банк: <b>{receipt.get('bank')}</b> ({receipt.get('domain')}) | Сумма: <b>{receipt.get('amount')} {receipt.get('currency')}</b> | Код: <b>{receipt.get('reference')}</b>
                            </div>
                        </div>
                        """
                        break
        except Exception:
            pass

        if not receipt_html:
            receipt_html = """
            <div style="background: #1e293b; color: #94a3b8; padding: 12px 16px; border-radius: 8px; margin-bottom: 14px; font-size: 13px; border: 1px dashed #475569;">
                📄 Банковский чек DKIM/PDF еще не загружен сторонами спора.
            </div>
            """

        # 3. Statements side-by-side
        maker_st = obj.maker_statement or "— Нет заявления —"
        taker_st = obj.taker_statement or "— Нет заявления —"
        statements_html = f"""
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px;">
            <div style="background: #1e293b; padding: 12px 14px; border-radius: 8px; border: 1px solid #334155;">
                <div style="font-weight: 700; color: #38bdf8; font-size: 12px; margin-bottom: 6px; text-transform: uppercase;">Позиция Мейкера:</div>
                <div style="font-size: 12px; color: #f1f5f9; max-height: 140px; overflow-y: auto; white-space: pre-wrap; line-height: 1.4;">{maker_st}</div>
            </div>
            <div style="background: #1e293b; padding: 12px 14px; border-radius: 8px; border: 1px solid #334155;">
                <div style="font-weight: 700; color: #f472b6; font-size: 12px; margin-bottom: 6px; text-transform: uppercase;">Позиция Тейкера:</div>
                <div style="font-size: 12px; color: #f1f5f9; max-height: 140px; overflow-y: auto; white-space: pre-wrap; line-height: 1.4;">{taker_st}</div>
            </div>
        </div>
        """

        cockpit_box = f"""
        <div style="background: #0f172a; border: 1px solid #334155; border-radius: 12px; padding: 18px; margin-bottom: 12px; font-family: system-ui, -apple-system, sans-serif;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; border-bottom: 1px solid #334155; padding-bottom: 10px;">
                <span style="font-size: 16px; font-weight: 700; color: #f8fafc;">🚨 Кабинет арбитра: Сделка #{obj.id} ({obj.amount} {obj.currency} / {obj.satoshis} sats)</span>
                <span style="font-size: 13px; color: #94a3b8;">Статус: <b style="color: #fbbf24;">{obj.get_status_display()}</b></span>
            </div>
            {rec_html}
            {receipt_html}
            {statements_html}
            <div style="font-size: 12px; color: #94a3b8; padding-top: 6px;">
                💡 <b>Быстрое разрешение:</b> выберите необходимое действие в выпадающем меню <i>«Действие»</i> списка сделок (например, <i>«⚡ Применить рекомендуемый вердикт арбитража (1 клик)»</i> или <i>«Разрешить спор: победа мейкера»</i>).
            </div>
        </div>
        """
        return mark_safe(cockpit_box)

    def _logs(self, obj):
        return mark_safe(render_order_logs(obj.logs))

    @admin.display(description=_("Bank Receipt (DKIM/PDF)"))
    def dkim_receipt(self, obj):
        if not obj.is_disputed:
            return "-"
        try:
            from api.dkim_verifier import validate_receipt_for_order
            for st in [obj.taker_statement, obj.maker_statement]:
                if st and ("DKIM-Signature:" in st or "From:" in st or "%PDF" in st):
                    raw_b = st.encode("utf-8") if isinstance(st, str) else st
                    valid, msg, receipt = validate_receipt_for_order(obj, raw_b)
                    if valid:
                        if receipt.get("is_standalone_pdf"):
                            return mark_safe(f"<span style='color:#3b82f6;font-weight:bold;'>📄 {receipt.get('domain')} (PDF match)</span>")
                        pdf_icon = " +PDF" if receipt.get("pdf_attachments_count", 0) > 0 else ""
                        return mark_safe(f"<span style='color:#10b981;font-weight:bold;'>✓ {receipt.get('domain')}{pdf_icon} PASS</span>")
                    elif receipt.get("is_trusted_bank"):
                        return mark_safe(f"<span style='color:#f59e0b;'>⚠ {receipt.get('domain')} (FAIL)</span>")
        except Exception:
            pass
        return "-"

    @admin.display(description=_("AI Verdict"))
    def arbitration_recommendation(self, obj):
        if not obj.is_disputed:
            return mark_safe("<span style='color:#9ca3af;'>-</span>")
        try:
            from api.dispute_automation import DisputeRecommendationEngine
            rec = DisputeRecommendationEngine.analyze_order(obj)
            conf_pct = int(rec.confidence * 100)
            if rec.action == "successful_trade":
                return mark_safe(f"<span style='color:#10b981;font-weight:bold;' title='{rec.reason}'>🤖 {conf_pct}% Pay Buyer (DKIM)</span>")
            elif rec.action in ["maker_wins", "taker_wins"]:
                role = "Maker" if rec.action == "maker_wins" else "Taker"
                return mark_safe(f"<span style='color:#3b82f6;font-weight:bold;' title='{rec.reason}'>⏱️ {conf_pct}% {role} Wins</span>")
            elif rec.action == "return_everything":
                return mark_safe(f"<span style='color:#8b5cf6;font-weight:bold;' title='{rec.reason}'>↩️ {conf_pct}% Return</span>")
            else:
                return mark_safe("<span style='color:#9ca3af;'>👤 Manual Review</span>")
        except Exception:
            return mark_safe("<span style='color:#9ca3af;'>-</span>")

    @admin.display(description=_("F2F Cash"))
    def f2f_badge(self, obj):
        if not obj.check_is_f2f():
            return mark_safe("<span style='color:#9ca3af;'>No</span>")
        pin_state = "PIN Active" if obj.f2f_release_secret_hash else "Pending"
        both = " | Both Here" if (obj.f2f_arrived_maker and obj.f2f_arrived_taker) else ""
        return mark_safe(
            f"<span style='padding:2px 8px; border-radius:10px; background:#f59e0b20; "
            f"color:#d97706; font-weight:600;'>🤝 F2F ({pin_state}{both})</span>"
        )

    actions = [
        "apply_recommended_arbitration",
        "cancel_public_order",
        "maker_wins",
        "taker_wins",
        "return_everything",
        "successful_trade",
        "compute_median_trade_time",
    ]

    @admin.action(description=_("⚡ Apply recommended arbitration verdict (1-Click)"))
    def apply_recommended_arbitration(self, request, queryset):
        """
        Applies pre-flight AI/rule-based arbitration recommendation in 1 click.
        """
        from api.dispute_automation import DisputeRecommendationEngine, DisputeAutomationService
        count = 0
        for order in queryset:
            if not order.is_disputed:
                self.message_user(request, f"Order #{order.id} is not in dispute", messages.WARNING)
                continue
            rec = DisputeRecommendationEngine.analyze_order(order)
            if rec.action in ["successful_trade", "maker_wins", "taker_wins", "return_everything"]:
                username = request.user.username if hasattr(request, "user") else "admin"
                success, msg = DisputeAutomationService.apply_resolution(
                    order, action=rec.action, actor=f"admin_1click_{username}", reason=rec.reason
                )
                if success:
                    count += 1
                    self.message_user(request, f"Order #{order.id}: {msg}", messages.SUCCESS)
                else:
                    self.message_user(request, f"Order #{order.id} failed: {msg}", messages.ERROR)
            else:
                self.message_user(
                    request,
                    f"Order #{order.id} cannot be auto-resolved ({rec.reason}). Manual investigation required.",
                    messages.WARNING,
                )

    @admin.action(description=_("Close public order"))
    def cancel_public_order(self, request, queryset):
        """
        Closes an existing Public/Paused order.
        """
        for order in queryset:
            if order.status in [Order.Status.PUB, Order.Status.PAU]:
                try:
                    success, _ = Logics.close_public_order(
                        order,
                        actor="coordinator",
                        notification_message="coordinator_cancelled",
                    )
                except Exception as e:
                    success = False
                    self.message_user(
                        request,
                        f"Could not close {order.id}: {e}",
                        messages.ERROR,
                    )
                    continue

                if success:
                    self.message_user(
                        request,
                        f"Order {order.id} successfully closed",
                        messages.SUCCESS,
                    )
                else:
                    self.message_user(
                        request,
                        f"Could not unlock bond of {order.id}",
                        messages.ERROR,
                    )

            else:
                self.message_user(
                    request,
                    f"Order {order.id} is not public or paused",
                    messages.ERROR,
                )

    @admin.action(description=_("Solve dispute: maker wins"))
    def maker_wins(self, request, queryset):
        """
        Solves a dispute on favor of the maker.
        Adds Sats to compensations (earned_rewards) of the maker robot.
        """
        for order in queryset:
            if (
                order.status in [Order.Status.DIS, Order.Status.WFR]
                and order.is_disputed
            ):
                own_bond_sats = order.maker_bond.num_satoshis
                if Logics.is_buyer(order, order.maker):
                    if order.is_swap:
                        trade_sats = order.payout_tx.num_satoshis
                    else:
                        trade_sats = order.payout.num_satoshis
                else:
                    trade_sats = order.trade_escrow.num_satoshis

                Robot.objects.filter(pk=order.maker.robot.pk).update(
                    earned_rewards=F("earned_rewards") + (own_bond_sats + trade_sats)
                )
                order.maker.robot.refresh_from_db(fields=["earned_rewards"])
                order.update_status(Order.Status.TLD)

                self.message_user(
                    request,
                    f"Dispute of order {order.id} solved successfully on favor of the maker",
                    messages.SUCCESS,
                )
                send_notification.delay(order_id=order.id, message="dispute_closed")

            else:
                self.message_user(
                    request,
                    f"Order {order.id} is not in a disputed state",
                    messages.ERROR,
                )

    @admin.action(description=_("Solve dispute: taker wins"))
    def taker_wins(self, request, queryset):
        """
        Solves a dispute on favor of the taker.
        Adds Sats to compensations (earned_rewards) of the taker robot.
        """
        for order in queryset:
            if (
                order.status in [Order.Status.DIS, Order.Status.WFR]
                and order.is_disputed
            ):
                own_bond_sats = order.taker_bond.num_satoshis
                if Logics.is_buyer(order, order.taker):
                    if order.is_swap:
                        trade_sats = order.payout_tx.num_satoshis
                    else:
                        trade_sats = order.payout.num_satoshis
                else:
                    trade_sats = order.trade_escrow.num_satoshis

                Robot.objects.filter(pk=order.taker.robot.pk).update(
                    earned_rewards=F("earned_rewards") + (own_bond_sats + trade_sats)
                )
                order.taker.robot.refresh_from_db(fields=["earned_rewards"])

                order.update_status(Order.Status.MLD)

                self.message_user(
                    request,
                    f"Dispute of order {order.id} solved successfully on favor of the taker",
                    messages.SUCCESS,
                )
                send_notification.delay(order_id=order.id, message="dispute_closed")

            else:
                self.message_user(
                    request,
                    f"Order {order.id} is not in a disputed state",
                    messages.ERROR,
                )

    @admin.action(description=_("Solve dispute: return everything"))
    def return_everything(self, request, queryset):
        """
        Solves a dispute by pushing back every bond and escrow to their sender.
        """
        for order in queryset:
            if (
                order.status in [Order.Status.DIS, Order.Status.WFR]
                and order.is_disputed
            ):
                Robot.objects.filter(pk=order.maker_bond.sender.robot.pk).update(
                    earned_rewards=F("earned_rewards") + order.maker_bond.num_satoshis
                )
                order.maker_bond.sender.robot.refresh_from_db(fields=["earned_rewards"])

                Robot.objects.filter(pk=order.taker_bond.sender.robot.pk).update(
                    earned_rewards=F("earned_rewards") + order.taker_bond.num_satoshis
                )
                order.taker_bond.sender.robot.refresh_from_db(fields=["earned_rewards"])

                Robot.objects.filter(pk=order.trade_escrow.sender.robot.pk).update(
                    earned_rewards=F("earned_rewards") + order.trade_escrow.num_satoshis
                )
                order.trade_escrow.sender.robot.refresh_from_db(fields=["earned_rewards"])

                order.update_status(Order.Status.CCA)

                self.message_user(
                    request,
                    f"Dispute of order {order.id} solved successfully, everything returned as compensations",
                    messages.SUCCESS,
                )

            else:
                self.message_user(
                    request,
                    f"Order {order.id} is not in a disputed state",
                    messages.ERROR,
                )

    @admin.action(description=_("Solve dispute: successful trade"))
    def successful_trade(self, request, queryset):
        """
        Solves a dispute as if the trade had been successful, i.e.,
        returns both bonds (added as compensations) and triggers the payout.
        """
        for order in queryset:
            if (
                order.status in [Order.Status.DIS, Order.Status.WFR]
                and order.is_disputed
            ):
                Robot.objects.filter(pk=order.maker.robot.pk).update(
                    earned_rewards=F("earned_rewards") + order.maker_bond.num_satoshis
                )
                order.maker.robot.refresh_from_db(fields=["earned_rewards"])

                Robot.objects.filter(pk=order.taker.robot.pk).update(
                    earned_rewards=F("earned_rewards") + order.taker_bond.num_satoshis
                )
                order.taker.robot.refresh_from_db(fields=["earned_rewards"])

                # Dispute timeouts cancel the onchain payout (order_expires ->
                # cancel_onchain_payment). The stored address was validated
                # when submitted and cannot change during a dispute, so
                # re-activate the payout; refuse to pay if no address was
                # ever validated.
                if order.is_swap and order.payout_tx:
                    if (
                        order.payout_tx.address
                        and order.payout_tx.status == OnchainPayment.Status.CANCE
                    ):
                        order.payout_tx.status = OnchainPayment.Status.VALID
                        order.payout_tx.save(update_fields=["status"])

                # Transition to PAY before initiating the payout. For onchain
                # swaps, pay_buyer() -> complete_order() only transitions to
                # SUC from [FSE, PAY, FAI]; dispute-resolved orders are in
                # DIS/WFR and would otherwise stay stuck in the dispute state
                # with proceeds never computed.
                order.update_status(Order.Status.PAY)

                paid = Logics.pay_buyer(order)

                if paid:
                    self.message_user(
                        request,
                        f"Dispute of order {order.id} solved as successful trade",
                        messages.SUCCESS,
                    )
                else:
                    self.message_user(
                        request,
                        f"Order {order.id} payout could not be initiated: escrow is not settled or payout address is not validated",
                        messages.ERROR,
                    )

            else:
                self.message_user(
                    request,
                    f"Order {order.id} is not in a disputed state",
                    messages.ERROR,
                )

    @admin.action(description=_("Compute median trade completion time"))
    def compute_median_trade_time(self, request, queryset):
        """
        Computes the median time from an order taken to finishing
        successfully for the set of selected orders.
        """
        times = []
        for order in queryset:
            if order.contract_finalization_time:
                timedelta = order.contract_finalization_time - order.last_satoshis_time
                times.append(timedelta.total_seconds())

        if len(times) > 0:
            median_time_secs = median(times)
            mins = int(median_time_secs / 60)
            secs = int(median_time_secs - mins * 60)
            self.message_user(
                request,
                f"The median time to complete the trades is {mins}m {secs}s",
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "There is no successfully finished orders in the selection",
                messages.ERROR,
            )

    def amt(self, obj):
        if obj.has_range and obj.amount is None:
            return str(float(obj.min_amount)) + "-" + str(float(obj.max_amount))
        else:
            return float(obj.amount)


class OrderInline(admin.StackedInline):
    model = Order
    can_delete = False
    show_change_link = True
    extra = 0
    fields = (
        "id",
        "type",
        "maker",
        "taker",
        "status",
        "amount",
        "currency",
        "last_satoshis",
        "is_disputed",
        "is_fiat_sent",
        "created_at",
        "expires_at",
        "payout_tx",
        "payout",
        "maker_bond",
        "taker_bond",
        "trade_escrow",
    )
    readonly_fields = fields


class PayoutOrderInline(OrderInline):
    verbose_name = "Order Paid"
    fk_name = "payout"


class MakerBondOrderInline(OrderInline):
    verbose_name = "Order Made"
    fk_name = "maker_bond"


class TakerBondOrderInline(OrderInline):
    verbose_name = "Order Taken"
    fk_name = "taker_bond"


class EscrowOrderInline(OrderInline):
    verbose_name = "Order Escrow"
    fk_name = "trade_escrow"


@admin.register(LNPayment)
class LNPaymentAdmin(AdminChangeLinksMixin, ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    inlines = [
        PayoutOrderInline,
        MakerBondOrderInline,
        TakerBondOrderInline,
        EscrowOrderInline,
    ]
    list_display = (
        "hash",
        "concept",
        "status",
        "num_satoshis",
        "fee",
        "type",
        "expires_at",
        "expiry_height",
        "sender_link",
        "receiver_link",
        "order_made_link",
        "order_taken_link",
        "order_escrow_link",
        "order_paid_LN_link",
        "order_donated_link",
    )
    list_display_links = ("hash", "concept")
    change_links = (
        "sender",
        "receiver",
        "order_made",
        "order_taken",
        "order_escrow",
        "order_paid_LN",
        "order_donated",
    )
    raw_id_fields = (
        "receiver",
        "sender",
        "order_donated",
    )
    list_filter = ("type", "concept", "status")
    ordering = ("-expires_at",)
    search_fields = [
        "payment_hash",
        "preimage",
        "num_satoshis",
        "sender__username",
        "receiver__username",
        "description",
    ]


@admin.register(OnchainPayment)
class OnchainPaymentAdmin(AdminChangeLinksMixin, ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    list_display = (
        "id",
        "address",
        "concept",
        "status",
        "broadcasted",
        "num_satoshis",
        "hash",
        "swap_fee_rate",
        "mining_fee_sats",
        "balance_link",
        "order_paid_TX_link",
    )
    change_links = (
        "balance",
        "order_paid_TX",
    )
    raw_id_fields = (
        "receiver",
        "balance",
    )
    list_display_links = ("id", "address", "concept")
    list_filter = ("concept", "status")
    search_fields = ["address", "num_satoshis", "receiver__username", "txid"]


@admin.register(Robot)
class UserRobotAdmin(AdminChangeLinksMixin, ModelAdmin):
    list_display = (
        "id",
        "user_link",
        "telegram_enabled",
        "webhook_enabled",
        "total_contracts",
        "earned_rewards",
        "claimed_rewards",
        "platform_rating",
        "num_disputes",
        "lost_disputes",
    )
    raw_id_fields = ("user",)
    list_editable = ["earned_rewards"]
    list_display_links = ["id"]
    change_links = ["user"]
    search_fields = ["user__username", "id"]
    readonly_fields = ("hash_id", "public_key", "encrypted_private_key")


@admin.register(Currency)
class CurrencieAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    list_display = ("id", "currency", "exchange_rate", "timestamp")
    list_display_links = ("id", "currency")
    readonly_fields = ("currency", "exchange_rate", "timestamp")
    ordering = ("id",)


@admin.register(MarketTick)
class MarketTickAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    list_display = ("timestamp", "price", "volume", "premium", "currency", "fee")
    readonly_fields = ("timestamp", "price", "volume", "premium", "currency", "fee")
    list_filter = ["currency"]
    ordering = ("-timestamp",)


@admin.register(CoordinatorNode)
class CoordinatorNodeAdmin(ModelAdmin):
    list_display = (
        "alias",
        "name",
        "status_badge",
        "last_response_time_ms",
        "last_order_count",
        "last_book_liquidity",
        "version",
        "uptime_24h_display",
        "last_checked_at",
    )
    list_filter = ("status", "is_active")
    search_fields = ("alias", "name", "onion_url", "clearnet_url")
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_seen_online",
        "last_checked_at",
    )
    actions = ["check_status_now", "sync_from_federation"]

    def status_badge(self, obj):
        colors = {
            CoordinatorNode.Status.ONLINE: "#10b981",  # green
            CoordinatorNode.Status.DEGRADED: "#f59e0b",  # yellow
            CoordinatorNode.Status.OFFLINE: "#ef4444",  # red
            CoordinatorNode.Status.UNKNOWN: "#6b7280",  # gray
        }
        color = colors.get(obj.status, "#6b7280")
        label = obj.get_status_display()
        return mark_safe(
            f'<span style="display:inline-block; padding:3px 8px; border-radius:12px; '
            f'background-color:{color}20; color:{color}; font-weight:600; font-size:12px;">'
            f'● {label}</span>'
        )

    status_badge.short_description = _("Status")

    def uptime_24h_display(self, obj):
        uptime = obj.calculate_uptime_24h()
        return f"{uptime}%"

    uptime_24h_display.short_description = _("24h Uptime")

    @admin.action(description=_("Check health of selected coordinators now"))
    def check_status_now(self, request, queryset):
        from api.coordinator_monitor import CoordinatorMonitorService

        service = CoordinatorMonitorService()
        checked = 0
        for node in queryset:
            service.check_coordinator(node)
            checked += 1
        self.message_user(
            request, f"Successfully checked {checked} coordinators.", messages.SUCCESS
        )

    @admin.action(description=_("Sync coordinators from federation.json"))
    def sync_from_federation(self, request, queryset):
        from api.coordinator_monitor import CoordinatorMonitorService

        service = CoordinatorMonitorService()
        count = service.sync_coordinators_from_federation()
        self.message_user(
            request, f"Synced {count} coordinators from federation seed."
        )


@admin.register(CoordinatorCheckLog)
class CoordinatorCheckLogAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
    list_display = (
        "checked_at",
        "coordinator",
        "status_badge",
        "response_time_ms",
        "order_count",
        "state_changed",
        "error_summary",
    )
    list_filter = ("status", "state_changed", "coordinator")
    search_fields = ("coordinator__alias", "coordinator__name", "error_message")
    readonly_fields = ("checked_at",)
    ordering = ("-checked_at",)

    def status_badge(self, obj):
        colors = {
            CoordinatorNode.Status.ONLINE: "#10b981",
            CoordinatorNode.Status.DEGRADED: "#f59e0b",
            CoordinatorNode.Status.OFFLINE: "#ef4444",
            CoordinatorNode.Status.UNKNOWN: "#6b7280",
        }
        color = colors.get(obj.status, "#6b7280")
        label = CoordinatorNode.Status(obj.status).label
        return mark_safe(f'<span style="color:{color}; font-weight:600;">● {label}</span>')

    status_badge.short_description = _("Status")

    def error_summary(self, obj):
        return (
            (obj.error_message[:80] + "...")
            if len(obj.error_message) > 80
            else obj.error_message
        )

    error_summary.short_description = _("Error")


@admin.register(TaprootEscrowContract)
class TaprootEscrowContractAdmin(ModelAdmin):
    list_display = (
        "id",
        "order",
        "status_badge",
        "address",
        "required_sats",
        "funded_sats",
        "funding_confirmed",
        "created_at",
    )
    list_filter = ("status", "funding_confirmed", "network")
    search_fields = (
        "address",
        "funding_txid",
        "payout_txid",
        "order__id",
        "maker_pubkey",
        "taker_pubkey",
    )
    readonly_fields = ("address", "descriptor", "created_at", "updated_at")

    def status_badge(self, obj):
        colors = {
            TaprootEscrowContract.Status.CREATED: "#6b7280",
            TaprootEscrowContract.Status.WAITING_DEPOSIT: "#f59e0b",
            TaprootEscrowContract.Status.FUNDED: "#3b82f6",
            TaprootEscrowContract.Status.RELEASED: "#10b981",
            TaprootEscrowContract.Status.DISPUTED: "#ef4444",
            TaprootEscrowContract.Status.RESOLVED: "#8b5cf6",
            TaprootEscrowContract.Status.REFUNDED: "#6b7280",
        }
        color = colors.get(obj.status, "#6b7280")
        return mark_safe(
            f'<span style="padding:2px 8px; border-radius:10px; background:{color}20; '
            f'color:{color}; font-weight:600;">● {obj.get_status_display()}</span>'
        )

    status_badge.short_description = _("Status")


@admin.register(EmailInboxConfig)
class EmailInboxConfigAdmin(ModelAdmin):
    list_display = (
        "public_receipt_email",
        "username",
        "host",
        "port",
        "use_ssl",
        "folder",
        "is_active",
        "last_checked_at",
        "last_status",
        "processed_count",
    )
    list_filter = ("is_active", "use_ssl")
    search_fields = ("username", "public_receipt_email", "host")
    actions = ["test_imap_connection", "poll_now"]

    @admin.action(description=_("🔌 Test IMAP connection"))
    def test_imap_connection(self, request, queryset):
        from api.email_ingestion import BankReceiptEmailWatcher
        for inbox in queryset:
            success, msg = BankReceiptEmailWatcher.test_connection(inbox)
            if success:
                self.message_user(request, f"✓ {inbox.username}: {msg}", messages.SUCCESS)
            else:
                self.message_user(request, f"✗ {inbox.username}: {msg}", messages.ERROR)

    @admin.action(description=_("📥 Poll unread receipts now"))
    def poll_now(self, request, queryset):
        from api.email_ingestion import BankReceiptEmailWatcher
        total = 0
        for inbox in queryset:
            results = BankReceiptEmailWatcher.poll_inbox(inbox)
            total += len(results)
            self.message_user(
                request,
                f"Inbox {inbox.username}: processed {len(results)} new receipts.",
                messages.INFO,
            )

