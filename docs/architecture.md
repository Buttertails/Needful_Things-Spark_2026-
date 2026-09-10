# Needful Things — AWS Architecture

## Overview

Needful Things is a community resource-sharing platform that connects people who need resources with those who can provide them. The application is fully hosted on AWS using a serverless-friendly, managed-services architecture.

---

## Architecture Diagram

```
                        ┌─────────────────────────────────────────────────────────┐
                        │                      USER BROWSER                        │
                        └───────────────────────────┬─────────────────────────────┘
                                                    │ HTTPS
                                        ┌───────────▼───────────┐
                                        │      CloudFront CDN    │
                                        │  dybar52ziekaj.        │
                                        │  cloudfront.net        │
                                        └───────┬───────┬────────┘
                                                │       │
                          ┌─────────────────────┘       └──────────────────────┐
                          │  Default origin                  Behavior routes:   │
                          │  (static files)             /login, /authorize,     │
                          │                             /logout, /api/*         │
                 ┌────────▼────────┐                  ┌──────────────────────┐  │
                 │  AWS Amplify    │                  │  Elastic Beanstalk   │  │
                 │  (S3-backed)    │                  │  Flask App           │  │
                 │                 │                  │  (Python/Gunicorn)   │  │
                 │  index.html     │                  └──────────┬───────────┘  │
                 │  role.html      │                             │               │
                 │  resources.html │                  ┌──────────▼───────────┐  │
                 │  map.html       │                  │   AWS Services       │  │
                 │  chat-widget.js │                  │                      │  │
                 └─────────────────┘                  │  ┌────────────────┐  │  │
                                                      │  │ Cognito        │  │  │
                          ┌───────────────────────────│  │ User Pool      │  │  │
                          │  Auth flow                │  │ (OIDC/OAuth2)  │  │  │
                          │                           │  └────────────────┘  │  │
                 ┌────────▼────────┐                  │                      │  │
                 │  Cognito        │                  │  ┌────────────────┐  │  │
                 │  Hosted UI      │                  │  │ DynamoDB       │  │  │
                 │  (Login/Signup) │                  │  │ resources      │  │  │
                 └─────────────────┘                  │  │ messages       │  │  │
                                                      │  └────────────────┘  │  │
                                                      │                      │  │
                                                      │  ┌────────────────┐  │  │
                                                      │  │ Bedrock Agent  │  │  │
                                                      │  │ (AI Assistant) │  │  │
                                                      │  └────────────────┘  │  │
                                                      │                      │  │
                                                      │  ┌────────────────┐  │  │
                                                      │  │ Amazon         │  │  │
                                                      │  │ Location Svc   │  │  │
                                                      │  │ (Maps/Geo)     │  │  │
                                                      │  └────────────────┘  │  │
                                                      └──────────────────────┘  │
                                                                                │
                        ─────────────────────────────────────────────────────────
```

---

## Services

### AWS Amplify
- Hosts the static frontend (S3-backed)
- URL: `https://staging.d1lkt3hd0w7zxm.amplifyapp.com`
- Files: `index.html`, `role.html`, `resources.html`, `map.html`, `chat-widget.js`
- Acts as the default CloudFront origin for all non-API traffic

### Amazon CloudFront
- CDN distribution in front of both Amplify and Elastic Beanstalk
- URL: `https://dybar52ziekaj.cloudfront.net`
- Routes:
  - Default (`/*`) → Amplify (static files)
  - `/login`, `/authorize`, `/logout` → Elastic Beanstalk (auth)
  - `/api/*` → Elastic Beanstalk (API)

### AWS Elastic Beanstalk
- Runs the Flask backend (`main.py`) with Gunicorn
- URL: `Needful-things-env-1.eba-vqemcjuu.us-east-1.elasticbeanstalk.com`
- Handles all auth flows and API requests
- Environment variables: `COGNITO_CLIENT_SECRET`, `SECRET_KEY`, `BEDROCK_AGENT_ID`, `BEDROCK_AGENT_ALIAS_ID`

