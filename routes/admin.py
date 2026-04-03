# routes/admin.py
import hmac
import json
import os

from bustapi import Blueprint, request
from bustapi import redirect
from bustapi import session
from bustapi.responses import HTMLResponse

from db.connection import get_db
from db.schema import get_content, parse_tags, render_md
from routes import render

admin_bp = Blueprint("admin", __name__)


# ── Auth ───────────────────────────────────────────────────

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        admin_pw = os.getenv("ADMIN_PASSWORD", "")
        if password and admin_pw and hmac.compare_digest(password, admin_pw):
            session["admin_authenticated"] = True
            return redirect("/admin")
        return render("pages/admin/login.html", error="Invalid password.")
    return render("pages/admin/login.html", error=None)


@admin_bp.route("/logout")
def logout():
    session.pop("admin_authenticated", None)
    return redirect("/admin/login")


# ── Dashboard ──────────────────────────────────────────────

@admin_bp.route("/")
def dashboard():
    db = get_db()
    post_count    = (db.query_one("SELECT COUNT(*) as n FROM posts") or {}).get("n", 0)
    project_count = (db.query_one("SELECT COUNT(*) as n FROM projects") or {}).get("n", 0)
    return render("pages/admin/dashboard.html",
                  post_count=post_count, project_count=project_count, view="overview")


# ── Posts ──────────────────────────────────────────────────

@admin_bp.route("/posts", methods=["GET"])
def posts_list():
    db = get_db()
    rows = db.query(
        "SELECT id, title, slug, published, created_at FROM posts ORDER BY created_at DESC"
    ) or []
    return render("pages/admin/dashboard.html", posts=rows, view="posts",
                  post_count=len(rows), project_count=0)


@admin_bp.route("/posts/new", methods=["GET"])
def posts_new():
    return render("pages/admin/post_edit.html", post=None)


@admin_bp.route("/posts", methods=["POST"])
def posts_create():
    db = get_db()
    title     = request.form.get("title", "").strip()
    slug      = request.form.get("slug", "").strip()
    summary   = request.form.get("summary", "").strip()
    body      = request.form.get("body", "").strip()
    tags_raw  = request.form.get("tags", "").strip()
    published = request.form.get("published") == "on"
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    db.execute(
        "INSERT INTO posts (title, slug, summary, body, tags, published) "
        "VALUES ($1,$2,$3,$4,$5,$6)",
        [title, slug, summary, body, json.dumps(tags), published],
    )
    return redirect("/admin/posts")


@admin_bp.route("/posts/<id>/edit", methods=["GET"])
def posts_edit(id: str):
    db = get_db()
    try:
        post_id = int(id)
    except ValueError:
        from bustapi.http.response import Response
        return Response("Not Found", status=404)
    post = db.query_one("SELECT * FROM posts WHERE id = $1", [post_id])
    if not post:
        return HTMLResponse("Not Found", status_code=404)
    post = {**post, "tags": parse_tags(post.get("tags", "[]"))}
    return render("pages/admin/post_edit.html", post=post)


@admin_bp.route("/posts/<id>/edit", methods=["POST"])
def posts_update(id: str):
    db = get_db()
    try:
        post_id = int(id)
    except ValueError:
        from bustapi.http.response import Response
        return Response("Not Found", status=404)
    existing = db.query_one("SELECT slug FROM posts WHERE id = $1", [post_id])
    if not existing:
        return HTMLResponse("Not Found", status_code=404)
    title     = request.form.get("title", "").strip()
    new_slug  = request.form.get("slug", "").strip()
    summary   = request.form.get("summary", "").strip()
    body      = request.form.get("body", "").strip()
    tags_raw  = request.form.get("tags", "").strip()
    published = request.form.get("published") == "on"
    tags      = [t.strip() for t in tags_raw.split(",") if t.strip()]
    old_slug  = existing["slug"]
    if new_slug != old_slug:
        db.execute(
            "INSERT INTO post_slug_history (post_id, slug) VALUES ($1, $2)",
            [post_id, old_slug],
        )
    db.execute(
        "UPDATE posts SET title=$1, slug=$2, summary=$3, body=$4, tags=$5, "
        "published=$6, updated_at=CURRENT_TIMESTAMP WHERE id=$7",
        [title, new_slug, summary, body, json.dumps(tags), published, post_id],
    )
    return redirect("/admin/posts")


@admin_bp.route("/posts/<id>/delete", methods=["POST"])
def posts_delete(id: str):
    db = get_db()
    try:
        post_id = int(id)
    except ValueError:
        from bustapi.http.response import Response
        return Response("Not Found", status=404)
    db.execute("DELETE FROM post_slug_history WHERE post_id = $1", [post_id])
    db.execute("DELETE FROM posts WHERE id = $1", [post_id])
    if request.htmx.is_htmx:
        return HTMLResponse("", status_code=200)
    return redirect("/admin/posts")


# ── Projects ───────────────────────────────────────────────

