

# animelon_download
Command line downloader for https://animelon.com/

## Requirements:
       requests
       progressbar
       numpy
       pycryptodome
       hashlib
## Usage:

       ⇒  ./animelon_dl.py -h                                                               
       usage: animelon_dl.py [-h] [--sleepTime delay] [--savePath savePath]
                             [--forks forks] [--maxTries maxTries]
                             videoURLs [videoURLs ...]

       Downloads videos from animelon.com

       positional arguments:
         videoURLs             A series or video page URL, eg:
                               https://animelon.com/series/Death%20Note or
                               https://animelon.com/video/579b1be6c13aa2a6b28f1364

       optional arguments:
         -h, --help            show this help message and exit
         --sleepTime delay, -d delay
                               Sleep time between each download (defaults to 5)
         --savePath savePath, -f savePath
                               Path to save
         --forks forks         Number of worker process for simultaneous downloads
                               (defaults to 1)
         --maxTries maxTries   Maximum number of retries in case of failed requests
                        (defaults to 5)

