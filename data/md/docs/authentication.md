# Authentication

Garden CMS supports two authentication methods for the admin interface: password login and OAuth2/OIDC.

## Password login

Set the `ADMIN_PASSWORD` environment variable:

```bash
ADMIN_PASSWORD=your-secure-password
```

Navigate to `/admin/login` and enter the password. The session is stored in an encrypted cookie.

Garden CMS also supports Piccolo's built-in `BaseUser` table. If a matching user exists in the database, authentication is checked against the stored password hash.

## OAuth2/OIDC

Garden CMS supports any OAuth2/OIDC provider that implements the standard discovery endpoint (`.well-known/openid-configuration`). The implementation uses PKCE (S256) for security.

### Configuration

Set these environment variables:

| Variable              | Description                                                     |
| --------------------- | --------------------------------------------------------------- |
| `OAUTH_CLIENT_ID`     | OAuth client ID                                                 |
| `OAUTH_CLIENT_SECRET` | OAuth client secret                                             |
| `OAUTH_ISSUER_URL`    | Provider issuer URL (e.g. `https://auth.example.com`)           |
| `OAUTH_REDIRECT_URI`  | Callback URL (e.g. `https://yoursite.com/admin/oauth/callback`) |
| `OAUTH_ALLOWED_GROUP` | Optional: restrict access to users in this group                |

### Flow

1. User clicks "Sign in with OAuth" on the login page
2. Redirected to the provider's authorization endpoint with PKCE challenge
3. After authentication, redirected back to `/admin/oauth/callback`
4. The application exchanges the authorization code for tokens and validates group membership
5. Session is established

### Group-based access control

If `OAUTH_ALLOWED_GROUP` is set, only users belonging to that group (via the `groups` claim in userinfo) are allowed access. This works with providers like Authentik, Keycloak, and Pocket ID that include group membership in the userinfo response.

## Session management

Sessions are stored in encrypted cookies using Litestar's `CookieBackendConfig`. The encryption key is derived from the `SECRET_KEY` environment variable. Use a strong, random value in production.

## Rate limiting

The password login endpoint is rate-limited to 5 attempts per minute to prevent brute-force attacks.

## Logout

Click **Log out** in the admin sidebar or POST to `/admin/logout`. The session is cleared and you are redirected to the login page.
