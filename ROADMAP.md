# Roadmap — `starter-template-fastapi`

> **Norte:** *AWS-first FastAPI starter. Local dev sin infraestructura, deploy a AWS — Cognito, SES, SQS, S3, RDS, ElastiCache. Una sola opción opinada > tres opciones a medias.*

Cada paso = **una sesión / un OpenSpec change**. Ejecutar en orden estricto.
Marcar `[x]` al cerrar.

---

## Cómo usar este documento

Cuando arranques una sesión, dime:

> *"Vamos por el paso N del ROADMAP"*

Yo lanzo `spec-writer` con el alcance exacto de ese paso, esperamos tu aprobación, luego `test-engineer` + `implementer` + `qa-reviewer`.

**Regla de oro:** no mezclar pasos en una misma PR. Si un paso resulta más grande de lo esperado, lo partimos en sub-pasos pero seguimos en orden.

---

## Decisiones ya tomadas (no re-discutir)

- AWS como único target de producción soportado.
- Mantener adaptadores dev-only (`console`, `in_process`, `local`, `in_memory`).
- Eliminar adaptadores production-shaped no-AWS (SMTP, Resend, arq, SpiceDB).
- Conservar los puertos: existen por testabilidad, no por portabilidad.
- **Cognito federa con auth local (Opción B)**: un usuario puede tener credenciales locales, identidades federadas (Cognito / Google / etc.), o ambas vinculadas a la misma fila `User`. Tabla `identities (provider, provider_sub, user_id)`. El adaptador local de credenciales NO se elimina ni reemplaza — coexiste con los providers federados.

---

# ETAPA I — Limpieza (dejar el repo honesto)

> Antes de añadir nada. Trabajar sobre ruido duplica esfuerzo.

- [x] **1. Eliminar el scaffold `_template`** de todo: `README.md`, `CLAUDE.md`, `docs/feature-template.md`, `docs/architecture.md`, sección "Adding a new feature". No documentarlo, no recuperarlo de git history. Borrar `docs/feature-template.md`.

- [ ] **2. Eliminar variables `APP_AUTH_OAUTH_*` y código muerto asociado** en `.env.example`, `AuthenticationSettings`, validators de producción. Auditar si hay referencias en docs.

- [ ] **3. Eliminar adaptador SMTP** (`src/features/email/adapters/outbound/smtp/`), sus settings, env vars `APP_EMAIL_SMTP_*`, tests, contract tests parametrizados, servicio `mailpit` en `docker-compose`, mención en docs.

- [ ] **4. Eliminar adaptador Resend** (`src/features/email/adapters/outbound/resend/`), sus settings, env vars `APP_EMAIL_RESEND_*`, extra `resend` en `pyproject.toml`, tests, docs.

- [ ] **5. Eliminar adaptador arq** (`src/features/background_jobs/adapters/outbound/arq/`), sus settings, env vars asociadas, rama del extra `worker` en `pyproject.toml`, tests, docs.

- [ ] **6. Eliminar stub SpiceDB** (`src/features/authorization/adapters/outbound/spicedb/`). Vive en git history si se necesita referencia.

- [ ] **7. Eliminar stub S3** que levanta `NotImplementedError`. El puerto `FileStoragePort` queda solo con `local` (dev) hasta el paso 23 que añade el adaptador real.

- [ ] **8. Actualizar `docs/api.md`**: borrar todas las referencias a endpoints Kanban (`/api/boards`, `/api/columns`, `/api/cards`). No existen en el código.

- [ ] **9. Actualizar `README.md`** con el nuevo tagline AWS-first. Quitar la matriz de features que promete SMTP/Resend/arq/SpiceDB. Quitar la mención al scaffold recuperable.

- [ ] **10. Actualizar `CLAUDE.md`** con el mismo encuadre: matriz de features post-limpieza, sección "Adding a new feature" (sin `_template`), reglas de producción actualizadas.

- [ ] **11. Actualizar `docs/operations.md`**: quitar de "producción rechaza arrancar si…" todas las reglas relacionadas a backends eliminados (`APP_EMAIL_BACKEND=console` ahora será la única no-AWS, etc.). Recortar la lista a la realidad post-limpieza.

- [ ] **12. Documentar `src/cli/`** en `README.md` + `CLAUDE.md`: qué comandos existen, cómo se invocan, cuándo se usan.

---

# ETAPA II — DX y fundamentos (antes de tocar AWS)

> Cosas baratas que pagan dividendos durante todo el resto del roadmap.

- [ ] **13. Consolidar fakes vs dev-adapters**: el `console` email adapter ES el fake; el `in_process` jobs adapter ES el fake. Auditar `tests/fakes/` y eliminar duplicaciones donde el dev-adapter alcance.