@admin_bp.route("/projects", methods=["GET"])
def projects_list():
    db = get_db()
    rows = db.query(
        "SELECT id, title, slug, published, featured FROM projects ORDER BY created_at DESC"
    ) or []
    return render("pages/admin/project_list.html", projects=rows)


@admin_bp.route("/projects/new", methods=["GET"])
def projects_new():
    return render("pages/admin/project_edit.html", project=None)


@admin_bp.route("/projects", methods=["POST"])
def projects_create():
    db = get_db()
    title     = request.form.get("title", "").strip()
    slug      = request.form.get("slug", "").strip()
    summary   = request.form.get("summary", "").strip()
    body      = request.form.get("body", "").strip()
    tags_raw  = request.form.get("tags", "").strip()
    url       = request.form.get("url", "").strip() or None
    repo_url  = request.form.get("repo_url", "").strip() or None
    featured  = request.form.get("featured") == "on"
    published = request.form.get("published") == "on"
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    db.execute(
        "INSERT INTO projects (title, slug, summary, body, tags, url, repo_url, featured, published) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        [title, slug, summary, body, json.dumps(tags), url, repo_url, featured, published],
    )
    return redirect("/admin/projects")


@admin_bp.route("/projects/<id>/edit", methods=["GET"])
def projects_edit(id: str):
    db = get_db()
    try:
        project_id = int(id)
    except ValueError:
        from bustapi.http.response import Response
        return Response("Not Found", status=404)
    project = db.query_one("SELECT * FROM projects WHERE id = $1", [project_id])
    if not project:
        return HTMLResponse("Not Found", status_code=404)
    project = {**project, "tags": parse_tags(project.get("tags", "[]"))}
    return render("pages/admin/project_edit.html", project=project)


@admin_bp.route("/projects/<id>/edit", methods=["POST"])
def projects_update(id: str):
    db = get_db()
    try:
        project_id = int(id)
    except ValueError:
        from bustapi.http.response import Response
        return Response("Not Found", status=404)
    existing   = db.query_one("SELECT slug FROM projects WHERE id = $1", [project_id])
    if not existing:
        return HTMLResponse("Not Found", status_code=404)
    title     = request.form.get("title", "").strip()
    new_slug  = request.form.get("slug", "").strip()
    summary   = request.form.get("summary", "").strip()
    body      = request.form.get("body", "").strip()
    tags_raw  = request.form.get("tags", "").strip()
    url       = request.form.get("url", "").strip() or None
    repo_url  = request.form.get("repo_url", "").strip() or None
    featured  = request.form.get("featured") == "on"
    published = request.form.get("published") == "on"
    tags      = [t.strip() for t in tags_raw.split(",") if t.strip()]
    old_slug  = existing["slug"]
    if new_slug != old_slug:
        db.execute(
            "INSERT INTO project_slug_history (project_id, slug) VALUES ($1, $2)",
            [project_id, old_slug],
        )
    db.execute(
        "UPDATE projects SET title=$1, slug=$2, summary=$3, body=$4, tags=$5, "
        "url=$6, repo_url=$7, featured=$8, published=$9, updated_at=CURRENT_TIMESTAMP "
        "WHERE id=$10",
        [title, new_slug, summary, body, json.dumps(tags), url, repo_url, featured, published, project_id],
    )
    return redirect("/admin/projects")


@admin_bp.route("/projects/<id>/delete", methods=["POST"])
def projects_delete(id: str):
    db = get_db()
    try:
        project_id = int(id)
    except ValueError:
        from bustapi.http.response import Response
        return Response("Not Found", status=404)
    db.execute("DELETE FROM project_slug_history WHERE project_id = $1", [project_id])
    db.execute("DELETE FROM projects WHERE id = $1", [project_id])
    if request.htmx.is_htmx:
        return HTMLResponse("", status_code=200)
    return redirect("/admin/projects")


# ── Site Content ───────────────────────────────────────────

@admin_bp.route("/content", methods=["GET"])
def content_list():
    db = get_db()
    rows = db.query(
        "SELECT content_key as key, value, label, is_markdown, updated_at FROM site_content ORDER BY content_key"
    ) or []
    return render("pages/admin/content.html", blocks=rows)


@admin_bp.route("/content/<key>", methods=["POST"])
def content_update(key: str):
    db = get_db()
    if not db.query_one("SELECT content_key FROM site_content WHERE content_key = $1", [key]):
        from bustapi.http.response import Response
        return Response("Not Found", status=404)
    value = request.form.get("value", "").strip()
    db.execute(
        "UPDATE site_content SET value=$1, updated_at=CURRENT_TIMESTAMP WHERE content_key=$2",
        [value, key],
    )
    if request.htmx.is_htmx:
        safe_id = key.replace(".", "-")
        return HTMLResponse(
            f'<span id="saved-{safe_id}" class="meta"><ins>Saved ✓</ins></span>',
            status_code=200,
        )
    return redirect("/admin/content")
