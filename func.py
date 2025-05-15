from pixivpy3 import AppPixivAPI
from pathlib import Path
from tqdm import tqdm
import re
import json
import time
import base64
import cv2
import numpy as np

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
    print("リスト取得中...")
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
        # イラスト情報取得
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
            # うごイラのURL取得
            if illust.type == "ugoira":
                ugoira_url = illust.meta_single_page.original_image_url.rsplit("0", 1)
                ugoira = api.ugoira_metadata(illust_pages["id"])
                ugoira_frames = len(ugoira.ugoira_metadata.frames)
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
    artist_dir = f"downloads/{artist_name} - {artist_id}"
    Path(f"{artist_dir}").mkdir(exist_ok=True, parents=True)
    with open(f"{artist_dir}/download_data.json", "w", encoding="utf-8") as f:
        json.dump(download_list, f, ensure_ascii=False, indent=4)
    return artist_dir


# mp4変換
def convert_ugoira_to_mp4(api, ugoira_dir, mp4_path, illust_id):
    frames = list(Path(ugoira_dir).iterdir())
    frames.sort(key=lambda s: int(re.findall(r"\d+", str(s))[-1]))

    ugoira_delay = api.ugoira_metadata(illust_id).ugoira_metadata.frames[0].delay
    fps = 1000 / ugoira_delay
    ugoira = api.illust_detail(illust_id)
    width = ugoira.illust.width
    height = ugoira.illust.height

    fourcc = cv2.VideoWriter_fourcc("m", "p", "4", "v")
    video = cv2.VideoWriter(mp4_path, fourcc, fps, (width, height))

    for frame in tqdm(frames, leave=False, desc="convertMP4"):
        buf = np.fromfile(frame, np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
        if img.shape[2] == 4:
            img = np.delete(img, 3, axis=2)
        video.write(img)

    video.release()


# html変換
# def convert_ugoira_to_html(api, ugoira_dir, html_path, illust_id):
#     illust_b64 = []
#     ugoira = api.ugoira_metadata(illust_id)
#     illust = api.illust_detail(illust_id)
#     width = illust.illust.width
#     height = illust.illust.height
#     frames = list(Path(ugoira_dir).iterdir())
#     frames.sort(key=lambda s: int(re.findall(r"\d+", str(s))[-1]))
#     img_ext = str(frames[0]).split(".")[-1]
#     for index, frame in enumerate(frames):
#         with open(frame, "rb") as f:
#             illust_b64.append(
#                 [
#                     f"data:image/{img_ext};base64,{base64.b64encode(f.read()).decode()}",
#                     ugoira.ugoira_metadata.frames[index]["delay"],
#                 ]
#             )
#     html = """
#     <!DOCTYPE html>
#     <html lang="ja">
#     <head>
#         <meta charset="UTF-8"
#         <meta name="viewport" content="width=device-width, initial-scale=1.0">
#         <title>ugoira</title>
#     </head>
#     <body>
#         <canvas id = "ugoira" width = "{width}" height = "{height}"></canvas>
#         <script>
#             const illust_b64 = {illust_b64};
#             const images = [];
#             for (let i=0; i<{frames}; i++) {{
#                 const img = new Image();
#                 img.src = illust_b64[i][0];
#                 images.push([img,illust_b64[i][1]]);
#             }};
#             const canvas = document.getElementById("ugoira");
#             const ctx = canvas.getContext("2d");
#             const drawImage = (index) = > {{
#                 if(index >= {frames}) index = 0;
#                 ctx.clearRect(0, 0, canvas.width, canvas.height);
#                 ctx.drawImage(images[index][0], 0, 0);
#                 setTimeout(drawImage, images[index][1], index + 1);
#             }};
#             window.addEventListener('load',() => drawImage(0));
#         </script>
#     </body>
#     </html>
#     """.format(
#         width=width,
#         height=height,
#         frames=frames,
#         illust_b64=str(illust_b64),
#     )
#     with open(html_path, "w", encoding="utf-8") as f:
#         f.write(html)


# ダウンローダー
def get_file(api, download_list, artist_dir):
    for illust in tqdm(download_list["illusts"], desc="total"):
        illust_dir = Path(
            f"{artist_dir}/{illust['id']} - {rename_for_windows(illust['title'])}"
        )
        illust_dir.mkdir(exist_ok=True, parents=True)
        # イラストダウンロード
        for image in tqdm(illust["image_urls"], leave=False, desc="illust"):
            file_name = image.split("/")[-1]
            file_name = rename_for_windows(file_name)
            file_path = Path(f"{illust_dir}/{file_name}")
            if not (file_path.exists()):
                api.download(image, name=file_path)
                time.sleep(2)
        # うごイラダウンロード
        if illust["type"] == "ugoira":
            ugoira_dir = Path(f"{illust_dir}/ugoira")
            ugoira_dir.mkdir(exist_ok=True, parents=True)
            for ugoira in tqdm(illust["ugoira_urls"], leave=False, desc="ugoira"):
                file_name = ugoira.split("/")[-1]
                file_path = Path(f"{ugoira_dir}/{file_name}")
                if not (file_path.exists()):
                    api.download(ugoira, name=file_path)
                    time.sleep(2)

            mp4_path = Path(f"{illust_dir}/{illust['id']}.mp4")
            if not (mp4_path.exists()):
                convert_ugoira_to_mp4(api, ugoira_dir, mp4_path, illust["id"])

            # html_path = Path(f"{illust_dir}/{illust['id']}.html")
            # if not (html_path.exists()):
            #     convert_ugoira_to_html(api, ugoira_dir, html_path, illust["id"])

    print("ダウンロード完了")
