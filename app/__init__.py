import click
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from .extensions import db, login_manager
from . import auth, loans, main


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(loans.bp)

    with app.app_context():
        db.create_all()

    @app.cli.command("list-users")
    def list_users_command() -> None:
        """Print users in the connected database (id, email, role)."""
        from .models import User

        users = User.query.order_by(User.id).all()
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
        """Set a user's password by email (e.g. Render Shell if cloud DB has no matching account)."""
        from .extensions import db
        from .models import User

        em = email.lower().strip()
        user = User.query.filter_by(email=em).first()
        if user is None:
            click.echo(f"No user with email {em!r}. Run list-users to see accounts.", err=True)
            raise SystemExit(1)
        if not password:
            password = click.prompt("New password", hide_input=True, confirmation_prompt=True)
        user.set_password(password)
        db.session.commit()
        click.echo(f"Password updated for {em}.")

    return app
