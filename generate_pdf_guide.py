#!/usr/bin/env python3
"""
Генератор PDF-шпаргалки по быстрому запуску и управлению координатором RoboSats
"""

import os
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
PDF_OUTPUT = DOCS_DIR / "RoboSats_Coordinator_Quickstart_Guide.pdf"
ARTIFACT_OUTPUT = Path(r"C:\Users\Garrysan\.gemini\antigravity\brain\4e419fc1-a83a-4327-a86e-a9e8a4c258af\RoboSats_Coordinator_Quickstart_Guide.pdf")

# Register TrueType Cyrillic fonts from Windows
pdfmetrics.registerFont(TTFont("Arial", r"C:\Windows\Fonts\arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", r"C:\Windows\Fonts\arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", r"C:\Windows\Fonts\ariali.ttf"))


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Arial", 8)
        self.setFillColor(colors.HexColor("#718096"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 800, "RoboSats Coordinator — Руководство по запуску и эксплуатации")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, 792, 541, 792)

        # Footer
        footer_text = f"Страница {self._pageNumber} из {page_count}"
        self.drawRightString(541, 35, footer_text)
        self.drawString(54, 35, "RoboSats Ops Cockpit • Umbrel LND Integration • Версия 0.9.15")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 48, 541, 48)
        self.restoreState()


