from flask import Flask, render_template, redirect, request, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, join_room, leave_room
from pymongo.errors import DuplicateKeyError

from db import get_user, save_user, get_room, save_room, update_room, get_room_members, add_room_members, remove_room_members 
from db import get_rooms_for_user, is_room_member, save_messages, get_messages, get_room_admin

app = Flask(__name__)

app.secret_key = "chitchat"
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

socketio = SocketIO(app)


#home page
@app.route('/')
def home():
    rooms = []
    if current_user.is_authenticated:
        rooms = get_rooms_for_user(current_user.username)
    return render_template("index.html", rooms=rooms)


#login/logout/signup
@app.route('/login/', methods=['GET', 'POST'])
def login():

    if current_user.is_authenticated:
        return redirect(url_for('home')) 

    err_msg = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password_input = request.form.get('password')
        user = get_user(username)
        if user and user.check_password(password_input):
            login_user(user)
            return redirect(url_for('home'))
        else:
            err_msg = '!! Login failed, Enter valid username password !!'
    
    return render_template('login.html', err_msg = err_msg)

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/signup/",methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    msg_error = ''
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password_input = request.form.get('password')
        if not username or not email or not password_input:
            msg_error = '!! Enter all fields !!'
        else:
            try:
                save_user(username, email, password_input)
                user = get_user(username)
                login_user(user)
                return redirect(url_for('home'))
            except DuplicateKeyError:
                msg_error = '!!! Username taken try different username !!!'
    
    return render_template('signup.html',msg_error = msg_error)



#chatrooms
#create room
@app.route('/create-room/', methods =['GET','POST'])
@login_required
def create_room():
    message = ''
    if request.method == 'POST':
        room_name = request.form.get('room_name')
        usernames = [username.strip() for username in request.form.get('members').split(',')]

        if len(room_name) and len(usernames):
            room_id = save_room(room_name, current_user.username)
            if current_user.username in usernames:
                usernames.remove(current_user.username)
            add_room_members(room_id, room_name, usernames, current_user.username)
            return redirect(url_for('view_room', room_id=room_id))
        else:
            message = "Dont leave fields empty"
            return render_template('create_room.html', message=message)
    else:
        return render_template('create_room.html')


#view room
@app.route('/rooms/<room_id>/')
@login_required
def view_room(room_id):
    room = get_room(room_id)

    if room and is_room_member(room_id, current_user.username):
        room_members = get_room_members(room_id)
        messages = get_messages(room_id)
        admin = get_room_admin(room_id)
        return render_template('view_room.html', room=room, room_members=room_members, username=current_user.username, messages=messages, admin=admin)
    else:
        return "Room not found", 404


#edit room
@app.route('/rooms/<room_id>/edit/', methods = ['GET', 'POST'])
@login_required
def edit_room(room_id):
    room = get_room(room_id)
    if room and is_room_member(room_id, current_user.username):
        existing_room_members = [member['_id']['username'] for member in get_room_members(room_id)]
        room_members_str = ",".join(existing_room_members)

        if request.method == 'POST':
            room_name = request.form.get('room_name')
            room['name'] = room_name
            update_room(room_id,room_name)
            new_members = [username.strip() for username in request.form.get('members').split(',')]
            members_to_add = list(set(new_members) - set(existing_room_members))
            members_to_remove = list(set(existing_room_members) - set(new_members))

            if len(members_to_add):
                add_room_members(room_id, room_name, members_to_add, current_user.username)
            if len(members_to_remove):
                remove_room_members(room_id,members_to_remove)
            
            room_members_str = ",".join(new_members)
            return redirect(url_for('view_room', room_id=room_id))
        
        return render_template('edit_room.html', room=room, room_members_str=room_members_str)
    else:
        return "Room not found", 404



#Serverside socketio event handlers
@socketio.on('join_room')
def handle_join_room_event(data):
    app.logger.info("{} has joined the room {}".format(data['username'], data['roomid']))
    join_room(data['roomid'])


@socketio.on('send_message')
def handle_send_message_event(data):
    app.logger.info("{} sent message {} to room {}".format(data['username'],data['msg'], data['roomid']))
    save_messages(data['roomid'], data['msg'], data['username'])
    socketio.emit('receive_message', data)


@socketio.on('leave_room')
def handle_leave_room_event(data):
    app.logger.info("{} has left the room".format(data['username'], data['roomid']))
    leave_room(data['roomid'])


@login_manager.user_loader
def load_user(username):
    return get_user(username)




if __name__ == "__main__":
    socketio.run(app, debug=True)
