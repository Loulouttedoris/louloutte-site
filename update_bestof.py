
import os
import re
import requests
from datetime import datetime, timezone

API_KEY = os.environ["YOUTUBE_API_KEY"]
HANDLE = "@louloutte_doris"

BASE_URL = "https://www.googleapis.com/youtube/v3"


def api_get(endpoint, params):
    params = params.copy()
    params["key"] = API_KEY

    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        params=params,
        timeout=30
    )
    response.raise_for_status()
    return response.json()


# 1. Trouver la chaîne
channel_data = api_get(
    "channels",
    {
        "part": "contentDetails",
        "forHandle": HANDLE
    }
)

if not channel_data.get("items"):
    raise RuntimeError("Chaîne YouTube introuvable.")

uploads_playlist = (
    channel_data["items"][0]
    ["contentDetails"]["relatedPlaylists"]["uploads"]
)


# 2. Récupérer toutes les vidéos de la chaîne
video_ids = []
next_page_token = None

while True:
    params = {
        "part": "contentDetails",
        "playlistId": uploads_playlist,
        "maxResults": 50
    }

    if next_page_token:
        params["pageToken"] = next_page_token

    data = api_get("playlistItems", params)

    for item in data.get("items", []):
        video_id = item["contentDetails"].get("videoId")

        if video_id:
            video_ids.append(video_id)

    next_page_token = data.get("nextPageToken")

    if not next_page_token:
        break

if not video_ids:
    raise RuntimeError("Aucune vidéo trouvée.")


print(f"{len(video_ids)} vidéos trouvées.")


# 3. Convertir les durées YouTube en secondes
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


# 4. Récupérer les statistiques par groupes de 50
shorts = []

for start in range(0, len(video_ids), 50):

    batch = video_ids[start:start + 50]

    videos_data = api_get(
        "videos",
        {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(batch)
        }
    )

    for video in videos_data.get("items", []):

        duration = duration_to_seconds(
            video["contentDetails"].get("duration", "")
        )

        # Conserver les vidéos de 3 minutes maximum
        if duration > 180 or duration == 0:
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
        except (ValueError, TypeError):
            published_date = datetime(
                2000, 1, 1, tzinfo=timezone.utc
            )

        age_days = max(
            1,
            (datetime.now(timezone.utc) - published_date).days
        )

        score = (
            views
            + (likes * 5)
            + (10000 / age_days)
        )

        shorts.append({
            "id": video["id"],
            "score": score,
            "views": views,
            "likes": likes
        })


# 5. Classer les meilleurs Shorts
shorts.sort(
    key=lambda video: video["score"],
    reverse=True
)

top5 = shorts[:5]

if len(top5) < 5:
    raise RuntimeError(
        f"Seulement {len(top5)} vidéos de 3 minutes "
        f"ou moins trouvées. Il en faut 5."
    )


# 6. Lire le fichier HTML
with open("bestof.html", "r", encoding="utf-8") as file:
    html = file.read()


# 7. Remplacer les cinq identifiants
for index, video in enumerate(top5, start=1):

    marker = f"VIDEO_ID_{index}"

    if marker not in html:
        raise RuntimeError(
            f"Marqueur {marker} introuvable dans bestof.html"
        )

    html = html.replace(
        marker,
        video["id"]
    )


# 8. Enregistrer le nouveau Best Of
with open("bestof.html", "w", encoding="utf-8") as file:
    file.write(html)


print("\nBEST OF LOULOUTTE ACTUALISÉ !")

for index, video in enumerate(top5, start=1):

    print(
        f"{index}. https://www.youtube.com/shorts/"
        f"{video['id']} | "
        f"{video['views']} vues | "
        f"{video['likes']} J'aime"
    )
