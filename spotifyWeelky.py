import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, request, url_for, session, redirect, render_template, jsonify
from werkzeug.exceptions import HTTPException
import logging

app = Flask(__name__)

app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
app.secret_key = '358935938593859385'  # 注意: 本番環境では安全な方法で管理してください
TOKEN_INFO = 'token_info'

@app.route('/')
def index():
    if not session.get(TOKEN_INFO):
        # トークンがない場合は認証ページにリダイレクト
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login')
def login():
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/redirect')
def redirect_page():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for('index'))

@app.route('/saveDiscoverWeekly', methods=['POST'])
def save_discover_weekly():
    try:
        token_info = get_token()
        sp = spotipy.Spotify(auth=token_info['access_token'])
        user_id = sp.current_user()['id']

        discover_weekly_playlist_id = None
        saved_weekly_playlist_id = None

        playlists = sp.current_user_playlists()
        for playlist in playlists['items']:
            if playlist['name'] == 'Discover Weekly':
                discover_weekly_playlist_id = playlist['id']
            if playlist['name'] == 'Saved Weekly':
                saved_weekly_playlist_id = playlist['id']

        if not discover_weekly_playlist_id:
            return jsonify({"error": "Discover Weekly playlist not found."}), 404

        if not saved_weekly_playlist_id:
            new_playlist = sp.user_playlist_create(user_id, 'Saved Weekly', public=False)
            saved_weekly_playlist_id = new_playlist['id']

        discover_weekly_playlist = sp.playlist_items(discover_weekly_playlist_id)
        song_uris = [song['track']['uri'] for song in discover_weekly_playlist['items'] if song['track']]
        
        if not song_uris:
            return jsonify({"error": "No tracks found in Discover Weekly"}), 404

        sp.user_playlist_add_tracks(user_id, saved_weekly_playlist_id, song_uris)
        
        added_songs = [{"name": song['track']['name'], "artists": [artist['name'] for artist in song['track']['artists']]} 
                       for song in discover_weekly_playlist['items'] if song['track']]
        
        return jsonify({"message": "Songs added successfully!", "added_songs": added_songs})
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "An error occurred while saving the playlist."}), 500

@app.route('/get_playlists')
def get_playlists():
    try:
        token_info = get_token()
        sp = spotipy.Spotify(auth=token_info['access_token'])
        playlists = sp.current_user_playlists()
        return jsonify([{'name': playlist['name'], 'id': playlist['id']} for playlist in playlists['items']])
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "An error occurred while fetching playlists."}), 500

def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        raise Exception("Token not found")
    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60
    if is_expired:
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session[TOKEN_INFO] = token_info
    return token_info

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id='0bbb7a5d2bdc4667bae08e4fe95c96c4',
        client_secret='a658209054ff46079866081b77c23de8',
        redirect_uri=url_for('redirect_page', _external=True),
        scope='user-library-read playlist-modify-public playlist-modify-private'
    )

if __name__ == '__main__':
    app.run(debug=True)