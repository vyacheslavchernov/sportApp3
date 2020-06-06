from datetime import datetime
from time import time
import re
import os
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
# from flask_login import UserMixin
from flask_security import UserMixin, RoleMixin
import jwt

from app import app, login, db

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

def slugify(string):
    pattern = r'[^\w+]'
    return re.sub(pattern, '-', string)

roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True)
    username = db.Column(db.String(64), index=True, unique=True)
    social_id = db.Column(db.String(64), unique=True)
    password = db.Column(db.String(255))
    confirmed_at = db.Column(db.DateTime)

    date = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    timestamp = db.Column(db.String(128), default=int(time()))
    city = db.Column(db.String(128))

    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean)

    mentor = db.Column(db.Boolean, default=False)
    level = db.Column(db.Integer, default=0)
    
    roles = db.relationship(
        'Role', secondary=roles_users, backref=db.backref('users_roles', lazy='dynamic'))

    # def set_password(self, password):
    #     self.password_hash = generate_password_hash(password)

    # def check_password(self, password):
    #     return check_password_hash(self.password_hash, password)

    def avatar(self):
        #avatar_url = os.path.join('user_data', self.username + self.timestamp, 'avatar\\avatar.png')
        #return avatar_url
        return 'user_data/{}/avatar/avatar.png'.format(self.username + self.timestamp)
 
#### FLASK SECURIT
class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    description = db.Column(db.String(255))
