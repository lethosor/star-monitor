import os, redis, requests, signal, threading, time, traceback
redis_client = redis.Redis("redis")

skipping = threading.Event()
exiting = threading.Event()

def delay(x):
    target = time.perf_counter() + x
    while time.perf_counter() < target:
        time.sleep(1)
        if exiting.is_set():
            exit()
        if skipping.is_set():
            skipping.clear()
            return

def handle_exit(*_):
    exiting.set()

signal.signal(signal.SIGTERM, handle_exit)

def handle_skip(*_):
    skipping.set()

signal.signal(signal.SIGHUP, handle_skip)
signal.signal(signal.SIGUSR1, handle_skip)

repo = os.environ["GITHUB_REPO"]
if "/" not in repo:
    raise ValueError("Invalid GITHUB_REPO:", repo)
slack_url = os.environ["SLACK_WEBHOOK_URL"]
if not slack_url.startswith("https://"):
    raise ValueError("Invalid SLACK_WEBHOOK_URL:", slack_url)

while True:
    try:
        first_run = not redis_client.exists("stars")
        res = requests.get(f"https://api.github.com/repos/{repo}/stargazers").json()
        print(f"fetched {len(res)} results")
        new_users = [u for u in res
            if redis_client.sadd("stars", u["login"])]
        for u in new_users:
            if first_run:
                print("existing star", u["login"])
            else:
                print("new star", u["login"])
        if new_users and not first_run:
            user_text = ", ".join("<{html_url}|{login}>".format(**u) for u in new_users)
            star_text = f"{len(new_users)} new stars" if len(new_users) > 1 else "New star"
            message = {"text": f"{star_text}: {user_text}"}
            requests.post(slack_url, json=message)

    except Exception:
        traceback.print_exc()
        delay(60 * 5)
    else:
        delay(60 * 30)
