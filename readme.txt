readme

Environmental variables to set in Heroku (in the Settings section of your app!)
 

Flair variables must match an existing flair on your subreddit.

For post variables you can include more or less whatever you want. The {title} element will fetch and insert whatever the YouTuber has chosen as the title of their livestream. Don't delete it.

For the webhook variable you must remember to include "/youtube-webhook" at the end of the URL.

You can check that the bot is working by clicking "more" in the top right side of your Heroku app dashboard and selecting "logs". If you have just started/restarted the bot, there should be logs related to starting the app and a number of printouts about streamcheckers being started and relevant posts being made/confirmed.

IMPORTANT: All "streamer online" posts must include the word "LIVE" (case sensitive), and all offline posts must contain the word "OFFLINE" (case sensitive). This is because I'm too lazy to code for flexibiltity. 

For better chances of the bot working, please stick to the formats below. If you prefer a version without "Now OFFLINE!" posts, let me know and I'll make an alternative.

Reddit API/Bot Variables:

REDDIT_CLIENT_ID=your_reddit_client_id,
REDDIT_CLIENT_SECRET=your_reddit_client_secret_code
REDDIT_USER_AGENT=reddit_bot_username
REDDIT_USERNAME=reddit_bot_username
REDDIT_PASSWORD=reddit_bot_password

YouTube API Variables:

YOUTUBE_API_KEY = your_developer_key
YOUTUBE_CHANNEL_ID = target_channel_id

Webhook Variable:

WEBHOOK_CALLBACK_URL = https://your-app-url.herokuapp.com/youtube-webhook

General Reddit Variables:

REDDIT_SUBREDDIT = subreddit_name
FLAIR_LIVE = desired_flair_for_live_post
FLAIR_OVER = desired_flair_for_offline_post

Post Variables:

POST_TITLE_LIVE = 🚨streamer_name_here is LIVE!🚨 - {title}
POST_TITLE_OFFLINE = 😴streamer_name_here is OFFLINE!😴
POST_BODY_LIVE = Join the stream: https://www.youtube.com/watch?v={video_id} If you click the edit pencil icon in Heroku, you'll get a bigger box to write your post body in!
POST_BODY_OFFLINE = Thanks for watching, see you next time! If you click the edit pencil icon in Heroku, you'll get a bigger box to write your post body in!
