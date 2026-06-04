from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length

from .. import db
from ..decorators import admin_required
from ..i18n import tr
from ..models import NewsPost

bp = Blueprint("news", __name__)


class NewsForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(1, 200)])
    body = TextAreaField("Body", validators=[DataRequired()])
    submit = SubmitField("Publish")


@bp.route("/")
def index():
    posts = NewsPost.query.order_by(NewsPost.published_at.desc()).all()
    return render_template("news/index.html", posts=posts)


@bp.route("/<int:post_id>")
def detail(post_id: int):
    post = NewsPost.query.get_or_404(post_id)
    return render_template("news/detail.html", post=post)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_post():
    form = NewsForm()
    if form.validate_on_submit():
        post = NewsPost(
            title=form.title.data,
            body=form.body.data,
            author_id=current_user.id,
        )
        db.session.add(post)
        db.session.commit()
        flash(tr("news.announcement_published"), "success")
        return redirect(url_for("news.detail", post_id=post.id))
    return render_template("news/edit.html", form=form, post=None)
