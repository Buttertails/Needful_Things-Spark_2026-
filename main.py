from flask import Flask, redirect, request, make_response, jsonify
from authlib.integrations.flask_client import OAuth
from flask_cors import CORS
import os, json, uuid, boto3
from functools import wraps
from jose import jwt

CLOUDFRONT_URL = 'https://staging.d1lkt3hd0w7zxm.amplifyapp.com'
BEDROCK_AGENT_ID = os.environ.get('BEDROCK_AGENT_ID')
BEDROCK_AGENT_ALIAS_ID = os.environ.get('BEDROCK_AGENT_ALIAS_ID')
bedrock = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('resources')
DATA_FILE = '/tmp/resources.json'
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

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE) as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def get_current_user():
    token = request.cookies.get('id_token')
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
    resp = make_response(redirect(f'{CLOUDFRONT_URL}/role.html'))
    resp.set_cookie('id_token', id_token, secure=True, samesite='Lax')
    return resp

@app.route('/logout')
def logout():
    resp = make_response(redirect(CLOUDFRONT_URL))
    resp.delete_cookie('id_token')
    return resp

# --- resource API ---

@app.route('/api/resources', methods=['POST'])
@require_auth
def post_resource():
    user = get_current_user()
    body = request.get_json()
    entry = {
        'id': str(uuid.uuid4()),
        'user_id': user.get('sub'),
        'email': user.get('email'),
        'type': body.get('type'),        # 'have' or 'need'
        'items': body.get('items', []),  # list of resource strings
        'lat': body.get('lat'),
        'lng': body.get('lng'),
    }
    data = load_data()
    # replace existing entry for this user+type
    data = [d for d in data if not (d['user_id'] == entry['user_id'] and d['type'] == entry['type'])]
    data.append(entry)
    save_data(data)
    return jsonify(entry), 201

@app.route('/api/match', methods=['GET'])
@require_auth
def get_matches():
    user = get_current_user()
    role = request.args.get('role', 'both')  # 'need', 'have', or 'both'
    data = load_data()
    user_id = user.get('sub')

    if role == 'need':
        # user needs resources, show people who have them
        matches = [d for d in data if d['type'] == 'have' and d['user_id'] != user_id]
    elif role == 'have':
        # user has resources, show people who need them
        matches = [d for d in data if d['type'] == 'need' and d['user_id'] != user_id]
    else:
        # show everything except own entries
        matches = [d for d in data if d['user_id'] != user_id]

    return jsonify(matches)

@app.route('/api/chat', methods=['POST'])
@require_auth
def chat():
    body = request.get_json()
    message = body.get('message', '').strip()
    session_id = body.get('session_id', str(uuid.uuid4()))
    if not message:
        return jsonify({'error': 'empty message'}), 400

    response = bedrock.invoke_agent(
        agentId=BEDROCK_AGENT_ID,
        agentAliasId=BEDROCK_AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=message
    )

    # stream the completion chunks into a single string
    reply = ''
    for event in response['completion']:
        if 'chunk' in event:
            reply += event['chunk']['bytes'].decode('utf-8')

    return jsonify({'reply': reply, 'session_id': session_id})

if __name__ == '__main__':
    app.run(debug=True)
