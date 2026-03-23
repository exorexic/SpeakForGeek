from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from datetime import datetime, timedelta
import sqlite3
import hashlib
import os
import uuid

app = Flask(__name__)
app.secret_key = 'speakforgeek_secret_key_2024'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Создаём папку для аватаров и фото
os.makedirs('static/avatars', exist_ok=True)
os.makedirs('static/posts', exist_ok=True)

def init_db():
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  avatar TEXT,
                  bio TEXT,
                  created TIMESTAMP,
                  last_post TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS posts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  content TEXT,
                  image TEXT,
                  created TIMESTAMP,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS follows
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  follower_id INTEGER,
                  following_id INTEGER,
                  FOREIGN KEY(follower_id) REFERENCES users(id),
                  FOREIGN KEY(following_id) REFERENCES users(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS likes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  post_id INTEGER,
                  user_id INTEGER,
                  FOREIGN KEY(post_id) REFERENCES posts(id),
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS comments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  post_id INTEGER,
                  user_id INTEGER,
                  content TEXT,
                  created TIMESTAMP,
                  FOREIGN KEY(post_id) REFERENCES posts(id),
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  from_user INTEGER,
                  to_user INTEGER,
                  content TEXT,
                  created TIMESTAMP,
                  is_read INTEGER DEFAULT 0,
                  FOREIGN KEY(from_user) REFERENCES users(id),
                  FOREIGN KEY(to_user) REFERENCES users(id))''')
    
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user(user_id):
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("SELECT id, username, avatar, bio, last_post FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def can_post_today(user_id):
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("SELECT last_post FROM users WHERE id = ?", (user_id,))
    last = c.fetchone()
    conn.close()
    if not last or not last[0]:
        return True
    last_post = datetime.strptime(last[0], '%Y-%m-%d %H:%M:%S')
    return datetime.now() - last_post >= timedelta(days=1)

def update_last_post(user_id):
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("UPDATE users SET last_post = ? WHERE id = ?", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
    conn.commit()
    conn.close()

def save_image(file, folder, prefix):
    ext = file.filename.split('.')[-1]
    filename = f"{prefix}_{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(folder, filename))
    return filename

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=yes">
    <title>Speak For Geek</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: #0a0c10;
            color: #e0e0e0;
            padding-bottom: 70px;
        }
        
        /* Header */
        .header {
            background: #111214;
            padding: 12px 16px;
            border-bottom: 1px solid #1e1f22;
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 { font-size: 20px; }
        .header h1 span { color: #5865f2; }
        
        /* Bottom Nav */
        .bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #111214;
            display: flex;
            justify-content: space-around;
            padding: 8px 12px;
            border-top: 1px solid #1e1f22;
            z-index: 100;
        }
        
        .nav-btn {
            background: none;
            border: none;
            color: #949ba4;
            font-size: 24px;
            padding: 8px;
            cursor: pointer;
            border-radius: 12px;
        }
        
        .nav-btn.active { color: #5865f2; background: #1e1f22; }
        
        /* Content */
        .content {
            max-width: 600px;
            margin: 0 auto;
            padding: 16px;
        }
        
        /* Post Form */
        .post-form {
            background: #111214;
            border-radius: 16px;
            padding: 12px;
            margin-bottom: 16px;
            border: 1px solid #1e1f22;
        }
        
        .post-form textarea {
            width: 100%;
            padding: 12px;
            background: #1e1f22;
            border: none;
            border-radius: 12px;
            color: #e0e0e0;
            font-size: 15px;
            resize: vertical;
            font-family: inherit;
        }
        
        .post-form input[type="file"] {
            margin: 8px 0;
            color: #949ba4;
        }
        
        .post-form button {
            background: #5865f2;
            border: none;
            padding: 10px 20px;
            border-radius: 24px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            margin-top: 8px;
        }
        
        /* Post Card */
        .post-card {
            background: #111214;
            border: 1px solid #1e1f22;
            border-radius: 20px;
            padding: 12px;
            margin-bottom: 12px;
        }
        
        .post-header {
            display: flex;
            gap: 12px;
            margin-bottom: 12px;
            cursor: pointer;
        }
        
        .avatar {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            object-fit: cover;
            background: #2b2d31;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
        }
        
        .post-author { font-weight: 600; }
        .post-time { font-size: 11px; color: #949ba4; }
        
        .post-content { margin: 8px 0; line-height: 1.4; }
        .post-image {
            max-width: 100%;
            border-radius: 16px;
            margin: 8px 0;
        }
        
        .post-actions {
            display: flex;
            gap: 16px;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #1e1f22;
        }
        
        .action-btn {
            background: none;
            border: none;
            color: #949ba4;
            cursor: pointer;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .action-btn:hover, .action-btn:active { background: #1e1f22; }
        .action-btn.liked { color: #5865f2; }
        
        /* Comments */
        .comments-section {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #1e1f22;
        }
        
        .comment {
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
        }
        
        .comment-avatar {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #2b2d31;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
        }
        
        .comment-content {
            background: #1e1f22;
            padding: 8px 12px;
            border-radius: 16px;
            flex: 1;
        }
        
        .comment-author { font-weight: 600; font-size: 13px; }
        .comment-text { font-size: 13px; }
        
        .comment-form {
            display: flex;
            gap: 8px;
            margin-top: 8px;
        }
        
        .comment-form input {
            flex: 1;
            padding: 8px 12px;
            background: #1e1f22;
            border: none;
            border-radius: 20px;
            color: #e0e0e0;
        }
        
        .comment-form button {
            background: #5865f2;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            color: white;
        }
        
        /* User Card */
        .user-card {
            background: #111214;
            border: 1px solid #1e1f22;
            border-radius: 20px;
            padding: 16px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .user-info {
            display: flex;
            gap: 12px;
            align-items: center;
            cursor: pointer;
        }
        
        .follow-btn {
            background: #5865f2;
            border: none;
            padding: 8px 20px;
            border-radius: 24px;
            color: white;
            cursor: pointer;
        }
        
        .follow-btn.following { background: #1e1f22; color: #e0e0e0; }
        
        /* Profile */
        .profile-header {
            text-align: center;
            padding: 20px;
            background: #111214;
            border-radius: 20px;
            margin-bottom: 16px;
        }
        
        .profile-avatar {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            object-fit: cover;
            margin: 0 auto 12px;
            background: #2b2d31;
        }
        
        /* Auth */
        .auth-container {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .auth-card {
            background: #111214;
            border-radius: 32px;
            padding: 32px;
            width: 100%;
            max-width: 400px;
        }
        
        .auth-card input {
            width: 100%;
            padding: 14px;
            margin: 8px 0;
            background: #1e1f22;
            border: none;
            border-radius: 16px;
            color: #e0e0e0;
            font-size: 16px;
        }
        
        .auth-card button {
            width: 100%;
            padding: 14px;
            background: #5865f2;
            border: none;
            border-radius: 28px;
            color: white;
            margin-top: 16px;
            font-weight: 600;
            cursor: pointer;
        }
        
        .switch-auth {
            text-align: center;
            margin-top: 20px;
            color: #5865f2;
            cursor: pointer;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #949ba4;
        }
        
        .edit-btn {
            background: #1e1f22;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            color: #e0e0e0;
            margin-top: 12px;
            cursor: pointer;
        }
        
        .modal {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        
        .modal-content {
            background: #111214;
            border-radius: 24px;
            padding: 20px;
            width: 90%;
            max-width: 350px;
        }
        
        .modal-content input, .modal-content textarea {
            width: 100%;
            padding: 12px;
            margin: 8px 0;
            background: #1e1f22;
            border: none;
            border-radius: 12px;
            color: #e0e0e0;
        }
        
        @media (max-width: 480px) {
            .content { padding: 12px; }
            .post-card { border-radius: 16px; }
        }
    </style>
</head>
<body>
    {% if session.user_id %}
    <div class="header">
        <h1>🎧 Speak For <span>Geek</span></h1>
        <div style="display: flex; gap: 8px;">
            <button class="nav-btn" onclick="showEditProfile()" style="font-size: 18px;">✏️</button>
            <button class="nav-btn" onclick="window.location.href='/logout'" style="font-size: 18px;">🚪</button>
        </div>
    </div>
    
    <div class="content" id="content-area">
        <div style="text-align: center; padding: 40px;">Загрузка...</div>
    </div>
    
    <div class="bottom-nav">
        <button class="nav-btn" id="nav-feed" onclick="loadFeed()">🏠</button>
        <button class="nav-btn" id="nav-search" onclick="loadSearch()">🔍</button>
        <button class="nav-btn" id="nav-friends" onclick="loadFriends()">👥</button>
        <button class="nav-btn" id="nav-messages" onclick="loadMessages()">💬</button>
        <button class="nav-btn" id="nav-profile" onclick="loadProfile()">👤</button>
    </div>
    
    <div id="modal" style="display: none;"></div>
    
    <script>
        let currentView = 'feed';
        let currentChatUser = null;
        
        function showModal(content) {
            document.getElementById('modal').innerHTML = `<div class="modal"><div class="modal-content">${content}</div></div>`;
            document.getElementById('modal').style.display = 'flex';
        }
        
        function closeModal() {
            document.getElementById('modal').style.display = 'none';
        }
        
        function showEditProfile() {
            showModal(`
                <h3 style="margin-bottom: 16px;">Редактировать профиль</h3>
                <input type="text" id="edit-bio" placeholder="О себе">
                <input type="file" id="edit-avatar" accept="image/*">
                <button onclick="saveProfile()">Сохранить</button>
                <button onclick="closeModal()" style="background: #1e1f22; margin-top: 8px;">Отмена</button>
            `);
        }
        
        function saveProfile() {
            const bio = document.getElementById('edit-bio').value;
            const file = document.getElementById('edit-avatar').files[0];
            
            const formData = new FormData();
            if (bio) formData.append('bio', bio);
            if (file) formData.append('avatar', file);
            
            fetch('/api/update_profile', { method: 'POST', body: formData })
                .then(() => { closeModal(); loadProfile(); });
        }
        
        function loadFeed() {
            currentView = 'feed';
            document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('nav-feed').classList.add('active');
            
            fetch('/api/feed')
                .then(r => r.json())
                .then(data => {
                    let html = `
                        <div class="post-form">
                            <textarea id="post-content" rows="3" placeholder="Что нового? (1 пост в день)"></textarea>
                            <input type="file" id="post-image" accept="image/*">
                            <button onclick="createPost()">📤 Опубликовать</button>
                        </div>
                    `;
                    
                    if (data.posts.length === 0) {
                        html += '<div class="empty-state">📭 Нет постов. Напишите первый!</div>';
                    }
                    
                    data.posts.forEach(post => {
                        html += `
                            <div class="post-card">
                                <div class="post-header" onclick="viewUser(${post.user_id})">
                                    <img class="avatar" src="/static/avatars/${post.avatar}" onerror="this.src=''; this.innerText='👤'" style="object-fit: cover;">
                                    <div>
                                        <div class="post-author">${escapeHtml(post.username)}</div>
                                        <div class="post-time">${post.created}</div>
                                    </div>
                                </div>
                                <div class="post-content">${escapeHtml(post.content)}</div>
                                ${post.image ? `<img class="post-image" src="/static/posts/${post.image}">` : ''}
                                <div class="post-actions">
                                    <button class="action-btn ${post.liked ? 'liked' : ''}" onclick="likePost(${post.id})">
                                        👍 <span class="like-count-${post.id}">${post.like_count}</span>
                                    </button>
                                    <button class="action-btn" onclick="toggleComments(${post.id})">
                                        💬 <span class="comment-count-${post.id}">${post.comment_count}</span>
                                    </button>
                                </div>
                                <div class="comments-section" id="comments-${post.id}" style="display: none;">
                                    <div id="comments-list-${post.id}"></div>
                                    <div class="comment-form">
                                        <input type="text" id="comment-input-${post.id}" placeholder="Написать комментарий...">
                                        <button onclick="addComment(${post.id})">→</button>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    document.getElementById('content-area').innerHTML = html;
                    
                    data.posts.forEach(post => {
                        if (post.comments) loadComments(post.id, post.comments);
                    });
                });
        }
        
        function loadComments(postId, comments) {
            let html = '';
            comments.forEach(c => {
                html += `
                    <div class="comment">
                        <div class="comment-avatar">${c.avatar || '👤'}</div>
                        <div class="comment-content">
                            <span class="comment-author">${escapeHtml(c.username)}</span>
                            <div class="comment-text">${escapeHtml(c.content)}</div>
                        </div>
                    </div>
                `;
            });
            const container = document.getElementById(`comments-list-${postId}`);
            if (container) container.innerHTML = html;
        }
        
        function toggleComments(postId) {
            const el = document.getElementById(`comments-${postId}`);
            if (el.style.display === 'none') {
                el.style.display = 'block';
                fetch(`/api/comments/${postId}`).then(r => r.json()).then(data => {
                    loadComments(postId, data.comments);
                });
            } else {
                el.style.display = 'none';
            }
        }
        
        function addComment(postId) {
            const input = document.getElementById(`comment-input-${postId}`);
            const content = input.value.trim();
            if (!content) return;
            
            fetch('/api/comment', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({post_id: postId, content})
            }).then(() => {
                input.value = '';
                loadFeed();
            });
        }
        
        function createPost() {
            const content = document.getElementById('post-content').value;
            const file = document.getElementById('post-image').files[0];
            
            const formData = new FormData();
            if (content) formData.append('content', content);
            if (file) formData.append('image', file);
            
            fetch('/api/post', { method: 'POST', body: formData })
                .then(r => r.json())
                .then(data => {
                    if (data.error) alert(data.error);
                    else loadFeed();
                });
        }
        
        function likePost(postId) {
            fetch('/api/like/' + postId, {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    const span = document.querySelector(`.like-count-${postId}`);
                    if (span) span.textContent = data.like_count;
                    const btn = document.querySelector(`[onclick="likePost(${postId})"]`);
                    if (data.liked) btn.classList.add('liked');
                    else btn.classList.remove('liked');
                });
        }
        
        function loadSearch() {
            currentView = 'search';
            document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('nav-search').classList.add('active');
            
            document.getElementById('content-area').innerHTML = `
                <div class="post-form">
                    <input type="text" id="search-query" placeholder="Введите юзернейм..." style="width: 100%; padding: 12px; background: #1e1f22; border: none; border-radius: 12px; color: white;">
                    <button onclick="searchUsers()" style="margin-top: 8px;">🔍 Найти</button>
                </div>
                <div id="search-results"></div>
            `;
        }
        
        function searchUsers() {
            const query = document.getElementById('search-query').value;
            if (!query) return;
            
            fetch(`/api/search?q=${encodeURIComponent(query)}`)
                .then(r => r.json())
                .then(data => {
                    let html = '';
                    data.users.forEach(user => {
                        html += `
                            <div class="user-card">
                                <div class="user-info" onclick="viewUser(${user.id})">
                                    <img class="avatar" src="/static/avatars/${user.avatar}" onerror="this.src=''; this.innerText='👤'" style="width: 44px; height: 44px;">
                                    <div><strong>@${escapeHtml(user.username)}</strong><div style="font-size: 12px; color: #949ba4;">${escapeHtml(user.bio || '')}</div></div>
                                </div>
                                ${user.id != {{ session.user_id }} ? `
                                    <button class="follow-btn ${user.is_following ? 'following' : ''}" onclick="toggleFollow(${user.id}, this)">
                                        ${user.is_following ? '✓ Подписан' : '+ Подписаться'}
                                    </button>
                                ` : ''}
                            </div>
                        `;
                    });
                    if (data.users.length === 0) html = '<div class="empty-state">👻 Не найдено</div>';
                    document.getElementById('search-results').innerHTML = html;
                });
        }
        
        function loadFriends() {
            currentView = 'friends';
            document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('nav-friends').classList.add('active');
            
            fetch('/api/friends')
                .then(r => r.json())
                .then(data => {
                    let html = `<div style="display: flex; gap: 16px; margin-bottom: 20px;"><div style="flex:1; text-align: center; background: #111214; padding: 12px; border-radius: 16px;"><div style="font-size: 24px; font-weight: bold;">${data.following_count}</div><div>Подписок</div></div><div style="flex:1; text-align: center; background: #111214; padding: 12px; border-radius: 16px;"><div style="font-size: 24px; font-weight: bold;">${data.followers_count}</div><div>Подписчиков</div></div></div>`;
                    
                    if (data.following.length) {
                        html += '<h3 style="margin: 16px 0 8px;">📌 Мои подписки</h3>';
                        data.following.forEach(u => {
                            html += `
                                <div class="user-card">
                                    <div class="user-info" onclick="viewUser(${u.id})">
                                        <img class="avatar" src="/static/avatars/${u.avatar}" onerror="this.src=''; this.innerText='👤'" style="width: 44px; height: 44px;">
                                        <div><strong>@${escapeHtml(u.username)}</strong></div>
                                    </div>
                                    <button class="follow-btn following" onclick="toggleFollow(${u.id}, this)">Отписаться</button>
                                </div>
                            `;
                        });
                    }
                    
                    if (data.followers.length) {
                        html += '<h3 style="margin: 16px 0 8px;">👥 Подписчики</h3>';
                        data.followers.forEach(u => {
                            html += `
                                <div class="user-card">
                                    <div class="user-info" onclick="viewUser(${u.id})">
                                        <img class="avatar" src="/static/avatars/${u.avatar}" onerror="this.src=''; this.innerText='👤'" style="width: 44px; height: 44px;">
                                        <div><strong>@${escapeHtml(u.username)}</strong></div>
                                    </div>
                                </div>
                            `;
                        });
                    }
                    
                    if (!data.following.length && !data.followers.length) html += '<div class="empty-state">👋 У вас пока нет друзей. Найдите кого-нибудь через поиск!</div>';
                    document.getElementById('content-area').innerHTML = html;
                });
        }
        
        function loadMessages() {
            currentView = 'messages';
            document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('nav-messages').classList.add('active');
            
            fetch('/api/messages')
                .then(r => r.json())
                .then(data => {
                    if (data.conversations.length === 0) {
                        document.getElementById('content-area').innerHTML = '<div class="empty-state">💬 Нет сообщений. Найдите друга и напишите ему!</div>';
                        return;
                    }
                    let html = '';
                    data.conversations.forEach(conv => {
                        html += `
                            <div class="user-card" onclick="openChat(${conv.user_id})">
                                <div class="user-info">
                                    <img class="avatar" src="/static/avatars/${conv.avatar}" onerror="this.src=''; this.innerText='👤'" style="width: 44px; height: 44px;">
                                    <div><strong>@${escapeHtml(conv.username)}</strong><div style="font-size: 12px; color: #949ba4;">${escapeHtml(conv.last_message || 'Нажми чтобы написать')}</div></div>
                                </div>
                            </div>
                        `;
                    });
                    document.getElementById('content-area').innerHTML = html;
                });
        }
        
        function openChat(userId) {
            currentChatUser = userId;
            document.getElementById('content-area').innerHTML = '<div style="text-align: center; padding: 40px;">Загрузка...</div>';
            
            fetch(`/api/chat/${userId}`)
                .then(r => r.json())
                .then(data => {
                    let html = '<div id="chat-messages" style="margin-bottom: 16px;">';
                    data.messages.forEach(msg => {
                        html += `
                            <div style="margin-bottom: 12px; ${msg.from_user == {{ session.user_id }} ? 'text-align: right;' : ''}">
                                <div style="display: inline-block; background: ${msg.from_user == {{ session.user_id }} ? '#5865f2' : '#1e1f22'}; padding: 10px 14px; border-radius: 20px; max-width: 80%;">
                                    <div style="font-size: 11px; color: #949ba4;">${msg.from_username}</div>
                                    <div>${escapeHtml(msg.content)}</div>
                                    <div style="font-size: 10px; color: #949ba4; margin-top: 4px;">${msg.time}</div>
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                    html += `
                        <div class="post-form">
                            <textarea id="message-content" rows="2" placeholder="Написать сообщение..."></textarea>
                            <button onclick="sendMessage()">📤 Отправить</button>
                            <button onclick="loadMessages()" style="background: #1e1f22; margin-left: 8px;">← Назад</button>
                        </div>
                    `;
                    document.getElementById('content-area').innerHTML = html;
                    const msgsDiv = document.getElementById('chat-messages');
                    if (msgsDiv) msgsDiv.scrollTop = msgsDiv.scrollHeight;
                });
        }
        
        function sendMessage() {
            const content = document.getElementById('message-content').value;
            if (!content.trim() || !currentChatUser) return;
            
            fetch('/api/send_message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({to_user: currentChatUser, content})
            }).then(() => {
                openChat(currentChatUser);
            });
        }
        
        function loadProfile() {
            currentView = 'profile';
            document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('nav-profile').classList.add('active');
            
            fetch('/api/profile')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('content-area').innerHTML = `
                        <div class="profile-header">
                            <img class="profile-avatar" src="/static/avatars/${data.avatar}" onerror="this.src=''; this.innerText='👤'" style="object-fit: cover;">
                            <h2>@${escapeHtml(data.username)}</h2>
                            <p style="color: #949ba4;">${escapeHtml(data.bio) || 'Нет описания'}</p>
                            <div style="display: flex; gap: 16px; justify-content: center; margin: 16px 0;">
                                <div><strong>${data.posts_count}</strong> постов</div>
                                <div><strong>${data.following_count}</strong> подписок</div>
                                <div><strong>${data.followers_count}</strong> подписчиков</div>
                            </div>
                            <button class="edit-btn" onclick="showEditProfile()">✏️ Редактировать профиль</button>
                        </div>
                        <h3 style="margin: 16px 0 8px;">📝 Мои посты</h3>
                    `;
                    if (data.posts.length === 0) {
                        document.getElementById('content-area').innerHTML += '<div class="empty-state">📭 У вас пока нет постов</div>';
                    }
                    data.posts.forEach(post => {
                        document.getElementById('content-area').innerHTML += `
                            <div class="post-card">
                                <div class="post-content">${escapeHtml(post.content)}</div>
                                ${post.image ? `<img class="post-image" src="/static/posts/${post.image}">` : ''}
                                <div class="post-time">${post.created}</div>
                                <div class="post-actions"><button class="action-btn">👍 ${post.likes}</button></div>
                            </div>
                        `;
                    });
                });
        }
        
        function viewUser(userId) {
            fetch(`/api/user/${userId}`)
                .then(r => r.json())
                .then(data => {
                    let html = `
                        <div class="profile-header">
                            <img class="profile-avatar" src="/static/avatars/${data.avatar}" onerror="this.src=''; this.innerText='👤'">
                            <h2>@${escapeHtml(data.username)}</h2>
                            <p style="color: #949ba4;">${escapeHtml(data.bio) || 'Нет описания'}</p>
                            <div style="display: flex; gap: 16px; justify-content: center; margin: 16px 0;">
                                <div><strong>${data.posts_count}</strong> постов</div>
                                <div><strong>${data.following_count}</strong> подписок</div>
                                <div><strong>${data.followers_count}</strong> подписчиков</div>
                            </div>
                            ${data.id != {{ session.user_id }} ? `
                                <div style="display: flex; gap: 8px; justify-content: center;">
                                    <button class="follow-btn ${data.is_following ? 'following' : ''}" onclick="toggleFollow(${data.id}, this)">
                                        ${data.is_following ? '✓ Подписан' : '+ Подписаться'}
                                    </button>
                                    <button class="follow-btn" onclick="openChat(${data.id})" style="background: #1e1f22;">💬 Написать</button>
                                </div>
                            ` : ''}
                        </div>
                        <h3 style="margin: 16px 0 8px;">📝 Посты</h3>
                    `;
                    if (data.posts.length === 0) html += '<div class="empty-state">📭 Нет постов</div>';
                    data.posts.forEach(post => {
                        html += `
                            <div class="post-card">
                                <div class="post-content">${escapeHtml(post.content)}</div>
                                ${post.image ? `<img class="post-image" src="/static/posts/${post.image}">` : ''}
                                <div class="post-time">${post.created}</div>
                                <div class="post-actions"><button class="action-btn">👍 ${post.likes}</button></div>
                            </div>
                        `;
                    });
                    document.getElementById('content-area').innerHTML = html;
                });
        }
        
        function toggleFollow(userId, btn) {
            fetch('/api/follow/' + userId, {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    if (data.following) {
                        btn.textContent = '✓ Подписан';
                        btn.classList.add('following');
                    } else {
                        btn.textContent = '+ Подписаться';
                        btn.classList.remove('following');
                    }
                    if (currentView === 'friends') loadFriends();
                    if (currentView === 'profile') loadProfile();
                });
        }
        
        function escapeHtml(text) {
            if (!text) return '';
            return text.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        }
        
        loadFeed();
    </script>
    {% else %}
    <div class="auth-container">
        <div class="auth-card">
            <h1 style="margin-bottom: 24px; text-align: center;">🎧 Speak For <span style="color: #5865f2;">Geek</span></h1>
            <div id="login-form">
                <input type="text" id="login-username" placeholder="Юзернейм">
                <input type="password" id="login-password" placeholder="Пароль">
                <button onclick="login()">Войти</button>
                <div class="switch-auth" onclick="showRegister()">Нет аккаунта? Зарегистрироваться</div>
            </div>
            <div id="register-form" style="display: none;">
                <input type="text" id="reg-username" placeholder="Юзернейм (латиница)">
                <input type="password" id="reg-password" placeholder="Пароль">
                <button onclick="register()">Зарегистрироваться</button>
                <div class="switch-auth" onclick="showLogin()">Уже есть аккаунт? Войти</div>
            </div>
        </div>
    </div>
    <script>
        function login() {
            fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    username: document.getElementById('login-username').value,
                    password: document.getElementById('login-password').value
                })
            }).then(r => r.json()).then(data => {
                if (data.success) location.reload();
                else alert('Неверный логин или пароль');
            });
        }
        
        function register() {
            const username = document.getElementById('reg-username').value;
            if (!/^[a-zA-Z0-9_]+$/.test(username)) {
                alert('Юзернейм может содержать только буквы, цифры и _');
                return;
            }
            fetch('/api/register', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    username: username,
                    password: document.getElementById('reg-password').value
                })
            }).then(r => r.json()).then(data => {
                if (data.success) location.reload();
                else alert('Пользователь уже существует');
            });
        }
        
        function showRegister() {
            document.getElementById('login-form').style.display = 'none';
            document.getElementById('register-form').style.display = 'block';
        }
        
        function showLogin() {
            document.getElementById('register-form').style.display = 'none';
            document.getElementById('login-form').style.display = 'block';
        }
    </script>
    {% endif %}
</body>
</html>
'''

