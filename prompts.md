You are a senior full-stack engineer extending an existing hackathon project called:

# Retention Predictor

### Find the Drop-Off Before You Publish

We already have the first phase working:

* Next.js frontend
* TypeScript
* Tailwind/shadcn UI
* FastAPI backend
* PostgreSQL/Supabase
* YouTube Data API v3 API-key integration
* Public YouTube video URL analysis
* Public video/channel metadata retrieval
* API-key stored only on the backend

Now implement the **creator authentication + YouTube Analytics + YouTube Reporting foundation**.

The goal of this phase is to make the application feel like a lightweight, custom version of **YouTube Studio specifically focused on retention and video analytics**.

Do NOT implement the machine-learning model yet.

Our friends will add the Random Forest/XGBoost/retention prediction pipeline later.

The current task is ONLY:

**Google/YouTube OAuth login + identify the creator's channel + retrieve channel analytics + retrieve video analytics + retrieve audience retention + retrieve bulk reports + build the analytics dashboard + create clean ML integration contracts.**

---

# IMPORTANT API AUTHENTICATION MODEL

Do NOT create separate API-key based authentication for YouTube Analytics and YouTube Reporting.

These APIs use OAuth 2.0.

Use one Google OAuth 2.0 Web Application client.

The existing YouTube Data API key remains available for public Data API operations.

The architecture should be:

```text
Public Video Mode
    ↓
YouTube Data API v3
    ↓
API Key

Creator Mode
    ↓
Google OAuth 2.0
    ↓
OAuth access/refresh token
    ↓
YouTube Data API
YouTube Analytics API
YouTube Reporting API
```

Google's official OAuth documentation states that YouTube Analytics and YouTube Reporting use OAuth 2.0 for private user data.

---

# REQUIRED OAUTH SCOPES

Use the minimum scopes required.

Primary Analytics scope:

```text
https://www.googleapis.com/auth/yt-analytics.readonly
```

This is required to read YouTube Analytics reports.

Use:

```text
https://www.googleapis.com/auth/youtube.readonly
```

because we need to identify the authenticated user's YouTube channel using:

```text
channels.list
mine=true
```

and retrieve its uploads playlist and related public channel/video information.

Do NOT request write permissions such as:

```text
https://www.googleapis.com/auth/youtube
```

because this application should be read-only.

Do NOT request:

```text
https://www.googleapis.com/auth/yt-analytics-monetary.readonly
```

unless explicitly needed later.

No monetization functionality is required in this phase.

---

# GOOGLE CLOUD CONFIGURATION

Create/update documentation explaining that the developer must enable these APIs in Google Cloud:

1. YouTube Data API v3
2. YouTube Analytics API
3. YouTube Reporting API

Create OAuth credentials:

```text
Credentials
→ Create Credentials
→ OAuth Client ID
→ Web Application
```

Development redirect URI:

```text
http://localhost:8000/api/auth/youtube/callback
```

or whatever backend callback route is implemented.

The redirect URI must exactly match the URI configured in Google Cloud.

Production URI should later be:

```text
https://YOUR_BACKEND_DOMAIN/api/auth/youtube/callback
```

Do not hardcode production URLs.

---

# ENVIRONMENT VARIABLES

Extend `.env.example`.

Use:

```env
YOUTUBE_API_KEY=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/youtube/callback

DATABASE_URL=

FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

SESSION_SECRET=
```

Never expose:

```text
GOOGLE_CLIENT_SECRET
YOUTUBE_API_KEY
SESSION_SECRET
refresh tokens
access tokens
```

to the frontend.

Never use:

```text
NEXT_PUBLIC_GOOGLE_CLIENT_SECRET
NEXT_PUBLIC_YOUTUBE_API_KEY
```

Do not put secrets in browser JavaScript.

---

# HIGH-LEVEL PRODUCT FLOW

The application should now have two major entry points.

## PAGE 1 — LOGIN

Route:

```text
/login
```

Purpose:

Allow the creator to securely connect their YouTube/Google account.

UI:

