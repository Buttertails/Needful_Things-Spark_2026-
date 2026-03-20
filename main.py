from flask import Flask, redirect, request, make_response, jsonify
from authlib.integrations.flask_client import OAuth
from flask_cors import CORS
import os, boto3, uuid
from functools import wraps
from jose import jwt
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key

CLOUDFRONT_URL = 'https://staging.d1lkt3hd0w7zxm.amplifyapp.com'
COGNITO_REGION = 'us-east-1'
COGNITO_POOL_ID = 'us-east-1_kowqhZ4fl'
CLIENT_ID = '25is9h8u5rka8qi4sti9qnu0d2'

BEDROCK_AGENT_ID = os.environ.get('BEDROCK_AGENT_ID')
BEDROCK_AGENT_ALIAS_ID = os.environ.get('BEDROCK_AGENT_ALIAS_ID')
bedrock = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('resources')
messages_table = dynamodb.Table('messages')

app = Flask(__name__)
CORS(app, origins=[
    CLOUDFRONT_URL,
    'https://dybar52ziekaj.cloudfront.net'
], supports_credentials=True)
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

def make_conversation_id(user_a, user_b):
    # always sort so conversation_id is consistent regardless of who initiates
    return '#'.join(sorted([user_a, user_b]))

# --- auth routes ---

@app.route('/login')
def login():
    redirect_uri = 'https://dybar52ziekaj.cloudfront.net/authorize'
    return oauth.oidc.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = oauth.oidc.authorize_access_token()
    id_token = token.get('id_token', '')
    resp = make_response(redirect(f'{CLOUDFRONT_URL}/role.html#token={id_token}'))
    return resp

@app.route('/logout')
def logout():
    resp = make_response(redirect(CLOUDFRONT_URL))
    resp.delete_cookie('id_token')
    return resp

# --- debug ---

@app.route('/api/debug-auth')
def debug_auth():
    token_cookie = request.cookies.get('id_token', 'none')
    auth_header = request.headers.get('Authorization', 'none')
    return jsonify({
        'cookie': token_cookie[:20] if token_cookie != 'none' else 'none',
        'header': auth_header[:20] if auth_header != 'none' else 'none'
    })

# --- resource API ---

@app.route('/api/resources', methods=['POST'])
@require_auth
def post_resource():
    user = get_current_user()
    body = request.get_json()
    entry = {
        'user_id': user.get('sub'),
        'id': str(uuid.uuid4()),
        'type': body.get('type'),
        'email': user.get('email'),
        'items': body.get('items', []),
        'lat': str(body.get('lat', '')),
        'lng': str(body.get('lng', '')),
    }
    table.put_item(Item=entry)
    return jsonify(entry), 201

@app.route('/api/resources/mine', methods=['GET'])
@require_auth
def get_my_resources():
    user = get_current_user()
    result = table.query(KeyConditionExpression=Key('user_id').eq(user.get('sub')))
    return jsonify(result.get('Items', []))

@app.route('/api/resources/<resource_id>', methods=['PUT'])
@require_auth
def update_resource(resource_id):
    user = get_current_user()
    body = request.get_json()
    table.update_item(
        Key={'user_id': user.get('sub'), 'id': resource_id},
        UpdateExpression='SET #items = :items, #type = :type',
        ExpressionAttributeNames={'#items': 'items', '#type': 'type'},
        ExpressionAttributeValues={':items': body.get('items', []), ':type': body.get('type')}
    )
    return jsonify({'status': 'updated'})

@app.route('/api/resources/<resource_id>', methods=['DELETE'])
@require_auth
def delete_resource(resource_id):
    user = get_current_user()
    table.delete_item(Key={'user_id': user.get('sub'), 'id': resource_id})
    return jsonify({'status': 'deleted'})

@app.route('/api/match', methods=['GET'])
@require_auth
def get_matches():
    user = get_current_user()
    role = request.args.get('role', 'both')
    user_id = user.get('sub')

    result = table.scan()
    data = result.get('Items', [])

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
            return len(items & user_needs) if user_needs else 1
        else:
            return len(items & user_haves) if user_haves else 1

    if role == 'need':
        matches = [d for d in data if d['type'] == 'have' and d['user_id'] != user_id]
    elif role == 'have':
        matches = [d for d in data if d['type'] == 'need' and d['user_id'] != user_id]
    else:
        matches = [d for d in data if d['user_id'] != user_id]

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

# --- messaging API ---

@app.route('/api/messages', methods=['POST'])
@require_auth
def send_message():
    user = get_current_user()
    body = request.get_json()
    recipient_id = body.get('recipient_id')
    text = body.get('text', '').strip()
    if not recipient_id or not text:
        return jsonify({'error': 'recipient_id and text required'}), 400

    sender_id = user.get('sub')
    conversation_id = make_conversation_id(sender_id, recipient_id)
    timestamp = datetime.now(timezone.utc).isoformat()
    message_id = str(uuid.uuid4())

    message = {
        'conversation_id': conversation_id,
        'timestamp': timestamp,
        'message_id': message_id,
        'sender_id': sender_id,
        'sender_email': user.get('email', ''),
        'recipient_id': recipient_id,
        'text': text,
        'read': False
    }
    messages_table.put_item(Item=message)
    return jsonify(message), 201

@app.route('/api/messages/<conversation_id>', methods=['GET'])
@require_auth
def get_messages(conversation_id):
    user = get_current_user()
    user_id = user.get('sub')

    # verify user is part of this conversation
    participants = conversation_id.split('#')
    if user_id not in participants:
        return jsonify({'error': 'forbidden'}), 403

    result = messages_table.query(
        KeyConditionExpression=Key('conversation_id').eq(conversation_id)
    )
    messages = result.get('Items', [])

    # mark unread messages from the other person as read
    for msg in messages:
        if msg['sender_id'] != user_id and not msg.get('read'):
            messages_table.update_item(
                Key={
                    'conversation_id': conversation_id,
                    'timestamp': msg['timestamp']
                },
                UpdateExpression='SET #r = :r',
                ExpressionAttributeNames={'#r': 'read'},
                ExpressionAttributeValues={':r': True}
            )
            msg['read'] = True

    return jsonify(sorted(messages, key=lambda x: x['timestamp']))

@app.route('/api/conversations', methods=['GET'])
@require_auth
def get_conversations():
    user = get_current_user()
    user_id = user.get('sub')

    # scan for all messages involving this user — in production use a GSI
    result = messages_table.scan()
    all_messages = result.get('Items', [])

    # group by conversation
    convos = {}
    for msg in all_messages:
        participants = msg['conversation_id'].split('#')
        if user_id not in participants:
            continue
        cid = msg['conversation_id']
        other_id = participants[0] if participants[1] == user_id else participants[1]
        if cid not in convos:
            convos[cid] = {
                'conversation_id': cid,
                'other_user_id': other_id,
                'other_email': msg['sender_email'] if msg['sender_id'] != user_id else msg.get('recipient_email', other_id),
                'last_message': msg['text'],
                'last_timestamp': msg['timestamp'],
                'unread_count': 0
            }
        else:
            if msg['timestamp'] > convos[cid]['last_timestamp']:
                convos[cid]['last_message'] = msg['text']
                convos[cid]['last_timestamp'] = msg['timestamp']
        if msg['sender_id'] != user_id and not msg.get('read'):
            convos[cid]['unread_count'] += 1

    result = sorted(convos.values(), key=lambda x: x['last_timestamp'], reverse=True)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)