# ========== API МАРШРУТЫ ==========
@app.route('/')
def index():
    if 'user_id' in session:
        return render_template_string(TEMPLATE, session=session)
    return render_template_string(TEMPLATE, session={})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = hash_password(data.get('password'))
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['username'] = user[1]
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    username = data.get('username')
    password = hash_password(data.get('password'))
    
    try:
        conn = sqlite3.connect('speakforgeek.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, avatar, bio, created) VALUES (?, ?, ?, ?, ?)",
                  (username, password, 'default.png', '', datetime.now()))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        
        session['user_id'] = user_id
        session['username'] = username
        return jsonify({'success': True})
    except:
        return jsonify({'success': False})

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'unauthorized'})
    
    bio = request.form.get('bio', '')
    avatar = request.files.get('avatar')
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    
    if avatar:
        filename = save_image(avatar, 'static/avatars', 'avatar')
        c.execute("UPDATE users SET avatar = ?, bio = ? WHERE id = ?", (filename, bio, session['user_id']))
    else:
        c.execute("UPDATE users SET bio = ? WHERE id = ?", (bio, session['user_id']))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/feed')
def api_feed():
    if 'user_id' not in session:
        return jsonify({'posts': []})
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute('''SELECT posts.id, posts.user_id, posts.content, posts.image, posts.created, 
                 users.username, users.avatar,
                 (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) as like_count,
                 (SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.id) as comment_count,
                 (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id AND likes.user_id = ?) as user_liked
                 FROM posts 
                 JOIN users ON posts.user_id = users.id
                 ORDER BY posts.created DESC''', (session['user_id'],))
    posts = c.fetchall()
    
    result = []
    for p in posts:
        c.execute('''SELECT comments.id, comments.content, comments.created, users.username, users.avatar
                     FROM comments JOIN users ON comments.user_id = users.id
                     WHERE comments.post_id = ? ORDER BY comments.created ASC''', (p[0],))
        comments = c.fetchall()
        
        result.append({
            'id': p[0],
            'user_id': p[1],
            'content': p[2] or '',
            'image': p[3],
            'created': p[4][:16] if p[4] else '',
            'username': p[5],
            'avatar': p[6] or 'default.png',
            'like_count': p[7],
            'comment_count': p[8],
            'liked': p[9] > 0,
            'comments': [{'id': c[0], 'content': c[1], 'time': c[2][:16] if c[2] else '', 'username': c[3], 'avatar': c[4] or 'default.png'} for c in comments]
        })
    conn.close()
    return jsonify({'posts': result})

