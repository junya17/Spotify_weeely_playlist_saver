import os
import time
from typing import Dict, List

import spotipy
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from spotipy.oauth2 import SpotifyOAuth

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
app.secret_key = os.getenv('FLASK_SECRET_KEY')
TOKEN_INFO = 'token_info'

@app.route('/')
def index():
    """Render the main page or redirect to login if not authenticated."""
    if not session.get(TOKEN_INFO):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login')
def login():
    """Redirect to Spotify login page."""
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/redirect')
def redirect_page():
    """Handle the redirect after Spotify authentication."""
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for('index'))

@app.route('/saveDiscoverWeekly', methods=['POST'])
def save_discover_weekly():
    """Save Discover Weekly playlist to a new or existing Saved Weekly playlist."""
    try:
        token_info = get_token()
        sp = spotipy.Spotify(auth=token_info['access_token'])
        user_id = sp.current_user()['id']

        discover_weekly_id, saved_weekly_id = find_playlists(sp)

        if not discover_weekly_id:
            return jsonify({"error": "Discover Weekly playlist not found."}), 404

        if not saved_weekly_id:
            saved_weekly_id = create_saved_weekly_playlist(sp, user_id)

        songs = get_discover_weekly_songs(sp, discover_weekly_id)
        
        if not songs:
            return jsonify({"error": "No tracks found in Discover Weekly"}), 404

        sp.user_playlist_add_tracks(user_id, saved_weekly_id, songs['uris'])
        
        return jsonify({
            "message": "Songs added successfully!",
            "added_songs": songs['details']
        })
    
    except Exception as e:
        app.logger.error(f"Error in save_discover_weekly: {e}")
        return jsonify({"error": "An error occurred while saving the playlist."}), 500

@app.route('/get_playlists')
def get_playlists():
    """Fetch and return user's playlists."""
    try:
        token_info = get_token()
        sp = spotipy.Spotify(auth=token_info['access_token'])
        playlists = sp.current_user_playlists()
        return jsonify([
            {'name': playlist['name'], 'id': playlist['id']}
            for playlist in playlists['items']
        ])
    except Exception as e:
        app.logger.error(f"Error in get_playlists: {e}")
        return jsonify({"error": "An error occurred while fetching playlists."}), 500

def get_token() -> Dict:
    """Retrieve and refresh the Spotify access token if necessary."""
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

def create_spotify_oauth() -> SpotifyOAuth:
    """Create and return a SpotifyOAuth object."""
    return SpotifyOAuth(
        client_id=os.getenv('SPOTIPY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
        redirect_uri=url_for('redirect_page', _external=True),
        scope='user-library-read playlist-modify-public playlist-modify-private'
    )

def find_playlists(sp: spotipy.Spotify) -> tuple:
    """Find Discover Weekly and Saved Weekly playlists."""
    playlists = sp.current_user_playlists()
    discover_weekly_id = None
    saved_weekly_id = None
    for playlist in playlists['items']:
        if playlist['name'] == 'Discover Weekly':
            discover_weekly_id = playlist['id']
        if playlist['name'] == 'Saved Weekly':
            saved_weekly_id = playlist['id']
        if discover_weekly_id and saved_weekly_id:
            break
    return discover_weekly_id, saved_weekly_id

def create_saved_weekly_playlist(sp: spotipy.Spotify, user_id: str) -> str:
    """Create a new Saved Weekly playlist and return its ID."""
    new_playlist = sp.user_playlist_create(user_id, 'Saved Weekly', public=False)
    return new_playlist['id']

def get_discover_weekly_songs(sp: spotipy.Spotify, playlist_id: str) -> Dict[str, List]:
    """Get songs from the Discover Weekly playlist."""
    playlist = sp.playlist_items(playlist_id)
    uris = []
    details = []
    for item in playlist['items']:
        if item['track']:
            uris.append(item['track']['uri'])
            details.append({
                "name": item['track']['name'],
                "artists": [artist['name'] for artist in item['track']['artists']]
            })
    return {"uris": uris, "details": details}

if __name__ == '__main__':
    app.run(debug=True)