- [ ] **14. README de tests** en `src/features/*/tests/` + sección en `docs/development.md` explicando la distinción `unit | e2e | integration | contracts` (especialmente qué hace contract test: misma suite contra fake y adapter real).

- [ ] **15. ADRs iniciales** en `docs/decisions/`:
  - 0001 — Por qué SQLModel
  - 0002 — Por qué ReBAC
  - 0003 — Por qué Result en vez de excepciones
  - 0004 — Por qué AWS-first
  - 0005 — Por qué Cognito federa (Opción B) y no reemplaza (Opción A): trade-offs, complejidad asumida, casos de uso (SSO empresarial, mantener auth local para B2C, evolución gradual)

- [ ] **16. `make check-prod`**: comando que valida un `.env` contra todas las reglas de "producción rechaza arrancar si…" en una sola pasada. Reporta todos los problemas, no uno a la vez. Salida JSON opcional para CI.

---

# ETAPA III — Brechas técnicas que bloquean Cognito y multi-servicio

> Hay que tenerlas antes de meter Cognito. Orden importa: JWT asimétrico → JWKS → todo lo demás de auth.

- [ ] **17. JWT asimétrico (RS256 / ES256)**: extender `AccessTokenService` para soportar claves asimétricas además de HMAC. Soporte de `kid` en el header. Settings nuevos: `APP_AUTH_JWT_PRIVATE_KEY`, `APP_AUTH_JWT_PUBLIC_KEY` o referencia a Secrets Manager (placeholder hasta paso 22). Rotación de claves documentada.

- [ ] **18. Endpoint JWKS público** (`GET /.well-known/jwks.json`): serializar la(s) clave(s) públicas. Cache headers correctos. Tests e2e que verifican que un cliente externo puede validar un JWT emitido por el servicio usando solo JWKS.

- [ ] **19. CSRF protection en flujo refresh-by-cookie**: auditar comportamiento actual con `SameSite=lax`. Decidir entre forzar `SameSite=strict`, double-submit token, u origin check estricto en `/auth/refresh`. Implementar y testear.

- [ ] **20. Idempotency keys middleware**: header `Idempotency-Key`, tabla `idempotency_records` (key, request_hash, response_body, response_status, expires_at), TTL configurable, replay del response cuando coincide. Aplicar a endpoints de escritura.

---

# ETAPA IV — Decisión multi-tenant (antes de IaC)

> Bloqueante: si decides "tenant como recurso ReBAC padre", afecta el esquema de DB de todas las features. Mejor decidirlo antes de desplegar infra.

- [ ] **21. ADR 0006 — Multi-tenancy**: comparar enfoques (tenant como tipo ReBAC padre / columna `tenant_id` en todas las tablas / row-level security en Postgres / no soportar multi-tenant). Decidir uno.

- [ ] **22. Implementación de tenant primitive** según ADR 0006. Si se decide soportarlo: migrar esquemas, ajustar `AuthorizationRegistry`, gateguards en `require_authorization`. Si se decide no soportarlo: documentar la decisión y cerrar.

---

# ETAPA V — Base AWS (adaptadores)

> El orden importa: `SecretsPort` primero porque los demás consumen secretos. `S3` antes que `SES`/`SQS` porque es el más sencillo y nos da confianza con el patrón `boto3`.

- [ ] **23. `SecretsPort` + adaptador Secrets Manager**
  - Nuevo puerto en `src/app_platform/config/secrets/` (o feature `secrets` — decidir en el spec)
  - Adaptador `aws_secrets_manager` con cache TTL
  - Adaptador `env` para dev (default)
  - `AppSettings` hidrata desde el puerto, no directamente de env
  - Settings sensibles migradas: `APP_AUTH_JWT_PRIVATE_KEY`, `APP_POSTGRESQL_DSN`, credenciales de servicios AWS

- [ ] **24. `aws_s3` adapter real** para `FileStoragePort`
  - Implementación completa de `put` / `get` / `delete` / `signed_url` con `boto3`
  - Soporte KMS opcional para SSE
  - Multipart upload para objetos grandes
  - Tests de integración con LocalStack o `moto`
  - Eliminar el "stub eliminado" del paso 7; ahora hay adapter real

- [ ] **25. `aws_ses` adapter** para `EmailPort`
  - Settings `EmailSettings.ses_region`
  - Soporte `SendEmail` y `SendBulkTemplatedEmail`
  - Decidir cómo encaja con `EmailTemplateRegistry`: renderizado local + raw send, o templates en SES
  - Production validator: si `APP_EMAIL_BACKEND=aws_ses`, exigir region y dominio verificado

