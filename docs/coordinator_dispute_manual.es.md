# 🛡️ Reglamento y procedimiento de resolución de disputas para el Coordinador RoboSats (Dispute SOP)

Este documento constituye el procedimiento estándar de operación (SOP) para administradores y árbitros del coordinador, definiendo el análisis de pruebas, validaciones criptográficas y acciones resolutivas en Django.

---

## 1. Principios fundamentales de arbitraje

1. **La criptografía prevalece sobre las palabras:** Las pruebas matemáticas y criptográficas (firmas bancarias DKIM, firmas Schnorr BIP-340, preimágenes Lightning y transacciones en cadena) tienen prioridad absoluta sobre capturas de pantalla, recibos PDF o declaraciones de texto.
2. **Minimización de datos (Zero-KYC):** El árbitro **nunca exige** pasaportes, selfies, fotos de tarjetas de crédito o videollamadas. El análisis se basa en pruebas técnicas y extractos verificables.
3. **Plazos y equidad:** Cada parte cuenta con **24 horas** para presentar pruebas en el chat cifrado de tres vías. Si una parte ignora la solicitud, el fallo se emitirá a favor de la parte cooperante.
4. **Irreversibilidad:** Los desembolsos ejecutados a través de Lightning o transacciones onchain no se pueden anular.

---

## 2. Lista de comprobación inicial

Cuando una orden entra en estado de disputa (`is_disputed = True`):
1. Abra la orden en la administración de Django (`RoboSats Admin` → `Orders`).
2. Examine el bloque `Logs` para comprobar marcas temporales y eventos.
3. Compruebe los distintivos de seguridad (`Bank Receipt (DKIM)`, `F2F Cash`).
4. Ingrese en el chat PGP tripartito y solicite información a la parte reclamante.

---

## 3. Acciones de resolución en el panel

| Botón de acción (Action) | Destino de los fondos | Cuándo aplicar |
| :--- | :--- | :--- |
| **`Solve dispute: maker wins`** | El creador recibe el importe + su fianza + fianza del tomador. | El tomador incumplió las reglas o intentó defraudar. |
| **`Solve dispute: taker wins`** | El tomador recibe el importe + su fianza + fianza del creador. | El creador se negó a liberar los fondos tras recibir el pago. |
| **`Solve dispute: successful trade`** | Liquidación normal: el comprador recibe BTC y se devuelven ambas fianzas. | Pago acreditado (DKIM PASS), creador ausente por fallo de conexión. |
| **`Solve dispute: return everything`** | Depósito devuelto al vendedor, fianzas devueltas a ambas partes. | Fuerza mayor, cancelación de mutuo acuerdo sin penalizaciones. |

---
*Manual oficial de resolución de disputas de RoboSats.*
