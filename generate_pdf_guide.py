#!/usr/bin/env python3
"""
Генератор PDF-шпаргалки по быстрому запуску, связке с Umbrel, Tor и автобэкапам RoboSats
"""

import os
import shutil
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
            self.drawString(48, 800, "RoboSats Coordinator — Экспресс-руководство и шпаргалка оператора")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(48, 792, 547, 792)

        # Footer
        footer_text = f"Страница {self._pageNumber} из {page_count}"
        self.drawRightString(547, 35, footer_text)
        self.drawString(48, 35, "RoboSats Ops Cockpit • Umbrel LND • Tor Protection • Резервирование")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(48, 48, 547, 48)
        self.restoreState()


def build_pdf():
    doc = SimpleDocTemplate(
        str(PDF_OUTPUT),
        pagesize=A4,
        leftMargin=48,
        rightMargin=48,
        topMargin=50,
        bottomMargin=50,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Arial-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1A202C"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Arial",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=12,
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Arial-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Arial",
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=4,
    )

    callout_style = ParagraphStyle(
        "Callout_Custom",
        parent=styles["Normal"],
        fontName="Arial",
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#1A365D"),
    )

    callout_warn = ParagraphStyle(
        "Callout_Warn",
        parent=styles["Normal"],
        fontName="Arial",
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#742A2A"),
    )

    elements = []

    # Title & Header
    elements.append(Paragraph("🤖 RoboSats P2P Coordinator — Экспресс-руководство", title_style))
    elements.append(Paragraph("Запуск в 1 клик • Связка с Umbrel • Защита Tor • Автобэкапы и восстановление", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3182CE"), spaceAfter=10))

    # Summary Table
    summary_data = [
        [
            Paragraph("<b>Панель управления (Ops Cockpit):</b>", body_style),
            Paragraph("<font color='#2B6CB0'><b>http://127.0.0.1:8000/coordinator/</b></font>", body_style)
        ],
        [
            Paragraph("<b>Логин и пароль администратора:</b>", body_style),
            Paragraph("Логин: <b>admin</b> &nbsp;|&nbsp; Пароль: <b>admin12345</b>", body_style)
        ],
        [
            Paragraph("<b>Запуск после перезагрузки ПК:</b>", body_style),
            Paragraph("Ярлык на Рабочем столе <b>«RoboSats Координатор»</b>", body_style)
        ],
        [
            Paragraph("<b>Горячий бэкап в 1 клик:</b>", body_style),
            Paragraph("Скрипт <b>backup_now.bat</b> (автоматически сохраняет в <code>backups/</code>)", body_style)
        ],
    ]
    t_summary = Table(summary_data, colWidths=[200, 295])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 10))

    # SECTION 1
    elements.append(Paragraph("1. Запуск на компьютере после выключения (В 1 клик)", h1_style))
    elements.append(Paragraph(
        "Вам не нужно вводить команды в консоли каждый день. Всё автоматизировано:",
        body_style
    ))

    step_data = [
        [
            Paragraph("<b>1. Клик:</b>", body_style),
            Paragraph("Дважды кликните по ярлыку <b>RoboSats Координатор.lnk</b> на вашем Рабочем столе.", body_style)
        ],
        [
            Paragraph("<b>2. Старт:</b>", body_style),
            Paragraph("Откроется окно сервера, и через 2 секунды браузер <b>автоматически откроет</b> панель управления.", body_style)
        ],
        [
            Paragraph("<b>3. Вход:</b>", body_style),
            Paragraph("Введите логин <code>admin</code> и пароль <code>admin12345</code>.", body_style)
        ],
        [
            Paragraph("<b>4. Выход:</b>", body_style),
            Paragraph("Сервер работает, пока открыто черное окно. Чтобы выключить сервер — нажмите <b>Ctrl + C</b> или закройте окно.", body_style)
        ],
    ]
    t_steps = Table(step_data, colWidths=[55, 440])
    t_steps.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_steps)
    elements.append(Spacer(1, 10))

    # SECTION 2
    elements.append(Paragraph("2. Подключение к ноде Umbrel (Lightning Network)", h1_style))
    elements.append(Paragraph(
        "Координатор использует каналы вашей ноды Umbrel для удержания залогов сделок (Hold Invoices) и выплат:",
        body_style
    ))
    elements.append(Paragraph(
        "• <b>Вариант А (Координатор на ПК, нода на Umbrel):</b> В папке проекта запустите <code>python umbrel-app/connect_umbrel_lnd.py</code>, "
        "введите IP вашей ноды (например <code>192.168.1.50</code>). Скрипт сам свяжет координатор с Umbrel через зашифрованные сертификаты.<br/>"
        "• <b>Вариант Б (Координатор прямо внутри Umbrel):</b> В папке <code>umbrel-app/</code> готов манифест для Umbrel App Store — приложение ставится прямо на ноду в 1 клик.",
        body_style
    ))
    elements.append(Spacer(1, 10))

    # SECTION 3
    elements.append(Paragraph("3. Арбитраж споров: приватные каналы и авто-чеки", h1_style))
    elements.append(Paragraph(
        "При возникновении спора координатор защищен от утечек информации между сторонами:",
        body_style
    ))

    dispute_table_data = [
        [
            Paragraph("<b>Возможность</b>", body_style),
            Paragraph("<b>Как это работает простыми словами</b>", body_style)
        ],
        [
            Paragraph("<b>Изолированные чаты</b>", body_style),
            Paragraph("Вы общаетесь с Покупателем и Продавцом в отдельных приватных ветках. Они <b>не видят</b> сообщений друг друга.", body_style)
        ],
        [
            Paragraph("<b>Авто-проверка чеков</b>", body_style),
            Paragraph("Банковский чек (DKIM / PDF / СБП) проверяется роботом: сверяется сумма, банк и номер сделки.", body_style)
        ],
        [
            Paragraph("<b>Решение в 1 клик</b>", body_style),
            Paragraph("Кнопки вердикта: «Победа Покупателя», «Победа Продавца» или «Возврат залогов». Выплата уходит мгновенно.", body_style)
        ]
    ]
    t_dispute = Table(dispute_table_data, colWidths=[140, 355])
    t_dispute.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_dispute)
    elements.append(Spacer(1, 12))

    # SECTION 4
    elements.append(Paragraph("4. Публикация в сети Tor: почему адрес нельзя увести?", h1_style))
    
    tor_box = [
        [Paragraph(
            "🔒 <b>Ваш адрес в Tor полностью статичен и не может быть украден:</b><br/>"
            "• <b>Нет регистраторов и судов:</b> В отличие от обычных сайтов (.ru, .com), в Tor нет компаний-регистраторов, серверов DNS или хостеров, которые могли бы отобрать или заблокировать домен.<br/>"
            "• <b>Адрес — это криптография:</b> Ваш <code>.onion</code> адрес математически привязан к секретному ключу (файлу <code>hs_ed25519_secret_key</code>). Трафик расшифровывает только ваш ключ.<br/>"
            "• <b>Никто не может подменить маршрут:</b> Ни интернет-провайдер, ни спецслужбы, ни создатели Tor физически не способны перенаправить посетителей вашего адреса на чужой сервер.<br/>"
            "• <b>Единственное правило:</b> Не потерять секретный ключ. Он хранится на вашем ПК и автоматически сохраняется в каждом бэкапе.",
            callout_style
        )]
    ]
    t_tor = Table(tor_box, colWidths=[495])
    t_tor.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EBF8FF")),
        ('PADDING', (0, 0), (-1, -1), 7),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#3182CE")),
    ]))
    elements.append(t_tor)
    elements.append(Spacer(1, 12))

    # SECTION 5
    elements.append(Paragraph("5. Горячая замена и автобэкапы (Варианты А и Б)", h1_style))
    elements.append(Paragraph(
        "Система поддерживает два режима горячего резервирования при выключении или сбое основного ПК:",
        body_style
    ))

    backup_table_data = [
        [
            Paragraph("<b>Режим горячей замены</b>", body_style),
            Paragraph("<b>Как настроить и запустить</b>", body_style),
            Paragraph("<b>Поведение при сбое</b>", body_style),
        ],
        [
            Paragraph("<b>Вариант А: Горячий резерв в 1 клик</b><br/>(Рекомендуется)", body_style),
            Paragraph("1. На основном ПК запустите <code>export_standby.bat</code>.<br/>2. Скопируйте архив на ноутбук и запустите <code>deploy_standby.bat</code>.", body_style),
            Paragraph("Если основной ПК выключен — кликните <code>start_coordinator.bat</code> на ноутбуке. <b>Тот же .onion адрес оживает за 30 секунд!</b>", body_style),
        ],
        [
            Paragraph("<b>Вариант Б: Авто-сторож (Watchdog)</b><br/>(Полный автомат)", body_style),
            Paragraph("На резервном ПК запустите <code>start_watchdog.bat</code> и укажите IP основного ПК (сторож опрашивает <code>/api/v1/health/</code>).", body_style),
            Paragraph("Если основной ПК не отвечает 3 раза подряд — <b>сторож сам автоматически поднимает сервер</b> на резервной машине.", body_style),
        ],
    ]
    t_backup = Table(backup_table_data, colWidths=[140, 185, 170])
    t_backup.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_backup)
    elements.append(Spacer(1, 8))

    # Golden Lightning Rule
    lnd_warn = [
        [Paragraph(
            "⚠️ <b>Золотое правило для Lightning (Umbrel LND):</b><br/>"
            "Никогда не копируйте вручную рабочую базу каналов <code>channel.db</code> на другой ПК — это приведет к штрафной потере средств от пиров за старое состояние каналов. "
            "Для Lightning ноды используется только <b>SCB (файл <code>channel.backup</code>)</b> + ваша сид-фраза ноды (Seed). На Umbrel этот файл бэкапится автоматически.",
            callout_warn
        )]
    ]
    t_warn = Table(lnd_warn, colWidths=[495])
    t_warn.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FFF5F5")),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E53E3E")),
    ]))
    elements.append(t_warn)
    elements.append(Spacer(1, 12))

    # Final signoff
    signoff_data = [
        [Paragraph(
            "✨ <b>Всё готово к работе:</b> Ярлык на Рабочем столе запускает сервер, автобэкапы создаются каждые 6 часов, "
            "а ваш приватный ключ обеспечивает вечный и неизменный адрес в Tor.",
            callout_style
        )]
    ]
    t_signoff = Table(signoff_data, colWidths=[495])
    t_signoff.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0FFF4")),
        ('PADDING', (0, 0), (-1, -1), 7),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#38A169")),
    ]))
    elements.append(t_signoff)

    doc.build(elements, canvasmaker=NumberedCanvas)
    print(f"PDF successfully built: {PDF_OUTPUT}")

    shutil.copyfile(PDF_OUTPUT, ARTIFACT_OUTPUT)
    print(f"PDF copied to artifact dir: {ARTIFACT_OUTPUT}")


if __name__ == "__main__":
    build_pdf()