- [ ] **26. `aws_sqs` adapter** para `JobQueuePort`
  - `enqueue` → `SendMessage`
  - `enqueue_at` → `DelaySeconds` (hasta 15 min) o **EventBridge Scheduler** para delays largos
  - DLQ handling: errores que excedan `APP_OUTBOX_MAX_ATTEMPTS` → DLQ configurable
  - Tests de integración con LocalStack

- [ ] **27. Lambda handler para el worker** (`src/worker_lambda.py`)
  - Invoca `JobHandlerRegistry` desde eventos SQS
  - Misma raíz de composición que `src/main.py` y `src/worker.py`
  - Empaquetado documentado (zip o container image)

- [ ] **28. Outbox dispatcher → SNS / EventBridge**
  - Convertir `DispatchPending` de handler interno a publisher a bus externo
  - Adaptador `aws_sns` o `aws_eventbridge` (decidir en el spec — EventBridge es más expresivo, SNS más simple)
  - Cierra el item "outbox sin broker real" del análisis original

- [ ] **29. Health check `/health/startup`** además de `/health/live` y `/health/ready`. ECS lo distingue; útil cuando el bootstrap (cargar secrets, validar Cognito, etc.) toma tiempo.

---

# ETAPA VI — Base AWS (infraestructura)

> Cada paso es una capa del stack de CDK. Despliega y valida antes de pasar al siguiente.

- [ ] **30. CDK base**: estructura del proyecto `infra/cdk/`, stacks, environments (dev/staging/prod), VPC con subnets privadas + NAT, IAM roles base.

- [ ] **31. CDK: persistencia**: RDS PostgreSQL (single-AZ para empezar), parameter group seguro, ElastiCache Redis, Secrets Manager para credenciales DB con rotación automática.

- [ ] **32. CDK: storage + messaging**: S3 bucket con lifecycle + KMS, SES con verificación de dominio + DKIM, SQS + DLQ, SNS topic (si el paso 28 eligió SNS) o EventBridge bus.

- [ ] **33. CDK: compute**: ECS Fargate service + ALB + ACM cert + Route53. Lambda function para el worker conectada a SQS. Task definitions con secrets desde Secrets Manager.

- [ ] **34. CDK: observability básica**: CloudWatch log groups, retención configurable, métricas básicas de ALB/ECS/RDS.

- [ ] **35. GitHub Actions con OIDC → AWS**: workflow que asume rol IAM sin credenciales de larga duración. Build → push a ECR → deploy a ECS / update Lambda. Validar contra dev environment.

---

# ETAPA VII — Cognito (federación con auth local)

> Requiere pasos 17 + 18 (JWT asimétrico + JWKS) ya cerrados.
> **Modelo: Opción B — federación.** El adaptador local de credenciales sigue vivo y funcional. Cognito (y otros providers en el futuro) se vinculan a la misma fila `User` vía tabla `identities`. Un usuario puede autenticarse con password local, con Cognito, o con ambos.

- [ ] **36. Tabla `identities` + modelo de federación**
  - Migración Alembic: tabla `identities (id, user_id, provider, provider_sub, linked_at, last_login_at, metadata_json)`, unique `(provider, provider_sub)`, unique `(user_id, provider)` — un usuario tiene como máximo una identidad por provider
  - Nuevo puerto `IdentityPort` en `users` (o en una sub-feature `identities` — decidir en el spec): `link`, `unlink`, `find_by_provider_sub`, `list_for_user`
  - El adaptador local de `CredentialRepository` permanece sin cambios — esto se suma, no reemplaza

- [ ] **37. `aws_cognito` adapter** como provider federado
  - Settings `APP_AUTH_COGNITO_ENABLED`, `APP_AUTH_COGNITO_USER_POOL_ID`, `APP_AUTH_COGNITO_CLIENT_ID`, región
  - Validación de JWT Cognito vía JWKS (reusa infraestructura del paso 18)
  - El adaptador implementa "verificar identidad federada", no `CredentialRepository`
  - Mapeo `cognito_sub` → fila `identities` → `user_id` → `User`

- [ ] **38. Use cases nuevos de federación**
  - `LinkIdentity`: un usuario autenticado vincula un provider externo (Cognito, etc.) a su cuenta existente
  - `UnlinkIdentity`: desvincula. Debe rechazar la última credencial activa (un usuario sin password local y sin identidades quedaría bloqueado)
  - `LoginWithFederatedIdentity`: presenta token del provider → valida → busca `identities` → resuelve `user_id` → emite JWT propio
  - `RegisterViaFederatedIdentity`: crea `User` + `identities` row en una transacción cuando el provider trae un email nunca visto

- [ ] **39. `CognitoPrincipalResolver`** (alternativa al resolver local)
  - Coexiste con el resolver local — el dispatcher elige según el `iss` del JWT entrante
  - Cachea principal igual

