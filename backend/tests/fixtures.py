VIDEO_ID = "dQw4w9WgXcQ"
CHANNEL_ID = "UCuAXFkgsw1L7xaCfnd5JJOw"

VIDEOS_RESPONSE = {
    "items": [
        {
            "id": VIDEO_ID,
            "snippet": {
                "publishedAt": "2026-01-01T00:00:00Z",
                "channelId": CHANNEL_ID,
                "channelTitle": "Example Channel",
                "title": "Example Video",
                "description": "Example description",
                "thumbnails": {
                    "default": {"url": "https://i.ytimg.com/default.jpg"},
                    "high": {"url": "https://i.ytimg.com/high.jpg"},
                },
                "categoryId": "28",
                "defaultAudioLanguage": "en",
            },
            "contentDetails": {"duration": "PT9M2S", "caption": "true"},
            "statistics": {"viewCount": "100000", "likeCount": "5000", "commentCount": "500"},
        }
    ]
}

CHANNELS_RESPONSE = {
    "items": [
        {
            "id": CHANNEL_ID,
            "snippet": {
                "title": "Example Channel",
                "description": "About",
                "customUrl": "@example",
                "publishedAt": "2010-05-05T00:00:00Z",
                "thumbnails": {"default": {"url": "https://i.ytimg.com/ch.jpg"}},
            },
            "statistics": {"subscriberCount": "12345", "viewCount": "999999", "videoCount": "42"},
            "contentDetails": {"relatedPlaylists": {"uploads": "UUuAXFkgsw1L7xaCfnd5JJOw"}},
        }
    ]
}

PLAYLIST_RESPONSE = {
    "nextPageToken": "NEXT",
    "items": [{"contentDetails": {"videoId": VIDEO_ID}}],
}

QUOTA_ERROR = {
    "error": {"code": 403, "message": "quota", "errors": [{"reason": "quotaExceeded"}]}
}
