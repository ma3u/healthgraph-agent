# Auth research — "How do we sign into Aura?"

Investigation conducted 2026-05-14 in response to the question: *can the iOS
app reuse `https://login.neo4j.com/` like the Aura Console does — with
Google / GitHub / Microsoft — so the user never sees a "server name" field?*

## Short answer

**No** — `login.neo4j.com` is Neo4j's private Auth0 tenant, used only for
their first-party products (Console, Workspace, Bloom, Browser). Third-party
mobile apps can't redirect users to it.

**But** — Aura's GraphQL Data API natively accepts JWTs issued by any IDP via
JWKS, so the *user-facing* sign-in flow (Google / GitHub / Microsoft / Apple)
can look identical to Aura's, just routed through an IDP **we** own (Auth0,
Cognito, Clerk, or direct Google/Apple Sign-In on-device).

This also lets us **drop the FastAPI backend** — the user's "no server name"
ask becomes literally true.

## What Neo4j actually supports

| Auth path | What it does | Can a mobile app use it? |
| --- | --- | --- |
| **`login.neo4j.com`** (Auth0 tenant) | SSO for Neo4j's own web Console/Workspace. Backed by Auth0 ([blog][auth0blog]) with Google/GitHub/Microsoft/Email/SSO connections. | **No.** It's Neo4j's private tenant; not a public OAuth provider. |
| **Aura *Tool* Auth** ([docs][toolauth]) | New (May 2025+). Lets Query/Explore connect with the user's Aura-account role instead of a DB password. | **No.** Explicitly first-party tools only. |
| **Aura *Management* API** ([docs][mgmtapi]) | OAuth client-credentials. Lets you list/create/pause instances. NOT for Cypher. | Server-to-server only — credentials must not live on a device. |
| **Aura *Query* API** ([docs][queryapi]) | HTTP endpoint for Cypher. Auth = Basic (DB user+password) OR Bearer JWT from an OAuth IDP ([Medium walk-through][querytoken]). | Yes, but Basic auth puts the DB password on the device; Bearer-JWT is the recommended path. |
| **Aura *GraphQL Data* API** ([docs][gqlauth]) | The thing in the Console screen you opened. Auth = `x-api-key` OR Bearer-JWT validated against any **JWKS URL** ([provider docs][gqlproviders]). | **Yes — JWKS is the right path.** Docs explicitly say API key "should not be used within a user-facing client application." |

[auth0blog]: https://neo4j.com/blog/developer/handling-authentication-and-identity-with-neo4j-and-auth0/
[toolauth]: https://neo4j.com/docs/aura/security/tool-auth/
[mgmtapi]: https://neo4j.com/docs/aura/platform/api/authentication/
[queryapi]: https://neo4j.com/docs/query-api/current/authentication-authorization/
[querytoken]: https://medium.com/@jongiffard/token-based-auth-with-neo4j-query-api-for-applications-b1ac65c215a9
[gqlauth]: https://neo4j.com/docs/graphql/current/aura-graphql/authentication-providers/
[gqlproviders]: https://neo4j.com/docs/graphql/current/aura-graphql/authentication-providers/

## Neo4j's actual recommendation

From the GraphQL Data API auth docs: **set up a JWKS authentication provider
pointing at your identity provider's `.well-known/jwks.json`**. That IDP can
be Auth0 (Neo4j's own choice), Google, GitHub via Auth0's social connection,
Apple Sign-In, or any OIDC-compliant provider. All requests then arrive at
Aura with `Authorization: Bearer <jwt>` and Aura validates the JWT against
that JWKS.

The setup is one CLI command per provider:

```sh
aura-cli data-api graphql auth-provider create \
  --data-api-id YOUR_GRAPHQL_DATA_API_ID \
  --instance-id YOUR_AURA_INSTANCE_ID \
  --name "Apple Sign-In" \
  --type jwks \
  --url https://appleid.apple.com/auth/keys
```

## Recommended architecture for HealthGraphSync

```
                  ┌─────────────────────────────┐
                  │  iOS app — HealthGraphSync  │
                  └──────────────┬──────────────┘
                                 │
                  ┌──────────────┴──────────────┐
                  │                             │
       1) Sign in (one-time)                 2) Sync
                  │                             │
                  ▼                             ▼
       ┌─────────────────────┐    Bearer JWT   ┌────────────────────────────┐
       │  Apple Sign-In  /   │ ───────────────▶│  Aura GraphQL Data API     │
       │  Sign in with       │  GraphQL        │  (the user's own instance) │
       │  Google             │  query/mutation │                            │
       └─────────────────────┘                 └────────────────────────────┘
                                                          │
                                                          ▼
                                               ┌────────────────────┐
                                               │  Neo4j Aura DB     │
                                               │  (user's own)      │
                                               └────────────────────┘
```

**Concrete changes from today's setup:**

1. **Drop the FastAPI backend.** Today's `backend/` becomes dead code (we
   keep it tagged for reference but stop running it). Saves the "server
   name" prompt the user disliked.

