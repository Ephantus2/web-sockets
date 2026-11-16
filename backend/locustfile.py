from locust import HttpUser, task, between
from locust.exception import StopUser
from itertools import cycle


# Ten dedicated load-testing accounts
test_accounts = [
    {
        "username": f"loadtest_{i}",
        "password": "LoadTest@2026"
    }
    for i in range(1, 11)
]

# Assign accounts to simulated users
account_pool = cycle(test_accounts)


class ChatPlatformUser(HttpUser):

    # Wait between requests
    wait_time = between(1, 3)

    def on_start(self):
        # Assign an account to this simulated user
        account = next(account_pool)

        # Authenticate using SimpleJWT
        response = self.client.post(
            "/api/token/",
            json={
                "username": account["username"],
                "password": account["password"]
            },
            name="/api/token/"
        )

        if response.status_code != 200:
            print(f"Login failed for {account['username']}")
            raise StopUser()

        # Extract JWT access token
        access_token = response.json()["access"]

        # Authenticate subsequent requests
        self.client.headers.update({
            "Authorization": f"Bearer {access_token}"
        })

        print(f"{account['username']} authenticated successfully")

    # Task 1: Retrieve conversations
    @task(3)
    def get_conversations(self):
        self.client.get("/api/conversation/")

    # Task 2: Retrieve unread counts
    @task(2)
    def get_unread_counts(self):
        self.client.get("/api/conversations/unread-counts/")

    # Task 3: Check API health
    @task(1)
    def health_check(self):
        self.client.get("/health/")