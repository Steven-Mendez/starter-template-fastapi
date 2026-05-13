## MODIFIED Requirements

### Requirement: Self-deactivation invalidates all session artifacts

`DELETE /me` SHALL, in a single response cycle, (1) clear the browser-side refresh cookie via `Set-Cookie` with empty value + `Max-Age=0` + `Path=/auth` and (2) revoke every server-side refresh-token family for the deactivated user inside the same Unit of Work that flips `is_active=False`. The server-side revocation MUST run inline (not via the outbox) so the response reflects revoked state.

(Note: this change does NOT introduce a deactivation audit event. `DeactivateUser` currently records none; if one is needed, it is the responsibility of a separate change.)

#### Scenario: Self-deactivate clears the cookie

- **GIVEN** an authenticated session whose refresh cookie is set
- **WHEN** the client sends `DELETE /me`
- **THEN** the response status is 204 (or the project's existing self-deactivate status)
- **AND** the response includes `Set-Cookie: refresh_token=; Max-Age=0; Path=/auth`

#### Scenario: Refresh after self-deactivate is rejected

- **GIVEN** a client that captured its refresh cookie before sending `DELETE /me`
- **WHEN** the client replays the captured cookie against `POST /auth/refresh`
- **THEN** the response status is 401
- **AND** no new access token is issued

#### Scenario: Server-side revocation runs inline

- **GIVEN** a `DeactivateUser` use case wired with a recording `RevokeAllRefreshTokens` collaborator
- **WHEN** `DELETE /me` is invoked and the use case returns `Ok`
- **THEN** the collaborator records exactly one invocation with the deactivated `user_id`
- **AND** the invocation occurred before the HTTP response was returned (no outbox round trip)
