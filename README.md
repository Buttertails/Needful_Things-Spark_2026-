# Needful Things

A community resource-sharing platform that connects people who **need** resources with people who **have** them. Users drop themselves on a map, list what they need or can offer, get matched with nearby people based on item overlap, and message each other directly. An AI assistant (Amazon Bedrock) is built in to help users find support.

Built for the **ECU Spark 2026** hackathon.

---

## What it does

- **Sign in** through a hosted, secure login (Amazon Cognito).
- **Pick a role** — "I need resources," "I have resources," or both.
- **List resources** — the items you need or can offer.
- **See matches on a map** — nearby people are scored and ranked by how well their items overlap with yours, shown as pins on an interactive map.
- **Message matches** — a built-in direct-messaging system with read receipts and conversation history.
- **Ask the AI assistant** — an in-app chat widget backed by an Amazon Bedrock agent.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML/CSS/JS, MapLibre GL JS |
| Backend | Python, Flask, Gunicorn |
| Auth | Amazon Cognito (OIDC / OAuth2), Authlib |
| Database | Amazon DynamoDB |
| AI | Amazon Bedrock agent |
| Maps | Amazon Location Service |
| Hosting | AWS Amplify (static), Elastic Beanstalk (API), CloudFront (CDN) |

## Architecture

The frontend is served as static files through AWS Amplify, fronted by CloudFront. CloudFront routes auth (`/login`, `/authorize`, `/logout`) and API (`/api/*`) traffic to a Flask backend on Elastic Beanstalk. The backend talks to DynamoDB for resource and message storage, Cognito for identity, and Bedrock for the AI assistant. Maps are rendered client-side with MapLibre against Amazon Location Service, authenticated through a Cognito identity pool.

A detailed diagram, service breakdown, auth flow, and API reference live in [`docs/architecture.md`](docs/architecture.md).

## Project structure

```
.
├── main.py                  # Flask backend — auth, resources, matching, messaging, AI chat
├── requirements.txt         # Python dependencies
├── Procfile                 # Gunicorn start command for Elastic Beanstalk
├── cognito-hosted-ui.css    # Custom styling for the Cognito hosted login UI
├── docs/
│   └── architecture.md      # Full AWS architecture, auth flow, and API reference
└── static/                  # Frontend served via Amplify
    ├── index.html           # Landing page
    ├── role.html            # Role selection (need / have / both)
    ├── resources.html       # Resource entry
    ├── map.html             # Interactive match map
    └── chat-widget.js       # AI assistant chat widget
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/login` | Initiate Cognito OIDC login |
| GET | `/authorize` | OAuth2 callback, exchange code for token |
| GET | `/logout` | Clear session |
| POST | `/api/resources` | Create a resource entry |
| GET | `/api/resources/mine` | Get the current user's resources |
| PUT | `/api/resources/<id>` | Update a resource entry |
| DELETE | `/api/resources/<id>` | Delete a resource entry |
| GET | `/api/match` | Get matched users, grouped and scored |
| POST | `/api/messages` | Send a message |
| GET | `/api/messages?convo_id=` | Get a conversation's messages |
| GET | `/api/conversations` | List the current user's conversations |
| POST | `/api/chat` | Send a message to the Bedrock AI agent |

## Running locally

The backend depends on AWS services (Cognito, DynamoDB, Bedrock, Location Service), so a local run needs valid AWS credentials and the environment variables below configured.

```bash
pip install -r requirements.txt

# required environment variables
# COGNITO_CLIENT_SECRET  — Cognito app client secret
# SECRET_KEY             — Flask session secret
# BEDROCK_AGENT_ID       — Bedrock agent ID
# BEDROCK_AGENT_ALIAS_ID — Bedrock agent alias ID

python main.py
```

## Deployment

- **Static frontend** — upload `static/` files to the S3 bucket backing Amplify, then invalidate CloudFront `/*`.
- **Flask backend** — zip `main.py`, `requirements.txt`, and `Procfile`, then upload via the Elastic Beanstalk console.
- **Environment config** — set the environment variables above in the Elastic Beanstalk console under Configuration → Software.

## Notes

This was built under hackathon time constraints. A couple of known shortcuts worth flagging before any production use: JWT tokens are decoded from their claims without signature verification, and `/api/conversations` and `/api/match` scan DynamoDB rather than using a GSI. Both are called out in `docs/architecture.md`.
