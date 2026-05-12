# Email

The `email` feature owns transactional mail dispatch. It ships with a port,
three adapters (console, SMTP, Resend), and a template registry features
contribute to at composition time.

## At A Glance

| Piece | Where |
| --- | --- |
| Port | `src/features/email/application/ports/email_port.py` — `EmailPort.send(to, template_name, context) -> Result[None, EmailError]` |
| Registry | `src/features/email/application/registry.py` — `EmailTemplateRegistry.register_template(name, path)` |
| Console adapter | `src/features/email/adapters/outbound/console/` |
| SMTP adapter | `src/features/email/adapters/outbound/smtp/` |
| Resend adapter | `src/features/email/adapters/outbound/resend/` (HTTP API) |
| Settings | `src/features/email/composition/settings.py` (`EmailSettings`) |
| Container | `src/features/email/composition/container.py` (`build_email_container`) |

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_EMAIL_BACKEND` | `console` | One of `console`, `smtp`, `resend`. **Production refuses `console`.** |
| `APP_EMAIL_FROM` | unset | Required when backend is `smtp` or `resend`. |
| `APP_EMAIL_SMTP_HOST` | unset | Required when backend is `smtp`. |
| `APP_EMAIL_SMTP_PORT` | `587` | Submission port. |
| `APP_EMAIL_SMTP_USERNAME` / `..._PASSWORD` | unset | Optional auth credentials. |
| `APP_EMAIL_SMTP_USE_STARTTLS` | `true` | STARTTLS upgrade on the submission port. |
| `APP_EMAIL_SMTP_USE_SSL` | `false` | Implicit TLS on port 465. Mutually exclusive with STARTTLS. |
| `APP_EMAIL_SMTP_TIMEOUT_SECONDS` | `10.0` | Socket timeout. |
| `APP_EMAIL_RESEND_API_KEY` | unset | Required when backend is `resend`. |
| `APP_EMAIL_RESEND_BASE_URL` | `https://api.resend.com` | Switch to `https://api.eu.resend.com` for the EU data plane or point at a Resend-compatible host. |

The settings validator refuses to start when:

- `APP_EMAIL_BACKEND=smtp` and either `APP_EMAIL_SMTP_HOST` or `APP_EMAIL_FROM` is missing,
- `APP_EMAIL_BACKEND=resend` and either `APP_EMAIL_RESEND_API_KEY` or `APP_EMAIL_FROM` is missing.

## How To Send Mail

Take `EmailPort` as a constructor dependency in your use case (or, for
non-blocking delivery, take `JobQueuePort` and enqueue the `send_email`
handler the email feature provides).

```python
from src.platform.shared.result import Result, Ok, Err

class NotifyUser:
    def __init__(self, email_port: EmailPort) -> None:
        self._email = email_port

    def execute(self, user_email: str) -> Result[None, EmailError]:
        return self._email.send(
            to=user_email,
            template_name="welcome",
            context={"display_name": "Sam"},
        )
```

For password-reset and email-verify flows the project enqueues the
`send_email` job instead of calling `EmailPort.send` synchronously — see
`docs/background-jobs.md`.

## Adding A Template

1. Drop the Jinja2 template under your feature, e.g.
   `src/features/<name>/email_templates/welcome.txt`.
2. In your feature's composition module, write a registration helper:

   ```python
   def register_my_feature_email_templates(registry: EmailTemplateRegistry) -> None:
       registry.register_template(
           name="welcome",
           path=Path(__file__).parent / "welcome.txt",
       )
   ```

3. Call that helper from `src/main.py` (and `src/worker.py` if the worker
   also renders the template) before `registry.seal()`.

The registry rejects duplicate names and any registration after sealing,
which catches accidental drift between the API process and the worker.

## Adapters

### Console (`ConsoleEmailAdapter`)

Logs the rendered email at `INFO` with structured fields:

```json
{
  "logger": "email.console",
  "to": "user@example.com",
  "template": "welcome",
  "subject": "Welcome to Starter",
  "body": "..."
}
```

Used in development, tests, and CI. Production refuses to start with this
backend selected.

### SMTP (`SmtpEmailAdapter`)

Uses `smtplib` with the configured host/port/credentials. Supports both
STARTTLS (port 587) and implicit TLS (port 465). `EmailError` covers
connection failure, authentication failure, and recipient rejection.

The contract test suite (`src/features/email/tests/contracts/`) runs the
same assertions against every adapter — the SMTP path uses a fake SMTP
server provided by `aiosmtpd`, so the production code path is exercised
against a real socket.

### Resend (`ResendEmailAdapter`)

POSTs the rendered email to Resend's `/emails` endpoint over `httpx`.
Status-code mapping:

- `2xx` → `Ok(None)`
- `4xx` → `Err(DeliveryError(reason="resend rejected: <status> <message>"))`,
  reading `message` from the JSON body when present, falling back to
  the raw response text.
- `5xx` → `Err(DeliveryError(reason="resend transient error: <status> ..."))`
- `httpx.HTTPError` (timeout, connect error) → `Err(DeliveryError(reason=str(exc)))`

The adapter does **not** retry. For at-least-once delivery, enqueue the
`send_email` background job (see `docs/background-jobs.md`) and let the
job-queue retry policy handle transient failures — retrying inside the
adapter risks double-sends because Resend's API is not idempotent on the
client side.

#### Acquiring an API key

Create an account at <https://resend.com>, verify the sending domain
(SPF + DKIM records are issued in the dashboard), and create an API
key under *API Keys*. Free tier today is 100 emails/day with a 10
emails/second cap — keep `APP_EMAIL_BACKEND=console` in development
unless you specifically want to spend the quota.

#### Region (EU vs US)

Resend's EU data plane is reachable at `https://api.eu.resend.com`.
Set `APP_EMAIL_RESEND_BASE_URL` to switch — no other change is needed.

The same setting can also point at a Resend-compatible self-hosted
service.

The Resend contract path is exercised by `respx`-mocked HTTP transport;
no real Resend account is touched in CI.

## Extending The Feature

- **Add a new adapter** (e.g. provider HTTP API): implement `EmailPort` and
  wire it in `build_email_container`. The contract tests should pass without
  modification.
- **Add a different template engine**: replace the `Jinja2` rendering helper
  in `application/rendering.py` (or its equivalent in your fork). The port
  takes only the template name and context, so the engine is hidden behind
  it.
- **Send mail with attachments**: extend the port signature with an optional
  `attachments` argument; current adapters only need to gain support, the
  feature contract stays put.