### Amazon Cognito
- User Pool ID: `us-east-1_kowqhZ4fl`
- App Client ID: `25is9h8u5rka8qi4sti9qnu0d2`
- Provides user registration, login, and OIDC token issuance
- Hosted UI used for login/signup pages (custom CSS applied)
- OAuth2 scopes: `email openid phone profile`
- Identity Pool ID: `us-east-1:0260092b-d425-423c-af14-b051783cf76b`
  - Used client-side in `map.html` to authenticate MapLibre with Amazon Location Services

### Amazon DynamoDB
- Region: `us-east-1`
- Table: `resources`
  - Partition key: `user_id` (Cognito `sub`)
  - Sort key: `id` (UUID)
  - Attributes: `type` (have/need), `display_name`, `items` (list), `lat`, `lng`
- Table: `messages`
  - Partition key: `conversation_id` (sorted join of two user IDs with `#`)
  - Sort key: `timestamp` (ISO 8601)
  - Attributes: `message_id`, `sender_id`, `sender_name`, `recipient_id`, `recipient_name`, `text`, `read`

### Amazon Bedrock
- Agent invoked via `bedrock-agent-runtime` client
- Agent ID and Alias ID stored as EB environment variables
- Called from `/api/chat` endpoint — streams response chunks back to the client
- Powers the in-app AI assistant chat widget

### Amazon Location Services
- Used client-side in `map.html` via MapLibre GL JS
- Provides map tile rendering with Standard style
- Active layers: Hillshade terrain, Contour density (Medium), Traffic (All)
- Light/Dark/Satellite style toggle supported
- Authentication via Cognito Identity Pool (unauthenticated role)

---

## Auth Flow

```
1. User clicks "Sign In" on index.html
2. Browser → CloudFront → EB /login
3. EB redirects to Cognito Hosted UI
4. User authenticates with Cognito
5. Cognito redirects to CloudFront /authorize with auth code
6. EB /authorize exchanges code for tokens via OIDC
7. EB redirects to Amplify role.html#token=<id_token>
8. role.html stores id_token in localStorage
9. All subsequent API calls send Authorization: Bearer <id_token>
10. EB validates token via JWT claims (unverified — no signature check)
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/login` | Initiates Cognito OIDC login |
| GET | `/authorize` | OAuth2 callback, exchanges code for token |
| GET | `/logout` | Clears session, redirects to home |
| POST | `/api/resources` | Create a resource entry |
| GET | `/api/resources/mine` | Get current user's resources |
| PUT | `/api/resources/<id>` | Update a resource entry |
| DELETE | `/api/resources/<id>` | Delete a resource entry |
| GET | `/api/match` | Get matched users grouped by user_id with scores |
| POST | `/api/messages` | Send a message |
| GET | `/api/messages?convo_id=` | Get messages for a conversation |
| GET | `/api/conversations` | Get all conversations for current user |
| POST | `/api/chat` | Send message to Bedrock AI agent |

---

## Data Flow — Resource Matching

```
User submits resources (POST /api/resources)
        │
        ▼
DynamoDB resources table
        │
        ▼
GET /api/match?role=<need|have|both>
        │
        ├── Scan all resources
        ├── Compute item overlap score vs. current user
        ├── Filter by role
        ├── Group entries by user_id (one pin per user)
        └── Return sorted by match_score desc
                │
                ▼
        MapLibre renders pins
        Popup shows all entries + Message button
```

---

## Deployment

| Component | How to deploy |
|-----------|--------------|
| Static frontend | Upload files to S3 bucket backing Amplify, then invalidate CloudFront `/*` |
| Flask backend | Zip `main.py`, `requirements.txt`, `Procfile` → upload via EB console |
| Environment config | Set env vars in EB console under Configuration → Software |