@app.route('/api/post', methods=['POST'])
def api_post():
    if 'user_id' not in session:
        return jsonify({'error': 'unauthorized'})
    
    if not can_post_today(session['user_id']):
        return jsonify({'error': 'Можно публиковать только 1 пост в день!'})
    
    content = request.form.get('content', '')
    image = request.files.get('image')
    
    image_filename = None
    if image:
        image_filename = save_image(image, 'static/posts', 'post')
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("INSERT INTO posts (user_id, content, image, created) VALUES (?, ?, ?, ?)",
              (session['user_id'], content, image_filename, datetime.now()))
    conn.commit()
    update_last_post(session['user_id'])
    conn.close()
    return jsonify({'success': True})

@app.route('/api/like/<int:post_id>', methods=['POST'])
def api_like(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False})
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("SELECT * FROM likes WHERE post_id = ? AND user_id = ?", (post_id, session['user_id']))
    existing = c.fetchone()
    
    if existing:
        c.execute("DELETE FROM likes WHERE post_id = ? AND user_id = ?", (post_id, session['user_id']))
        liked = False
    else:
        c.execute("INSERT INTO likes (post_id, user_id) VALUES (?, ?)", (post_id, session['user_id']))
        liked = True
    
    conn.commit()
    c.execute("SELECT COUNT(*) FROM likes WHERE post_id = ?", (post_id,))
    like_count = c.fetchone()[0]
    conn.close()
    return jsonify({'success': True, 'liked': liked, 'like_count': like_count})