2. **iOS adds Sign-In:**
   - **Apple Sign-In** (native, no SDK, zero friction on iPhone) — covers
     ~all iOS users.
   - **Google / GitHub / Microsoft** — via Auth0 universal login web sheet
     (`ASWebAuthenticationSession`). Auth0 free tier handles 7,500 MAUs.

3. **iOS reads HealthKit → builds GraphQL mutations → POSTs to the user's
   own Aura GraphQL Data API** with the JWT. The GraphQL SDL we already
   committed (`cypher/graphql_schema.graphql`) needs mutations enabled —
   one config flag in the Aura Console.

4. **"Search the right database" UX:**
   - First launch after sign-in: the app prompts "Which Aura instance?".
   - Three options for getting it:
     a) Paste the GraphQL Data API URL (looks like
        `https://<api-id>.<region>.data.neo4j.io/graphql`). Cheapest.
     b) Scan a QR code generated from the Aura Console (would require a
        small companion script).
     c) Use the Aura Management API with the user's `client_id`/`secret`
        to list their instances and pick one. Most magical, but requires
        the user to generate API keys in the Console first.

   v1 = option (a). Add (c) later if the friction warrants it.

5. **The DB password disappears from the device.** JWT carries the user's
   identity; Aura's GraphQL `@authorization` rules enforce who can read/write
   what.

## What this means for what we already built

| Today | Tomorrow |
| --- | --- |
| FastAPI backend with `/auth/login` + `/ingest/healthkit` + `/sync/preview` | **Removed** (or archived as `backend-legacy/`). The graph schema, ingest semantics, and DailySummary aggregation move to GraphQL mutations defined in the Aura GraphQL Data API. |
| `Keychain auth.token` (our JWT) | `Keychain auth.token` (IDP's JWT) + `Keychain aura.graphql_url` (which Aura DB to talk to). |
| iOS `APIClient.ingest(payload, token)` | iOS `GraphQLClient.run(mutation, jwt)`. |
| `etl/load_to_neo4j.py` (Bolt) | Still works for the **offline initial bulk load** from a downloaded export. Only the *incremental* iOS path moves to GraphQL. |
| Email/password login | Apple Sign-In (default) + optional Google/GitHub/Microsoft via Auth0. |

## What's NOT possible (set expectations honestly)

- **"Sign in with Aura"** — there is no public OAuth flow at
  `login.neo4j.com` for third-party apps. The Aura Console screenshot you
  posted is Neo4j's own Auth0 tenant; we can't redirect into it.
- **Listing the user's Aura instances without the user generating M2M
  credentials first.** The Aura Management API requires `client_id` +
  `client_secret` that the user creates manually in the Console; there's
  no SSO-bridge for it. So "discover databases automatically" needs the
  user to paste those keys.

## Decision points before I write code

1. **Confirm the pivot.** This rewrites the iOS sync path (GraphQL mutations
   instead of FastAPI POST). The backend we built today gets archived. OK
   to proceed?
2. **Pick the IDP shape.**
   - Apple Sign-In only — cleanest, native, no third-party. Doesn't cover
     "Continue with Google/GitHub/Microsoft" though.
   - Apple Sign-In + Auth0 universal login (covers Google/GitHub/Microsoft
     in one web sheet). Requires an Auth0 tenant (free) + one client app
     config. Closest match to the Aura Console UX you screenshotted.
3. **"Search the right database":** v1 = paste the GraphQL endpoint URL.
   OK, or do you want the Management-API-based instance picker right away?
