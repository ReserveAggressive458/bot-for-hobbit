
import praw
import googleapiclient.discovery
from flask import Flask, request, Response
import xml.etree.ElementTree as ET
import threading
import requests
import schedule
import time
from googleapiclient.discovery import build
import subprocess
import os
import html



# Reddit API setup
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD")
)

# YouTube API setup
youtube = googleapiclient.discovery.build(
    "youtube", "v3", developerKey=os.getenv("YOUTUBE_API_KEY")
)

# Constants
CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")
SUBREDDIT = os.getenv("REDDIT_SUBREDDIT")
WEBHOOK_CALLBACK_URL = os.getenv("WEBHOOK_CALLBACK_URL")  
PUBSUB_HUB_URL = "https://pubsubhubbub.appspot.com/subscribe"

# Flairs
FLAIR_NOW_LIVE = os.getenv("FLAIR_LIVE")  
FLAIR_STREAM_OVER = os.getenv("FLAIR_OVER")  

app = Flask(__name__)

# Current state tracking
current_live_video_id = None
current_sticky_post = None
stream_check_job = None
 

# Subscribe to YouTube channel updates
def subscribe_to_youtube():
    topic_url = f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={CHANNEL_ID}"
    data = {
        "hub.callback": WEBHOOK_CALLBACK_URL,
        "hub.mode": "subscribe",
        "hub.topic": topic_url,
        "hub.verify": "async"
    }
    response = requests.post(PUBSUB_HUB_URL, data=data)
    if response.status_code == 202:
        print("Successfully subscribed to YouTube notifications.")
    else:
        print(f"Failed to subscribe: {response.status_code} - {response.text}")

