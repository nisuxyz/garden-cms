# routes/pages.py
import json

from bustapi import Blueprint, request
from bustapi import redirect

from db.connection import get_db
from db.schema import get_content, parse_tags
from routes import render

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    db = get_db()
    content = {
        "hero_headline": get_content(db, "home.hero_headline"),
        "hero_subtext":  get_content(db, "home.hero_subtext"),
        "about":         get_content(db, "home.about"),
    }
    raw_posts = db.query(
        "SELECT title, slug, summary, tags, created_at FROM posts "
        "WHERE published = $1 ORDER BY created_at DESC LIMIT $2",
        [True, 3],
    ) or []
    posts = [{**p, "tags": parse_tags(p.get("tags", "[]"))} for p in raw_posts]

    raw_projects = db.query(
        "SELECT title, slug, summary, tags, url, repo_url FROM projects "
        "WHERE published = $1 AND featured = $2 ORDER BY created_at DESC LIMIT $3",
        [True, True, 4],
    ) or []
    projects = [{**p, "tags": parse_tags(p.get("tags", "[]"))} for p in raw_projects]

    return render("pages/index.html", content=content, posts=posts, projects=projects)


@pages_bp.route("/resume")
def resume():
    db = get_db()
    content = {
        "intro":      get_content(db, "resume.intro"),
        "experience": get_content(db, "resume.experience"),
        "education":  get_content(db, "resume.education"),
        "skills":     get_content(db, "resume.skills"),
    }
    return render("pages/resume.html", content=content)


@pages_bp.route("/contact", methods=["GET"])
def contact():
    db = get_db()
    return render(
        "pages/contact.html",
        intro=get_content(db, "contact.intro"),
        success=request.args.get("success") == "1",
        error_msg=request.args.get("error") == "1",
    )


@pages_bp.route("/contact", methods=["POST"])
def contact_post():
    name    = request.form.get("name", "").strip()
    email   = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

    is_htmx = bool(request.headers.get("HX-Request"))

    if not (name and email and message):
        if is_htmx:
            return render("htmx/contact/error.html", error="All fields are required."), 422
        return redirect("/contact?error=1")

    # TODO: integrate email/notification delivery
    if is_htmx:
        return render("htmx/contact/success.html")
    return redirect("/contact?success=1")
