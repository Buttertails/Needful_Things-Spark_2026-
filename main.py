from flask import Flask, redirect, request, make_response, jsonify
from authlib.integrations.flask_client import OAuth
from flask_cors import CORS
import os, json, uuid
import os, boto3
from functools import wraps
from jose import jwt

CLOUDFRONT_URL = 'https://staging.d1lkt3hd0w7zxm.amplifyapp.com'

DATA_FILE = '/tmp/resources.json'
BEDROCK_AGENT_ID = os.environ.get('BEDROCK_AGENT_ID')
BEDROCK_AGENT_ALIAS_ID = os.environ.get('BEDROCK_AGENT_ALIAS_ID')
bedrock = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('resources')
COGNITO_REGION = 'us-east-1'
COGNITO_POOL_ID = 'us-east-1_kowqhZ4fl'
CLIENT_ID = '25is9h8u5rka8qi4sti9qnu0d2'

app = Flask(__name__)
CORS(app, origins=[CLOUDFRONT_URL, 'https://staging.d1lkt3hd0w7zxm.amplifyapp.com'], supports_credentials=True)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
oauth = OAuth(app)

oauth.register(
    name='oidc',
    authority=f'https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_POOL_ID}',
    client_id=CLIENT_ID,
    client_secret=os.environ.get('COGNITO_CLIENT_SECRET'),
    server_metadata_url=f'https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_POOL_ID}/.well-known/openid-configuration',
    client_kwargs={'scope': 'email openid phone'}
)

# --- helpers ---

def get_current_user():
    token = request.cookies.get('id_token')
    if not token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
    if not token:
        return None
    try:
        claims = jwt.get_unverified_claims(token)
        return claims
    except Exception:
        return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_current_user():
            return jsonify({'error': 'unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# --- auth routes ---

@app.route('/login')
def login():
    redirect_uri = 'https://dybar52ziekaj.cloudfront.net/authorize'
    return oauth.oidc.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = oauth.oidc.authorize_access_token()
    id_token = token.get('id_token', '')
    # Pass token via URL fragment to static page — fragment never hits the server
    resp = make_response(redirect(f'{CLOUDFRONT_URL}/role.html#token={id_token}'))
    return resp

@app.route('/logout')
def logout():
    resp = make_response(redirect(CLOUDFRONT_URL))
    resp.delete_cookie('id_token')
    return resp

# --- resource API ---

@app.route('/api/debug-auth')
def debug_auth():
    token_cookie = request.cookies.get('id_token', 'none')
    auth_header = request.headers.get('Authorization', 'none')
    return jsonify({'cookie': token_cookie[:20] if token_cookie != 'none' else 'none', 'header': auth_header[:20] if auth_header != 'none' else 'none'})

@app.route('/api/resources', methods=['POST'])
@require_auth
def post_resource():
    user = get_current_user()
    body = request.get_json()
    entry = {
        'user_id': user.get('sub'),
        'type': body.get('type'),
        'email': user.get('email'),
        'items': body.get('items', []),
        'lat': str(body.get('lat', '')),
        'lng': str(body.get('lng', '')),
    }
    table.put_item(Item=entry)
    return jsonify(entry), 201

@app.route('/api/match', methods=['GET'])
@require_auth
def get_matches():
    user = get_current_user()
    role = request.args.get('role', 'both')
    user_id = user.get('sub')

    result = table.scan()
    data = result.get('Items', [])

    # get current user's own entries to match against
    user_entries = [d for d in data if d['user_id'] == user_id]
    user_needs = set()
    user_haves = set()
    for e in user_entries:
        items = set(i.lower().strip() for i in e.get('items', []))
        if e['type'] == 'need':
            user_needs.update(items)
        elif e['type'] == 'have':
            user_haves.update(items)

    def match_score(entry):
        items = set(i.lower().strip() for i in entry.get('items', []))
        if entry['type'] == 'have':
            # they have things — score by overlap with what user needs
            return len(items & user_needs) if user_needs else 1
        else:
            # they need things — score by overlap with what user has
            return len(items & user_haves) if user_haves else 1

    if role == 'need':
        matches = [d for d in data if d['type'] == 'have' and d['user_id'] != user_id]
    elif role == 'have':
        matches = [d for d in data if d['type'] == 'need' and d['user_id'] != user_id]
    else:
        matches = [d for d in data if d['user_id'] != user_id]

    # sort by match score descending, include score in response
    for m in matches:
        m['match_score'] = match_score(m)
        try:
            m['lat'] = float(m['lat'])
            m['lng'] = float(m['lng'])
        except (ValueError, TypeError):
            m['lat'] = None
            m['lng'] = None

    matches.sort(key=lambda x: x['match_score'], reverse=True)

    return jsonify(matches)

if __name__ == '__main__':
    app.run(debug=True)