@app.route('/api/comment', methods=['POST'])
def api_comment():
    if 'user_id' not in session:
        return jsonify({'error': 'unauthorized'})
    
    data = request.json
    post_id = data.get('post_id')
    content = data.get('content')
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("INSERT INTO comments (post_id, user_id, content, created) VALUES (?, ?, ?, ?)",
              (post_id, session['user_id'], content, datetime.now()))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/comments/<int:post_id>')
def api_comments(post_id):
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute('''SELECT comments.id, comments.content, comments.created, users.username, users.avatar
                 FROM comments JOIN users ON comments.user_id = users.id
                 WHERE comments.post_id = ? ORDER BY comments.created ASC''', (post_id,))
    comments = c.fetchall()
    conn.close()
    return jsonify({'comments': [{'id': c[0], 'content': c[1], 'time': c[2][:16] if c[2] else '', 'username': c[3], 'avatar': c[4] or 'default.png'} for c in comments]})

@app.route('/api/profile')
def api_profile():
    if 'user_id' not in session:
        return jsonify({})
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("SELECT username, avatar, bio FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    c.execute("SELECT id, content, image, created, (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) as likes FROM posts WHERE user_id = ? ORDER BY created DESC", (session['user_id'],))
    posts = c.fetchall()
    following, followers = get_following_count(session['user_id'])
    conn.close()
    
    return jsonify({
        'username': user[0] if user else '',
        'avatar': user[1] if user else 'default.png',
        'bio': user[2] if user else '',
        'posts_count': len(posts),
        'following_count': following,
        'followers_count': followers,
        'posts': [{'id': p[0], 'content': p[1] or '', 'image': p[2], 'created': p[3][:16] if p[3] else '', 'likes': p[4]} for p in posts]
    })

@app.route('/api/user/<int:user_id>')
def api_user(user_id):
    if 'user_id' not in session:
        return jsonify({})
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("SELECT id, username, avatar, bio FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({})
    
    c.execute("SELECT id, content, image, created, (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) as likes FROM posts WHERE user_id = ? ORDER BY created DESC", (user_id,))
    posts = c.fetchall()
    following, followers = get_following_count(user_id)
    is_following_bool = is_following(session['user_id'], user_id)
    conn.close()
    
    return jsonify({
        'id': user[0],
        'username': user[1],
        'avatar': user[2] or 'default.png',
        'bio': user[3] or '',
        'posts_count': len(posts),
        'following_count': following,
        'followers_count': followers,
        'is_following': is_following_bool,
        'posts': [{'id': p[0], 'content': p[1] or '', 'image': p[2], 'created': p[3][:16] if p[3] else '', 'likes': p[4]} for p in posts]
    })

@app.route('/api/search')
def api_search():
    if 'user_id' not in session:
        return jsonify({'users': []})
    
    query = request.args.get('q', '')
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("SELECT id, username, avatar, bio FROM users WHERE username LIKE ? AND id != ? LIMIT 20", (f'%{query}%', session['user_id']))
    users = c.fetchall()
    conn.close()
    
    result = []
    for u in users:
        result.append({
            'id': u[0],
            'username': u[1],
            'avatar': u[2] or 'default.png',
            'bio': u[3] or '',
            'is_following': is_following(session['user_id'], u[0])
        })
    return jsonify({'users': result})

@app.route('/api/friends')
def api_friends():
    if 'user_id' not in session:
        return jsonify({'following': [], 'followers': []})
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute('''SELECT users.id, users.username, users.avatar FROM follows 
                 JOIN users ON follows.following_id = users.id 
                 WHERE follows.follower_id = ?''', (session['user_id'],))
    following = c.fetchall()
    c.execute('''SELECT users.id, users.username, users.avatar FROM follows 
                 JOIN users ON follows.follower_id = users.id 
                 WHERE follows.following_id = ?''', (session['user_id'],))
    followers = c.fetchall()
    following_count, followers_count = get_following_count(session['user_id'])
    conn.close()
    
    return jsonify({
        'following': [{'id': f[0], 'username': f[1], 'avatar': f[2] or 'default.png'} for f in following],
        'followers': [{'id': f[0], 'username': f[1], 'avatar': f[2] or 'default.png'} for f in followers],
        'following_count': following_count,
        'followers_count': followers_count
    })

@app.route('/api/follow/<int:user_id>', methods=['POST'])
def api_follow(user_id):
    if 'user_id' not in session or user_id == session['user_id']:
        return jsonify({'success': False})
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    existing = is_following(session['user_id'], user_id)
    
    if existing:
        c.execute("DELETE FROM follows WHERE follower_id = ? AND following_id = ?", (session['user_id'], user_id))
        following = False
    else:
        c.execute("INSERT INTO follows (follower_id, following_id) VALUES (?, ?)", (session['user_id'], user_id))
        following = True
    
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'following': following})

