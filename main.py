# main.py
import os

from dotenv import load_dotenv
from jinja2 import select_autoescape

from bustapi import BustAPI

load_dotenv()

app = BustAPI(template_folder="templates", static_folder="static")

# Jinja2 autoescape for all HTML/XML templates
app.jinja_options = {"autoescape": select_autoescape(["html", "xml"])}

# Required for session-based admin auth
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

# Request/response hooks (BustAPI before_request / after_request)
from middleware.htmx import HTMXDetails
from middleware.auth import AdminAuthMiddleware

_auth = AdminAuthMiddleware()


@app.before_request
def _attach_htmx():
    from bustapi import request
    request.htmx = HTMXDetails(request)


@app.before_request
def _check_admin_auth():
    from bustapi import request
    return _auth.process_request(request)


@app.after_request
def _add_vary(response):
    response.headers["Vary"] = "HX-Request"
    return response

# Blueprints
from routes.pages import pages_bp
from routes.blog import blog_bp
from routes.projects import projects_bp
from routes.admin import admin_bp

app.register_blueprint(pages_bp)
app.register_blueprint(blog_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(admin_bp, url_prefix="/admin")

# Initialize DB schema and seed content
from db.connection import get_db
from db.schema import init_db

init_db(get_db())

if __name__ == "__main__":
    debug = os.getenv("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=8000, debug=debug)
