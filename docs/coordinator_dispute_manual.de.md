# 🛡️ RoboSats Schlichtungsordnung & Streitbeilegung (Dispute SOP)

Dieses Dokument dient als Standard-Betriebsanweisung (SOP) für Koordinatoren und Schlichter zur Prüfung von Beweismitteln, kryptografischer Verifikation und Durchführung von Schlichtungsmaßnahmen in Django.

---

## 1. Grundsätze der Streitbeilegung

1. **Kryptografie vor Aussage:** Mathematische und kryptografische Beweise (DKIM-Signaturen der Bank, BIP-340 Schnorr-Signaturen, Lightning-Preimages, Onchain-Transaktionen) haben bedingungslosen Vorrang vor Screenshots, PDF-Rechnungen und reinen Behauptungen.
2. **Datensparsamkeit (Zero-KYC):** Der Schlichter verlangt **niemals** Ausweisdokumente, Selfies oder sensible Personendaten.
3. **Fristen & Fairness:** Jeder Partei stehen **24 Stunden** zur Einreichung von Beweismitteln zur Verfügung. Reagiert eine Partei nicht, ergeht die Entscheidung zugunsten der kooperierenden Gegenpartei.
4. **Endgültigkeit:** Ausgeführte Auszahlungen im System sind unwiderruflich.

---

## 2. Erstprüfung bei Disput-Eröffnung

Sobald eine Order in den Status `Disputed` (`is_disputed = True`) wechselt:
1. Öffnen Sie die Order in der Django-Verwaltung (`RoboSats Admin` → `Orders`).
2. Prüfen Sie die `Logs` (Ereignishistorie) und Transaktionszeitpunkte.
3. Überprüfen Sie den Status der Sicherheitsabzeichen (`Bank Receipt (DKIM)`, `F2F Cash`).
4. Treten Sie dem verschlüsselten Dreier-Chat bei und fordern Sie die Parteien zur Darlegung auf.

---

## 3. Schlichtungsaktionen im Dashboard

| Aktion (Button) | Mittelverwendung | Anwendungsfall |
| :--- | :--- | :--- |
| **`Solve dispute: maker wins`** | Maker erhält Ordervolumen + eigene Kaution + Taker-Kaution. | Taker verstößt gegen Regeln oder täuscht Zahlung vor. |
| **`Solve dispute: taker wins`** | Taker erhält Ordervolumen + eigene Kaution + Maker-Kaution. | Maker verweigert Freigabe trotz nachgewiesenem Geldeingang. |
| **`Solve dispute: successful trade`** | Reguläre Abwicklung: Käufer erhält BTC, beide Kautionen zurück. | Zahlung nachgewiesen (DKIM PASS), technischer Verbindungsausfall des Verkäufers. |
| **`Solve dispute: return everything`** | Escrow zurück an Verkäufer, Kautionen zurück an beide. | Höhere Gewalt, einvernehmliche Stornierung ohne Sanktionen. |

---
*RoboSats Schlichtungshandbuch.*