@app.route('/api/messages')
def api_messages():
    if 'user_id' not in session:
        return jsonify({'conversations': []})
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute('''SELECT DISTINCT 
                 CASE WHEN from_user = ? THEN to_user ELSE from_user END as other_user,
                 (SELECT username FROM users WHERE id = other_user) as username,
                 (SELECT avatar FROM users WHERE id = other_user) as avatar,
                 (SELECT content FROM messages WHERE (from_user = ? AND to_user = other_user) OR (from_user = other_user AND to_user = ?) ORDER BY created DESC LIMIT 1) as last_message
                 FROM messages 
                 WHERE from_user = ? OR to_user = ?
                 ORDER BY created DESC''', 
              (session['user_id'], session['user_id'], session['user_id'], session['user_id'], session['user_id']))
    convs = c.fetchall()
    conn.close()
    
    result = []
    seen = set()
    for c in convs:
        if c[0] not in seen:
            seen.add(c[0])
            result.append({'user_id': c[0], 'username': c[1] or 'Unknown', 'avatar': c[2] or 'default.png', 'last_message': c[3] or ''})
    return jsonify({'conversations': result})

@app.route('/api/chat/<int:user_id>')
def api_chat(user_id):
    if 'user_id' not in session:
        return jsonify({'messages': []})
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute('''SELECT messages.*, users.username, users.avatar 
                 FROM messages 
                 JOIN users ON messages.from_user = users.id
                 WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
                 ORDER BY created ASC''', 
              (session['user_id'], user_id, user_id, session['user_id']))
    msgs = c.fetchall()
    conn.close()
    
    result = []
    for m in msgs:
        result.append({
            'id': m[0],
            'from_user': m[1],
            'to_user': m[2],
            'content': m[3],
            'time': m[4][:16] if m[4] else '',
            'from_username': m[5],
            'from_avatar': m[6] or 'default.png'
        })
    return jsonify({'messages': result})