# Confirm if a video is live
def is_video_live(video_id, max_retries=3, retry_delay=2):
    for attempt in range(1, max_retries + 1):
        try:
            request = youtube.videos().list(
                part="liveStreamingDetails, snippet",
                id=video_id
            )
            response = request.execute()
            
            # Extract the relevant details
            items = response.get('items', [])
            if not items:
                print(f"[Info] No items found for video ID {video_id}.")
                return False
            
            # Get liveStreamingDetails
            details = items[0].get('liveStreamingDetails', {})
            print(f"[Debug] liveStreamingDetails: {details}")
            
            # Check snippet for liveBroadcastContent
            snippet = items[0].get('snippet', {})
            live_broadcast_content = snippet.get('liveBroadcastContent', '')

            # Detect live state
            if live_broadcast_content == 'live':
                print(f"[Info] Video ID {video_id} is currently live (liveBroadcastContent is 'live').")
                return True
            elif details.get('actualStartTime') and not details.get('actualEndTime'):
                print(f"[Info] Video ID {video_id} appears to be live (actualStartTime present, no actualEndTime).")
                return True
            else:
                print(f"[Info] Video ID {video_id} is not live.")
                return False

        except Exception as e:
            print(f"[Error] Attempt {attempt}/{max_retries} - Failed to check live status for video ID {video_id}: {e}")
            
            if attempt < max_retries:
                print(f"[Retry] Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)  # Wait before retrying
            else:
                print("[Error] Max retries reached. Giving up.")
                return False  # Return False after max retries

# Post to Reddit when live
def post_to_reddit(title, video_id):
    global current_sticky_post
    subreddit = reddit.subreddit(SUBREDDIT)
    title = html.unescape(title)
    post_title_template = os.getenv('POST_TITLE_LIVE')
    expected_post_title = post_title_template.replace("{title}", title)

    # Check the bot's own post history for a "Now Live" post
    for post in reddit.redditor(reddit.user.me().name).submissions.new(limit=50):
        if post.subreddit.display_name == SUBREDDIT and expected_post_title in post.title:
            if post.stickied:
                print(f"A 'Now Live' post for '{title}' is already stickied. No new post will be created.")
                current_sticky_post = post
                return

    post_title_template = os.getenv('POST_TITLE_LIVE')
    post_title = post_title_template.replace("{title}", title)
    post_body_template = os.getenv('POST_BODY_LIVE')
    post_body = post_body_template.replace("{video_id}", video_id)
    post = reddit.subreddit(SUBREDDIT).submit(post_title, selftext=post_body)
    post.mod.sticky()
    post.mod.suggested_sort('new')


    # Assign flair
    for flair in subreddit.flair.link_templates:
        if flair['text'] == FLAIR_NOW_LIVE:
            post.flair.select(flair['id'])
            break

    current_sticky_post = post
    print(f"Posted and stickied: {post_title}")

def post_offline():
    global current_sticky_post
    subreddit = reddit.subreddit(SUBREDDIT)
    
    post_title_template = os.getenv("POST_TITLE_OFFLINE")

    # Check the bot's own post history for a "Stream Ended" post
    for post in reddit.redditor(reddit.user.me().name).submissions.new(limit=50):
        if post.subreddit.display_name == SUBREDDIT:
            if post_title_template in post.title:  # Match the title for "Stream Ended" posts
                if post.stickied:
                    print("An existing 'Stream Ended' post is already stickied. No new post will be created.")
                    current_sticky_post = post  # Set the existing post as the sticky post
                    return
                else:
                    print("An existing 'Stream Ended' post found but not stickied. Stickying it now.")
                    post.mod.sticky()
                    current_sticky_post = post
                    return

    # Create a new "Stream Ended" post if none exists
    post_title = os.getenv("POST_TITLE_OFFLINE")
    post_body = os.getenv("POST_BODY_OFFLINE")
    post = reddit.subreddit(SUBREDDIT).submit(post_title, selftext=post_body)
    post.mod.sticky()  # Sticky the post
    current_sticky_post = post

    # Assign flair
    for flair in subreddit.flair.link_templates:
        if flair['text'] == FLAIR_STREAM_OVER:
            post.flair.select(flair['id'])
            break

    print(f"Posted and stickied: {post_title}")

@app.route('/youtube-webhook', methods=['GET', 'POST'])
def youtube_webhook():
    global current_live_video_id, current_sticky_post
    
    post_title_offline_template = os.getenv("POST_TITLE_OFFLINE")

    print(f"Webhook hit! Method: {request.method}")
    if request.method == 'GET':
        challenge = request.args.get('hub.challenge')
        print(f"GET Challenge received: {challenge}")
        return Response(challenge, status=200, content_type='text/plain')

    elif request.method == 'POST':
        try:
            print(f"POST data received: {request.data}")
            xml_data = ET.fromstring(request.data)
            for entry in xml_data.findall('{http://www.w3.org/2005/Atom}entry'):
                video_id = entry.find('{http://www.youtube.com/xml/schemas/2015}videoId').text
                title = entry.find('{http://www.w3.org/2005/Atom}title').text
                print(f"Notification received: {title} (Video ID: {video_id})")

                # Check if video is live
                if is_video_live(video_id):
                    if video_id != current_live_video_id:

                        # Handle existing 'OFFLINE' sticky post
                        if current_sticky_post and post_title_offline_template in current_sticky_post.title:
                            print("Unsticking and deleting 'OFFLINE' post to make way for 'Now Live' post.")
                            current_sticky_post.mod.sticky(state=False)
                            current_sticky_post.delete()
                            current_sticky_post = None
                            
                        # New live stream started
                        if current_sticky_post:
                            current_sticky_post.mod.sticky(state=False)
                            current_sticky_post.delete()
                            print("Deleted previous post.")

                        post_to_reddit(title, video_id)
                        current_live_video_id = video_id
                        start_periodic_check()  # Start periodic checks
                else:
                    # Stream ended
                    if current_live_video_id == video_id:
                        print("Stream has ended.")
                        if current_sticky_post:
                            current_sticky_post.mod.sticky(state=False)
                            print("Unstuck defunct live post.")
                        post_offline()
                        current_live_video_id = None
            return '', 204
        except Exception as e:
            print(f"Error processing webhook: {e}")
            return Response("Invalid XML", status=400)

def check_stream_status():
    global current_live_video_id, current_sticky_post, stream_check_job

    print(f"[Stream Checker] Running stream status check at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    if current_live_video_id:
        if not is_video_live(current_live_video_id):
            print(f"[Stream Checker] Stream with ID {current_live_video_id} has ended (detected by periodic check).")
            if current_sticky_post:
                current_sticky_post.mod.sticky(state=False)
                print("[Stream Checker] Unstuck defunct live post.")
            post_offline()
            current_live_video_id = None

            # Cancel the periodic check
            if stream_check_job:
                schedule.cancel_job(stream_check_job)
                stream_check_job = None
        else:
            print(f"[Stream Checker] Stream with ID {current_live_video_id} is still live.")
    else:
        print("[Stream Checker] No active stream to check.")

def start_periodic_check():
    global stream_check_job
    if not stream_check_job:
        stream_check_job = schedule.every(5).minutes.do(check_stream_status)
        print("[Scheduler] Started periodic stream status checks.")

def run_scheduler():
    print("[Scheduler] Starting scheduler thread...")
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            print(f"[Scheduler] Error in scheduler thread: {e}")
            time.sleep(10)  # Wait before retrying

#def start_server(): (Gunicorn renders this obsolete)
    #app.run(port=5000)

# Search for live streams on startup
def search_for_live_stream(channel_id):
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        eventType="live",
        type="video"
    )
    response = request.execute()
    items = response.get("items", [])
    if items:
        video_id = items[0]["id"]["videoId"]
        title = items[0]["snippet"]["title"]
        return video_id, title
    return None, None

def main():

    global current_live_video_id, current_sticky_post
    

    # Start the scheduler
    print("[Main] Starting scheduler thread...")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    # Subscribe to YouTube notifications
    subscribe_to_youtube()

    print("Checking if the stream is already live...")
    video_id, title = search_for_live_stream(CHANNEL_ID)

    print("Checking for existing sticky posts...")
    for post in reddit.redditor(reddit.user.me().name).submissions.new(limit=50):
        if post.subreddit.display_name == SUBREDDIT and post.stickied:
            if "LIVE" in post.title:
                print(f"Found existing 'Now Live' post: {post.title}")
                current_sticky_post = post
                if video_id:
                    print("Stream is still live. No action needed.")
                    current_live_video_id = video_id
                    start_periodic_check()  # Start periodic checks
                else:
                    print("Stream has ended. Cleaning up 'Now Live' post.")
                    post.mod.sticky(state=False)
                    post_offline()
                break
            elif "OFFLINE" in post.title:
                current_sticky_post = post
                if video_id:
                    print("Stream is live. Updating post to'Now Live'.")
                    # Unstick and delete the offline post
                    post.mod.sticky(state=False)
                    post.delete()

                    # Create a new post for the live stream
                    post_to_reddit(title, video_id)
                    current_live_video_id = video_id
                    start_periodic_check()  # Start periodic checks
                else:
                    print("No live stream detected at startup, ensuring offline post is up.")
                    post_offline()  # Ensure the offline post is updated as well
                break

    if not current_sticky_post:
        if video_id:
            print(f"Stream is already live: {title} (Video ID: {video_id})")
            try:
                post_to_reddit(title, video_id)
                current_live_video_id = video_id
                start_periodic_check()  # Start periodic checks
            except Exception as e:
                print(f"Error posting to Reddit: {e}")
        else:
            print("No live stream detected at startup.")
            post_offline()

if __name__ == "__main__":
    print("[App] Starting application (run directly)...")
    main()
else:
    # This block runs when the script is imported (e.g., by Gunicorn)
    print("[App] Starting application (imported as module)...")
    main()

