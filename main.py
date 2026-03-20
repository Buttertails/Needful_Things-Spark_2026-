from flask import Flask, redirect, request, make_response
from authlib.integrations.flask_client import OAuth
import os

CLOUDFRONT_URL = 'https://d84l1y8p4kdic.cloudfront.net'

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
oauth = OAuth(app)

oauth.register(
    name='oidc',
    authority='https://cognito-idp.us-east-1.amazonaws.com/us-east-1_SVWFWvH1I',
    client_id='7l2fh3lmk09rfi1neoh3ghujek',
    client_secret=os.environ.get('COGNITO_CLIENT_SECRET'),
    server_metadata_url='https://cognito-idp.us-east-1.amazonaws.com/us-east-1_SVWFWvH1I/.well-known/openid-configuration',
    client_kwargs={'scope': 'phone openid email'}
)

@app.route('/login')
def login():
    redirect_uri = request.host_url.rstrip('/') + '/authorize'
    return oauth.oidc.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = oauth.oidc.authorize_access_token()
    id_token = token.get('id_token', '')
    # Pass token via secure cookie, redirect to static role selection page on CloudFront
    resp = make_response(redirect(f'{CLOUDFRONT_URL}/role.html'))
    resp.set_cookie('id_token', id_token, secure=True, samesite='Lax')
    return resp

@app.route('/logout')
def logout():
    resp = make_response(redirect(CLOUDFRONT_URL))
    resp.delete_cookie('id_token')
    return resp

if __name__ == '__main__':
    app.run(debug=True)
