import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, jsonify, session, request, redirect, url_for
from flask_cors import CORS
from database.schema import init_db
from routes.api_routes import api
from routes.auth_routes import auth_bp, oauth
from services.scheduler import start_scheduler

def create_app():
    app = Flask(__name__)
    
    # Configure CORS - allow the frontend URL
    frontend_url = os.environ.get("FRONTEND_URL", "https://garudaa-frontend.onrender.com")
    CORS(app, supports_credentials=True, origins=[frontend_url, "http://localhost:5500", "http://127.0.0.1:5500"])

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "synthmon-dev-secret")
    
    # Session configuration for Cross-Domain support (Vercel -> Render)
    app.config.update(
        SESSION_COOKIE_SAMESITE='None',
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
    )

    # Init DB
    init_db()

    # Configure OAuth
    oauth.init_app(app)

    # Register blueprints
    app.register_blueprint(api)
    app.register_blueprint(auth_bp)

    @app.before_request
    def require_login():
        # Allow access to auth routes, health check and CORS preflight
        allowed_endpoints = ['auth.login_page', 'auth.auth_login', 'auth.auth_callback', 'health']
        if request.method == 'OPTIONS':
            return
        
        if request.endpoint and request.endpoint not in allowed_endpoints:
            user = session.get('user')
            if not user or not isinstance(user, dict):
                # Return 401 Unauthorized for API requests
                if request.path.startswith('/api/'):
                    return jsonify({"error": "Unauthorized"}), 401
                # For others, clear session
                session.pop('user', None)

    @app.route("/health")
    def health():
        return jsonify({"status": "healthy", "service": "SynthMonitor API"}), 200

    @app.route("/api/me")
    def get_me():
        user = session.get('user')
        if user:
            return jsonify(user)
        return jsonify({"error": "Not logged in"}), 401

    # Start background monitor scheduler
    start_scheduler()

    @app.errorhandler(500)
    def handle_500(e):
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal Server Error"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