```text
                 RETAINAI

        Understand your audience.
        Predict where viewers leave.

       ┌───────────────────────────┐
       │                           │
       │     Connect YouTube       │
       │                           │
       │   [ Continue with Google ]│
       │                           │
       └───────────────────────────┘

     We only request read-only access
     to your YouTube analytics.
```

Do NOT create an email/password authentication system.

Use Google OAuth.

The button should call:

```text
GET /api/auth/youtube/login
```

which redirects to Google's OAuth server.

---

# OAUTH FLOW

Implement the standard server-side web application OAuth flow.

Flow:

```text
Browser
   ↓
GET /api/auth/youtube/login
   ↓
FastAPI generates Google OAuth URL
   ↓
Google login/consent
   ↓
Google redirects to
/api/auth/youtube/callback?code=...
   ↓
FastAPI exchanges authorization code
   ↓
receive access_token + refresh_token
   ↓
retrieve authenticated channel
   ↓
create/update application user
   ↓
create authenticated session
   ↓
redirect frontend to /dashboard
```

Use the OAuth `state` parameter and validate it on callback to prevent CSRF.

Use a server-side authorization-code flow.

Do not put access tokens in the URL.

---

# TOKEN STORAGE

The application needs to support long-lived access to analytics.

Store refresh tokens securely server-side.

Never send refresh tokens to the browser.

Suggested database tables:

## users

```text
id
google_sub
email
name
profile_image
created_at
updated_at
```

## oauth_accounts

```text
id
user_id
provider
access_token_encrypted
refresh_token_encrypted
expires_at
scope
created_at
updated_at
```

Use encryption or a clearly isolated secure storage mechanism for tokens.

At minimum, never store tokens in plain client-side storage.

Do not use:

```text
localStorage
sessionStorage
frontend cookies containing refresh tokens
```

Use secure server-side sessions.

For cookies use appropriate flags:

```text
HttpOnly
Secure in production
SameSite=Lax or Strict
```

---

# IDENTIFY THE USER'S YOUTUBE CHANNEL

After OAuth succeeds:

Call YouTube Data API:

```text
channels.list
```

with:

```text
part=snippet,contentDetails,statistics
mine=true
```

The `mine=true` request must be OAuth-authorized.

Store:

```text
channel_id
channel title
description
thumbnail
published_at
subscriber count
view count
video count
uploads playlist ID
```

in the database.

The uploads playlist ID is important.

The authenticated channel's uploads playlist can then be used with:

```text
playlistItems.list
```

to retrieve the channel's uploaded videos.

---

# CHANNEL TABLE

Extend the existing database schema.

Create/update:

## youtube_channels

```text
id
user_id
youtube_channel_id
title
description
custom_url
thumbnail_url
published_at
subscriber_count
total_views
video_count
uploads_playlist_id
created_at
updated_at
last_synced_at
```

Add a unique constraint on:

```text
youtube_channel_id
```

---

# VIDEO TABLE

Extend the existing video schema.

Store:

```text
id
youtube_video_id
channel_id
title
description
thumbnail_url
published_at
duration_seconds
category_id
category_name
view_count
like_count
comment_count
privacy_status
upload_position
created_at
updated_at
```

Do not assume every video is public.

Handle deleted/private/unavailable videos gracefully.

---

# PAGE 2 — CREATOR ANALYTICS DASHBOARD

Route:

```text
/dashboard
```

This is the main product page.

It should look visually similar to a modern analytics product / YouTube Studio, but should NOT copy YouTube's branding.

The dashboard is focused specifically on the Retention Predictor product.

---

# DASHBOARD LAYOUT

Header:

```text
RETAINAI

[Creator channel name]

Overview
Videos
Retention
Audience
Traffic
[Sync Data]
[Logout]
```

Main sections:

1. Channel Overview
2. Performance Summary
3. Video Library
4. Audience Retention
5. Traffic Sources
6. Audience/Geography
7. Device/OS
8. ML Readiness
9. Future Retention Prediction

---

# CHANNEL OVERVIEW

Display cards such as:

