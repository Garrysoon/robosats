# RoboSats Koordinator: Leitfaden für Bereitstellung, Inbetriebnahme und Betrieb

Dieser Leitfaden bietet eine schrittweise Produktionsanleitung für Betreiber und Administratoren des RoboSats P2P-Koordinators, einschließlich automatischer Schlichtung, kryptografischer Verifizierung von Bankbelegen (DKIM / PDF), Onchain-Taproot-Escrows (2-von-3 Multisig) und Barzahlungsprotokollen (F2F).

---

## Inhaltsverzeichnis
0. [⚡ 1-Klick-Schnellstart (Quickstart)](#0--1-klick-schnellstart-quickstart)
1. [Systemarchitektur & Voraussetzungen](#1-systemarchitektur--voraussetzungen)
2. [Docker-Produktionsbereitstellung](#2-docker-produktionsbereitstellung)
3. [Konfiguration der Umgebungsvariablen (.env)](#3-konfiguration-der-umgebungsvariablen-env)
4. [LND Lightning-Node-Anbindung](#4-lnd-lightning-node-anbindung)
5. [E-Mail-Postfächer für Bankbelege (IMAP + DKIM)](#5-e-mail-postfächer-für-bankbelege-imap--dkim)
6. [Hintergrund-Dienste & Celery](#6-hintergrund-dienste--celery)
7. [Schlichtungscockpit (Dispute Cockpit)](#7-schlichtungscockpit-dispute-cockpit)
8. [Fehlerbehebung & Failover](#8-fehlerbehebung--failover)

---

## 0. ⚡ 1-Klick-Schnellstart (Quickstart)

Um den Koordinator innerhalb weniger Minuten betriebsbereit zu schalten, stehen automatisierte Assistenten bereit:

### Option A: Automatischer plattformübergreifender Python-Assistent
```bash
# Interaktiven Installationsassistenten starten:
python setup_coordinator.py

# Oder mit Standardparametern im Express-Modus:
python setup_coordinator.py --quick
```

### Option B: Windows-Desktop 1-Klick-Start
Doppelklicken Sie auf dem Desktop auf die Verknüpfung **„RoboSats Koordinator“** (oder führen Sie `start_coordinator.bat` aus). Das Skript prüft die Umgebung und öffnet den Browser nach 2 Sekunden:
- **URL der Konsole:** `http://127.0.0.1:8000/coordinator/`
- **Standard-Benutzer:** `admin`
- **Standard-Passwort:** `admin12345`

### Option C: Hot-Standby & Failover
- **Standby-Export:** Führen Sie `export_standby.bat` aus.
- **Automatischer Watchdog:** Führen Sie auf dem Standby-Server `start_watchdog.bat` aus. Bei einem Ausfall übernimmt der Standby-Knoten nahtlos die identische Onion-Adresse.

---

## 7. 🚨 Schlichtungscockpit (Dispute Cockpit)
Das Schlichtungscockpit ermöglicht eine 1-Klick-Beilegung von Streitfällen:
- **`Solve dispute: maker wins`**: Erstattung an Maker inkl. Sicherheiten.
- **`Solve dispute: taker wins`**: Erstattung an Taker inkl. Sicherheiten.
- **`Solve dispute: return everything`**: Beidseitige Rückabwicklung ohne Strafen.

---
*RoboSats Coordinator Betriebsdokumentation.*
