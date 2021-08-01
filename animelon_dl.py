#!/usr/bin/env python3

from requests import get , post, Session
import time
import os
import json
import numpy as np
from multiprocessing import Process
import progressbar
import argparse
import sys
import subtitle_decryptor

class AnimelonDownloader():
	def __init__(self, baseURL:str="https://animelon.com/", session=Session(), processMax:int=1, sleepTime:int=0,
				maxTries:int=5, savePath:str="./", subtitlesTypes:list=["englishSub", "romajiSub", "hiraganaSub", "japaneseSub"],
				sleepTimeRetry=5, qualityPriorities=["ozez", "stz", "tsz"], subtitlesOnly=False,
				userAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"):
		'''
			Initialize the downloader
			Parameters:
				baseURL: the base url of the API
				session: the requests session
				processMax: the maximum number of processes to use
				sleepTime: the time to sleep between requests
				maxTries: the maximum number of tries to make
				savePath: the path to save the files to
				subtitlesTypes: the types of subtitle to download (englishSub, romajiSub, hiraganaSub, japaneseSub)
				userAgent: the user agent to use
				sleepTimeRetry: the time to sleep between retries
				qualityPriorities: the quality priorities to use [best, .., worst], ozez is the best, stz is the medium, tsz is the worst
		'''
		self.baseURL = baseURL
		self.session = session
		self.userAgent = userAgent
		self.headers = { "User-Agent": self.userAgent }
		self.apiVideoFormat = "https://animelon.com/api/languagevideo/findByVideo?videoId=%s&learnerLanguage=en&subs=1&cdnLink=1&viewCounter=1"
		self.session.headers.update(self.headers)
		self.processList = []
		self.processMax = processMax
		self.sleepTime = sleepTime
		self.sleepTimeRetry = sleepTimeRetry
		self.maxTries = maxTries
		self.savePath = savePath
		self.initSavePath(savePath)
		self.subtitlesTypes = subtitlesTypes
		self.qualityPriorities = qualityPriorities
		self.subtitlesOnly = subtitlesOnly
	def updateUserAgent(self, userAgent:str):
		'''
			Updates the user agent
			Parameters:
				userAgent: the new user agent
		'''
		self.userAgent = userAgent
		self.headers = { "User-Agent": self.userAgent }
		self.session.headers.update(self.headers)

	def __repr__(self):
		'''
			Returns:
				the string representation of the object
		'''
		rep = 'AnimelonDownloader(baseURL="%s", processMax=%d, sleepTime=%d, maxTries=%d, savePath="%s", session=%s, userAgent="%s", headers="%s", processList=%s)' \
		% (self.baseURL, self.processMax, self.sleepTime, self.maxTries, self.savePath, self.session, self.userAgent, self.headers, self.processList)
		return (rep)

	def waitForFreeProcess(self, processMax=None):
		'''
			Waits for the process list to be < processMax long
		'''
		if processMax is None:
			processMax = self.processMax
		while len(self.processList) >= processMax:
			newList = [process for process in self.processList if process.is_alive()]
			self.processList = newList
			time.sleep(self.sleepTime)

	def launchBackgroundTask(self, function, args:tuple):
		'''
			Launches a background task and adds it to the process list.
				Parameters:
					function: the function to run
					args: the arguments to pass to the function
				Returns:
					the process
		'''
		self.waitForFreeProcess()
		p = Process(target=function, args=args)
		self.processList.append(p)
		p.start()
		return (p)

	def __del__(self):
		'''
			Closes the session
		'''
		self.waitForFreeProcess(1)

	def downloadVideo(self, url, fileName=None, stream=None, quality="unknown"):
		'''
			Downloads a video from the url
				Parameters:
					url: the url of the video
					fileName: the name of the video
					stream: the stream to download from (mp4, webm, ogg, mkv)
				Returns:
					the file name
		'''
		if fileName is None:
			fileName = url.split("/")[-1] + ".mp4"
			fileName = os.path.join(self.savePath, fileName)
		video = stream
		if video is None:
			video = self.session.get(url, stream=True)
			# Estimates the number of bar updates
		block_size = 1024
		file_size = int(video.headers.get('Content-Length', None))
		print ("Downloading : ", fileName.split('/')[-1] , "(%.2f MB)" % (file_size * 1024 ** -2) , quality, " quality", " ...\n")
		n_chunk = 2
		num_bars = np.ceil(file_size / (n_chunk * block_size))
		bar = None
		if len(self.processList) == 1:
			bar = progressbar.ProgressBar(maxval=num_bars).start()
		with open(fileName, 'wb') as f:
			for i, chunk in enumerate(video.iter_content(chunk_size=n_chunk * block_size)):
				f.write(chunk)
				if bar is not None:
					bar.update(i+1)
		return (fileName)
		# (did not)Add a little sleep so you can see the bar progress

	def getSubtitleFromJSON(self, resObj, languageSubList:list=None):
		'''	Retrieves subtitle from API's resObj['resObj']['subtitles'][n]['content']['languageSub'] and uncipheres them
				Paremeters:
					resObj: the response object from the API
					languageSubList: the list of languageSub to save (englishSub, romajiSub, hiraganaSub, japaneseSub)
					savePath: the path to save the subtitle to
				Return:
					a list of tuples (subtitleName, subtitleContent)
		'''
		decryptor = subtitle_decryptor.SubtitleDecryptor()
		if languageSubList is None:
			languageSubList = self.subtitlesTypes
		subtitles = []
		subObj = resObj["subtitles"]
		for i in subObj:
			subtitleList = i["content"]
			for j in languageSubList:
				if j in subtitleList.keys():
					subtitles.append((j, decryptor.decrypt_subtitle(subtitleList[j])))
		return (subtitles)

	#def saveSubtitle(self, resObj, languageSubList:list=None, savePath:str=None):
	#	'''	Parse the subtitle from resObj and saves them '''
	#	subs = self.getSubtitleFromJSON(resObj, languageSubList)
	#	for i in subs:
	#		self.saveSubtitleToFile(i[0], i[1], savePath=savePath)

	def languageSubToIso(self, languageSub:str):
		iso = {"englishSub" : "en", 'romajiSub' : "ja", "japaneseSub" : "jp", "hiraganaSub" : "hiragana"}
		if languageSub in iso:
			return (iso[languageSub])
		return (languageSub)

	def saveSubtitleToFile(self, languageSub, content, videoName:str="" ,savePath:str=None):
		'''
			Saves the subtitle to a file
				Parmeters:
					languageSub: the language of the subtitle (englishSub, romajiSub, hiraganaSub, japaneseSub)
					content: the content of the subtitle
					videoName: the name of the video
					savePath: the path to save the file
				Returns:
					the file name
		'''
		if savePath is None:
			savePath = self.savePath
		ext = ".ass"
		if content[0:4] == b"\x31\x0A\x30\x30": #srt magicbytes
			ext = ".srt"
		languageSub = self.languageSubToIso(languageSub)
		fileName = videoName + "." + languageSub + ext
		fileName = os.path.join(savePath, fileName)
		with open(fileName, "wb") as f:
			f.write(content)
		return (fileName)

	def saveSubtitlesFromResObj(self, resObj, videoName=None, languageSubList:list=None, savePath:str=None):
		'''
		Parse the subtitle from resObj and saves them
			Parameters:
				resObj: the resOBJ JSON object from the JSON response from the API
				videoName: the name of the video
				languageSubList: the list of languageSub to save (englishSub, romajiSub, hiraganaSub, japaneseSub)
				savePath: the path to save the subtitle to
			Returns:
				a list of file names
		'''
		fileNames = []
		subtitleList = self.getSubtitleFromJSON(resObj, languageSubList)
		for sub in subtitleList:
			fileNames.append(self.saveSubtitleToFile(sub[0], sub[1], savePath=savePath, videoName=videoName))
		return (fileNames)
	
	def downloadFromResObj(self, resObj, fileName=None, saveSubtitle=True, subtitlesOnly=False):
		''' Downloads the video and it's subtitles from the API's JSON's resObj
				Parameters:
					resObj: the resOBJ JSON object from the JSON response from the API
					fileName: the name of the video file to be saved
					saveSubtitle: whether to save the subtitle or not
				Returns:
					the file name
		'''
		title = resObj["title"]
		if fileName is None:
			fileName = os.path.join(self.savePath, title + ".mp4")
		if (saveSubtitle):
			self.saveSubtitlesFromResObj(resObj, videoName=os.path.basename(fileName).replace(".mp4", ""),
				savePath=os.path.dirname(fileName))
		if (self.subtitlesOnly):
			return (None)
		video = (resObj["video"])
		videoURLs = video["videoURLsData"]
		time.sleep(self.sleepTime)
		for userAgentKey in videoURLs.keys():
			# animelon will allow us to download the video only if we send the corresponding user agent
			#also idk why the userAgent is formatted that way in the JSON, but we have to replace this.
			self.updateUserAgent(userAgentKey.replace("=+(dot)+=", "."))
			mobileUrlList = videoURLs[userAgentKey]
			videoURLsSublist = mobileUrlList["videoURLs"]
			for quality in self.qualityPriorities:
				if quality in videoURLsSublist.keys():
					videoURL = videoURLsSublist[quality]
					videoStream = self.session.get(videoURL, stream=True)
					if videoStream.status_code == 200:
						self.downloadVideo(videoURL, fileName=fileName, stream=videoStream, quality=quality)
						print ("Finished downloading ", fileName)
						return (fileName)
		return (None)

	def downloadFromVideoPage(self, url=None, id=None, fileName=None, background=False, saveSubtitle=True):
		''' Downloads a video from the video page or it's id
				Parameters:
					url: the video page url (https://animelon.com/video/5b5412ce33107581e4f672a5)
					id: the video id (5b5412ce33107581e4f672a5)
					fileName: the file name to save the video to
					background: if True, the download will be started in the background
					saveSubtitle: if True, the subtitle will be saved
				Returns:
					the file name
		'''
		assert(url is not None or id is not None)
		if background:
			self.launchBackgroundTask(self.downloadFromVideoPage, (url, id, fileName, False))
			time.sleep(self.sleepTime)
			return (None)
		if url is None:
			url = self.baseURL + "video/" + id
		if id is None:
			id = url.split("/")[-1]
		
		apiUrl = self.apiVideoFormat % (id)
		for tries in range(self.maxTries):
			response = get(apiUrl, headers=self.headers)
			if response.status_code == 200:		
				jsonsed = json.loads(response.content)
				file = self.downloadFromResObj(jsonsed["resObj"], fileName=fileName, saveSubtitle=saveSubtitle)
				if file is not None:
					return (file)
				print ("Failed to download ", fileName, "retrying ... (", self.maxTries - tries, " tries left)"),
				time.sleep(self.sleepTime * tries)
		print ("Failed to download ", fileName)
		return (None)

	def getEpisodeList(self, seriesURL):
		''' 
			Returns a list of all the episodes of a series from the series page
			ex: https://animelon.com/series/Shoujo%20Shuumatsu%20Ryokou%20(Girls'%20Last%20Tour)
			
		'''
		seriesName = seriesURL.rsplit('/', 1)[-1]
		url = self.baseURL + "api/series/" + seriesName
		statusCode = 403
		tries = 0
		while statusCode != 200 and tries < self.maxTries:
			response = self.session.get(url)
			statusCode = response.status_code
			tries += 1
			time.sleep(0.5)
		if (statusCode != 200):
			print ("Error getting anime info")
			return (None)
		try:
			jsoned = json.loads(response.text)
			resObj = jsoned["resObj"]
			if resObj is None and '\\' in seriesURL:
				seriesURL = seriesURL.replace('\\', '')
				return ((self.getEpisodeList(seriesURL)))
			assert (resObj is not None)
		except Exception as e:
			print ("Error: Could not parse anime info :\n", e, url , "\n", response, response.content, file=sys.stderr)
			return (None)
		return (resObj)

	def initSavePath(self, name):
		'''
		Initialize the save path and creates the directories
			Parameters:
				name: the name of the anime
			Returns:
				the save path
		'''
		if self.savePath == "./" or name == "":
			self.savePath = name
		if self.savePath == "":
			self.savePath = "./"
		os.makedirs(self.savePath, exist_ok=True)
		return (self.savePath)

	def downloadEpisodes(self, episodes:dict, title:str, episodesToDownload:dict=None, seasonNumber:int=0, savePath:str="./"):
		'''
			Downloads the episodes from the episodes dict

				Parameters:
					episodes: dict of episodes
					title: name of the series
					episodesToDownload: dict of episodes to download
					seasonNumber: season number
					savePath: path to save the episodes
				Returns:
					the list of downloaded episodes
		'''
		index = 0
		downloadedEpisodes = []
		for episode in episodes:
			index += 1
			if episodesToDownload is None or index in episodesToDownload[seasonNumber]:
				self.waitForFreeProcess()
				url = self.baseURL + "video/" + episode
				fileName = title + " S" + str(seasonNumber) + "E" + str(index) + ".mp4"
				os.makedirs(savePath, exist_ok=True)
				fileName = os.path.join(savePath, fileName)
				print(fileName, " : ", url)
				try:
					self.downloadFromVideoPage(url, fileName=fileName, background=True)
					downloadedEpisodes.append(index)
				except Exception as e:
					print("Error: Failed to download " + url, file=sys.stderr)
					print(e)
		return (downloadedEpisodes)

#episodesToDownload = {season_i : [episode_j, episode_j+1]}
	def downloadSeries(self, url, seasonsToDownload:list=None, episodesToDownload:dict=None, background=False):
		'''
			Downloads the episodes of a series from it's page url (/series/)

				Parameters:
					url: url of the series page
					seasonsToDownload: list of seasons to download
					episodesToDownload: dict of episodes to download, keys are season number, values are list of episode numbers
					background: if true, the downloads will be launched in a background process
				Returns:
					A dict of downloaded episodes
						key: season number
						value: list of downloaded episodes
		'''
		resObj = self.getEpisodeList(url)
		if resObj is None:
			return ()
		title = resObj["_id"]
		print("Title: ", title)
		seriesSavePath = os.path.join(self.savePath, title)
		seasons = resObj["seasons"]
		downloadedEpisodesDict = dict()
		for season in seasons:
			seasonNumber = int(season["number"])
			seasonSavePath = os.path.join(seriesSavePath, "S%.2d" % seasonNumber)
			os.makedirs(seasonSavePath, exist_ok=True)
			if seasonsToDownload is None or seasonNumber in seasonsToDownload:
				print("Season %d:" % (seasonNumber))
				episodes = season["episodes"]
				downloadedEpisodes = self.downloadEpisodes(episodes, title, episodesToDownload=episodesToDownload, seasonNumber=seasonNumber, savePath=seasonSavePath)
				downloadedEpisodesDict[seasonNumber] = downloadedEpisodes
		if background is False:
			self.waitForFreeProcess(1)
		return (downloadedEpisodesDict)

	def downloadFromURL(self, url:str, seasonsToDownload:list=None, episodesToDownload:dict=None, parallell=False):
		'''
			Either downloads the episodes of a series from it's page url (/series/) or downloads the episodes of a video from it's page url (/video/)
				
				Parameters:
					url: url of the video or series page
					seasonsToDownload: list of seasons to download
					episodesToDownload: dict of episodes to download, keys are season number, values are list of episode numbers
					parallell: if true, the downloads will be launched in a background process
				Returns:
					Either a dict of downloaded episodes or 				
		'''
		try:
			type = url.split('/')[3]
		except IndexError:
			print('Error: Bad URL : "%s"' % url)
			return ()
		if type == 'series':
			dl = downloader.downloadSeries(url, seasonsToDownload=seasonsToDownload, episodesToDownload=episodesToDownload)
		elif type == 'video':
			downloader.downloadFromVideoPage(url, background=parallell)
		else:
			print('Error: Unknown URL type "%"' % type, file=sys.stderr)


	def downloadFromURLList(self, URLs:list, seasonsToDownload:list=None, episodesToDownload:dict=None, background=False):
		'''
			Downloads the episodes of a series from a list of URLs
				Parameters:
					URLs: list of URLs
					seasonsToDownload: list of seasons to download
					episodesToDownload: dict of episodes to download, keys are season number, values are list of episode numbers
					background: if true, the downloads will be launched in background processes
				Returns:
					A list of dict of downloaded episodes
		'''
		dlEpisodes = []
		for url in URLs:
			dlEpisodes.append(self.downloadFromURL(url, seasonsToDownload=seasonsToDownload, episodesToDownload=episodesToDownload, parallell=True))
		if background is False:
			self.waitForFreeProcess(1)
		return (dlEpisodes)

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Downloads videos from animelon.com')
	parser.add_argument('videoURLs', metavar='videoURLs', type=str, nargs='+',
						help='A series or video page URL, eg: https://animelon.com/series/Death%%20Note or https://animelon.com/video/579b1be6c13aa2a6b28f1364')
	parser.add_argument("--sleepTime", '-d', metavar='delay', help="Sleep time between each download (defaults to 5)", type=float, default=5)
	parser.add_argument("--savePath", '-f', metavar='savePath', help='Path to save', type=str, default="")
	parser.add_argument('--forks', metavar='forks', help='Number of worker process for simultaneous downloads (defaults to 1)', type=int, default=1)
	parser.add_argument('--maxTries', metavar='maxTries', help='Maximum number of retries in case of failed requests (defaults to 5)', type=int, default=5)
	parser.add_argument('--sleepTimeRetry', metavar='sleepTimeRetry', help='Sleep time between retries (defaults to 5)', type=float, default=5)
	parser.add_argument('--subtitlesType', metavar='subtitlesType', help='Subtitles types to download (englishSub, romajiSub, hiraganaSub, japaneseSub, none)',\
		type=str, default=("englishSub", "romajiSub", "hiraganaSub", "japaneseSub"), nargs='+')
	parser.add_argument('--subtitlesOnly', help='Only downloads subtitles', action='store', default=False, const=True, nargs='?')
	args = parser.parse_args()
	urls = args.videoURLs
	downloader = AnimelonDownloader(savePath=args.savePath, processMax=args.forks, maxTries=args.maxTries,
		sleepTime=args.sleepTime, sleepTimeRetry=args.sleepTimeRetry, subtitlesTypes=args.subtitlesType, subtitlesOnly=args.subtitlesOnly)
	downloader.downloadFromURLList(urls)
	exit(0)
