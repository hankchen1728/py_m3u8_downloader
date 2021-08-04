import os
import re
import glob
import time
import tqdm
import shutil
import argparse
import requests
import threading
import subprocess
from datetime import datetime
from functools import partial
from requests.models import Response
from multiprocessing.dummy import Pool


header = {
    'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3) "
                  "AppleWebKit/602.4.8 (KHTML, like Gecko) Version"
                  "/10.0.3 Safari/602.4.8"
}


class Video_Decoder(object):
    def __init__(self, x_key: dict, m3u8_http_base: str = ""):
        self.method = x_key["METHOD"] if "METHOD" in x_key.keys() else ""
        self.uri = decode_key_uri(m3u8_http_base+x_key["URI"]) \
            if "URI" in x_key.keys() else ""
        self.iv = x_key["IV"].lstrip("0x") if "IV" in x_key.keys() else ""

        # print("URI", self.uri)
        # print("IV", self.iv)

    def decode_aes_128(self, video_fname: str):
        subprocess.run([
            "openssl",
            "aes-128-cbc",
            "-d",
            "-in", video_fname,
            "-out", "out" + video_fname,
            "-nosalt",
            "-iv", self.iv,
            "-K", self.uri
        ])
        subprocess.run(["rm", "-f", video_fname])
        subprocess.run(["mv", "out" + video_fname, video_fname])

    def __call__(self, video_fname: str):
        if self.method == "AES-128":
            self.decode_aes_128(video_fname)
        else:
            pass


def decode_key_uri(URI: str):
    uri_req = requests.get(URI, headers=header)
    uri_str = "".join(["{:02x}".format(c) for c in uri_req.content])
    return uri_str


def decode_ext_x_key(key_str: str):
    # TODO: check if there is case with "'"
    key_str = key_str.replace('"', '').lstrip("#EXT-X-KEY:")
    v_list = re.findall(r"[^,=]+", key_str)
    key_map = {v_list[i]: v_list[i+1] for i in range(0, len(v_list), 2)}
    return key_map


def download_ts_file(ts_url: str, store_dir: str, attempts: int = 10):
    # TODO: check 403 Forbidden
    ts_fname = ts_url.split('/')[-1]
    ts_dir = os.path.join(store_dir, ts_fname)
    ts_res = None

    for _ in range(attempts):
        try:
            ts_res = requests.get(ts_url, headers=header)
            if ts_res.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(.5)

    if isinstance(ts_res, Response) and ts_res.status_code == 200:
        with open(ts_dir, 'wb+') as f:
            f.write(ts_res.content)
    else:
        print(f"Failed to download streaming file: {ts_fname}.")


