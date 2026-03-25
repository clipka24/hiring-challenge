# AB Test Analyzer

Ein serverloser AWS-Service, der AB-Test-Zwischenstände über SNS empfängt, die leistungsstärkste Variante ermittelt und das Ergebnis in einer PostgreSQL-Datenbank speichert.

---

## Architekturübersicht

```
Publisher → SNS Topic → Lambda Function → PostgreSQL (RDS)
                              ↕
                       Secrets Manager
                       (DB-Credentials)
```

### Komponenten

| Komponente | Technologie | Zweck |
|---|---|---|
| Messaging | AWS SNS | Empfang der AB-Test-Nachrichten |
| Verarbeitung | AWS Lambda (Python 3.12) | Analyse & Gewinnermittlung |
| Datenbank | AWS RDS PostgreSQL 16 | Persistenz der Ergebnisse |
| Credentials | AWS Secrets Manager | Sichere DB-Zugangsdaten |
| Verschlüsselung | AWS KMS | Encryption at Rest (je Service ein Key) |
| Logging | Amazon CloudWatch Logs | Fehler- und Statusmeldungen |

---

## Gewinner-Kriterium

Eine Variante wird als Gewinner gewertet, wenn ihre **CTR (Click-Through-Rate) mindestens 20 % höher** ist als die CTR **aller** anderen Varianten:

```
winner_ctr >= andere_ctr × 1.20   für ALLE anderen Varianten
```

Wenn kein Kandidat diese Bedingung erfüllt, wird `winner_variant = NULL` gespeichert (kein Gewinner zum aktuellen Zeitpunkt).

---

## SNS Message Format

```json
{
  "test_id": "100042256:::headline:::2773242877",
  "content_id": "100042256",
  "variants": [
    { "id": 0, "clicks": "120", "views": "5464" },
    { "id": 1, "clicks": "160", "views": "5470" },
    { "id": 2, "clicks": "170", "views": "5468" }
  ],
  "msg_timestamp": "2025-01-08 10:09:13"
}
```

---

## Datenbankschema

### `ab_test_results`

| Spalte | Typ | Beschreibung |
|---|---|---|
| `test_id` | TEXT (PK) | Eindeutige Test-ID |
| `test_name` | TEXT | Content-ID des Tests |
| `evaluated_at` | TIMESTAMPTZ | Zeitpunkt der Auswertung |
| `winner_variant` | BIGINT / NULL | ID der Gewinner-Variante oder NULL |
| `raw_payload` | JSONB | Originalnachricht |
| `created_at` | TIMESTAMPTZ | Erstellungszeitpunkt |
| `updated_at` | TIMESTAMPTZ | Letztes Update |

### `ab_test_variant_snapshots`

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | BIGSERIAL (PK) | Interne ID |
| `test_id` | TEXT (FK) | Referenz auf Test |
| `variant_id` | BIGINT | ID der Variante |
| `impressions` | BIGINT | Anzahl Views |
| `clicks` | BIGINT | Anzahl Klicks |
| `ctr` | NUMERIC(10,6) | Click-Through-Rate |
| `recorded_at` | TIMESTAMPTZ | Zeitpunkt der Aufzeichnung |

---

## Projektstruktur

```
hiring-challenge/
├── src/
│   ├── app.py              # Lambda Entry Point
│   ├── analyzer.py         # Gewinnermittlung & SNS-Parsing
│   ├── db.py               # DB-Verbindung & Schema-Init
│   ├── requirements.txt    # Python-Abhängigkeiten
│   └── tests/
│       └── test_analyzer.py  # Unit Tests
├── terraform/
│   ├── main.tf             # Lambda, SNS, RDS
│   ├── iam.tf              # IAM Roles & Policies (least privilege)
│   ├── security_groups.tf  # Netzwerksicherheit
│   ├── kms.tf              # KMS Keys pro Service
│   ├── variables.tf        # Eingabeparameter
│   ├── locals.tf           # Gemeinsame Tags
│   └── outputs.tf          # Ausgabewerte
├── sample-requests/        # Beispiel-SNS-Nachrichten für lokale Tests
├── docker-compose.yaml     # Lokale Testumgebung
└── README.md
```

---

## Sicherheitskonzept (Least Privilege)

### Lambda IAM Role – nur folgende Berechtigungen:
- **CloudWatch Logs**: `CreateLogStream`, `PutLogEvents` – nur für die eigene Log Group
- **Secrets Manager**: `GetSecretValue`, `DescribeSecret` – nur für das RDS-Secret
- **KMS**: `Decrypt` – je Key nur für den eigenen Service (via `kms:ViaService` Condition)
- **VPC**: Netzwerkzugang über `AWSLambdaVPCAccessExecutionRole`

### Netzwerk:
- Lambda und RDS befinden sich in **privaten Subnetzen** ohne direkten Internetzugang
- RDS akzeptiert Verbindungen **ausschließlich von der Lambda Security Group** auf Port 5432
- Lambda kommuniziert outbound nur zu RDS (5432) und AWS-Endpunkten (443)

### Verschlüsselung:
- **KMS Keys** für: Lambda-Umgebungsvariablen, RDS Storage, SNS, CloudWatch Logs
- **RDS**: `storage_encrypted = true`, `sslmode = require`
- **Secrets Manager**: Credential-Rotation via RDS Managed Passwords

---

## Fehlerbehandlung & Logging

Alle Fehler werden über Python's `logging`-Modul geloggt und landen in CloudWatch Logs:

| Fehlertyp | Behandlung |
|---|---|
| `ValueError` | Validierungsfehler (fehlendes Feld, ungültige Daten) → geloggt, kein Retry |
| `psycopg2.Error` | Datenbankfehler → geloggt mit Fehlercode |
| Unbekannte Fehler | `exc_info=True` → vollständiger Stacktrace in CloudWatch |

Jeder Log-Eintrag enthält `request_id` (Lambda-Anfrage-ID) und `test_id` für Traceability.

---

## Deployment

### Voraussetzungen

- Terraform >= 1.6
- AWS CLI konfiguriert
- Python 3.12
- Ein bestehendes VPC mit privaten Subnetzen
- psycopg2 Lambda Layer ZIP (z. B. von [keithrozario/Klayers](https://github.com/keithrozario/Klayers))

### Infrastruktur bereitstellen

```bash
cd terraform

terraform init
terraform validate
terraform plan -var vpc_id=vpc-xxx -var 'private_subnet_ids=["subnet-aaaa","subnet-bbbb"]'
terraform apply
```

### Tests ausführen

```bash
cd src
pip install -r requirements.txt pytest
pytest tests/ -v
```

---

## SNS-Nachricht manuell senden (Test)

```bash
aws sns publish \
  --topic-arn "$(terraform -chdir=terraform output -raw sns_topic_arn)" \
  --message '{
    "test_id": "test-001",
    "content_id": "test-001",
    "variants": [
      {"id": 0, "clicks": "100", "views": "1000"},
      {"id": 1, "clicks": "130", "views": "1000"}
    ],
    "msg_timestamp": "2025-01-08 10:00:00"
  }'
```