```text
Views
Watch Time
Average View Duration
Average View Percentage
Subscribers Gained
Subscribers Lost
```

Also calculate:

```text
Net Subscribers
```

as:

```text
subscribersGained - subscribersLost
```

Do not invent values.

Use data returned by the Analytics API.

---

# DATE RANGE CONTROL

Add:

```text
Last 7 days
Last 28 days
Last 90 days
Last 365 days
Custom
```

Default:

```text
Last 28 days
```

Backend should send:

```text
startDate
endDate
```

to the Analytics API.

Do not hardcode date ranges.

---

# CHANNEL ANALYTICS API

Use the YouTube Analytics API for interactive reports.

Important metrics may include:

```text
views
engagedViews
estimatedMinutesWatched
averageViewDuration
averageViewPercentage
likes
comments
shares
subscribersGained
subscribersLost
```

Only request metrics supported by the specific Analytics report.

Handle unsupported metric combinations gracefully.

---

# OVERVIEW CHARTS

Create charts such as:

## Views Over Time

X-axis:

```text
date
```

Y-axis:

```text
views
```

---

## Watch Time

Display:

```text
estimatedMinutesWatched
```

over time.

---

## Subscriber Growth

Graph:

```text
subscribersGained
subscribersLost
```

and show net change.

---

# VIDEO LIBRARY

Create a section:

```text
Your Videos
```

Display every available uploaded video using pagination.

Table columns:

```text
Thumbnail
Title
Published
Duration
Views
Watch Time
Avg View Duration
Avg View %
Likes
Comments
Subscribers Gained
```

Add:

```text
Search
Sort
Filter
Pagination
```

Filters:

```text
Newest
Oldest
Most Views
Highest Avg View %
Lowest Avg View %
Longest
Shortest
```

Do not load thousands of videos into the browser simultaneously.

Use backend pagination and caching.

---

# IMPORTANT: VIDEO METRICS

For video-level Analytics, design an efficient system.

The Analytics API allows filtering by video IDs and supports multiple video IDs for many reports, with up to 500 IDs in a filter; however, audience-retention queries are different and require a single video ID. Use this distinction when implementing the service.

For normal video performance metrics, prefer efficient batched Analytics requests where the report supports them.

Do NOT make unnecessary one-request-per-video calls for ordinary aggregate metrics.

For retention:

```text
one video at a time
```

---

# VIDEO DETAIL INTERACTION

When the user clicks a video:

Open a dedicated analytics drawer/modal or route within the dashboard.

Do not require a complete new page unless necessary.

Show:

```text
Video Thumbnail
Title
Duration
Published Date
```

Then:

```text
Views
Watch Time
Average View Duration
Average View %
Likes
Comments
Subscribers Gained
Subscribers Lost
```

---

# AUDIENCE RETENTION

This is the most important part of the application.

For a selected video, query the YouTube Analytics API's audience retention report.

Use:

```text
dimension:
elapsedVideoTimeRatio

metrics:
audienceWatchRatio
relativeRetentionPerformance
```

Optionally retrieve:

```text
startedWatching
stoppedWatching
```

when supported by the relevant report.

The API's audience retention uses elapsed video time ratio, meaning the curve is normalized across the duration of the video.

Transform the returned data into:

```json
{
  "video_id": "VIDEO_ID",
  "points": [
    {
      "time_ratio": 0.00,
      "audience_watch_ratio": 1.0,
      "relative_retention_performance": 1.0
    }
  ]
}
```

Do not invent or smooth data in a way that changes its meaning.

You may create a display-friendly interpolation ONLY for visualization and clearly distinguish raw points from interpolated display values.

---

# RETENTION GRAPH

Build a high-quality interactive chart:

```text
Audience Retention

100% ─────╮
           ╲
            ╲
             ╲────
                  ╲
                   ╲────
                        ╲
                         ╰──
0% ─────────────────────────────
0:00                      10:00
```

Hover should show:

```text
00:42
Audience watching: 81.4%
Relative performance: 1.17x
```

