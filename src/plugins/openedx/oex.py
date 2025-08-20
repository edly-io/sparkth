import base64
import requests
from urllib.parse import urljoin

LMS_BASE = "http://local.openedx.io:8000/"
STUDIO_BASE = "http://studio.local.openedx.io:8001/"

CLIENT_ID = "T1QCRcApKsO7AGzGkBIARwM8lUbJ9TiMG10JXWhS"
CLIENT_SECRET = "AEM8cObhy8zPXL8AOe6dgJH1E96dDqB8Cwppheyd1ZdhSczQqWEg1b50ojH7k2BIdMNkurQTir0ZE16prB8RVDYJNaOhKyo3bwXuiQccc78Shf8NK8t43hCjdDaJH42l"

# ---------- Auth ----------
def get_jwt_with_client_credentials(lms_base, client_id, client_secret):
    """Return a JWT using client credentials grant."""
    url = urljoin(lms_base, "oauth2/access_token")
    credential = f"{client_id}:{client_secret}"
    encoded_credential = base64.b64encode(credential.encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {encoded_credential}",
        "Cache-Control": "no-cache"
    }
    data = {
        "grant_type": "client_credentials",
        "token_type": "jwt"
    }
    r = requests.post(url, headers=headers, data=data)
    r.raise_for_status()
    return r.json()["access_token"]


USERNAME = "edx"  # must be superuser
PASSWORD = "edx"

# ---------- Auth ----------
def get_jwt(lms_base, username, password):
    """Return a JWT access token from LMS using password grant."""
    url = urljoin(lms_base, "oauth2/access_token")
    data = {
        "grant_type": "password",
        "username": username,
        "password": password,
        "token_type": "jwt",
        "client_id": "login-service-client-id"  # must be registered in LMS OAuth apps
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

# ---------- API Calls ----------
def create_course_run(jwt_token, studio_base, org, number, run, title, pacing_type="instructor_paced"):
    url = urljoin(studio_base, "api/v1/course_runs/")
    headers = {
        "Authorization": f"JWT {jwt_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "org": org,
        "number": number,
        "run": run,
        "title": title,
        "pacing_type": pacing_type,
        # Optional: add yourself or another user to the course team
        "team": []
    }
    r = requests.post(url, json=payload, headers=headers)
    r.raise_for_status()
    return r.json()

def list_course_runs(jwt_token, studio_base, page=1, page_size=20):
    url = urljoin(studio_base, "api/v1/course_runs/")
    headers = {"Authorization": f"JWT {jwt_token}"}
    params = {"page": page, "page_size": page_size}
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()

# ---------- Example usage ----------
if __name__ == "__main__":
    token = get_jwt(LMS_BASE, USERNAME, PASSWORD)

    # Create a course run
    # course_data = create_course_run(token, STUDIO_BASE, "TestOrg", "CS3", "2025", "Intro CS3")
    # print("Created course run:", course_data)

    # # List course runs
    course_list = list_course_runs(token, STUDIO_BASE)
    print("Course runs list:", course_list)