def main(args):
    m3u8_link = args.m3u8
    startTime = datetime.now()

    # Reading the m3u8 file
    m3u8_http_base = ""

    if args.output is not None:
        merged_mp4 = args.output
        if not merged_mp4.endswith(".mp4"):
            merged_mp4 += ".mp4"
    else:
        merged_mp4 = m3u8_link.split("/")[-1].rstrip('.m3u8') + ".mp4"

    if m3u8_link.startswith("http"):
        m3u8_content = requests.get(
            m3u8_link, headers=header
        ).content.decode("utf-8")
        m3u8_http_base = m3u8_link.rstrip(m3u8_link.split("/")[-1])
    else:
        m3u8_content = ""
        # read m3u8 file content
        with open(m3u8_link, 'r') as f:
            m3u8_content = f.read()
            if not m3u8_content:
                raise RuntimeError(f"The m3u8 file: {m3u8_link} is empty.")

    # Parsing the content in m3u8
    m3u8 = m3u8_content.split('\n')
    ts_url_list = []
    ts_names = []
    x_key_dict = dict()
    for i_str in range(len(m3u8)):
        line_str = m3u8[i_str]
        if line_str.startswith("#EXT-X-KEY:"):
            x_key_dict = decode_ext_x_key(line_str)
        elif line_str.startswith("#EXTINF"):
            ts_url = m3u8[i_str+1]
            ts_names.append(ts_url.split('/')[-1])
            if not ts_url.startswith("http"):
                ts_url = m3u8_http_base + ts_url
            ts_url_list.append(ts_url)
    print("There are", len(ts_url_list), "files to download ...")
    video_decoder = Video_Decoder(
        x_key=x_key_dict,
        m3u8_http_base=m3u8_http_base
    )

    # Setting Paths
    DIR = os.getcwd()
    print("mp4 stored in: ", DIR)
    ts_foler = os.path.join(DIR, ".tmp_ts")
    os.makedirs(ts_foler, exist_ok=True)
    os.chdir(ts_foler)

    # Using multithreading to parallel downloading
    pool = Pool(20)
    lock = threading.Lock()
    gen = pool.imap(partial(download_ts_file, store_dir='.'), ts_url_list)
    for _ in tqdm.tqdm(gen, total=len(ts_url_list)):
        pass
    pool.close()
    pool.join()
    time.sleep(1)
    print("Streaming files downloading completed.")

    # Start to merge all *.ts files
    downloaded_ts = glob.glob("*.ts")
    # Decoding videos
    for ts_fname in tqdm.tqdm(
        downloaded_ts, desc="Decoding the *.ts files"
    ):
        video_decoder(ts_fname)

    ordered_ts_names = [
        ts_name for ts_name in ts_names if ts_name in downloaded_ts
    ]

    if len(ordered_ts_names) > 200:
        mp4_fnames = []
        part_num = len(ordered_ts_names) // 200 + 1
        for _i in range(part_num):
            sub_files_str = "concat:"

            _idx_list = range(200)
            if _i == part_num - 1:
                _idx_list = range(len(ordered_ts_names[_i * 200:]))
            for ts_idx in _idx_list:
                sub_files_str += ordered_ts_names[ts_idx + _i * 200] + '|'
            sub_files_str.rstrip('|')

            # files_str += 'part_{}.mp4'.format(_i) + '|'
            mp4_fnames.append('part_{}.mp4'.format(_i))
            subprocess.run([
                'ffmpeg', '-i', sub_files_str, '-c', 'copy', '-bsf:a', 'aac_adtstoasc', 'part_{}.mp4'.format(_i)
            ])

        with open("mylist.txt", 'w') as f:
            for mp4_fname in mp4_fnames:
                f.write(f"file {mp4_fname}\n")
        subprocess.run([
            'ffmpeg', "-f",
            "concat", "-i", "mylist.txt",
            '-codec', 'copy', merged_mp4
        ])
    else:
        files_str = "concat:"
        for ts_filename in ordered_ts_names:
            files_str += ts_filename+'|'
        files_str.rstrip('|')
        subprocess.run([
            'ffmpeg', '-i', files_str, '-c', 'copy', '-bsf:a', 'aac_adtstoasc', merged_mp4
        ])

    print("mp4 file merging completed.")

    # Remove all split *.ts
    mp4_newpath = os.path.join(DIR, os.path.basename(merged_mp4))
    mp4_fullpath = os.path.abspath(merged_mp4)
    os.chdir(DIR)
    shutil.move(mp4_fullpath, mp4_newpath)
    shutil.rmtree(ts_foler)
    endTime = datetime.now()
    print("Finish:", endTime)
    print("Time spent:", endTime - startTime)
    # end


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Python3 m3u8 downloader")

    parser.add_argument(
        "m3u8",
        type=str,
        help="File path or URL to a m3u8 file, e.g. index.m3u8"
    )

    parser.add_argument(
        "--output", "-O",
        type=str,
        help="File path for saved mp4, e.g. anime.mp4. "
             "If not specified, the output file name will be set to the `M3U8`. "
             "For example, index.mp4 for index.m3u8"
    )

    args = parser.parse_args()

    main(args)