Do not call the metric simply "retention %" if the underlying metric is actually `audienceWatchRatio`.

Use correct labels.

---

# DROP-OFF VISUALIZATION

For the current non-ML version, DO NOT claim that the system has predicted a drop-off.

Instead show:

### Observed Audience Behavior

Using actual YouTube Analytics data:

```text
Largest observed declines
```

where derivable from the retention data.

Mark observed changes on the graph.

Later, the ML model will replace this with:

```text
Predicted Drop-Off Risk
```

Do not mix observed and predicted data.

---

# RELATIVE RETENTION

Display:

```text
Relative Retention Performance
```

Explain briefly:

```text
How this video's audience retention compares
with other videos of similar length.
```

Do not convert this into an arbitrary "score out of 100."

Preserve the actual metric semantics.

---

# TRAFFIC SOURCE SECTION

Create:

```text
Traffic Sources
```

Show available traffic source dimensions/metrics.

Examples may include:

```text
YouTube Search
Suggested Videos
Browse Features
External
Direct or Unknown
Playlists
```

Use the values returned by the Analytics API.

Display:

* views
* watch time where supported
* average view duration where supported

Use a bar chart or table.

---

# AUDIENCE / GEOGRAPHY

Create:

```text
Top Viewer Countries
```

Use country-based reports where available.

Display:

```text
Country
Views
Watch Time
Average View Duration
Average View %
```

Do not infer sensitive personal attributes.

Use the aggregated analytics returned by YouTube.

---

# DEVICE / PLATFORM

Display:

```text
Viewer Devices
```

Examples:

```text
Mobile
Desktop
TV
Tablet
Game Console
```

based on returned API dimensions.

Show:

```text
Views
Watch Time
Average View Duration
Average View %
```

where supported.

---

# VIDEO PERFORMANCE TABLE

Create a chart/table that lets a creator identify their strongest and weakest existing videos.

Show:

```text
Title
Views
Average View %
Average View Duration
Subscribers Gained
```

Provide sorting.

Do NOT create a ranking called "best creator" or anything unrelated to the user's own videos.

This is simply their own channel performance.

---

# CHANNEL INSIGHTS

For this phase, do NOT use an LLM.

Instead compute basic descriptive statistics from the Analytics API data.

Examples:

```text
Average View %
Median View %
Average View Duration
Median View Duration
Average Views per Video
```

Also show:

```text
Videos analyzed
```

and date range.

These are descriptive analytics only.

---

# REPORTING API

Integrate the YouTube Reporting API as a separate service.

IMPORTANT:

Do not pretend that Reporting API behaves like the interactive Analytics API.

Reporting API is intended for bulk reports and scheduled report generation.

Use it for:

```text
Historical data synchronization
Bulk channel video activity
Historical analytics archive
```

Create a reporting service:

```text
services/youtube_reporting_service.py
```

Support:

```text
reportTypes.list
jobs.list
jobs.create
jobs.get
jobs.reports.list
jobs.reports.get
```

Use the user's OAuth credentials.

For the current prototype, implement the infrastructure needed to request a useful channel report, especially:

```text
channel_basic_a3
```

where appropriate.

Do not download huge reports on every dashboard load.

---

# REPORTING JOB DESIGN

Create database tables:

## youtube_reporting_jobs

```text
id
user_id
youtube_job_id
report_type
status
created_at
updated_at
last_report_at
```

## youtube_reports

```text
id
job_id
youtube_report_id
start_time
end_time
download_url
created_at
processed_at
```

If a reporting job does not exist:

```text
create job
```

Then let a sync process retrieve generated reports.

Do NOT block the dashboard waiting for a daily bulk report.

The dashboard should use Analytics API data for immediate results.

---

# DATA SYNC SERVICE

Create:

```text
services/youtube_sync_service.py
```

Responsibilities:

1. Identify authenticated channel
2. Fetch channel metadata
3. Fetch uploads playlist
4. Fetch uploaded videos
5. Normalize videos
6. Store/update videos
7. Fetch available Analytics summaries
8. Store analytics
9. Schedule/update Reporting jobs
10. Record last synchronization time

