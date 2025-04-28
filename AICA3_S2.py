import streamlit as st
import requests
import json
import time
import random
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64
import os
from PIL import Image
import io

# Try to import google.generativeai, with a fallback message if not installed
try:
    import google.generativeai as genai
except ImportError:
    st.error("The 'google-generativeai' package is not installed. Please install it using: pip install google-generativeai")
    st.stop()

# -----------------------------
# PASTE YOUR GEMINI API KEY HERE
# -----------------------------
DEFAULT_API_KEY = "AIzaSyAr36mv2KIQ8KLvVl7lXuZKf6EMh7piaYg"  # Replace with your valid Gemini API key from https://ai.google.dev/
# -----------------------------

# Set page configuration
st.set_page_config(
    page_title="Game Tester Dashboard",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="collapsed",  # Start with sidebar collapsed
)

# Hide sidebar
st.markdown(
    """
    <style>
    [data-testid="collapsedControl"] {
        display: none
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Add custom CSS for the chatbot and overall styling
st.markdown(
    """
    <style>
    body {
        background-color: #f0f0f0; /* Light background for better contrast */
        color: #333; /* Dark text for readability */
    }
    .chat-container {
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 350px;
        z-index: 1000;
        transition: all 0.3s ease; /* Smooth transition for chat */
    }
    .chat-box {
        max-height: 400px;
        overflow-y: auto;
        padding: 10px;
        border-radius: 10px 10px 0 0;
        background-color: #2d3748;
        border: 1px solid #4a5568;
        box-shadow: 0 0 10px rgba(0,0,0,0.1);
    }
    .chat-input {
        width: 100%;
        border-radius: 0 0 10px 10px;
    }
    .user-message {
        background-color: #4299e1;
        color: white;
        padding: 8px 12px;
        border-radius: 15px 15px 0 15px;
        margin: 5px 0;
        max-width: 80%;
        margin-left: auto;
        word-wrap: break-word;
        transition: background-color 0.3s; /* Hover effect */
    }
    .user-message:hover {
        background-color: #3182ce; /* Lighter on hover */
    }
    .bot-message {
        background-color: #4a5568;
        color: white;
        padding: 8px 12px;
        border-radius: 15px 15px 15px 0;
        margin: 5px 0;
        max-width: 80%;
        word-wrap: break-word;
        transition: background-color 0.3s; /* Hover effect */
    }
    .bot-message:hover {
        background-color: #2d3748; /* Lighter on hover */
    }
    .chat-header {
        background-color: #4CAF50;
        color: white;
        padding: 10px 15px;
        border-radius: 10px 10px 0 0;
        font-weight: bold;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .minimize-btn {
        background: none;
        border: none;
        color: white;
        font-size: 20px;
        cursor: pointer;
    }
    .hidden {
        display: none;
    }
    .chat-icon {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: #4CAF50;
        color: white;
        width: 60px;
        height: 60px;
        border-radius: 50%;
        display: flex;
        justify-content: center;
        align-items: center;
        cursor: pointer;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        z-index: 1000;
        transition: transform 0.3s; /* Hover effect */
    }
    .chat-icon:hover {
        transform: scale(1.1); /* Scale on hover */
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.5rem 1rem;
        transition: background-color 0.3s; /* Hover effect */
    }
    .stButton>button:hover {
        background-color: #45a049; /* Darker on hover */
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
    .report-card {
        background-color: white;
        border-radius: 10px;
        padding: 0.2px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .api-key-container {
        margin-top: 20px;
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 10px;
        border: 1px solid #e9ecef;
    }
    .file-upload-button {
        background-color: #e9f5ff;
        border: 1px dashed #2196F3;
        border-radius: 5px;
        padding: 10px;
        cursor: pointer;
        text-align: center;
        margin-bottom: 10px;
        transition: background-color 0.3s; /* Hover effect */
    }
    .file-upload-button:hover {
        background-color: #d0e8ff;
    }
    .image-preview {
        max-width: 100%;
        max-height: 200px;
        border-radius: 5px;
        margin-top: 5px;
    }
    .message-image {
        max-width: 200px;
        max-height: 150px;
        border-radius: 5px;
        margin-top: 5px;
    }
    .file-info {
        font-size: 12px;
        color: #666;
        margin-top: 5px;
    }
    /* Remove gridlines from plotly charts */
    .plotly .gridline {
        display: none;
    }
    /* Chat input styling */
    .stTextInput>div>div>input {
        color: #333;
        background-color: white;
    }
    /* File uploader styling */
    .stFileUploader>div>div {
        color: #333;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state
if 'chat_visible' not in st.session_state:
    st.session_state.chat_visible = False
if 'messages' not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi there! I'm your Game Test Assistant. How can I help you with your game testing today?", "type": "text"}]
if 'game_name' not in st.session_state:
    st.session_state.game_name = ""
if 'report_generated' not in st.session_state:
    st.session_state.report_generated = False
if 'loading' not in st.session_state:
    st.session_state.loading = False
if 'test_results' not in st.session_state:
    st.session_state.test_results = None
if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = DEFAULT_API_KEY
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None

# List of valid game names
VALID_GAMES = [
    # Best-Selling and Globally Famous Games
    "Minecraft", "Grand Theft Auto V", "Tetris", "Wii Sports", "PUBG: Battlegrounds",
    "Super Mario Bros.", "Mario Kart 8 Deluxe", "Pokémon Red", "Pokémon Blue", "Pokémon Gold",
    "Pokémon Silver", "The Legend of Zelda: Breath of the Wild", "The Witcher 3: Wild Hunt",
    "Red Dead Redemption 2", "Skyrim", "Fortnite", "ROBLOX", "League of Legends", "Valorant",
    "Dota 2", "Counter-Strike 2", "Overwatch 2", "Apex Legends", "Call of Duty: Modern Warfare",
    "Call of Duty: Black Ops", "Call of Duty: Warzone", "FIFA 23", "FIFA 24", "NBA 2K24",
    "Animal Crossing: New Horizons", "Super Smash Bros. Ultimate", "Elden Ring", "Cyberpunk 2077",
    "Horizon Forbidden West", "God of War", "God of War Ragnarök", "Assassin's Creed Valhalla",
    "Starfield", "Baldur's Gate 3", "Diablo IV", "Final Fantasy VII", "Final Fantasy XV",
    "Final Fantasy XVI", "Resident Evil 4", "Street Fighter 6", "Tekken 8", "Genshin Impact",
    "Among Us", "Hollow Knight", "Celeste", "Stardew Valley", "Hades", "Rocket League",
    "Marvel Rivals", "Pac-Man", "Sonic the Hedgehog", "Donkey Kong", "Space Invaders",
    "Mortal Kombat 11", "Gran Turismo 7", "Civilization VI", "The Sims 4", "World of Warcraft",
    "Destiny 2", "Battlefield 2042", "Far Cry 6", "Splatoon 3", "Fire Emblem: Three Houses",
    "Xenoblade Chronicles 3", "Terraria", "The Last of Us", "The Last of Us Part II",
    "Uncharted 4: A Thief's End", "Metal Gear Solid V: The Phantom Pain", "Death Stranding",
    "Sekiro: Shadows Die Twice", "Ghost of Tsushima", "Halo Infinite", "Forza Horizon 5",
    # Call of Duty Series (20+ titles)
    "Call of Duty", "Call of Duty 2", "Call of Duty 3", "Call of Duty 4: Modern Warfare",
    "Call of Duty: World at War", "Call of Duty: Modern Warfare 2", "Call of Duty: Black Ops II",
    "Call of Duty: Ghosts", "Call of Duty: Advanced Warfare", "Call of Duty: Black Ops III",
    "Call of Duty: Infinite Warfare", "Call of Duty: WWII", "Call of Duty: Black Ops 4",
    "Call of Duty: Modern Warfare (2019)", "Call of Duty: Black Ops Cold War",
    "Call of Duty: Vanguard", "Call of Duty: Modern Warfare II (2022)", "Call of Duty: Modern Warfare III",
    "Call of Duty: Black Ops 6", "Call of Duty: Mobile",
    # Pokémon Series (30+ titles)
    "Pokémon Yellow", "Pokémon Crystal", "Pokémon Ruby", "Pokémon Sapphire", "Pokémon Emerald",
    "Pokémon FireRed", "Pokémon LeafGreen", "Pokémon Diamond", "Pokémon Pearl", "Pokémon Platinum",
    "Pokémon HeartGold", "Pokémon SoulSilver", "Pokémon Black", "Pokémon White",
    "Pokémon Black 2", "Pokémon White 2", "Pokémon X", "Pokémon Y", "Pokémon Omega Ruby",
    "Pokémon Alpha Sapphire", "Pokémon Sun", "Pokémon Moon", "Pokémon Ultra Sun",
    "Pokémon Ultra Moon", "Pokémon Let's Go Pikachu", "Pokémon Let's Go Eevee",
    "Pokémon Brilliant Diamond", "Pokémon Shining Pearl", "Pokémon Scarlet", "Pokémon Violet",
    "Pokémon Legends: Arceus", "Pokémon TCG Pocket", "Pokémon Go",
    # Super Mario Series
    "Super Mario Bros. 2", "Super Mario Bros. 3", "Super Mario World", "Super Mario 64",
    "Super Mario Sunshine", "Super Mario Galaxy", "Super Mario Galaxy 2", "Super Mario 3D Land",
    "Super Mario 3D World", "Super Mario Odyssey", "New Super Mario Bros.", "New Super Mario Bros. Wii",
    "New Super Mario Bros. U", "Super Mario Maker", "Super Mario Maker 2", "Super Mario Run",
    # The Legend of Zelda Series
    "The Legend of Zelda", "Zelda II: The Adventure of Link", "A Link to the Past",
    "Link's Awakening", "Ocarina of Time", "Majora's Mask", "The Wind Waker",
    "Twilight Princess", "Skyward Sword", "A Link Between Worlds", "Tears of the Kingdom",
    # Final Fantasy Series (15+ mainline, spin-offs)
    "Final Fantasy", "Final Fantasy II", "Final Fantasy III", "Final Fantasy IV",
    "Final Fantasy V", "Final Fantasy VI", "Final Fantasy VIII", "Final Fantasy IX",
    "Final Fantasy X", "Final Fantasy XI", "Final Fantasy XII", "Final Fantasy XIII",
    "Final Fantasy XIII-2", "Lightning Returns: Final Fantasy XIII", "Final Fantasy XIV",
    "Grand Theft Auto III", "Grand Theft Auto: Vice City",
    "Grand Theft Auto: San Andreas", "Grand Theft Auto: Liberty City Stories",
    "Grand Theft Auto: Vice City Stories", "Grand Theft Auto IV",
    "Grand Theft Auto: The Lost and Damned", "Grand Theft Auto: The Ballad of Gay Tony",
    "Grand Theft Auto: Chinatown Wars", "Saints Row", "Saints Row 2",
    "Saints Row: The Third", "Saints Row IV", "Saints Row: Gat out of Hell",
    "Sleeping Dogs", "Watch Dogs", "Watch Dogs: Legion",
    "Mafia", "Mafia II", "Mafia III", "Mafia: Definitive Edition",
    "Yakuza", "Yakuza 2", "Yakuza 3", "Yakuza 4", "Yakuza 5",
    "Yakuza 6: The Song of Life", "Yakuza 0", "Yakuza Kiwami",
    "Yakuza Kiwami 2", "Judgment", "Lost Judgment",
    "Like a Dragon: Ishin!", "Yakuza: Dead Souls",
    "Shenmue", "Shenmue II", "Shenmue III", "No More Heroes",
    "No More Heroes 2: Desperate Struggle", "No More Heroes 3",
    "Killer7", "MadWorld", "The Wonderful 101", "Astral Chain",
    "Bayonetta", "Bayonetta 2", "Bayonetta 3", "Vanquish",
    "Metal Gear Solid", "Metal Gear Solid 2: Sons of Liberty",
    "Metal Gear Solid 3: Snake Eater", "Metal Gear Solid 4: Guns of the Patriots",
    "Metal Gear Solid: Peace Walker", "Metal Gear Rising: Revengeance",
    "Zone of the Enders", "Zone of the Enders: The 2nd Runner",
    "Silent Hill", "Silent Hill 3", "Silent Hill 4: The Room",
    "Silent Hill: Origins", "Silent Hill: Homecoming",
    "Silent Hill: Shattered Memories", "Silent Hill: Downpour",
    "Castlevania", "Castlevania II: Simon's Quest",
    "Castlevania III: Dracula's Curse", "Super Castlevania IV",
    "Castlevania: Bloodlines", "Castlevania: Aria of Sorrow",
    "Castlevania: Dawn of Sorrow", "Castlevania: Portrait of Ruin",
    "Castlevania: Order of Ecclesia", "Metroid", "Metroid II: Return of Samus",
    "Super Metroid", "Metroid Fusion", "Metroid: Zero Mission",
    "Metroid Prime", "Metroid Prime 2: Echoes", "Metroid Prime 3: Corruption",
    "Metroid: Other M", "Metroid: Samus Returns", "Metroid Dread",
    "Kid Icarus", "Kid Icarus: Of Myths and Monsters", "Kid Icarus: Uprising",
    "Fire Emblem: Shadow Dragon", "Fire Emblem: Mystery of the Emblem",
    "Fire Emblem: Genealogy of the Holy War", "Fire Emblem: Thracia 776",
    "Fire Emblem: The Binding Blade", "Fire Emblem: The Blazing Blade",
    "Fire Emblem: The Sacred Stones", "Fire Emblem: Path of Radiance",
    "Fire Emblem: Radiant Dawn", "Fire Emblem: Shadow Dragon and the Blade of Light",
    "Fire Emblem: New Mystery of the Emblem", "Fire Emblem Awakening",
    "Fire Emblem Fates", "Fire Emblem Echoes: Shadows of Valentia",
    "Fire Emblem: Three Houses", "Fire Emblem Engage",
    "Advance Wars", "Advance Wars 2: Black Hole Rising",
    "Advance Wars: Dual Strike", "Advance Wars: Days of Ruin",
    "Battalion Wars", "Battalion Wars 2", "Wargroove",
    "Wargroove 2", "Tactics Ogre: Let Us Cling Together",
    "Tactics Ogre: Reborn", "Final Fantasy Tactics Advance",
    "Final Fantasy Tactics A2: Grimoire of the Rift",
    "Disgaea: Hour of Darkness", "Disgaea 2: Cursed Memories",
    "Disgaea 3: Absence of Justice", "Disgaea 4: A Promise Unforgotten",
    "Disgaea 5: Alliance of Vengeance", "Disgaea 6: Defiance of Destiny",
    "Phantom Brave", "Makai Kingdom", "Soul Nomad & the World Eaters",
    "Z.H.P. Unlosing Ranger VS Darkdeath Evilman",
    "Prinny: Can I Really Be the Hero?", "Prinny 2: Dawn of Operation Panties, Dood!",
    "La Pucelle: Tactics", "Rhapsody: A Musical Adventure",
    "Rhapsody II: Ballad of the Little Princess",
    "Rhapsody III: Memories of Marl Kingdom",
    "Atelier Iris: Eternal Mana", "Atelier Iris 2: The Azoth of Destiny",
    "Atelier Iris 3: Grand Phantasm", "Mana Khemia: Alchemists of Al-Revis",
    "Mana Khemia 2: Fall of Alchemy", "Atelier Rorona: The Alchemist of Arland",
    "Atelier Totori: The Adventurer of Arland",
    "Atelier Meruru: The Apprentice of Arland",
    "Atelier Ayesha: The Alchemist of Dusk",
    "Atelier Escha & Logy: Alchemists of the Dusk Sky",
    "Atelier Shallie: Alchemists of the Dusk Sea",
    "Atelier Sophie: The Alchemist of the Mysterious Book",
    "Atelier Firis: The Alchemist and the Mysterious Journey",
    "Atelier Lydie & Suelle: The Alchemists and the Mysterious Paintings",
    "Atelier Ryza: Ever Darkness & the Secret Hideout",
    "Atelier Ryza 2: Lost Legends & the Secret Fairy",
    "Atelier Ryza 3: Alchemist of the End & the Secret Key",
    "Shining Resonance Refrain", "Valkyria Chronicles",
    "Valkyria Chronicles 2", "Valkyria Chronicles 3", "Valkyria Chronicles 4",
    "Sakura Wars", "Shining Force", "Shining Force II",
    "Shining Force III", "Phantasy Star", "Phantasy Star II",
    "Phantasy Star III: Generations of Doom",
    "Phantasy Star IV: The End of the Millennium",
    "Phantasy Star Universe", "Phantasy Star Portable",
    "Phantasy Star Portable 2", "Phantasy Star Online",
    "Phantasy Star Online: Blue Burst",
    "Phantasy Star Online 2: New Genesis",
    "Xenoblade Chronicles", "Xenoblade Chronicles 2",
    "Xenoblade Chronicles X", "Xenoblade Chronicles: Definitive Edition",
    "Xenoblade Chronicles 2: Torna – The Golden Country",
    "Xenogears", "Xenosaga Episode I: Der Wille zur Macht",
    "Xenosaga Episode II: Jenseits von Gut und Böse",
    "Xenosaga Episode III: Also sprach Zarathustra",
    "Chrono Cross", "Radical Dreamers", "Vagrant Story",
    "Parasite Eve", "Parasite Eve II", "The 3rd Birthday",
    "Legend of Mana", "Trials of Mana", "Secret of Mana",
    "Seiken Densetsu 3", "Dawn of Mana", "Heroes of Mana",
    "Breath of Fire", "Breath of Fire II", "Breath of Fire III",
    "Breath of Fire IV", "Breath of Fire: Dragon Quarter",
    "Suikoden", "Suikoden II", "Suikoden III", "Suikoden IV",
    "Suikoden V", "Suikoden Tactics", "Wild Arms",
    "Wild Arms 2", "Wild Arms 3", "Wild Arms 4", "Wild Arms 5",
    "Wild Arms XF", "Shadow Hearts", "Shadow Hearts: Covenant",
    "Shadow Hearts: From the New World", "Koudelka",
    "Arc the Lad", "Arc the Lad II", "Arc the Lad III",
    "Arc the Lad: Twilight of the Spirits",
    "Arc the Lad: End of Darkness", "Lunar: Silver Star Story Complete",
    "Lunar 2: Eternal Blue Complete", "Lunar Legend",
    "Lunar: Dragon Song", "Grandia", "Grandia II", "Grandia III",
    "Grandia Xtreme", "Skies of Arcadia", "Valkyrie Profile",
    "Valkyrie Profile 2: Silmeria", "Valkyrie Profile: Covenant of the Plume",
    "Star Ocean", "Star Ocean: The Second Story",
    "Star Ocean: Till the End of Time",
    "Star Ocean: The Last Hope",
    "Star Ocean: Integrity and Faithlessness",
    "Star Ocean: The Divine Force",
    "Radiata Stories", "Rogue Galaxy", "Dark Cloud",
    "Dark Cloud 2", "Jeanne d'Arc", "Odin Sphere",
    "Odin Sphere Leifthrasir", "Muramasa: The Demon Blade",
    "Dragon's Crown", "13 Sentinels: Aegis Rim",
    "Persona", "Persona 2: Innocent Sin",
    "Persona 2: Eternal Punishment", "Persona 3",
    "Persona 3 Portable", "Persona 4", "Persona 4 Golden",
    "Persona 5 Strikers", "Persona 3 Reload",
    "Shin Megami Tensei III: Nocturne",
    "Shin Megami Tensei IV", "Shin Megami Tensei V",
    "Shin Megami Tensei: Digital Devil Saga",
    "Shin Megami Tensei: Digital Devil Saga 2",
    "Shin Megami Tensei: Devil Summoner",
    "Shin Megami Tensei: Devil Summoner 2",
    "Devil Summoner: Soul Hackers",
    "Soul Hackers 2", "Tokyo Mirage Sessions #FE",
    "Etrian Odyssey", "Etrian Odyssey II",
    "Etrian Odyssey III", "Etrian Odyssey IV",
    "Etrian Odyssey V", "Etrian Odyssey Nexus",
    "The World Ends With You",
    "Neo: The World Ends With You",
    "Kingdom Hearts", "Kingdom Hearts: Chain of Memories",
    "Kingdom Hearts II", "Kingdom Hearts: Birth by Sleep",
    "Kingdom Hearts: Dream Drop Distance",
    "Kingdom Hearts 0.2: Birth by Sleep – A Fragmentary Passage",
    "Kingdom Hearts III", "Kingdom Hearts: Melody of Memory",
    "Theatrhythm Final Fantasy",
    "Theatrhythm Final Bar Line",
    "Dissidia Final Fantasy",
    "Dissidia 012 Final Fantasy",
    "Dissidia Final Fantasy NT",
    "World of Final Fantasy",
    "Crisis Core: Final Fantasy VII",
    "Dirge of Cerberus: Final Fantasy VII",
    "Before Crisis: Final Fantasy VII",
    "Final Fantasy Type-0",
    "Final Fantasy Agito",
    "Final Fantasy Awakening",
    "Final Fantasy Record Keeper",
    "Final Fantasy Brave Exvius",
    "Mobius Final Fantasy",
    "Final Fantasy Dimensions",
    "Final Fantasy Dimensions II",
    "Final Fantasy Explorers",
    "Final Fantasy Mystic Quest",
    "Final Fantasy Adventure",
    "Final Fantasy Legend",
    "Final Fantasy Legend II",
    "Final Fantasy Legend III",
    "SaGa Frontier",
    "SaGa Frontier 2",
    "Romancing SaGa",
    "Romancing SaGa 2",
    "Romancing SaGa 3",
    "SaGa Scarlet Grace",
    "Imperial SaGa",
    "Emperor's SaGa",
    "Collection of SaGa",
    "The Last Remnant",
    "Infinite Undiscovery",
    "Blue Dragon",
    "Lost Odyssey",
    "Enchanted Arms",
    "MagnaCarta 2",
    "Resonance of Fate",
    "Nier",
    "Drakengard",
    "Drakengard 2",
    "Drakengard 3",
    "Tales of Phantasia",
    "Tales of Destiny",
    "Tales of Eternia",
    "Tales of Symphonia",
    "Tales of Legendia",
    "Tales of the Abyss",
    "Tales of Innocence",
    "Tales of Vesperia",
    "Tales of Hearts",
    "Tales of Graces",
    "Tales of Xillia",
    "Tales of Xillia 2",
    "Tales of Zestiria",
    "Tales of Berseria",
    "Tales of Crestoria",
    "Tales of Luminaria",
    "Dragon Quest",
    "Dragon Quest II",
    "Dragon Quest III",
    "Dragon Quest IV",
    "Dragon Quest V",
    "Dragon Quest VI",
    "Dragon Quest VII",
    "Dragon Quest VIII",
    "Dragon Quest IX",
    "Dragon Quest X",
    "Dragon Quest Heroes",
    "Dragon Quest Heroes II",
    "Dragon Quest Builders",
    "Dragon Quest Builders 2",
    "Dragon Quest Monsters",
    "Dragon Quest Monsters 2",
    "Dragon Quest Monsters: Joker",
    "Dragon Quest Monsters: Joker 2",
    "Dragon Quest Monsters: Joker 3",
    "Dragon Quest Treasures",
    "Dragon Quest Swords",
    "Dragon Quest Wars",
    "The Legend of Dragoon",
    "Vandal Hearts",
    "Vandal Hearts II",
    "Front Mission",
    "Front Mission 2",
    "Front Mission 3",
    "Front Mission 4",
    "Front Mission 5",
    "Front Mission Evolved",
    "Vanguard Bandits",
    "Growlanser",
    "Growlanser II",
    "Growlanser III",
    "Growlanser IV",
    "Growlanser V",
    "Growlanser VI",
    "Langrisser",
    "Langrisser II",
    "Langrisser III",
    "Langrisser IV",
    "Langrisser V",
    "Warsong",
    "Master of Monsters",
    "Brigandine",
    "Brigandine: The Legend of Runersia",
    "Shining Force: Resurrection of the Dark Dragon",
    "Shining Force EXA",
    "Shining Force Feather",
    "Shining Force Neo",
    "Shining Tears",
    "Shining Wind",
    "Shining Ark",
    "Shining Blade",
    "Shining Hearts",
    "Shining Resonance",
    "Blade Arcus from Shining",
    "Valhalla Knights",
    "Valhalla Knights 2",
    "Valhalla Knights 3",
    "Zwei: The Ilvard Insurrection",
    "Zwei: The Arges Adventure",
    "Ys I",
    "Ys II",
    "Ys III: Wanderers from Ys",
    "Ys IV: The Dawn of Ys",
    "Ys V",
    "Ys VI: The Ark of Napishtim",
    "Ys: The Oath in Felghana",
    "Ys Origin",
    "Ys Seven",
    "Ys: Memories of Celceta",
    "Ys VIII: Lacrimosa of Dana",
    "Ys IX: Monstrum Nox",
    "The Legend of Heroes: Trails in the Sky",
    "The Legend of Heroes: Trails in the Sky SC",
    "The Legend of Heroes: Trails in the Sky the 3rd",
    "The Legend of Heroes: Trails of Cold Steel",
    "The Legend of Heroes: Trails of Cold Steel II",
    "The Legend of Heroes: Trails of Cold Steel III",
    "The Legend of Heroes: Trails of Cold Steel IV",
    "The Legend of Heroes: Trails into Reverie",
    "The Legend of Heroes: Trails to Azure",
    "The Legend of Heroes: Trails from Zero",
    "The Legend of Heroes: Trails through Daybreak",
    "Tokyo Xanadu",
    "Gurumin: A Monstrous Adventure",
    "PoPoLoCrois",
    "PoPoLoCrois: Narcia's Tears and the Fairy's Flute",
    "Return to PoPoLoCrois: A Story of Seasons Fairytale",
    "Harvest Moon",
    "Harvest Moon: Friends of Mineral Town",
    "Harvest Moon: More Friends of Mineral Town",
    "Harvest Moon: A Wonderful Life",
    "Harvest Moon: Another Wonderful Life",
    "Harvest Moon: DS",
    "Harvest Moon: Island of Happiness",
    "Harvest Moon: Sunshine Islands",
    "Harvest Moon: Grand Bazaar",
    "Harvest Moon: The Tale of Two Towns",
    "Harvest Moon: A New Beginning",
    "Harvest Moon: The Lost Valley",
    "Harvest Moon: Seeds of Memories",
    "Harvest Moon: Skytree Village",
    "Harvest Moon: Light of Hope",
    "Harvest Moon: One World",
    "Story of Seasons",
    "Story of Seasons: Friends of Mineral Town",
    "Story of Seasons: Pioneers of Olive Town",
    "Story of Seasons: A Wonderful Life",
    "Rune Factory",
    "Rune Factory 2",
    "Rune Factory 3",
    "Rune Factory 4",
    "Rune Factory 5",
    "Rune Factory: Tides of Destiny",
    "Rune Factory: Frontier",
    "Innocent Life: A Futuristic Harvest Moon",
    "Bokujō Monogatari: Harvest Moon for Girl",
    "Harvest Moon: Tree of Tranquility",
    "Harvest Moon: Animal Parade",
    "Harvest Moon: Hero of Leaf Valley",
    "Harvest Moon: Mad Dash",
    "Harvest Moon: Save the Homeland",
    "Harvest Moon: Magical Melody",
    "Harvest Moon: Back to Nature",
    "Harvest Moon 64",
    "Harvest Moon: Song of Happiness",
    "Harvest Moon: The Winds of Anthos",
    "Return to Monkey Island",
    "The Secret of Monkey Island",
    "Monkey Island 2: LeChuck's Revenge",
    "The Curse of Monkey Island",
    "Escape from Monkey Island",
    "Tales of Monkey Island",
    "Day of the Tentacle",
    "Sam & Max Hit the Road",
    "Sam & Max: Save the World",
    "Sam & Max: Beyond Time and Space",
    "Sam & Max: The Devil's Playhouse",
    "Grim Fandango",
    "Full Throttle",
    "The Dig",
    "Maniac Mansion",
    "Zak McKracken and the Alien Mindbenders",
    "Loom",
    "Indiana Jones and the Last Crusade",
    "Indiana Jones and the Fate of Atlantis",
    "The Secret of Monkey Island: Special Edition",
    "Monkey Island 2: Special Edition",
    "Grim Fandango Remastered",
    "Day of the Tentacle Remastered",
    "Full Throttle Remastered",
    "Broken Sword: The Shadow of the Templars",
    "Broken Sword II: The Smoking Mirror",
    "Broken Sword: The Sleeping Dragon",
    "Broken Sword: The Angel of Death",
    "Broken Sword 5: The Serpent's Curse",
    "Syberia",
    "Syberia II",
    "Syberia 3",
    "Syberia: The World Before",
    "Still Life",
    "Still Life 2",
    "Post Mortem",
    "The Longest Journey",
    "Dreamfall: The Longest Journey",
    "Dreamfall Chapters",
    "Draugen",
    "The Vanishing of Ethan Carter",
    "Ethan Carter",
    "Kona",
    "Firewatch",
    "Oxenfree",
    "What Remains of Edith Finch",
    "Tacoma",
    "Gone Home",
    "Dear Esther",
    "Everybody's Gone to the Rapture",
    "The Stanley Parable",
    "The Beginner's Guide",
    "Soma",
    "Amnesia: The Dark Descent",
    "Amnesia: A Machine for Pigs",
    "Amnesia: Rebirth",
    "Outlast",
    "Outlast 2",
    "Layers of Fear",
    "Layers of Fear 2",
    "Observer",
    "Observer: System Redux",
    "Blair Witch",
    "Visage",
    "Among the Sleep",
    "Dead by Daylight",
    "Friday the 13th: The Game",
    "Phasmophobia",
    "Five Nights at Freddy's",
    "Five Nights at Freddy's 2",
    "Five Nights at Freddy's 3",
    "Five Nights at Freddy's 4",
    "Five Nights at Freddy's: Sister Location",
    "Five Nights at Freddy's: Help Wanted",
    "Five Nights at Freddy's: Security Breach",
    "Bendy and the Ink Machine",
    "Hello Neighbor",
    "Granny",
    "Slender: The Eight Pages",
    "FNAF World",
    "Ultimate Custom Night",
    "Freddy Fazbear's Pizzeria Simulator",
    "Poppy Playtime",
    "Poppy Playtime: Chapter 2",
    "Poppy Playtime: Chapter 3",
    "My Friendly Neighborhood",
    "Amanda the Adventurer",
    "Little Nightmares",
    "Little Nightmares II",
    "Brütal Legend",
    "Psychonauts",
    "Psychonauts 2",
    "Stacking",
    "Costume Quest",
    "Costume Quest 2",
    "Broken Age",
    "Massive Chalice",
    "Headlander",
    "The Cave",
    "Iron Brigade",
    "Middle-earth: Shadow of Mordor",
    "Middle-earth: Shadow of War",
    "Mad Max",
    "L.A. Noire",
    "Bully",
    "Manhunt",
    "The Warriors",
    "Red Dead Revolver",
    "Red Dead Redemption",
    "Red Dead Redemption: Undead Nightmare",
    "Grand Theft Auto III",
    "Grand Theft Auto: Vice City",
    "Grand Theft Auto: San Andreas",
    "Grand Theft Auto: Liberty City Stories",
    "Grand Theft Auto: Vice City Stories",
    "Grand Theft Auto IV",
    "Grand Theft Auto: The Lost and Damned",
    "Grand Theft Auto: The Ballad of Gay Tony",
    "Grand Theft Auto: Chinatown Wars",
    "Saints Row",
    "Saints Row 2",
    "Saints Row: The Third",
    "Saints Row IV",
    "Saints Row: Gat out of Hell",
    "Sleeping Dogs",
    "Watch Dogs",
    "Watch Dogs: Legion",
    "Mafia",
    "Mafia II",
    "Mafia III",
    "Mafia: Definitive Edition",
    "Yakuza",
    "Yakuza 2",
    "Yakuza 3",
    "Yakuza 4",
    "Yakuza 5",
    "Yakuza 6: The Song of Life",
    "Yakuza 0",
    "Yakuza Kiwami",
    "Yakuza Kiwami 2",
    "Judgment",
    "Lost Judgment",
    "Like a Dragon: Ishin!",
    "Yakuza: Dead Souls",
    "Shenmue",
    "Shenmue II",
    "Shenmue III",
    "No More Heroes",
    "No More Heroes 2: Desperate Struggle",
    "No More Heroes 3",
    "Killer7",
    "MadWorld",
    "The Wonderful 101",
    "Astral Chain",
    "Bayonetta",
    "Bayonetta 2",
    "Bayonetta 3",
    "Vanquish",
    "Metal Gear Solid",
    "Metal Gear Solid 2: Sons of Liberty",
    "Metal Gear Solid 3: Snake Eater",
    "Metal Gear Solid 4: Guns of the Patriots",
    "Metal Gear Solid: Peace Walker",
    "Metal Gear Rising: Revengeance",
    "Zone of the Enders",
    "Zone of the Enders: The 2nd Runner",
    "Silent Hill",
    "Silent Hill 3",
    "Silent Hill 4: The Room",
    "Silent Hill: Origins",
    "Silent Hill: Homecoming",
    "Silent Hill: Shattered Memories",
    "Silent Hill: Downpour",
    "Castlevania",
    "Castlevania II: Simon's Quest",
    "Castlevania III: Dracula's Curse",
    "Super Castlevania IV",
    "Castlevania: Bloodlines",
    "Castlevania: Aria of Sorrow",
    "Castlevania: Dawn of Sorrow",
    "Castlevania: Portrait of Ruin",
    "Castlevania: Order of Ecclesia",
    "Metroid",
    "Metroid II: Return of Samus",
    "Super Metroid",
    "Metroid Fusion",
    "Metroid: Zero Mission",
    "Metroid Prime",
    "Metroid Prime 2: Echoes",
    "Metroid Prime 3: Corruption",
    "Metroid: Other M",
    "Metroid: Samus Returns",
    "Metroid Dread",
    "Kid Icarus",
    "Kid Icarus: Of Myths and Monsters",
    "Kid Icarus: Uprising"
]

# Configure Gemini API
def configure_gemini(api_key):
    genai.configure(api_key=api_key)

# Function to list available models (for debugging)
def list_available_models(api_key):
    try:
        configure_gemini(api_key)
        models = genai.list_models()
        return [model.name for model in models]
    except Exception as e:
        return f"Error listing models: {str(e)}"

# Function to process image files
def process_image(uploaded_file):
    if uploaded_file is not None:
        # Convert to PIL image
        image = Image.open(uploaded_file)
        return image
    return None

# Function to encode image to base64
def encode_image(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    return base64.b64encode(img_bytes).decode()

# Function to process text files
def process_text_file(uploaded_file):
    if uploaded_file is not None:
        # Read file content
        content = uploaded_file.read()
        try:
            # Try to decode as text
            text_content = content.decode('utf-8')
            return text_content
        except UnicodeDecodeError:
            # If not text, return info about binary file
            return f"Binary file received: {uploaded_file.name}, size: {len(content)} bytes"
    return None

# Function to call Gemini API
def get_chat_response(messages, api_key, uploaded_file=None):
    if not api_key:
        return "Please provide a Gemini API key to use the chatbot."
    
    try:
        # Configure Gemini
        configure_gemini(api_key)
        
        # Prepare context messages
        prompt = ""
        
        # Add game context if available
        if st.session_state.game_name and st.session_state.report_generated:
            prompt += f"You are a game testing assistant helping with the game '{st.session_state.game_name}'. The test results show: Average FPS: {st.session_state.test_results['summary']['avg_fps']:.1f}, Total Bugs: {st.session_state.test_results['summary']['total_bugs']}, Satisfaction Score: {st.session_state.test_results['summary']['satisfaction_score']:.1f}. "
        
        # Add recent messages for context
        for msg in messages[-5:]:  # Last 5 messages
            if msg['role'] == 'user':
                prompt += f":User  {msg['content']}\n"
            else:
                prompt += f"Assistant: {msg['content']}\n"
        
        # Create model (use gemini-1.5-flash for both text and vision tasks)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # If there's an uploaded file
        if uploaded_file is not None:
            file_type = uploaded_file.type
            # Process image file
            if file_type.startswith('image/'):
                image = process_image(uploaded_file)
                
                # Generate content with image
                response = model.generate_content([
                    prompt,
                    image
                ])
                
            # Process text file
            else:
                file_content = process_text_file(uploaded_file)
                prompt += f"\nFile content: {file_content}\n\nPlease analyze this file and provide insights related to game testing."
                response = model.generate_content(prompt)
        else:
            # Text only query
            response = model.generate_content(prompt)
        
        return response.text
    
    except Exception as e:
        # Fallback for any exceptions
        available_models = list_available_models(api_key)
        if str(e).find("404") != -1 and "models/gemini" in str(e):
            error_msg = f"Model not found: {str(e)}. Available models: {available_models}. Your API key may not have access to the requested model. Please check your API key or try a different model."
        else:
            error_msg = f"Connection issue: {str(e)}. Available models: {available_models}."
        if st.session_state.get('test_results'):
            return f"{error_msg} But I can still assist with interpreting your test results based on the data we have. What specific aspect would you like to explore?"
        else:
            return f"{error_msg} Please try again later or feel free to explore the dashboard manually. You can also try entering a game name to generate test results."

# Function to generate mock test data
def generate_test_data(game_name):
    # Check if game is valid
    if game_name not in VALID_GAMES:
        return None
    
    # Performance metrics
    fps_data = [random.uniform(40, 120) for _ in range(100)]
    avg_fps = sum(fps_data) / len(fps_data)
    
    memory_usage = random.uniform(1.5, 8.0)
    gpu_usage = random.uniform(50, 95)
    cpu_usage = random.uniform(30, 85)
    
    # Bugs data
    bug_categories = ["Graphics", "Gameplay", "UI", "Audio", "Performance", "Networking"]
    bug_counts = [random.randint(2, 20) for _ in range(len(bug_categories))]
    total_bugs = sum(bug_counts)
    critical_bugs = random.randint(0, int(total_bugs * 0.2))
    major_bugs = random.randint(int(total_bugs * 0.2), int(total_bugs * 0.5))
    minor_bugs = total_bugs - critical_bugs - major_bugs
    
    # Gameplay metrics
    playtime_hours = random.uniform(20, 100)
    completion_rate = random.uniform(70, 98)
    player_deaths = random.randint(50, 500)
    achievement_completion = random.uniform(30, 90)
    
    # User satisfaction
    satisfaction_score = random.uniform(6.0, 9.8)
    
    # Platform performance
    platforms = ["Windows", "MacOS", "PlayStation", "Xbox", "Switch"]
    platform_scores = [random.uniform(6.0, 9.5) for _ in range(len(platforms))]
    
    # Generate detailed bugs list
    bugs_list = []
    bug_types = ["Crash", "Visual Glitch", "AI Issue", "Sound Bug", "Control Problem", "Loading Error", "Saving Issue"]
    severities = ["Critical", "Major", "Minor"]
    areas = ["Main Menu", "Level 1", "Level 2", "Character Creator", "Inventory", "Combat System", "Dialogue System"]
    # Dictionary mapping bug types to specific descriptions
    bug_descriptions = {
        "Crash": [
            "Game freezes and crashes to desktop when entering {area}",
            "Application terminates unexpectedly after {time} minutes of gameplay in {area}",
            "System memory error occurs when loading {area} with multiple enemies",
            "Game crashes when transitioning between {area} and another level",
            "Blue screen occurs on specific hardware configurations when entering {area}"
        ],
        "Visual Glitch": [
            "Textures fail to load properly in {area}, showing checkerboard patterns",
            "Character models clip through terrain in {area}",
            "Lighting effects flicker abnormally in {area}, especially near water surfaces",
            "Z-fighting occurs between overlapping objects in {area}",
            "Screen tearing visible during fast camera movements in {area}"
        ],
        "AI Issue": [
            "Enemy NPCs in {area} stop responding to player actions",
            "Companion AI gets stuck in pathfinding loops in narrow sections of {area}",
            "NPCs in {area} ignore collision with environmental objects",
            "Enemy difficulty scaling incorrectly in {area}, making encounters too easy/difficult",
            "AI characters in {area} exhibit erratic behavior during scripted events"
        ],
        "Sound Bug": [
            "Audio desynchronization during cutscenes in {area}",
            "Sound effects missing when performing specific actions in {area}",
            "Background music abruptly cuts out when entering {area}",
            "Echo effect inappropriately applied to dialogue in {area}",
            "Volume levels inconsistent between different audio sources in {area}"
        ],
        "Control Problem": [
            "Input lag detected when performing quick movements in {area}",
            "Controller mapping fails for specific actions in {area}",
            "Character movement becomes unresponsive after interacting with objects in {area}",
            "Double-input registered for single button presses in {area}",
            "Button prompts display incorrect keys/buttons in {area}"
        ],
        "Loading Error": [
            "Infinite loading screen when attempting to enter {area}",
            "Assets fail to load properly in {area}, resulting in missing objects",
            "Level streaming causes frame rate drops when moving quickly through {area}",
            "Loading checkpoint in {area} results in player spawning in wrong location",
            "Game state not properly preserved when loading saved game in {area}"
        ],
        "Saving Issue": [
            "Unable to save game progress when in {area}",
            "Save files become corrupted after performing specific actions in {area}",
            "Autosave feature fails to trigger at designated checkpoints in {area}",
            "Save data missing player inventory items acquired in {area}",
            "Multiple save attempts in {area} overwrite each other instead of creating new slots"
        ]
    }
    # Time periods for crash descriptions
    time_periods = ["5-10", "15-20", "30+", "2-3", "45+"]
    
    for i in range(min(20, total_bugs)):
        bug_type = random.choice(bug_types)
        area = random.choice(areas)
        
        # Get a random description template for this bug type
        description_template = random.choice(bug_descriptions[bug_type])
        
        # Replace placeholders in the template
        description = description_template
        if "{area}" in description_template:
            description = description_template.replace("{area}", area)
        if "{time}" in description_template:
            description = description.replace("{time}", random.choice(time_periods))
        
        bugs_list.append({
            "id": f"BUG-{i+1:03d}",
            "type": bug_type,
            "severity": random.choice(severities),
            "area": area,
            "description": description,
            "reproducible": random.choice([True, False, True, True]),
            "fixed": random.choice([True, False, False, False])
        })
    
    # Performance over time
    timestamps = [datetime.now().timestamp() - (i * 3600) for i in range(24, 0, -1)]
    dates = [datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') for ts in timestamps]
    perf_over_time = [{"timestamp": dates[i], "fps": random.uniform(40, 120), 
                       "memory": random.uniform(1.5, 8.0), "cpu": random.uniform(30, 85)} 
                      for i in range(len(dates))]
    
    results = {
        "game_name": game_name,
        "test_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "avg_fps": avg_fps,
            "memory_usage_gb": memory_usage,
            "gpu_usage_percent": gpu_usage,
            "cpu_usage_percent": cpu_usage,
            "total_bugs": total_bugs,
            "critical_bugs": critical_bugs,
            "major_bugs": major_bugs,
            "minor_bugs": minor_bugs,
            "playtime_hours": playtime_hours,
            "completion_rate": completion_rate,
            "player_deaths": player_deaths,
            "achievement_completion": achievement_completion,
            "satisfaction_score": satisfaction_score
        },
        "detailed_performance": {
            "fps_data": fps_data,
            "performance_over_time": perf_over_time
        },
        "bugs_by_category": {
            "categories": bug_categories,
            "counts": bug_counts
        },
        "platform_performance": {
            "platforms": platforms,
            "scores": platform_scores
        },
        "detailed_bugs": bugs_list,
        "recommendations": generate_recommendations(game_name, avg_fps, total_bugs, satisfaction_score)
    }
    
    return results

def generate_recommendations(game_name, fps, bugs, satisfaction):
    recommendations = []
    
    if fps < 60:
        recommendations.append("Optimize game performance to improve frame rates, especially during combat sequences.")
    
    if bugs > 15:
        recommendations.append("Prioritize bug fixing, particularly for critical issues affecting game progression.")
    
    if satisfaction < 7.5:
        recommendations.append("Address user feedback regarding game mechanics and interface usability.")
    
    generic_recommendations = [
        f"Consider adding more difficulty options to make {game_name} accessible to broader audiences.",
        "Implement additional player tutorials for complex game mechanics.",
        "Review loading times and optimize asset loading procedures.",
        "Evaluate balance of in-game economy and progression systems.",
        "Consider expanding end-game content to increase replayability."
    ]
    
    # Add some generic recommendations
    for _ in range(min(3, 5 - len(recommendations))):
        rec = random.choice(generic_recommendations)
        if rec not in recommendations:
            recommendations.append(rec)
            generic_recommendations.remove(rec)
    
    return recommendations

# Function to display chatbot
def display_chat():
    chat_container = st.container()
    
    with chat_container:
        # Only display chat icon if chat is not visible
        if not st.session_state.chat_visible:
            if st.button("💬", key="chat_icon"):
                st.session_state.chat_visible = True
                st.rerun()

        # Only display if chat is visible
        if st.session_state.chat_visible:
            st.markdown('<div class="chat-container">', unsafe_allow_html=True)
            
            # Chat header with minimize button
            st.markdown(
                """
                <div class="chat-header">
                    <span>Game Test Assistant</span>
                </div>
                <div id="chat-content">
                """, 
                unsafe_allow_html=True
            )
            
            # Minimize button using Streamlit
            if st.button("−", key="minimize_chat"):
                st.session_state.chat_visible = False
                st.rerun()
            
            # Chat messages
            st.markdown('<div class="chat-box">', unsafe_allow_html=True)
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    if msg.get("type") == "image":
                        st.markdown(f'<div class="user-message">{msg["content"]}<br><img src="data:image/png;base64,{msg["image_data"]}" class="message-image"></div>', unsafe_allow_html=True)
                    elif msg.get("type") == "file":
                        st.markdown(f'<div class="user-message">{msg["content"]}<br><div class="file-info">File: {msg["file_name"]}</div></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="user-message">{msg["content"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="bot-message">{msg["content"]}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Chat input and file upload
            with st.form(key="chat_form", clear_on_submit=True):
                # File upload section
                uploaded_file = st.file_uploader("Upload file or image", type=["png", "jpg", "jpeg", "pdf", "txt", "csv", "json", "py", "js", "html", "css"], 
                                                 label_visibility="collapsed", accept_multiple_files=False)
                
                # Preview uploaded file if it's an image
                if uploaded_file is not None and uploaded_file.type.startswith('image/'):
                    image = Image.open(uploaded_file)
                    st.image(image, caption="Image preview", use_container_width=True, clamp=True)
                    
                # Text input for user message
                user_input = st.text_input("Type your message:", key="user_input", placeholder="Ask me about game testing or upload a file...", label_visibility="collapsed")
                
                # Submit button
                submit_button = st.form_submit_button("Send")
                
                if submit_button and (user_input or uploaded_file):
                    # Add user message to chat history
                    if uploaded_file is not None:
                        # Handle file upload
                        file_type = uploaded_file.type
                        
                        # For image files
                        if file_type.startswith('image/'):
                            image = Image.open(uploaded_file)
                            img_data = encode_image(image)
                            message_text = user_input if user_input else f"I've uploaded an image: {uploaded_file.name}"
                            st.session_state.messages.append({
                                "role": "user", 
                                "content": message_text,
                                "type": "image",
                                "image_data": img_data
                            })
                        # For other files
                        else:
                            message_text = user_input if user_input else f"I've uploaded a file: {uploaded_file.name}"
                            st.session_state.messages.append({
                                "role": "user", 
                                "content": message_text,
                                "type": "file",
                                "file_name": uploaded_file.name
                            })
                    else:
                        # Normal text message
                        st.session_state.messages.append({"role": "user", "content": user_input, "type": "text"})
                    
                    # Get API key from session state
                    api_key = st.session_state.gemini_api_key
                    
                    # Get response from API
                    with st.spinner("Assistant is thinking..."):
                        response = get_chat_response(st.session_state.messages, api_key, uploaded_file)
                        st.session_state.messages.append({"role": "assistant", "content": response, "type": "text"})
                    
                    st.rerun()
            
            st.markdown('</div></div>', unsafe_allow_html=True)

# Main Application Logic
st.title("🎮 Game Tester Dashboard")

# API Key container (instead of sidebar)
# with st.expander("API Key Configuration", expanded=False):
#     gemini_api_key = st.text_input(
#         "Gemini API Key", 
#         value=st.session_state.gemini_api_key,
#         type="password",
#         help="Enter your Gemini API key. Get one at https://ai.google.dev/"
#     )
    
#     if gemini_api_key:
#         st.session_state.gemini_api_key = gemini_api_key
    
#     st.markdown("### About")
#     st.info(
#         """
#         This dashboard helps game developers test their games and get comprehensive reports.
#         Enter your game name and get detailed analytics about performance, bugs, and player experience.
#         Use the chatbot for personalized assistance and upload files/images for analysis.
#         """
#     )

# Main content - Use full width since sidebar is removed
st.header("Game Test Analysis")

# Game input form
with st.form(key="game_form"):
    game_name = st.selectbox("Select Game Name", options=[""] + sorted(VALID_GAMES), index=0, placeholder="Choose a game...")
    submit_button = st.form_submit_button("Generate Test Report")
    
    if submit_button and game_name:
        st.session_state.game_name = game_name
        st.session_state.loading = True
        st.session_state.report_generated = False

# Show loading animation
if st.session_state.loading and not st.session_state.report_generated:
    with st.spinner(f"Running tests for {st.session_state.game_name}..."):
        # Simulate processing time
        progress_bar = st.progress(0)
        for i in range(100):
            time.sleep(0.03)  # Adjust for desired loading time
            progress_bar.progress(i + 1)
        
        # Generate test data
        st.session_state.test_results = generate_test_data(st.session_state.game_name)
        st.session_state.loading = False
        st.session_state.report_generated = True if st.session_state.test_results is not None else False
        st.rerun()

# Display report if generated
if st.session_state.report_generated and st.session_state.test_results:
    results = st.session_state.test_results
    
    # Top metrics
    st.subheader(f"Test Results for: {results['game_name']}")
    st.markdown(f"**Test Date:** {results['test_date']}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Avg. FPS", f"{results['summary']['avg_fps']:.1f}")
    with col2:
        st.metric("Total Bugs", str(results['summary']['total_bugs']))
    with col3:
        st.metric("Satisfaction", f"{results['summary']['satisfaction_score']:.1f}/10")
    with col4:
        st.metric("Test Hours", f"{results['summary']['playtime_hours']:.1f}")
    
    # Performance metrics
    st.markdown("### Performance Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # FPS Distribution
        st.markdown('<div class="report-card">', unsafe_allow_html=True)
        st.subheader("FPS Distribution")
        fig = px.histogram(
            x=results['detailed_performance']['fps_data'],
            nbins=20,
            labels={'x': 'FPS', 'y': 'Frequency'},
            color_discrete_sequence=['#4CAF50']
        )
        fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))  # Remove gridlines
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        # Resource Usage
        st.markdown('<div class="report-card">', unsafe_allow_html=True)
        st.subheader("Resource Utilization")
        resources = ['CPU', 'GPU', 'Memory (GB)']
        values = [
            results['summary']['cpu_usage_percent'],
            results['summary']['gpu_usage_percent'],
            results['summary']['memory_usage_gb']
        ]
        
        fig = go.Figure(data=[
            go.Bar(
                x=resources, 
                y=values,
                marker_color=['#FFA500', '#4CAF50', '#2196F3']
            )
        ])
        fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))  # Remove gridlines
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Performance over time
    st.markdown('<div class="report-card">', unsafe_allow_html=True)
    st.subheader("Performance Over Time")
    
    perf_df = pd.DataFrame(results['detailed_performance']['performance_over_time'])
    
    fig = px.line(
        perf_df, 
        x='timestamp', 
        y=['fps', 'cpu', 'memory'],
        labels={'value': 'Value', 'variable': 'Metric', 'timestamp': 'Time'},
        title="Performance Metrics During Testing"
    )
    fig.update_layout(margin=dict(l=20, r=20, t=50, b=20), xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))  # Remove gridlines
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Bugs analysis
    col1, col2 = st.columns(2)
    
    with col1:
        # Bug distribution by category
        st.markdown('<div class="report-card">', unsafe_allow_html=True)
        st.subheader("Bugs by Category")
        
        bug_df = pd.DataFrame({
            'Category': results['bugs_by_category']['categories'],
            'Count': results['bugs_by_category']['counts']
        })
        
        fig = px.pie(
            bug_df, 
            values='Count', 
            names='Category',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))  # Remove gridlines
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        # Bug severity
        st.markdown('<div class="report-card">', unsafe_allow_html=True)
        st.subheader("Bug Severity")
        
        severities = ['Critical', 'Major', 'Minor']
        counts = [
            results['summary']['critical_bugs'],
            results['summary']['major_bugs'],
            results['summary']['minor_bugs']
        ]
        
        fig = go.Figure(data=[
            go.Bar(
                x=severities,
                y=counts,
                marker_color=[' #FF0000', '#FFA500', '#FFFF00']
            )
        ])
        fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))  # Remove gridlines
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Platform comparison
    st.markdown('<div class="report-card">', unsafe_allow_html=True)
    st.subheader("Performance Across Platforms")
    
    platform_df = pd.DataFrame({
        'Platform': results['platform_performance']['platforms'],
        'Score': results['platform_performance']['scores']
    })
    
    fig = px.bar(
        platform_df,
        x='Platform',
        y='Score',
        color='Score',
        color_continuous_scale='Viridis',
        labels={'Score': 'Performance Score'}
    )
    fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))  # Remove gridlines
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Detailed bugs list
    st.markdown('<div class="report-card">', unsafe_allow_html=True)
    st.subheader("Detailed Bug List")
    
    bugs_df = pd.DataFrame(results['detailed_bugs'])
    st.dataframe(
        bugs_df,
        column_config={
            "id": "Bug ID",
            "type": "Type",
            "severity": st.column_config.SelectboxColumn(
                "Severity",
                help="Bug severity level",
                width="medium",
                options=["Critical", "Major", "Minor"],
            ),
            "area": "Area",
            "description": "Description",
            "reproducible": "Reproducible",
            "fixed": "Fixed"
        },
        use_container_width=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Recommendations
    st.markdown('<div class="report-card">', unsafe_allow_html=True)
    st.subheader("Recommendations")
    
    for i, rec in enumerate(results['recommendations']):
        st.markdown(f"**{i+1}.** {rec}")
    
    st.markdown('</div>', unsafe_allow_html=True)
elif st.session_state.loading == False and st.session_state.game_name and not st.session_state.report_generated:
    st.error(f"Game '{st.session_state.game_name}' not found in our database. Please enter a valid game name.")

# Ensure chatbot is displayed regardless of report status
display_chat()