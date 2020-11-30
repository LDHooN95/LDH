import os
import jwt
import bcrypt
import config

from flask import Flask, request, jsonify,current_app,Response,g
from flask_cors import CORS
from flask.json import JSONEncoder
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from functools import wraps

db={
        'user':'root',
        'password':'Mevius8791!@',
        'host':'localhost',
        'port':3306,
        'database':'miniter'
        }
db_url=f"mysql+mysqlconnector://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['database']}?charset=utf8"
JWT_SECRET_KEY='SOME_SUPER_SECRET_KEY'
class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return JSONEncoder.default(self, obj)

def login_required(f):
    @wraps(f)
    def decorated_function(*args,**kwargs):
        access_token=request.headers.get('Authorization')
        if access_token is not None:
            try:
                payload=jwt.decode(access_token,'JWT_SECRET_KEY','HS256')
            except jwt.InvalidTokenError:
                payload=None

            if payload is None: return Response(status=401)
            user_id=payload['user_id']
            g.user_id=user_id

            row=current_app.database.execute(text("""
            SELECT id,name,email,profile FROM users
            WHERE id=:user_id"""),{'user_id':user_id}).fetchone()

            g.user={
                    'id':row['id'],
                    'name':row['name'],
                    'email':row['email'],
                    'profile':row['profile']} if row else None
        else: 
            return Response(status=401)
        return f(*args,**kwargs)
    return decorated_function


def create_app(test_config=None):

    app=Flask(__name__,instance_relative_config=True)
   
    CORS(app)
    
    app.json_encoder=CustomJSONEncoder
    if test_config is None:
        app.config.from_pyfile("config.py",silent=True)
    else:
        app.config.update(test_config)
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db=create_engine(db_url, encoding='utf-8', max_overflow=0)
    app.database=db

    #return app

    @app.route("/ping",methods=['GET'])
    def ping():
        return "pong"
    @app.route("/sign-up",methods=['POST'])
    def sign_up():
        new_user=request.json
        new_user["password"]=bcrypt.hashpw(new_user["password"].encode('UTF-8'),bcrypt.gensalt())
        current_app.database.execute(text("""
        INSERT INTO users(id,name,email,profile,password)
        VALUES(:id,:name,:email,:profile,:password)"""),new_user)
        row=current_app.database.execute(text("""
        SELECT id,name,email,profile
        FROM users
        WHERE id=:user_id"""),{'user_id':new_user['id']}).fetchone()
        created_user={'id':row['id'],
                'name':row['name'],
                'email':row['email'],
                'profile':row['profile']} if row else None
        return jsonify(created_user)
    @app.route("/login",methods=["POST"])
    def login():
        credential=request.json
        r_id=credential['id']
        password=credential['password']
        row=current_app.database.execute(text("""
        SELECT id,password FROM users
        WHERE id=:id"""),{'id':r_id}).fetchone()
       # print(row)
       # print()
       # print(row['id'])
        if row and bcrypt.checkpw(password.encode('UTF-8'), row['password'].encode('UTF-8')):
            user_id=row['id']
            #print(user_id)
            payload={
                    'user_id':user_id,
                    'exp': datetime.utcnow() + timedelta(seconds =60*60*24)
            }
            token=jwt.encode(payload,'JWT_SECRET_KEY','HS256')
            #print(token)
            #print()
            #print(token.decode('UTF-8'))
            return jsonify({
                'access_token':token.decode('UTF-8'),
                'user_id':r_id
            })
        else:
            return 'login falied',401
    @app.route("/tweet",methods=['POST'])
    @login_required
    def tweet():
        user_tweet=request.json
        user_tweet['id']=g.user_id
        print(g.user_id)
        tweet=user_tweet["tweet"]
        if len(tweet)>300:
            return '300자를 초과하였습니다.',400
        if len(tweet)<=0:
            return '내용을 입력하세요.', 400
        app.database.execute(text("""
            INSERT INTO tweet(id,content) VALUES (:id,:tweet)"""),
            {'id':user_tweet['id'],'tweet':tweet})
        return '',200

    @app.route("/follow",methods=['POST'])
    @login_required
    def follow():
        user_follow=request.json
        user_follow['id']=g.user_id
        app.database.execute(text("""
        INSERT INTO follow_list(to_id,from_id) VALUES (:id,:follow)"""),
        {'id':user_follow['id'],'follow':user_follow['follow']})
        return '',200
            
    @app.route("/unfollow",methods=['POST'])
    @login_required
    def unfollow():
        user_unfollow=request.json
        user_unfollow['id']=g.user_id
        app.database.execute(text("""
            DELETE FROM follow_list WHERE to_id=:id and from_id=:unfollow""")
            ,{'id':user_unfollow['id'],'unfollow':user_unfollow['unfollow']})
        return '',200

    @app.route("/timeline",methods=['GET'])
    @login_required
    def timeline():
        user_id=g.user_id
        rows=app.database.execute(text("""
        SELECT id,content FROM tweet JOIN follow_list ON tweet.id=follow_list.from_id
        WHERE follow_list.to_id=:user_id"""),{'user_id':user_id}).fetchall()
        timeline=[{
            'user_id':row['id'],
            'timeline':row['content']
            }for row in rows]
        
        return jsonify({
            'user_id':g.user_id,
            'timeline':timeline
            })

    return app
