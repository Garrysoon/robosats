# Guía completa de implementación, inicio y operación del Coordinador RoboSats

Esta guía proporciona un procedimiento paso a paso para operadores y administradores del coordinador P2P RoboSats, incluyendo resolución automatizada de disputas, verificación criptográfica de recibos bancarios (DKIM / PDF), contratos de custodia Taproot (2-de-3 multisig) y protocolo de efectivo en persona (F2F).

---

## Índice
0. [⚡ Inicio rápido en 1 clic (Quickstart)](#0--inicio-rápido-en-1-clic-quickstart)
1. [Arquitectura del sistema y requisitos](#1-arquitectura-del-sistema-y-requisitos)
2. [Despliegue de producción con Docker](#2-despliegue-de-producción-con-docker)
3. [Configuración de variables de entorno (.env)](#3-configuración-de-variables-de-entorno-env)
4. [Conexión con el nodo Lightning LND](#4-conexión-con-el-nodo-lightning-lnd)
5. [Buzones de correo de recibos bancarios (IMAP + DKIM)](#5-buzones-de-correo-de-recibos-bancarios-imap--dkim)
6. [Demonios en segundo plano y Celery](#6-demonios-en-segundo-plano-y-celery)
7. [Cabina de disputas (Dispute Cockpit)](#7-cabina-de-disputas-dispute-cockpit)
8. [Resolución de problemas y conmutación por error (Failover)](#8-resolución-de-problemas-y-conmutación-por-error-failover)

---

## 0. ⚡ Inicio rápido en 1 clic (Quickstart)

Para poner en marcha el coordinador en cuestión de minutos, dispone de asistentes automatizados:

### Opción A: Asistente Python multiplataforma
```bash
# Inicie el asistente interactivo:
python setup_coordinator.py

# O en modo rápido con valores por defecto:
python setup_coordinator.py --quick
```

### Opción B: Acceso directo en el escritorio de Windows
Haga doble clic en el acceso directo **«RoboSats Coordinador»** en el escritorio (o ejecute `start_coordinator.bat`). El script comprobará el entorno y abrirá el navegador en 2 segundos:
- **URL de la consola:** `http://127.0.0.1:8000/coordinator/`
- **Usuario por defecto:** `admin`
- **Contraseña por defecto:** `admin12345`

### Opción C: Espera activa y conmutación por error (Hot Failover)
- **Exportar respaldo en espera:** Ejecute `export_standby.bat`.
- **Guardián automático (Watchdog):** En la máquina de reserva ejecute `start_watchdog.bat`. Si el servidor principal no responde en 3 comprobaciones consecutivas, la máquina de reserva asumirá el servicio con la misma dirección Onion.

---

## 7. 🚨 Cabina de disputas (Dispute Cockpit)
La cabina de arbitraje permite resolver disputas con un solo clic:
- **`Solve dispute: maker wins`**: Fondos y fianzas asignados al creador.
- **`Solve dispute: taker wins`**: Fondos y fianzas asignados al tomador.
- **`Solve dispute: return everything`**: Devolución completa de fondos y fianzas a las partes sin penalizaciones.

---
*Documentación oficial de operaciones de RoboSats.*
