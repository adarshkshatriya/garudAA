import os
from flask import Blueprint, redirect, url_for, session, render_template
from authlib.integrations.flask_client import OAuth
from models.user import get_or_create_user

auth_bp = Blueprint('auth', __name__)
oauth = OAuth()

# We will register google here, but it needs to be initialized with the app in app.py
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

@auth_bp.route('/login')
def login_page():
    """Renders the login page with the Google Sign-in button."""
    return render_template('login.html')

@auth_bp.route('/auth/login')
def auth_login():
    """Initiates the Google OAuth login flow."""
    redirect_uri = url_for('auth.auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@auth_bp.route('/auth/callback')
def auth_callback():
    """Handles the callback from Google OAuth."""
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if not user_info:
        return "Failed to get user information from Google.", 400
        
    # Store or fetch user from DB
    user = get_or_create_user(user_info)
    
    if not user:
        return "Failed to create or retrieve user in database.", 500
    
    # Save user to session
    session['user'] = user
    return redirect(url_for('dashboard'))

@auth_bp.route('/auth/logout')
def auth_logout():
    """Logs out the user and clears the session."""
    session.pop('user', None)
    return redirect(url_for('auth.login_page'))
