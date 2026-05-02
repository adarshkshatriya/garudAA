import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, session, redirect, url_for
from database.schema import init_db
from routes.api_routes import api
from routes.auth_routes import auth_bp, oauth
from services.scheduler import start_scheduler

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "synthmon-dev-secret")

    # Init DB
    init_db()

    # Configure OAuth
    oauth.init_app(app)

    # Register blueprints
    app.register_blueprint(api)
    app.register_blueprint(auth_bp)

    @app.before_request
    def require_login():
        # Allow access to auth routes and static files without logging in
        allowed_endpoints = ['auth.login_page', 'auth.auth_login', 'auth.auth_callback', 'static']
        # If user is not logged in and trying to access a protected route
        if request.endpoint and request.endpoint not in allowed_endpoints:
            user = session.get('user')
            if not user or not isinstance(user, dict):
                session.pop('user', None)  # Clear invalid session data
                return redirect(url_for('auth.login_page'))

    # UI routes
    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/monitors")
    def monitors_page():
        return render_template("dashboard.html", page="monitors")

    @app.route("/alerts")
    def alerts_page():
        return render_template("dashboard.html", page="alerts")

    @app.route("/ssl")
    def ssl_page():
        return render_template("dashboard.html", page="ssl")

    @app.route("/settings")
    def settings_page():
        return render_template("dashboard.html", page="settings")

    # Start background monitor scheduler
    start_scheduler()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