Make the sync process idempotent.

Running it twice should update existing records instead of duplicating them.

---

# SYNC BUTTON

On dashboard:

```text
[ Sync YouTube Data ]
```

When clicked:

```text
Starting sync...
Fetching channel...
Fetching videos...
Fetching analytics...
Updating database...
Done.
```

Do not freeze the browser.

Use a background job where appropriate.

Return a job ID:

```json
{
  "sync_id": "uuid",
  "status": "started"
}
```

Then expose:

```text
GET /api/sync/{sync_id}
```

to retrieve status.

---

# CACHING

Do not repeatedly request the same Analytics data.

Store analytics results in PostgreSQL with:

```text
user_id
channel_id
video_id
report_type
start_date
end_date
metrics
fetched_at
```

Before making a new request:

```text
check cache
```

Use a reasonable freshness period.

Allow manual refresh from the UI.

---

# BACKEND API STRUCTURE

Extend the existing backend:

```text
backend/
  app/
    routes/
      auth.py
      youtube.py
      analytics.py
      reporting.py
      sync.py
      health.py

    services/
      oauth_service.py
      youtube_data_service.py
      youtube_analytics_service.py
      youtube_reporting_service.py
      youtube_sync_service.py

    repositories/
      user_repository.py
      channel_repository.py
      video_repository.py
      analytics_repository.py

    schemas/
      auth.py
      channel.py
      video.py
      analytics.py
      retention.py
      reporting.py
      sync.py
```

Keep route handlers thin.

Business logic belongs in services.

Database operations belong in repositories.

---

# REQUIRED AUTH ENDPOINTS

Implement:

```text
GET /api/auth/youtube/login
```

Redirect to Google OAuth.

---

```text
GET /api/auth/youtube/callback
```

Handle callback and create session.

---

```text
GET /api/auth/me
```

Return:

```json
{
  "authenticated": true,
  "user": {
    "name": "...",
    "email": "...",
    "image": "..."
  },
  "channel": {
    "id": "...",
    "title": "..."
  }
}
```

Do not return tokens.

---

```text
POST /api/auth/logout
```

Destroy session.

---

# REQUIRED CHANNEL ENDPOINTS

```text
GET /api/channel/me
```

Returns authenticated user's channel.

---

```text
GET /api/channel/me/videos
```

Returns uploaded videos.

Support:

```text
page
limit
search
sort
```

---

# REQUIRED ANALYTICS ENDPOINTS

```text
GET /api/analytics/overview
```

Parameters:

```text
start_date
end_date
```

Return:

* views
* watch time
* average view duration
* average view percentage
* likes
* comments
* shares
* subscribers gained
* subscribers lost

---

```text
GET /api/analytics/timeseries
```

Return time-series analytics.

---

```text
GET /api/analytics/videos
```

Return video-level performance metrics.

Support:

```text
page
limit
sort
search
start_date
end_date
```

---

```text
GET /api/analytics/video/{video_id}
```

Return detailed analytics for one video.

---

```text
GET /api/analytics/video/{video_id}/retention
```

Return:

```text
elapsedVideoTimeRatio
audienceWatchRatio
relativeRetentionPerformance
```

and supported observed watch behavior metrics such as:

```text
startedWatching
stoppedWatching
```

when available.

---

```text
GET /api/analytics/traffic-sources
```

---

```text
GET /api/analytics/geography
```

---

```text
GET /api/analytics/devices
```

---

# FUTURE ML CONTRACTS

This application must remain ready for the machine-learning team.

Create:

```text
schemas/ml.py
```

with something like:

```json
{
  "video_id": "...",
  "duration_seconds": 542,
  "title": "...",
  "category": "...",
  "views": 100000,
  "average_view_duration": 231.4,
  "average_view_percentage": 0.425,

  "analytics_features": {},
  "content_features": {},
  "retention_features": {}
}
```

Do not fill unavailable ML features with fake values.

Use:

```text
null
```

or clearly mark them as unavailable.

