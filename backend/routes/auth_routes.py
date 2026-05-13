import os
from flask import Blueprint, redirect, url_for, session, current_app
from authlib.integrations.flask_client import OAuth
from models.user import get_or_create_user

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
oauth = OAuth()

# Google OAuth registration
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

@auth_bp.route('/login')
def auth_login():
    """Initiates the Google OAuth login flow."""
    # Use internal callback but ensure it's https in production
    redirect_uri = url_for('auth.auth_callback', _external=True)
    if 'onrender.com' in redirect_uri:
        redirect_uri = redirect_uri.replace('http://', 'https://')
    return google.authorize_redirect(redirect_uri)

@auth_bp.route('/callback')
def auth_callback():
    """Handles the callback from Google OAuth."""
    frontend_url = os.environ.get("FRONTEND_URL", "")
    
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        
        if not user_info:
            return redirect(f"{frontend_url}/?error=no_user_info")
            
        # Store or fetch user from DB
        user = get_or_create_user(
            google_id=user_info.get('sub'),
            email=user_info.get('email'),
            name=user_info.get('name'),
            picture=user_info.get('picture')
        )
        
        if not user:
            return redirect(f"{frontend_url}/?error=db_fail")
        
        # Save user to session
        session['user'] = user
        
        # Redirect to frontend dashboard
        return redirect(f"{frontend_url}/dashboard.html")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Auth error: {e}")
        return redirect(f"{frontend_url}/?error=auth_failed")

@auth_bp.route('/auth/logout')
def auth_logout():
    """Logs out the user and clears the session."""
    frontend_url = os.environ.get("FRONTEND_URL", "")
    session.pop('user', None)
    return redirect(f"{frontend_url}/")
