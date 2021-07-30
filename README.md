

# animelon_download
Command line downloader for https://animelon.com/

## Requirements:
       requests
       progressbar
       numpy
## Usage:

    ⇒  ./animelon_dl.py -h
    usage: animelon_dl.py [-h] [-d delay] [--savePath savePath] [--forks forks]
                          [--maxTries maxTries]
                          videoURLs [videoURLs ...]
    
    Downloads videos from animelon.com
    
    positional arguments:
      videoURLs             A series or video page URL, eg:
                            https://animelon.com/series/Death%20Note or
                            https://animelon.com/video/579b1be6c13aa2a6b28f1364
    
    optional arguments:
      -h, --help            show this help message and exit
      -d delay, --sleepTime delay
                            Sleep time between each download (defaults to 5)
      --savePath savePath   Path to save
      --forks forks         Number of worker process for simultaneous downloads
                            (defaults to 1)
      --maxTries maxTries   Maximum number of retries in case of failed requests
                            (defaults to 5)

## TODO:
This script does not currently supports fetching subtitles from animelon, this is because animelon serves it's subtitles in encrypted Base64 via an API and decrypts it using obfuscated Javascript.

Feel free to contribute if you find a way.
