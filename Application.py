import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import openai
import json
import os

# Spotify API credentials
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not CLIENT_ID:
    st.error("CLIENT_ID n'est pas défini. Assurez-vous qu'il est configuré dans vos variables d'environnement.")
if not CLIENT_SECRET:
    st.error("CLIENT_SECRET n'est pas défini. Assurez-vous qu'il est configuré dans vos variables d'environnement.")
if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY n'est pas défini. Assurez-vous qu'elle est configurée dans vos variables d'environnement.")


# Configuration de l'API OpenAI
openai.api_key = OPENAI_API_KEY

# Function to get OAuth token
def get_token():
    auth_response = requests.post(
        'https://accounts.spotify.com/api/token',
        data={'grant_type': 'client_credentials'},
        auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    )
    return auth_response.json().get('access_token')

# Function to search for tracks
def search_track(query, token):
    headers = {'Authorization': f'Bearer {token}'}
    params = {'q': query, 'type': 'track', 'limit': 1}
    response = requests.get('https://api.spotify.com/v1/search', headers=headers, params=params)
    return response.json().get('tracks', {}).get('items', [])

# Function to search for artists
def search_artists(query, token):
    headers = {'Authorization': f'Bearer {token}'}
    params = {'q': query, 'type': 'artist', 'limit': 10}
    response = requests.get('https://api.spotify.com/v1/search', headers=headers, params=params)
    return response.json().get('artists', {}).get('items', [])

# Function to get available genres
def get_available_genres(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('https://api.spotify.com/v1/recommendations/available-genre-seeds', headers=headers)
    return response.json().get('genres', [])

# Function to get recommendations based on selected filters
def get_recommendations(token, seed_artists=None, seed_genres=None, target_popularity=None, target_energy=None, target_danceability=None):
    headers = {'Authorization': f'Bearer {token}'}
    params = {'limit': 10}
    if seed_artists:
        params['seed_artists'] = seed_artists
    if seed_genres:
        params['seed_genres'] = seed_genres
    if target_popularity:
        params['min_popularity'] = target_popularity[0]
        params['max_popularity'] = target_popularity[1]
    if target_energy is not None:
        params['min_energy'] = target_energy[0] / 100
        params['max_energy'] = target_energy[1] / 100
    if target_danceability is not None:
        params['min_danceability'] = target_danceability[0] / 100
        params['max_danceability'] = target_danceability[1] / 100
    
    response = requests.get('https://api.spotify.com/v1/recommendations', headers=headers, params=params)
    return response.json().get('tracks', [])

# Function to get recommendations from OpenAI
def get_openai_recommendations(prompt):
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": f"Generate a 10 real songs playlist based on the following input: {prompt}. Answer only with a JSON array, for each item return the song and the artist like this example {{\"playlist\": [\"Billie Jean - Michael Jackson\", \"One - U2\"]}}"}
        ],
        temperature=1,
        max_tokens=400
    )
    return response.choices[0].message.content

# Function to convert Chat GPT response to Spotify track recommendations
def get_spotify_recommendations_from_gpt(gpt_response, token):
    gpt_content = json.loads(gpt_response)
    songs = gpt_content.get('playlist', [])
    track_details = []
    
    for song in songs:
        tracks = search_track(song, token)
        if tracks:
            track = tracks[0]
            track_info = {
                'name': track['name'],
                'artist': track['artists'][0]['name'],
                'album': track['album']['name'],
                'release_date': track['album']['release_date'],
                'image_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
                'preview_url': track['preview_url']
            }
            track_details.append(track_info)
    return track_details

# Main Streamlit application
st.markdown("# 🎵 Application de Recommandation Musicale 🎵")

# Tabs
tab1, tab2 = st.tabs(["Recommandations Chat GPT", "Recommandations par Filtres"])