@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    if 'user_id' not in session:
        return jsonify({'success': False})
    
    data = request.json
    to_user = data.get('to_user')
    content = data.get('content')
    
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (from_user, to_user, content, created, is_read) VALUES (?, ?, ?, ?, 0)",
              (session['user_id'], to_user, content, datetime.now()))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

def get_following_count(user_id):
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM follows WHERE follower_id = ?", (user_id,))
    following = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM follows WHERE following_id = ?", (user_id,))
    followers = c.fetchone()[0]
    conn.close()
    return following, followers

def is_following(follower_id, following_id):
    conn = sqlite3.connect('speakforgeek.db')
    c = conn.cursor()
    c.execute("SELECT id FROM follows WHERE follower_id = ? AND following_id = ?", (follower_id, following_id))
    result = c.fetchone()
    conn.close()
    return result is not None

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    init_db()
    print("\n" + "="*50)
    print("🎧 SPEAK FOR GEEK - Обновлённая версия!")
    print("="*50)
    print("\n✅ Что добавлено:")
    print("   • Аватарки из галереи")
    print("   • Посты с фото")
    print("   • Комментарии")
    print("   • Редактирование профиля")
    print("   • 1 пост в день")
    print("   • Всеобщая лента")
    print("   • Мобильный интерфейс")
    print("="*50)
    app.run(host='0.0.0.0', port=5000, debug=True)
