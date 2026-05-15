import os

import click
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from .extensions import login_manager
from . import models  # noqa: F401 — registers Flask-Login user_loader
from .db import init_db
from .logging_config import setup_logging
from . import auth, loans, main


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    setup_logging(app)

    if os.environ.get("RENDER") == "true":
        app.logger.info(
            "Render deploy: MySQL from DATABASE_URL or MYSQL_*; view live logs in Render Dashboard → Logs."
        )

    login_manager.init_app(app)

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(loans.bp)

    with app.app_context():
        init_db()
        from .db import verify_connection

        host, database = verify_connection()
        app.logger.info("MySQL ready: host=%s database=%s (users, loan_applications, repayments)", host, database)

    @app.cli.command("list-users")
    def list_users_command() -> None:
        from app.db import user_list_by_created_desc

        users = user_list_by_created_desc()
        if not users:
            click.echo("No users in this database.")
            return
        for u in users:
            click.echo(f"{u.id}\t{u.email}\t{u.role}")

    @app.cli.command("set-password")
    @click.argument("email")
    @click.option(
        "--password",
        "-p",
        default=None,
        help="New password. If omitted, you are prompted (safer on a shared screen).",
    )
    def set_password_command(email: str, password: str | None) -> None:
        from werkzeug.security import generate_password_hash

        from app.db import user_get_by_email, user_set_password_hash

        em = email.lower().strip()
        user = user_get_by_email(em)
        if user is None:
            click.echo(f"No user with email {em!r}. Run list-users to see accounts.", err=True)
            raise SystemExit(1)
        if not password:
            password = click.prompt("New password", hide_input=True, confirmation_prompt=True)
        user_set_password_hash(user.id, generate_password_hash(password))
        click.echo(f"Password updated for {em}.")

    return app
