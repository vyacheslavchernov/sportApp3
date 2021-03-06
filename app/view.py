from datetime import datetime
from werkzeug.urls import url_parse
import os
import logging
from oauth import OAuthSignIn

from flask import render_template, flash, redirect, url_for, request
from flask import Blueprint

from flask_security import login_required, login_user, logout_user, current_user, url_for_security
from flask_security import SQLAlchemyUserDatastore
from flask_security import Security
from flask_security.utils import hash_password
from flask_security.registerable import register_user

from app.forms import *
from app import app
from app import db
from app import log

from app.models import *
from app.copydir import copydir
from app.security import user_datastore, security

import git


@app.before_first_request
def create_initial_users():
    initial_users_list = [
        {'name': 'admin', 'description': 'administrator', 'email': 'admin@admin.com', 'password': 'admin'},
        {'name': 'guest', 'description': 'guest', 'email': 'guest@guest.com', 'password': 'guest'},
        {'name': 'user', 'description': 'user', 'email': 'user@user.com', 'password': 'user'},
    ]
    def create_user(initial_users_list):
        for user in initial_users_list:
            if not user_datastore.get_user(user['email']):
                user_datastore.create_role(name=user['name'], description=user['description'])
                db.session.commit()
                role = Role.query.filter_by(name=user['name']).first()
                user_datastore.create_user(
                    email=user['email'], username=user['name'], password=hash_password(user['password']))
                user = User.query.filter_by(username=user['name']).first()
                user_datastore.add_role_to_user(user, role)
                db.session.commit()
    create_user(initial_users_list)

    for activity in ['jogging', 'workout', 'box', 'fitness']:
        if not Tag.query.filter(Tag.name==activity).first():
            tag = Tag(name=activity, slug=slugify(activity))
            db.session.add(tag)
            db.session.commit()

    for sportclub in ['testclub']:
        if not Club.query.filter(Club.name==sportclub).first():
            club = Club(name=sportclub, slug=slugify(sportclub))
            db.session.add(club)
            db.session.commit()

    for level in range(1, 11):
        if not Level.query.filter(Level.number==level).first():
            level = Level(number=level)
            db.session.add(level)
            db.session.commit()

    for theme in ['sport', 'charity', 'party']:
        if not Theme.query.filter(Theme.name==theme).first():
            theme = Theme(name=theme)
            db.session.add(theme)
            db.session.commit()

@app.before_request
def before_request():
    if request.path.startswith('/admin'):
        if current_user.is_authenticated:
            if not current_user.has_role("admin"):
                return redirect(url_for('security.logout'))
        else:
            return redirect(url_for('security.login'))

    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

    if current_user.is_authenticated and not user_datastore.find_user(email=current_user.email).roles:
        role = Role.query.filter_by(name='user').first()
        user = User.query.filter_by(username=current_user.username).first()
        user_datastore.add_role_to_user(user, role)
        db.session.commit()

@app.route('/update_server', methods=['POST'])
def webhook():
    if request.method == 'POST':
        repo = git.Repo('path/to/git_repo')
        origin = repo.remotes.origin
        origin.pull()
        return 'Updated PythonAnywhere successfully', 200
    else:
        return 'Wrong event type', 400

@app.route('/')
@app.route('/index')
@login_required
def index():
    events = Event.query.all() # 37.62, 55.75
    user = User.query.filter_by(username=current_user.username).first_or_404()
    
    user_dir = user.username + user.timestamp
    user_folders = os.path.join('app', 'static', 'user_data', user_dir)
    if not os.path.isdir(user_folders):
        log.info("User '%s' register." % (user.username)) 
        os.mkdir(user_folders)
        os.mkdir(os.path.join(user_folders, 'photos'))
        os.mkdir(os.path.join(user_folders, 'tracking_data'))
        copydir(os.path.join('app', 'static', 'user_data', 'avatar'), user_folders)

    remote_addr = request.remote_addr or 'untrackable'
    old_current_login, new_current_login = user.current_login_at, datetime.utcnow()
    old_current_ip, new_current_ip = user.current_login_ip, remote_addr
    user.last_login_at = old_current_login or new_current_login
    user.current_login_at = new_current_login
    user.last_login_ip = old_current_ip or new_current_ip
    user.current_login_ip = new_current_ip
    user.login_count = user.login_count + 1 if user.login_count else 1
    db.session.commit()
    log.info("User '%s' login with ip '%s'." % (user.username, user.current_login_ip)) 
    return render_template('index.html', user=user, events=events)

@app.route('/explore')
@login_required
def explore():
    user = User.query.filter_by(username=current_user.username).first_or_404()
    return render_template('explore.html', user=user)

@app.route('/filter')
@login_required
def filter():
    user = User.query.filter_by(username=current_user.username).first_or_404()
    return render_template('filter.html', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    geocode = 37.62#, 55.75
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ExtendedLoginForm()
    if form.validate_on_submit():
        user = User(username='guest', email='guest@guest.com', password='guest')
        form = ExtendedLoginForm(formdata=request.form, obj=user)
        login_user(user)
        log.info("User '%s' login." % (user.username)) 
        return redirect(url_for('index'), geocode=geocode)

@app.route('/authorize/<provider>')
def oauth_authorize(provider):
    if not current_user.is_anonymous:
        return redirect(url_for('index'))
    try:
        oauth = OAuthSignIn.get_provider(provider)
        return oauth.authorize()
    except:
        return redirect(url_for_security('login'))

@app.route('/callback/<provider>')
def oauth_callback(provider):
    if not current_user.is_anonymous:
        return redirect(url_for('index'))
    oauth = OAuthSignIn.get_provider(provider)
    social_id, username, email = oauth.callback()
    if social_id is None:
        flash('Authentication failed.')
        return redirect(url_for('index'))
    user = User.query.filter_by(social_id=social_id).first()
    if not user:
        user_datastore.create_user(social_id=social_id, username=username, email=email)
        user = User.query.filter_by(social_id=social_id).first()
        db.session.commit()
    login_user(user, True)
    return redirect(url_for('index'))
