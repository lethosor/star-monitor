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

def scan(*, noun, redis_key, api_route, name_key):
    first_run = not redis_client.exists(redis_key)
    res = requests.get(f"https://api.github.com/repos/{repo}/{api_route}", params={"per_page": 100}).json()
    print(f"{api_route}: fetched {len(res)} results")
    new_users = [u for u in res
        if redis_client.sadd(redis_key, u[name_key])]
    for u in new_users:
        if first_run:
            print(f"existing {noun}: {u[name_key]}")
        else:
            print(f"new {noun}: {u[name_key]}")
    if new_users and not first_run:
        user_text = ", ".join(f"<{u['html_url']}|{u[name_key]}>" for u in new_users)
        desc_text = f"{len(new_users)} new {noun}s" if len(new_users) > 1 else f"New {noun}"
        message = {"text": f"{desc_text}: {user_text}"}
        requests.post(slack_url, json=message)

while True:
    try:
        scan(noun="star", redis_key="stars", api_route="stargazers", name_key="login")
        scan(noun="fork", redis_key="forks", api_route="forks", name_key="full_name")

    except Exception:
        traceback.print_exc()
        delay(60 * 5)
    else:
        delay(60 * 30)