def build_pdf():
    doc = SimpleDocTemplate(
        str(PDF_OUTPUT),
        pagesize=A4,
        leftMargin=50,
        rightMargin=50,
        topMargin=55,
        bottomMargin=55,
    )

    styles = getSampleStyleSheet()

    # Define custom styles
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Arial-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1A202C"),
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Arial",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=15,
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Arial-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Normal"],
        fontName="Arial-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#2D3748"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Arial",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=6,
    )

    code_style = ParagraphStyle(
        "Code_Custom",
        parent=styles["Normal"],
        fontName="Arial",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#805AD5"),
    )

    callout_style = ParagraphStyle(
        "Callout_Custom",
        parent=styles["Normal"],
        fontName="Arial",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1A365D"),
    )

    elements = []

    # Title & Header
    elements.append(Paragraph("🤖 RoboSats P2P Coordinator", title_style))
    elements.append(Paragraph("Руководство по запуску, связке с нодой Umbrel и арбитражу споров", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3182CE"), spaceAfter=12))

    # Info Box: Quick Access Summary
    summary_data = [
        [
            Paragraph("<b>Панель управления (Командный центр):</b>", body_style),
            Paragraph("<font color='#2B6CB0'><b>http://127.0.0.1:8000/coordinator/</b></font>", body_style)
        ],
        [
            Paragraph("<b>Логин по умолчанию:</b>", body_style),
            Paragraph("<b>admin</b>", body_style)
        ],
        [
            Paragraph("<b>Пароль по умолчанию:</b>", body_style),
            Paragraph("<b>admin12345</b>", body_style)
        ],
        [
            Paragraph("<b>Быстрый запуск на ПК:</b>", body_style),
            Paragraph("Ярлык на Рабочем столе <b>«RoboSats Координатор»</b>", body_style)
        ],
    ]
    t_summary = Table(summary_data, colWidths=[200, 290])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 14))

    # SECTION 1
    elements.append(Paragraph("1. Запуск на компьютере после выключения (В 1 клик)", h1_style))
    elements.append(Paragraph(
        "Для ежедневной работы координатора на вашем рабочем столе создан ярлык <b>«RoboSats Координатор»</b>. "
        "После включения или перезагрузки компьютера просто дважды кликните по нему.",
        body_style
    ))

    step_data = [
        [
            Paragraph("<b>Шаг 1:</b>", body_style),
            Paragraph("Дважды кликните по ярлыку <b>RoboSats Координатор.lnk</b> на Рабочем столе.", body_style)
        ],
        [
            Paragraph("<b>Шаг 2:</b>", body_style),
            Paragraph("Откроется окно консоли, которое проверит окружение и запустит веб-сервер.", body_style)
        ],
        [
            Paragraph("<b>Шаг 3:</b>", body_style),
            Paragraph("Через 2 секунды браузер <b>автоматически откроет</b> панель управления координатора.", body_style)
        ],
        [
            Paragraph("<b>Шаг 4:</b>", body_style),
            Paragraph("Введите логин <code>admin</code> и пароль <code>admin12345</code>.", body_style)
        ],
    ]
    t_steps = Table(step_data, colWidths=[60, 430])
    t_steps.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_steps)
    elements.append(Spacer(1, 10))

    # Callout Tip
    callout_content = [
        [Paragraph("💡 <b>Совет:</b> Окно консоли должно оставаться открытым во время работы. Для остановки сервера просто нажмите <b>Ctrl + C</b> в этом окне.", callout_style)]
    ]
    t_callout = Table(callout_content, colWidths=[490])
    t_callout.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FEFCBF")),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#D69E2E")),
    ]))
    elements.append(t_callout)
    elements.append(Spacer(1, 14))

    # SECTION 2
    elements.append(Paragraph("2. Подключение к ноде Umbrel (Lightning LND)", h1_style))
    elements.append(Paragraph(
        "Координатор RoboSats использует Lightning Network ноду для удержания залогов сделок (Hold Invoices) "
        "и проведения выплат. Для подключения вашей ноды Umbrel доступны два варианта:",
        body_style
    ))

    elements.append(Paragraph("Вариант А: Запуск Координатора на ПК со связкой с Umbrel нодой", h2_style))
    elements.append(Paragraph(
        "Если ваш координатор работает на Windows-компьютере, а Umbrel — на домашней ноде (Raspberry Pi или мини-ПК):<br/>"
        "1. Запустите в командной строке мастер связки: <code>python umbrel-app/connect_umbrel_lnd.py</code><br/>"
        "2. Укажите IP-адрес вашей ноды (например <code>192.168.1.50</code> или <code>umbrel.local</code>).<br/>"
        "3. Файлы авторизации LND на Umbrel находятся в папке:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• Macaroon: <code>~/umbrel/app-data/lightning/data/lnd/data/chain/bitcoin/mainnet/admin.macaroon</code><br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• Сертификат: <code>~/umbrel/app-data/lightning/data/lnd/tls.cert</code><br/>"
        "4. Мастер сохранит зашифрованные токены в <code>.env</code>, и координатор начнет проводить платежи через каналы Umbrel.",
        body_style
    ))

    elements.append(Paragraph("Вариант Б: Установка Координатора прямо на Umbrel (В 1 клик)", h2_style))
    elements.append(Paragraph(
        "В репозитории подготовлен нативный пакет <code>umbrel-app/</code>. При установке в Umbrel App Store "
        "приложение автоматически подключается к локальной шине LND без необходимости копирования сертификатов вручную.",
        body_style
    ))
    elements.append(Spacer(1, 10))

    # SECTION 3
    elements.append(Paragraph("3. Разрешение споров и приватный двухканальный чат", h1_style))
    elements.append(Paragraph(
        "В версии 0.9.15 внедрена архитектура <b>изолированного двухстороннего общения</b> координатора с участниками спора:",
        body_style
    ))

    dispute_table_data = [
        [
            Paragraph("<b>Канал</b>", body_style),
            Paragraph("<b>Назначение и уровень приватности</b>", body_style)
        ],
        [
            Paragraph("<font color='#3182CE'><b>Канал с Мейкером (Maker)</b></font>", body_style),
            Paragraph("Приватная ветка запроса подтверждений у создателя оффера. Тейкер <b>не видит</b> эту переписку.", body_style)
        ],
        [
            Paragraph("<font color='#805AD5'><b>Канал с Тейкером (Taker)</b></font>", body_style),
            Paragraph("Приватная ветка запроса чеков у принявшего сделку. Мейкер <b>не видит</b> эту переписку.", body_style)
        ],
        [
            Paragraph("<font color='#38A169'><b>Авто-валидация чеков (DKIM/PDF)</b></font>", body_style),
            Paragraph("Координатор автоматически сопоставляет полученный банковский чек с суммой и реквизитами сделки.", body_style)
        ],
        [
            Paragraph("<font color='#DD6B20'><b>Быстрый вердикт (1 клик)</b></font>", body_style),
            Paragraph("Кнопки в Cockpit: «Победа Покупателя», «Победа Продавца», «Возврат залогов». Залоги выплачиваются мгновенно.", body_style)
        ]
    ]
    t_dispute = Table(dispute_table_data, colWidths=[150, 340])
    t_dispute.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_dispute)
    elements.append(Spacer(1, 12))

    # SECTION 4
    elements.append(Paragraph("4. Автоматическое резервное копирование и безопасность", h1_style))
    elements.append(Paragraph(
        "Для координатора настроена автоматическая система горячего резервного копирования:<br/>"
        "• <b>Горячий бэкап в 1 клик:</b> Скрипт <code>backup_now.bat</code> (или <code>python backup_coordinator.py</code>) "
        "создает целостный снимок базы данных SQLite через Online Backup API без остановки сделок.<br/>"
        "• <b>Что входит в бэкап:</b> База <code>db.sqlite3</code>, ключи шифрования <code>.env</code>, а также приватные ключи Tor (<code>hs_ed25519_secret_key</code>).<br/>"
        "• <b>Авто-расписание в Windows:</b> Запустите <code>setup_autobackup.bat</code> — архивы будут создаваться в папке <code>backups/</code> автоматически по расписанию с ротацией 14 дней.<br/>"
        "• <b>Резервирование Lightning (Umbrel LND):</b> Для каналов используется <code>channel.backup</code> (SCB). Не копируйте рабочую <code>channel.db</code> вручную во избежание штрафных транзакций.",
        body_style
    ))
    elements.append(Spacer(1, 14))

    # Sign-off box
    signoff_data = [
        [Paragraph("<b>Командный центр RoboSats Ops Cockpit успешно настроен и готов к работе.</b><br/>"
                   "Для доступа ко встроенной документации перейдите в браузере: "
                   "<b>http://127.0.0.1:8000/coordinator/docs/</b>", callout_style)]
    ]
    t_signoff = Table(signoff_data, colWidths=[490])
    t_signoff.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EBF8FF")),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#63B3ED")),
    ]))
    elements.append(t_signoff)

    doc.build(elements, canvasmaker=NumberedCanvas)
    print(f"PDF successfully built: {PDF_OUTPUT}")

    # Copy to artifacts directory
    import shutil
    shutil.copyfile(PDF_OUTPUT, ARTIFACT_OUTPUT)
    print(f"PDF copied to artifact dir: {ARTIFACT_OUTPUT}")


if __name__ == "__main__":
    build_pdf()