---

# FUTURE ML ENDPOINT

Prepare:

```text
POST /api/ml/predict
```

Do NOT implement prediction now.

Return:

```text
501 Not Implemented
```

or an equivalent controlled response.

Document that our friends will later attach:

```text
Random Forest
XGBoost
feature engineering
retention model
```

without modifying the authentication or analytics code.

---

# DATA CONTRACT FOR FRIENDS

Create:

```text
docs/ml-integration.md
```

Document exactly what the ML team will receive.

Example:

```json
{
  "video_id": "...",
  "duration_seconds": 542,
  "title": "...",
  "views": 100000,
  "likes": 5000,
  "comments": 300,
  "average_view_duration": 231.4,
  "average_view_percentage": 0.425,

  "retention": {
    "time_ratio": [],
    "audience_watch_ratio": [],
    "relative_retention_performance": []
  },

  "content_features": {},
  "audio_features": {},
  "language_features": {}
}
```

Make the schema versioned.

Example:

```text
feature_schema_version: "1.0"
```

The ML team should never need access to raw OAuth credentials.

---

# FRONTEND ROUTES

Minimum required:

```text
/login
/dashboard
```

Keep the existing public video analyzer available.

Suggested:

```text
/
```

for public video analysis.

Then:

```text
/login
```

for creator authentication.

Then:

```text
/dashboard
```

for authenticated analytics.

Do not require login for the public-video analyzer.

---

# LOGIN PAGE UI

Make it polished.

Hero:

```text
RETAINAI

Turn YouTube Analytics into
pre-publication intelligence.

Connect your channel to see:
• Video performance
• Audience retention
• Watch time
• Traffic sources
• Historical content performance

[ Continue with YouTube ]
```

Add a small privacy explanation:

```text
Read-only access.
No videos are uploaded, edited or deleted.
```

Do not claim capabilities we don't have.

---

# DASHBOARD UI

Use a modern dark/light analytics interface.

Navigation:

```text
Overview
Videos
Retention
Audience
Traffic
```

Header:

```text
Channel avatar
Channel name
Sync status
Last synced
Sync button
Logout
```

---

# DASHBOARD FIRST SCREEN

Create:

## Channel Overview

Top cards:

```text
Total Views
Watch Time
Avg View Duration
Avg View %
Subscribers
```

Then:

```text
Views Over Time
```

Then:

```text
Watch Time Over Time
```

Then:

```text
Top Videos
```

Then:

```text
Recent Videos
```

---

# RETENTION TAB

Create:

```text
Retention
```

At top:

```text
Select a video
[ Video dropdown ]
```

Then show:

```text
Video thumbnail
Title
Duration
Views
Average View %
```

Then the actual:

```text
Audience Retention Curve
```

Then:

```text
Relative Retention Performance
```

Then:

```text
Observed Drop-Offs
```

This page is the bridge to the future ML functionality.

Clearly separate:

```text
Observed YouTube Analytics
```

from:

```text
Predicted by RetainAI
```

When ML is later connected, the predicted curve can be overlaid on the same chart.

---

# FUTURE PREDICTION VISUALIZATION

Create an empty state:

```text
RETENTION PREDICTOR

Your ML model will appear here.

Once connected, RetainAI will compare:

Actual YouTube Retention
        vs
Predicted Retention
```

Do not display fictional prediction values.

This section is intentionally waiting for the ML team.

---

# SECURITY REQUIREMENTS

Never:

* expose Google client secret
* expose refresh tokens
* expose access tokens
* put credentials in localStorage
* put API keys in frontend code
* log OAuth tokens
* commit `.env`
* commit Google credentials JSON
* commit downloaded report files containing sensitive analytics

Use:

```text
.gitignore
```

for:

```text
.env
*.json
credentials/
tokens/
reports/
```

except intentionally documented example configuration files.

---

# ERROR HANDLING

Handle:

```text
OAuth denied
OAuth callback failure
invalid state
expired access token
refresh token failure
YouTube channel unavailable
no YouTube channel
Analytics API permission error
Reporting API permission error
quota exceeded
rate limiting
invalid date range
video unavailable
analytics unavailable for video
```