with tab2:
    st.markdown('<div class="section-banner">', unsafe_allow_html=True)
    
    # Authentication
    token = get_token()

    # Get available genres
    genres = get_available_genres(token)
    formatted_genres = [genre.capitalize() for genre in genres]

    st.markdown("<h2>Sélection de Genres</h2>", unsafe_allow_html=True)
    selected_genres = st.multiselect('Sélectionnez des Genres', formatted_genres, key='genre_select')

    st.markdown("<h2>Recherche d'Artistes</h2>", unsafe_allow_html=True)
    artist_query = st.text_input('Rechercher des Artistes')
    selected_artist = None
    artist_id = None
    if artist_query:
        artists = search_artists(artist_query, token)
        if artists:
            artist_options = {artist['name']: artist['id'] for artist in artists}
            selected_artist = st.selectbox('Sélectionnez un Artiste', list(artist_options.keys()), key='artist_select')
            if selected_artist:
                artist_id = artist_options[selected_artist]
        else:
            st.write("Aucun artiste trouvé")

    st.markdown("<h2>Attributs des Pistes</h2>", unsafe_allow_html=True)
    popularity = st.slider('Popularité', 0, 100, (0, 100))
    energy_level = st.slider('Niveau d’Énergie', 0, 100, (0, 100))
    danceability_level = st.slider('Dansabilité', 0, 100, (0, 100))

    st.markdown('</div>', unsafe_allow_html=True)

    if st.button('Recommandations'):
        with st.spinner('Récupération des recommandations...'):
            seed_artists = artist_id if artist_id else None
            seed_genres = ','.join(selected_genres).lower() if selected_genres else None
            
            recommendations = get_recommendations(
                token, 
                seed_artists=seed_artists, 
                seed_genres=seed_genres, 
                target_popularity=popularity, 
                target_energy=energy_level, 
                target_danceability=danceability_level
            )
            
            if recommendations:
                for track in recommendations:
                    st.markdown('<div class="result-card">', unsafe_allow_html=True)
                    st.write(f"**Artiste :** {', '.join([artist['name'] for artist in track['artists']])}")
                    st.write(f"**Piste :** {track['name']}")
                    st.write(f"**Année de Sortie :** {track['album']['release_date'][:4]}")
                    if track['album']['images']:
                        st.image(track['album']['images'][0]['url'], width=300)
                    if track['preview_url']:
                        st.audio(track['preview_url'], format="audio/mp3")
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.write("Aucune piste trouvée correspondant aux critères")

with tab1:
    #st.markdown('<div class="section-banner">', unsafe_allow_html=True)
    
    st.markdown("<h2>Recommandations Chat GPT</h2>", unsafe_allow_html=True)
    prompt = st.text_area("Entrez votre demande pour Chat GPT", "Donne-moi une playlist de musique pop des années 70", key='chatgpt_prompt')
    if st.button('Obtenir des Recommandations Chat GPT', key='chatgpt_button'):
        progress_bar = st.progress(0)
        for percent_complete in range(100):
            progress_bar.progress(percent_complete + 1)

            gpt_response = get_openai_recommendations(prompt)
            
            # Convert the response to track recommendations
            token = get_token()
            recommendations = get_spotify_recommendations_from_gpt(gpt_response, token)
            
            if recommendations:
                for track in recommendations:
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        if track['image_url']:
                            st.image(track['image_url'], use_column_width=True)
                    with col2:
                        st.write(f"**{track['name']}**")
                        st.write(f"{track['artist']}")
                        st.write(f"*{track['album']}*")
                        year = track['release_date'].split('-')[0]
                        st.write(f"{year}")
                        if track['preview_url']:
                            st.audio(track['preview_url'], format="audio/mp3")
            else:
                st.write("Aucune piste trouvée correspondant aux critères")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Apply custom CSS for styling
st.markdown("""
    <style>
    body {
        background-color: #121212;
        color: #FFFFFF;
    }
    .main-banner {
        background-color: black;
        padding: 20px;
        text-align: center;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .main-banner h1 {
        font-family: 'Roboto', sans-serif;
        color: #1DB954;
        font-size: 40px;
    }
    .section-banner {
        background-color: #282828;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .section-banner h2 {
        font-family: 'Helvetica Neue', sans-serif;
        color: #1DB954;
    }
    .result-card {
        background-color: #333333;
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
    }
    .result-card img {
        margin-right: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
