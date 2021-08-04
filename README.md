# Python3 M3U8 Downloader
## Requirements
- Python 3.6+
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [requests](http://docs.python-requests.org/en/master)
- [FFmpeg](https://github.com/FFmpeg/FFmpeg)

```
$ pip install beautifulsoup4 requests
$ brew install ffmpeg
```

## Usage
```
$ python3 m3u8_downloader.py index.m3u8 -O video.mp4
```
Download all `*.ts` files from `index.m3u8`, and then merge them togethor to `video.mp4`

### Help
```sh
Python3 m3u8 downloader

positional arguments:
  m3u8                  File path or URL to a m3u8 file, e.g. index.m3u8

optional arguments:
  -h, --help            show this help message and exit
  --output OUTPUT, -O OUTPUT
                        File path for saved mp4, e.g. anime.mp4. If not
                        specified, the output file name will be set to the
                        `M3U8`. For example, index.mp4 for index.m3u8
```