Return user-friendly messages.

Example:

```text
We connected your Google account, but no YouTube channel
was found for this account.
```

Do not expose Google API stack traces to users.

---

# TOKEN REFRESH

Implement automatic access-token refresh.

When:

```text
access_token expired
```

use:

```text
refresh_token
```

to obtain a new access token.

Update stored token expiry.

The frontend should not notice this.

---

# LOGOUT

When the user clicks logout:

```text
POST /api/auth/logout
```

clear the application session.

Do not necessarily revoke the Google grant unless explicitly implemented as a separate "Disconnect Google account" feature.

---

# REPORTING API LIMITATION

Document clearly:

The YouTube Reporting API is not an instant mirror of YouTube Studio.

It is intended for bulk reports and scheduled report generation.

Use:

### YouTube Analytics API

for interactive dashboard queries.

Use:

### YouTube Reporting API

for bulk historical ingestion/synchronization.

Use:

### YouTube Data API v3

for channel/video resource metadata.

The product should use all three for their respective strengths.

---

# API SOURCE MAPPING

Document this table:

| Application feature             | API                         |
| ------------------------------- | --------------------------- |
| Public video metadata           | YouTube Data API v3         |
| Authenticated user's channel    | YouTube Data API v3 + OAuth |
| Uploaded videos                 | YouTube Data API v3         |
| Channel overview metrics        | YouTube Analytics API       |
| Video performance metrics       | YouTube Analytics API       |
| Audience retention              | YouTube Analytics API       |
| Traffic sources                 | YouTube Analytics API       |
| Geography                       | YouTube Analytics API       |
| Device/OS                       | YouTube Analytics API       |
| Bulk historical channel reports | YouTube Reporting API       |
| Future ML input                 | Internal feature contract   |

---

# VERY IMPORTANT RETENTION DETAIL

Audience retention reports have special behavior.

The retention report uses:

```text
elapsedVideoTimeRatio
```

and metrics such as:

```text
audienceWatchRatio
relativeRetentionPerformance
```

The retention query requires a single video ID.

Design the backend accordingly.

Do not attempt to request retention curves for hundreds of videos in one retention query.

The dashboard should request the retention data only when a user selects a video.

---

# PERFORMANCE REQUIREMENTS

Do NOT make the dashboard perform hundreds of API requests sequentially.

At login/sync:

1. identify channel
2. retrieve uploads playlist
3. paginate video list
4. batch public video metadata where possible
5. retrieve analytics using efficient supported queries
6. cache results

When the user selects one video:

```text
retrieve detailed video analytics
retrieve retention curve
```

only then.

Use asynchronous/background jobs for large synchronization tasks.

---

# DATABASE INDEXES

Add indexes for:

```text
youtube_channel_id
youtube_video_id
user_id
published_at
video_id
channel_id
analytics date range
```

Avoid duplicate records.

---

# TESTS

Add tests for:

### OAuth

* login URL generation
* state generation/validation
* callback handling
* invalid state
* token refresh

### YouTube

* authenticated channel lookup
* uploads playlist lookup
* pagination

### Analytics

* overview normalization
* video metrics normalization
* retention normalization

### Reporting

* job creation
* report listing
* report processing

Mock Google API requests in unit tests.

Do not depend entirely on live YouTube APIs for tests.

---

# README UPDATE

Expand the README with:

## 1. Architecture

Explain:

```text
Public Mode
    ↓
Data API

Creator Mode
    ↓
OAuth
    ↓
Data API + Analytics API + Reporting API
    ↓
PostgreSQL
    ↓
Dashboard
    ↓
Future ML
```

---

## 2. Google Cloud Setup

Detailed instructions:

1. Select project
2. Enable YouTube Data API v3
3. Enable YouTube Analytics API
4. Enable YouTube Reporting API
5. Configure OAuth consent screen
6. Create OAuth client ID
7. Select Web Application
8. Add redirect URI
9. Add environment variables
10. Run locally

