# routes/__init__.py
from bustapi.responses import HTMLResponse


def render(template_name: str, status: int = 200, **context) -> HTMLResponse:
    """
    Render a Jinja2 template using the app's cached environment.
    Avoids creating a new Environment on every call.
    """
    from bustapi import current_app
    env = current_app.create_jinja_environment()
    html = env.get_template(template_name).render(**context)
    return HTMLResponse(html, status_code=status)
