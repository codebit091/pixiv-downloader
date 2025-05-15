from pathlib import Path

from auth import login, refresh
from func import (
    get_json,
    make_download_list,
    make_dir,
    get_file,
)


def main():
    user_id = int(input("User ID: "))

    refresh_file = Path("refresh_token.txt")
    if not refresh_file.exists():
        login()
    with open("refresh_token.txt", "r", encoding="utf-8") as f:
        refresh_token = f.read().strip()

    api, json_result = get_json(refresh_token, user_id)
    download_list = make_download_list(api, json_result, user_id)
    artist_dir = make_dir(download_list)
    print(f"「{json_result.user.name}」")
    get_file(api, download_list, artist_dir)


if __name__ == "__main__":
    main()
