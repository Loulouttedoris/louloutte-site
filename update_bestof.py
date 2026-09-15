import os
import re
import requests
from datetime import datetime, timezone

API_KEY = os.environ["YOUTUBE_API_KEY"]
HANDLE = "@louloutte_doris"

BASE_URL = "https://www.googleapis.com/youtube/v3"


def api_get(endpoint, params):
    params["key"] = API_KEY
    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        params=params,
        timeout=30
    )
    response.raise_for_status()
    return response.json()


# 1. Trouver la chaîne à partir de son nom @
channel_data = api_get(
    "channels",
    {
        "part": "contentDetails",
        "forHandle": HANDLE
    }
)

if not channel_data.get("items"):
    raise RuntimeError("Chaîne YouTube introuvable.")

channel = channel_data["items"][0]
uploads_playlist = channel["contentDetails"]["relatedPlaylists"]["uploads"]


# 2. Récupérer les dernières vidéos de la chaîne
playlist_data = api_get(
    "playlistItems",
    {
        "part": "contentDetails",
        "playlistId": uploads_playlist,
        "maxResults": 50
    }
)

video_ids = [
    item["contentDetails"]["videoId"]
    for item in playlist_data.get("items", [])
]


if not video_ids:
    raise RuntimeError("Aucune vidéo trouvée.")


# 3. Récupérer les statistiques et la durée
videos_data = api_get(
    "videos",
    {
        "part": "snippet,statistics,contentDetails",
        "id": ",".join(video_ids)
    }
)


def duration_to_seconds(duration):
    match = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        duration
    )

    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return hours * 3600 + minutes * 60 + seconds


# 4. Garder les vidéos courtes
#
# YouTube ne fournit pas directement un champ "isShort"
# dans cette API. On utilise donc une durée maximale de 3 minutes,
# ce qui correspond à la limite actuelle des Shorts.
shorts = []

for video in videos_data.get("items", []):
    duration = duration_to_seconds(
        video["contentDetails"].get("duration", "")
    )

    if duration > 180:
        continue

    stats = video.get("statistics", {})
    snippet = video.get("snippet", {})

    views = int(stats.get("viewCount", 0))
    likes = int(stats.get("likeCount", 0))

    published = snippet.get("publishedAt", "")

    try:
        published_date = datetime.fromisoformat(
            published.replace("Z", "+00:00")
        )
    except Exception:
        published_date = datetime(2000, 1, 1, tzinfo=timezone.utc)

    age_days = max(
        1,
        (datetime.now(timezone.utc) - published_date).days
    )

    # Classement :
    # - beaucoup de vues = très important
    # - likes = bonus
    # - vidéos récentes = petit bonus
    score = (
        views
        + (likes * 5)
        + (10000 / age_days)
    )

    shorts.append({
        "id": video["id"],
        "score": score
    })


# 5. Trier et garder les 5 meilleurs
shorts.sort(
    key=lambda video: video["score"],
    reverse=True
)

top5 = shorts[:5]


if len(top5) < 5:
    raise RuntimeError(
        f"Seulement {len(top5)} Short(s) trouvé(s). "
        "Il en faut au moins 5."
    )


# 6. Mettre à jour bestof.html
with open("bestof.html", "r", encoding="utf-8") as file:
    html = file.read()


for index, video in enumerate(top5, start=1):
    video_id = video["id"]

    # Remplace VIDEO_ID_1, VIDEO_ID_2, etc.
    html = html.replace(
        f"VIDEO_ID_{index}",
        video_id
    )


with open("bestof.html", "w", encoding="utf-8") as file:
    file.write(html)


print("✅ Best Of mis à jour avec les 5 meilleurs Shorts :")

for index, video in enumerate(top5, start=1):
    print(f"{index}. https://www.youtube.com/shorts/{video['id']}")
