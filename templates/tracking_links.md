# Tracking links

Steam reports visits, wishlists and purchases for store links that carry UTM labels, for visitors signed in to Steam.

Format: `{store_url}?utm_source={channel}&utm_medium={type}&utm_campaign={moment}`
- `utm_source`: the channel, lowercase (x, bluesky, reddit, youtube, tiktok, instagram, discord, twitch, newsletter, website, presskit).
- `utm_medium`: social, email, video, web.
- `utm_campaign`: the moment (reveal, devlog, demo, festival, launch).
Make one link per channel. The owner reads results in Steamworks and enters them at check-in.