- [ ] **40. Post-confirmation Lambda trigger de Cognito**
  - Cognito → Lambda → API interna (`POST /internal/cognito/post-confirmation`) → crea `User` + `identities` row si el email no existe, o vincula la identidad al `User` existente si ya hay una cuenta con ese email (con confirmación del usuario para evitar account takeover)
  - Alternativa: lazy provisioning en primer login — decidir en el spec del paso 38

- [ ] **41. Endpoints HTTP para gestión de identidades**
  - `GET /me/identities` — lista los providers vinculados al usuario actual
  - `POST /me/identities/{provider}/link` — vincular un nuevo provider
  - `DELETE /me/identities/{provider}` — desvincular
  - Gated por `require_authorization`

- [ ] **42. CDK: Cognito User Pool**, app clients, hosted UI opcional, Lambda triggers (post-confirmation, pre-token-generation si aplica), dominio personalizado. Conectar al stack existente.

- [ ] **43. Docs: patrón de federación**
  - Cuándo usar password local vs federar
  - Cómo manejar account linking con email duplicado de forma segura (verificación previa al merge)
  - Migración: cómo un usuario existente con password local puede vincular Cognito sin perder acceso
  - SSO empresarial: cómo conectar un IdP corporativo (SAML/OIDC) vía Cognito Federation

---

# ETAPA VIII — Observability y compliance

- [ ] **44. `AuditExportPort`**: reemplaza el modelo donde el audit muere en una tabla. Define el puerto y un adaptador noop por defecto.

- [ ] **45. Adaptador `cloudwatch_logs`** para `AuditExportPort`: log group dedicado, JSON estructurado, retención configurable.

- [ ] **46. Adaptador `kinesis_firehose`** para `AuditExportPort`: stream a S3 (Glacier para retención larga, Athena para queries).

- [ ] **47. Adaptador `eventbridge`** para `AuditExportPort`: audit events como eventos de dominio para consumidores externos (SIEM, analytics).

- [ ] **48. CloudWatch EMF metrics emitter**: alternativa al exporter Prometheus. Reusa el logger estructurado. Decidir si coexiste con Prometheus o lo reemplaza.

- [ ] **49. ADOT (AWS Distro for OpenTelemetry) sidecar documentado**: deployment como sidecar en ECS, extension en Lambda. Traces a X-Ray, logs a CloudWatch. Validar nombres de campos esperados por CloudWatch Insights.

- [ ] **50. CDK: alarms de SLO**: latency p99, error rate, queue depth, DLQ size, DB connection saturation. SNS topic para alertas.

---

# ETAPA IX — Brechas restantes (cuando todo lo anterior esté estable)

- [ ] **51. MFA / TOTP**: nuevo puerto `SecondFactorPort`. Empezar con TOTP (RFC 6238). Adaptador local (TOTP en DB) y adaptador `aws_cognito_mfa` cuando el usuario se autentica vía Cognito (Cognito tiene MFA propio). WebAuthn/passkeys queda para fase posterior.

- [ ] **52. Streaming first-class (SSE / WebSockets)**: patrón documentado y ejemplo end-to-end de cómo compone con `require_authorization`, rate limiter, y principal cache. Validación detrás de ALB / API Gateway.

---

# ETAPA X — Avanzado / opcional

- [ ] **53. `aws_avp` adapter** para `AuthorizationPort` (Amazon Verified Permissions, políticas Cedar). ADR comparando ReBAC vs AVP. Decidir si coexisten o reemplaza.

- [ ] **54. `KMSCryptoPort`**: envelope encryption con cache de DEKs. Cifrado de columnas con PII serias. Firma de cookies / tokens internos.

- [ ] **55. RDS con IAM auth + rotación automática**: token rotativo en vez de password estática. Lambda de rotación gestionada por Secrets Manager.

- [ ] **56. Multi-region considerations** (esbozo, no implementación): replicación de RDS, SES multi-region, DynamoDB Global Tables si se introduce.

---

## Checklist de progreso

| Etapa | Items | Estado |
|---|---|---|
| I — Limpieza | 1–12 | Pendiente |
| II — DX y fundamentos | 13–16 | Pendiente |
| III — Brechas pre-Cognito | 17–20 | Pendiente |
| IV — Decisión multi-tenant | 21–22 | Pendiente |
| V — Base AWS (adaptadores) | 23–29 | Pendiente |
| VI — Base AWS (infra) | 30–35 | Pendiente |
| VII — Cognito (federación) | 36–43 | Pendiente |
| VIII — Observability | 44–50 | Pendiente |
| IX — Brechas restantes | 51–52 | Pendiente |
| X — Avanzado | 53–56 | Pendiente |