Document localhost and production separately.

---

## 3. OAuth Scopes

Document exactly:

```text
https://www.googleapis.com/auth/youtube.readonly
https://www.googleapis.com/auth/yt-analytics.readonly
```

Explain why each is requested.

Do not add unnecessary scopes.

---

## 4. API Documentation

Document every endpoint.

---

## 5. Analytics Data Model

Explain:

* channel metrics
* video metrics
* retention metrics
* normalized time ratio
* cached analytics

---

## 6. Reporting API

Explain:

* report types
* jobs
* generated reports
* asynchronous nature
* synchronization

---

## 7. Security

Explain:

* token storage
* API-key storage
* `.env`
* secure cookies
* no frontend secrets

---

## 8. ML Integration

Explain exactly how the friends' ML branch will connect.

Reference:

```text
https://github.com/avalanchesiqi/youtube-engagement

https://github.com/Mukeshthenraj/Video-engagement-prediction
```

Do not copy or merge their code into this phase.

The ML branch will be connected later.

---

# FUTURE ARCHITECTURE

The final system should eventually become:

```text
                     RETAINAI
                         │
        ┌────────────────┴────────────────┐
        │                                 │
 PUBLIC VIDEO MODE                  CREATOR MODE
        │                                 │
 YouTube Data API                  Google OAuth
        │                                 │
 Gemini/Content                    Data API
 Analysis                          Analytics API
        │                           Reporting API
        │                                 │
        └──────────────┬──────────────────┘
                       │
                 PostgreSQL
                       │
                 Feature Layer
                       │
                ┌──────┴──────┐
                │             │
           Content ML      Analytics ML
                │             │
                └──────┬──────┘
                       │
              Retention Predictor
                       │
              Drop-Off Detection
                       │
                Edit Suggestions
```

This phase only implements the parts up through:

```text
OAuth
↓
YouTube data retrieval
↓
Analytics retrieval
↓
Reporting synchronization
↓
Dashboard
↓
ML-ready feature contract
```

---

# DO NOT IMPLEMENT MACHINE LEARNING

This instruction is critical.

Do NOT implement:

* Random Forest
* XGBoost
* LightGBM
* neural networks
* retention prediction
* predicted retention curves
* drop-off prediction
* SHAP
* AI edit recommendations
* LLM reasoning
* counterfactual simulation

The ML team will add those later.

Only create the interfaces and data contracts necessary for them.

---

# FINAL ACCEPTANCE CRITERIA

The implementation is complete when:

1. `/login` loads.
2. "Continue with YouTube" redirects to Google OAuth.
3. Google consent requests the correct read-only scopes.
4. OAuth callback works.
5. Authenticated user's channel is identified.
6. Channel information is stored.
7. Uploads playlist is identified.
8. Uploaded videos are synchronized.
9. `/dashboard` displays the user's channel.
10. Dashboard shows real analytics data.
11. Date range works.
12. Video table works.
13. Selecting a video loads its analytics.
14. Selecting a video loads its actual audience-retention curve.
15. Traffic sources work where supported.
16. Geography works where supported.
17. Device/OS analytics work where supported.
18. Reporting API infrastructure is present.
19. Bulk reporting jobs can be created/listed/retrieved.
20. Access tokens refresh automatically.
21. Logout works.
22. No tokens/secrets reach the browser.
23. No fake ML numbers appear.
24. The future ML integration contract is documented.
25. README accurately describes the implementation.
26. The existing public YouTube URL analyzer continues working.

After implementation, run the application locally and test the complete flow using a real Google/YouTube test account if credentials are configured.

Do not claim any API works unless you actually test it.

At the end, provide:

* final project tree
* all new files
* all new environment variables
* Google Cloud configuration required
* OAuth redirect URI
* API routes
* database tables
* dashboard features
* Reporting API behavior
* exact ML integration point
* commands to run frontend/backend
* known limitations

Do not rewrite the existing public-video analyzer unnecessarily.
Extend the current codebase cleanly.
