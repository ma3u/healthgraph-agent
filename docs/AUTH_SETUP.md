# Auth0 + Aura JWKS setup

One-time setup the user (or any installer) does so the iOS app can sign in
with **Continue with Apple / Google / GitHub / Microsoft** and write to their
own Aura GraphQL Data API. Roughly 15 minutes start to finish.

Why this shape: see [`AUTH_RESEARCH.md`](AUTH_RESEARCH.md). TL;DR — Neo4j
can't share its private Auth0 tenant with third-party apps, but Aura's
GraphQL Data API natively accepts any JWT validated against a public JWKS,
so we own the IDP.

## 1. Create an Auth0 tenant (free, 7,500 MAU)

1. Go to <https://auth0.com/signup>, sign up. Pick a tenant name like
   `healthgraph` — your tenant domain becomes `healthgraph.us.auth0.com`
   (or `.eu.auth0.com` if you choose EU).
2. In the Auth0 dashboard sidebar, **Applications → Applications → Create
   Application**.
   - Name: **HealthGraphSync iOS**
   - Type: **Native**
   - Click **Create**.
3. In the new app's **Settings** tab:
   - Note **Client ID** (you'll need it).
   - **Allowed Callback URLs**: `io.healthgraph.sync://callback`
   - **Allowed Logout URLs**: `io.healthgraph.sync://logout`
   - Scroll down → **Save Changes**.

## 2. Enable the social connections

Auth0 dashboard sidebar → **Authentication → Social**. Enable each of:

- **Apple** — needs an Apple developer Sign in with Apple Service ID. See
  [Auth0's guide](https://auth0.com/docs/authenticate/identity-providers/social-identity-providers/apple-native).
- **Google** — quickest, click "Try" first to use Auth0's dev keys, then
  add your own Google OAuth client.
- **GitHub** — register an OAuth app at
  <https://github.com/settings/developers> with callback
  `https://YOUR_TENANT.auth0.com/login/callback`.
- **Microsoft Account** — register an app at <https://portal.azure.com>
  under App Registrations, redirect URI as above.

Then on each social connection: **Applications** tab → enable
**HealthGraphSync iOS**.

You can skip any of these and just enable, say, Apple + Google to ship
faster. Add the others later without rebuilding the app.

## 3. Create an API audience

This is the value that ends up in the JWT's `aud` claim and that Aura will
validate against.

1. Auth0 dashboard → **Applications → APIs → Create API**.
   - Name: **HealthGraphSync Aura**
   - Identifier: `https://healthgraph.io/aura` (any URL — it's just a
     unique string, never fetched)
   - Signing Algorithm: **RS256**
2. Save.

The JWKS URL for your tenant is:

```
https://YOUR_TENANT.us.auth0.com/.well-known/jwks.json
```

## 4. Register the JWKS provider on the Aura GraphQL Data API

Install the Aura CLI if you don't have it:

```sh
brew install neo4j/aura/aura-cli  # or pip install aura-cli
aura-cli login                     # enter your Aura M2M client_id/secret
```

Create the JWKS auth provider on your GraphQL Data API:

```sh
aura-cli data-api graphql auth-provider create \
  --data-api-id YOUR_DATA_API_ID \
  --instance-id YOUR_AURA_INSTANCE_ID \
  --name "Auth0" \
  --type jwks \
  --url https://YOUR_TENANT.us.auth0.com/.well-known/jwks.json
```

Where to find `YOUR_DATA_API_ID` and `YOUR_AURA_INSTANCE_ID`:

- Aura Console → **GraphQL Data APIs** (sidebar) → click your API → URL bar
  has `/data-apis/<DATA_API_ID>`.
- Aura Console → **Instances** → click your instance → URL bar has
  `/instances/<INSTANCE_ID>`.

You can also do this in the Aura Console UI: GraphQL Data API → **Auth
providers** → **Add provider** → **JWKS** → paste the URL.

## 5. Configure the iOS app

Edit `ios/project.yml`:

```yaml
info:
  properties:
    AUTH0_DOMAIN: YOUR_TENANT.us.auth0.com
    AUTH0_CLIENT_ID: YOUR_CLIENT_ID_FROM_STEP_1
    AUTH0_AUDIENCE: https://healthgraph.io/aura
```

Then regenerate:

```sh
cd ios && xcodegen generate
```

## 6. (Optional) Add Aura `@authorization` rules

To ensure each user only sees their own data, extend the GraphQL SDL with
authorization rules keyed off the JWT `sub` claim. Example for `Person`:

```graphql
type Person @node @authorization(
  validate: [{ where: { node: { name_EQ: "$jwt.sub" } } }]
) { ... }
```

This is optional today because your Aura instance is single-tenant — only
your data is there. If the app ever supports multiple users sharing one
Aura, do this then.

## 7. Sanity check

Once everything's wired up:

```sh
# Get a JWT manually (Auth0 dashboard → Application → Quick Start → cURL)
TOKEN="<paste-from-auth0>"
ENDPOINT="https://YOUR_DATA_API.YOUR_REGION.data.neo4j.io/graphql"

curl -X POST "$ENDPOINT" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ days(limit: 1) { date } }"}'
```

You should get back a `data.days` array. If you get a 401, the JWKS URL is
wrong or the JWT's audience/issuer doesn't match the Aura JWKS provider's
expected claims.
