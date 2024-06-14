import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import openai
import json
import os
import time

# Configuration de la page
st.set_page_config(layout="wide", page_title="Recommandation Musicale")

# Cacher le menu et le pied de page
hide_default_format = """
    <style>
    #MainMenu {visibility: hidden; }
    footer {visibility: hidden;}
    .align-start {
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
    }
    .center-button {
        display: flex;
        justify-content: center;
        padding-top: 20px;
    }
    </style>
    """
st.markdown(hide_default_format, unsafe_allow_html=True)

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
    
    if response.status_code == 200:
        return response.json().get('genres', [])
    elif response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 1))
        st.warning(f"Trop de requêtes. Veuillez réessayer après {retry_after} secondes.")
        time.sleep(retry_after)
        return get_available_genres(token)  # Réessayez après la période d'attente
    else:
        st.error(f"Erreur lors de la récupération des genres : {response.status_code}")
        return []

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
def get_openai_recommendations(prompt, num_tracks=20):
    response = openai.chat.completions.create(
        model="gpt-4o",
        response_format={ "type": "json_object" },
        messages=[
            {"role": "user", "content": f"Generate a {num_tracks} real songs playlist based on the following input: {prompt}. Answer only with a JSON array, for each item return the song and the artist like this example {{\"playlist\": [\"Billie Jean - Michael Jackson\", \"One - U2\"]}}"}
        ],
        temperature=1,
        max_tokens=500
    )
    return response.choices[0].message.content

# Function to convert Chat GPT response to Spotify track recommendations
def get_spotify_recommendations_from_gpt(gpt_response, token):
    try:
        gpt_content = json.loads(gpt_response)
    except json.JSONDecodeError:
        st.error("Erreur lors de l'analyse de la réponse GPT. La réponse n'est pas un JSON valide.")
        return []
    
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
st.markdown("# 〽️ Application de Recommandation Musicale 〽️")

# Tabs
tab1, tab2 = st.tabs(["Recommandations Chat GPT", "Recommandations par filtres"])

with tab1:
    st.markdown("<h2>Recommandations Chat GPT</h2>", unsafe_allow_html=True)
    prompt = st.text_area("Entrez votre demande de playlist générés par Chat GPT", "Une playlist 90s house classics", key='chatgpt_prompt')
    
    if st.button('Obtenir des recommandations', key='chatgpt_button'):
        progress_bar = st.progress(0)
        progress = 0

        all_recommendations = []
        while len(all_recommendations) < 10:
            gpt_response = get_openai_recommendations(prompt, num_tracks=20)
            
            # Convertir la réponse en recommandations de pistes
            token = get_token()
            recommendations = get_spotify_recommendations_from_gpt(gpt_response, token)

            # Filtrer les recommandations pour n'afficher que celles avec un preview_url non vide
            recommendations_with_preview = [track for track in recommendations if track['preview_url']]
            all_recommendations.extend(recommendations_with_preview)

            progress += 20
            if progress > 100:
                progress = 100
            progress_bar.progress(progress)

        progress_bar.empty()
        
        if all_recommendations:
            count = 0
            for track in all_recommendations:
                if count >= 10:
                    break
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
                    st.audio(track['preview_url'], format="audio/mp3")
                count += 1
        else:
            st.write("Aucune piste trouvée correspondant aux critères")
    
    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    # Authentication
    token = get_token()

    # Get available genres
    genres = get_available_genres(token)
    formatted_genres = [genre.capitalize() for genre in genres]

    st.markdown("<h2 style='text-align: center;'>Recommandations par filtres</h2>", unsafe_allow_html=True)

    left, right = st.columns(2)
    
    with left:
        st.markdown("<h3>Sélection de Genres</h3>", unsafe_allow_html=True)
        selected_genres = st.multiselect('Sélectionnez des Genres', formatted_genres, key='genre_select')

        st.markdown("<h3>Recherche d'Artistes</h3>", unsafe_allow_html=True)
        artist_query = st.text_input('Rechercher des Artistes', key='artist_query')
        
        selected_artist = None
        artist_id = None
        if artist_query:
            artists = search_artists(artist_query, token)
            if artists:
                artist_options = {artist['name']: artist['id'] for artist in artists}
                selected_artist = st.selectbox('Sélectionnez un Artiste', list(artist_options.keys()), key='artist_select')
                artist_id = artist_options[selected_artist]
            else:
                st.write("Aucun artiste trouvé")
    
    with right:
        st.markdown("<h3>Attributs des Pistes</h3>", unsafe_allow_html=True)
        popularity = st.slider('Niveau de Popularité du track', 1, 100, (1, 100))
        energy_level = st.slider('Niveau d’Énergie du track', 1, 100, (1, 100))
        danceability_level = st.slider('Niveau de Dansabilité du track', 1, 100, (1, 100))

    st.markdown('<div class="center-button">', unsafe_allow_html=True)
    if st.button('Obtenir des recommandations'):
        with st.spinner('Récupération des recommandations...'):
            if artist_id:
                # Recommander les meilleures pistes de l'artiste sélectionné
                response = requests.get(f'https://api.spotify.com/v1/artists/{artist_id}/top-tracks?market=US', headers={'Authorization': f'Bearer {token}'})
                recommendations = response.json().get('tracks', [])
            elif selected_genres:
                # Recommander des pistes basées sur les genres sélectionnés
                seed_genres = ','.join(selected_genres).lower()
                recommendations = get_recommendations(
                    token,
                    seed_genres=seed_genres,
                    target_popularity=popularity,
                    target_energy=energy_level,
                    target_danceability=danceability_level
                )
            else:
                # Obtenir des recommandations générales
                recommendations = get_recommendations(
                    token,
                    target_popularity=popularity,
                    target_energy=energy_level,
                    target_danceability=danceability_level
                )

            if recommendations:
                # Filtrer les recommandations pour n'afficher que celles avec un preview_url non vide
                recommendations_with_preview = [track for track in recommendations if track['preview_url']]

                # Limiter l'affichage à 10 résultats
                count = 0
                for track in recommendations_with_preview:
                    if count >= 10:
                        break
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        if track['album']['images']:
                            st.image(track['album']['images'][0]['url'], use_column_width=True)
                    with col2:
                        st.write(f"**{track['name']}**")
                        st.write(f"{', '.join([artist['name'] for artist in track['artists']])}")
                        st.write(f"*{track['album']['name']}*")
                        year = track['album']['release_date'].split('-')[0]
                        st.write(f"{year}")
                        st.audio(track['preview_url'], format="audio/mp3")
                    count += 1
            else:
                st.write("Aucune piste trouvée correspondant aux critères")
    st.markdown('</div>', unsafe_allow_html=True)
