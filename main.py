from pixivpy3 import AppPixivAPI
from pathlib import Path
import os, glob
import json
import time
from tqdm import tqdm

from auth import login, refresh


# 禁止文字置換
def rename_for_windows(name):
    while True:
        tmp = name
        # 半角文字の削除
        name = name.translate(
            (
                str.maketrans(
                    {
                        "\a": "",
                        "\b": "",
                        "\f": "",
                        "\n": "",
                        "\r": "",
                        "\t": "",
                        "\v": "",
                        "'": "'",
                        '"': '"',
                        "\0": "",
                    }
                )
            )
        )
        # エスケープシーケンスを削除
        name = name.translate(
            (
                str.maketrans(
                    {
                        "\\": "￥",
                        "/": "／",
                        ":": "：",
                        "*": "＊",
                        "?": "？",
                        '"': "”",
                        ">": "＞",
                        "<": "＜",
                        "|": "｜",
                    }
                )
            )
        )
        # 先頭/末尾のドットの削除
        name = name.strip(".")
        # 先頭/末尾の半角スペースを削除
        name = name.strip(" ")
        # 先頭/末尾の全角スペースを削除
        name = name.strip("　")

        if name == tmp:
            break

    return name


# JSON取得
def get_json(refresh_token, user_id):
    api = AppPixivAPI()
    api.auth(refresh_token=refresh_token)
    json_result = api.user_detail(user_id)
    print("データ取得中...")
    return api, json_result


# データリスト作成
def make_download_list(api, json_result, user_id):
    download_list = {
        "name": json_result.user.name,
        "id": json_result.user.id,
        "total_illusts": json_result.profile.total_illusts,
        "total_manga": json_result.profile.total_manga,
        "total_novel": json_result.profile.total_novel,
        "illusts": [],
    }

    for page in range(0, download_list["total_illusts"], 30):
        if page == 0:
            json_result = api.user_illusts(user_id)
        else:
            next_qs = api.parse_qs(json_result.next_url)
            if next_qs == None:
                break
            json_result = api.user_illusts(**next_qs)

        for illust in json_result.illusts:
            illust_pages = {}
            illust_pages["id"] = illust.id
            illust_pages["title"] = illust.title
            illust_pages["type"] = illust.type
            illust_pages["tags"] = []
            illust_pages["image_urls"] = []
            illust_pages["ugoira_urls"] = []
            illust_pages["manga_urls"] = []
            for tag in illust.tags:
                illust_pages["tags"].append(tag.name)
            if illust.meta_single_page:
                illust_pages["image_urls"].append(
                    illust.meta_single_page.original_image_url
                )
            for image in illust.meta_pages:
                illust_pages["image_urls"].append(image.image_urls.original)

            if illust.type == "ugoira":
                ugoira_url = illust.meta_single_page.original_image_url.rsplit("0", 1)
                ugoira = api.ugoira_metadata(illust_pages["id"])
                ugoira_frames = len(ugoira.ugoira_metadata.frames)
                # ugoita_delay = ugoira.ugoira_metadata.frames[0].delay
                for frame in range(ugoira_frames):
                    illust_pages["ugoira_urls"].append(
                        ugoira_url[0] + str(frame) + ugoira_url[1]
                    )
            download_list["illusts"].append(illust_pages)
        time.sleep(2)
    return download_list


# ディレクトリ作成
def make_dir(download_list):
    artist_name = rename_for_windows(download_list["name"])
    artist_id = download_list["id"]
    artist_dir = f"download/{artist_name} - {artist_id}"
    Path(f"{artist_dir}").mkdir(exist_ok=True, parents=True)
    with open(f"{artist_dir}/download_data.json", "w", encoding="utf-8") as f:
        json.dump(download_list, f, ensure_ascii=False, indent=4)
    return artist_dir


def ugoira_to_mp4(api, ugoira_dir):
    frames = glob.glob(f"{ugoira_dir}/*_ugoira*")
    frames.sort()


# ダウンローダー
def get_file(api, download_list, artist_dir):
    for illust in tqdm(download_list["illusts"], desc="total"):
        illust_dir = Path(
            f"{artist_dir}/{illust['id']} - {rename_for_windows(illust['title'])}"
        )
        illust_dir.mkdir(exist_ok=True, parents=True)
        for image in tqdm(illust["image_urls"], leave=False, desc="illust"):
            file_name = image.split("/")[-1]
            file_name = rename_for_windows(file_name)
            file_path = Path(f"{illust_dir}/{file_name}")
            if not (file_path.exists()):
                api.download(image, name=file_path)
                time.sleep(2)

        if illust["type"] == "ugoira":
            ugoira_dir = Path(f"{illust_dir}/ugoira")
            ugoira_dir.mkdir(exist_ok=True, parents=True)
            for ugoira in tqdm(illust["ugoira_urls"], leave=False, desc="ugoira"):
                file_name = ugoira.split("/")[-1]
                file_path = Path(f"{ugoira_dir}/{file_name}")
                if not (file_path.exists()):
                    api.download(ugoira, name=file_path)
                    time.sleep(2)

    print("ダウンロード完了")


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
