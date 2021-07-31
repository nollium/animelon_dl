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
	def __init__(self, baseURL="https://animelon.com/", session=Session(), processMax=1, sleepTime=5, maxTries=5, savePath="./", userAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"):
		self.baseURL = baseURL
		self.session = session
		self.userAgent = userAgent
		self.videoUserAgent="Mozilla/5=+(dot)+=0 (Linux; Android 9; CPH2015) AppleWebKit/537=+(dot)+=36 (KHTML, like Gecko) Chrome/91=+(dot)+=0=+(dot)+=4472=+(dot)+=164 Mobile Safari/537=+(dot)+=36"
		self.headers = { "user-agent": self.userAgent }
		self.apiVideoFormat = "https://animelon.com/api/languagevideo/findByVideo?videoId=%s&learnerLanguage=en&subs=1&cdnLink=1&viewCounter=1"
		self.session.headers.update(self.headers)
		self.processList = []
		self.processMax = processMax
		self.sleepTime = sleepTime
		self.maxTries = maxTries
		self.savePath = savePath
		self.initSavePath(savePath)
		self.subtitleTypes = ["englishSub", "romajiSub", "hiraganaSub", "japaneseSub"]

	def __repr__(self):
		'''
			Returns:
				the string representation of the object
		'''
		rep = 'AnimelonDownloader(baseURL="%s", processMax=%d, sleepTime=%d, maxTries=%d, savePath="%s", session=%s, userAgent="%s", headers="%s", processList=%s)' \
		% (self.baseURL, self.processMax, self.sleepTime, self.maxTries, self.savePath, self.session, self.userAgent, self.headers, self.processList)
		return rep

	def waitForFreeProcess(self, processMax=None):
		'''
			Waits for the process list to be < processMax long
		'''
		if processMax is None:
			processMax = self.processMax
		while len(self.processList) >= processMax:
			newList = [process for process in self.processList if process.is_alive()]
			self.processList = newList
			time.sleep(5)

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
		return p

	def __del__(self):
		'''
			Closes the session
		'''
		self.waitForFreeProcess(1)

	def downloadVideo(self, url, fileName=None, stream=None):
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
		print ("Downloading : ", fileName , "(%.2f MB)" % (file_size * 1024 ** -2) , " ...\n")
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
		return fileName
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
			languageSubList = self.subtitleTypes
		subtitles = []
		subObj = resObj["subtitles"]
		for i in subObj:
			subtitleList = i["content"]
			for j in languageSubList:
				if j in subtitleList.keys():
					subtitles.append((j, decryptor.decrypt_subtitle(subtitleList[j])))
		return subtitles

	#def saveSubtitle(self, resObj, languageSubList:list=None, savePath:str=None):
	#	'''	Parse the subtitle from resObj and saves them '''
	#	subs = self.getSubtitleFromJSON(resObj, languageSubList)
	#	for i in subs:
	#		self.saveSubtitleToFile(i[0], i[1], savePath=savePath)

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
		fileName = languageSub + "_" + videoName + ext
		fileName = os.path.join(savePath, fileName)
		with open(fileName, "wb") as f:
			f.write(content)
		return fileName

	def saveSubtitleFromResObj(self, resObj, videoName=None, languageSubList:list=None, savePath:str=None):
		'''
		Parse the subtitle from resObj and saves them
			Parameters:
				resObj: the resOBJ JSON object from the JSON response from the API
				videoName: the name of the video
				languageSubList: the list of languageSub to save (englishSub, romajiSub, hiraganaSub, japaneseSub)
				savePath: the path to save the subtitle to

		'''
		subs = self.getSubtitleFromJSON(resObj, languageSubList)
		for i in subs:
			self.saveSubtitleToFile(i[0], i[1], savePath=savePath, videoName=videoName)
	
	def downloadFromResObj(self, resObj, fileName=None, saveSubtitle=True):
		''' Downloads the video and it's subtitles from the API's JSON's resObj
				Parameters:
					resObj: the resOBJ JSON object from the JSON response from the API
					fileName: the name of the video file to be saved
					saveSubtitle: whether to save the subtitle or not
				Returns:
					False in case of failure
					True in case of success
		'''
		title = resObj["title"]
		if fileName is None:
			fileName = os.path.join(self.savePath, title + ".mp4")
		if saveSubtitle:
			self.saveSubtitleFromResObj(resObj, videoName=title, savePath=os.path.dirname(fileName))
		video = (resObj["video"])
		videoUrls = video["videoURLsData"]
		#list of lists of lists of urls, yeah
		#only one of them is valid, so we try all of them
		for i in range(1, self.maxTries + 1):
			for mobileUrlList in videoUrls.values():
				for mobileUrlList in videoUrls.values():
					videoUrlsSublist = mobileUrlList["videoURLs"]
					for videoUrl in videoUrlsSublist.values():
						time.sleep(0.2)
						videoStream = self.session.get(videoUrl, stream=True)
						if videoStream.status_code == 200:
							self.downloadVideo(videoUrl, fileName=fileName, stream=videoStream)
							print ("Finished downloading ", fileName)
							return True
			print ("No video found for %s, retrying ... (%d tries left)" % (fileName, self.maxTries - i))
			time.sleep(self.sleepTime * i)
			
		print ("No valid download link found for %s after %d retries" % (fileName, self.maxTries))
		return False

#unused and unfinished
	def recursiveDownload(self, url, filename=None):
		'''
			Do not use
		'''
		response = get(url, headers=self.headers, stream=True)
		if response.status_code == 200:
			headers = response.headers
			if (headers["Content-Type"] == "video/mp4"):
				self.downloadVideo(url, fileName=filename, stream=response)
				return
			elif (headers["Content-Type"] == "application/json"):
				data = json.loads(response.content)
				if "resObj" in data.keys():
					self.downloadFromResObj(data["resObj"], fileName=filename)
					return

	def downloadFromVideoPage(self, url=None, id=None, fileName=None, background=False, saveSubtitle=True):
		''' Downloads a video from the video page or it's id
				Parmeters:
					url: the video page url (https://animelon.com/video/5b5412ce33107581e4f672a5)
					id: the video id (5b5412ce33107581e4f672a5)
					fileName: the file name to save the video to
					background: if True, the download will be started in the background
					saveSubtitle: if True, the subtitle will be saved
		'''
		assert(url is not None or id is not None)
		if background:
			self.launchBackgroundTask(self.downloadFromVideoPage, (url, id, fileName, False))
			time.sleep(self.sleepTime)
			return None
		if url is None:
			url = self.baseURL + "video/" + id
		if id is None:
			id = url.split("/")[-1]
		apiUrl = self.apiVideoFormat % (id)
		response = get(apiUrl, headers=self.headers)
		jsonsed = json.loads(response.content)
		return (self.downloadFromResObj(jsonsed["resObj"], fileName=fileName, saveSubtitle=saveSubtitle))

	def getEpisodeList(self, seriesUrl):
		''' Returns a list of all the episodes of a series from the series page
			ex: https://animelon.com/series/Shoujo%20Shuumatsu%20Ryokou%20(Girls'%20Last%20Tour)
		'''
		seriesName = seriesUrl.rsplit('/', 1)[-1]
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
			return None
		try:
			jsoned = json.loads(response.text)
			resObj = jsoned["resObj"]
			if resObj is None and '\\' in seriesUrl:
				seriesUrl = seriesUrl.replace('\\', '')
				return (self.getEpisodeList(seriesUrl))
			assert (resObj is not None)
		except Exception as e:
			print ("Error: Could not parse anime info :\n", e, url , "\n", response, response.content, file=sys.stderr)
			return None
		return resObj

	def initSavePath(self, name):
		'''
		Initialize the save path and creates the directories
			Parameters:
				name: the name of the anime
		'''
		if self.savePath == "./" or name == "":
			self.savePath = name
		if self.savePath == "":
			self.savePath = "./"
		os.makedirs(self.savePath, exist_ok=True)

	def downloadEpisodes(self, episodes:dict, title:str, episodesToDownload:dict=None, seasonNumber:int=0, savePath:str="./"):
		'''
			Downloads the episodes from the episodes dict

				Parameters:
					episodes: dict of episodes
					title: name of the series
					episodesToDownload: dict of episodes to download
					seasonNumber: season number
					savePath: path to save the episodes
		'''
		index = 0
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
				except Exception as e:
					print("Error: Failed to download " + url, file=sys.stderr)
					print(e)

#episodesToDownload = {season_i : [episode_j, episode_j+1]}
	def downloadSeries(self, url, seasonsToDownload:list=None, episodesToDownload:dict=None, background=False):
		'''
			Downloads the episodes of a series from it's page url (/series/)

				Parameters:
					url: url of the series page
					seasonsToDownload: list of seasons to download
					episodesToDownload: dict of episodes to download, keys are season number, values are list of episode numbers
					background: if true, the downloads will be launched in a background process
		'''
		resObj = self.getEpisodeList(url)
		if resObj is None:
			return
		title = resObj["_id"]
		print("Title: ", title)
		seriesSavePath = os.path.join(self.savePath, title)
		seasons = resObj["seasons"]
		for season in seasons:
			seasonNumber = int(season["number"])
			seasonSavePath = os.path.join(seriesSavePath, "S%.2d" % seasonNumber)
			os.makedirs(seasonSavePath, exist_ok=True)
			if seasonsToDownload is None or seasonNumber in seasonsToDownload:
				print("Season %d:" % (seasonNumber))
				episodes = season["episodes"]
				self.downloadEpisodes(episodes, title, episodesToDownload=episodesToDownload, seasonNumber=seasonNumber, savePath=seasonSavePath)
		if background is False:
			self.waitForFreeProcess(1)

	def downloadFromURL(self, url:str, seasonsToDownload:list=None, episodesToDownload:dict=None, parallell=False):
		'''
			Either downloads the episodes of a series from it's page url (/series/) or downloads the episodes of a video from it's page url (/video/)
				
				Parameters:
					url: url of the video or series page
					seasonsToDownload: list of seasons to download
					episodesToDownload: dict of episodes to download, keys are season number, values are list of episode numbers
					parallell: if true, the downloads will be launched in a background process
		'''
		try:
			type = url.split('/')[3]
		except IndexError:
			print('Error: Bad URL : "%s"' % url)
			return
		if type == 'series':
			downloader.downloadSeries(url, seasonsToDownload=seasonsToDownload, episodesToDownload=episodesToDownload)
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
		'''
		for url in URLs:
			self.downloadFromURL(url, seasonsToDownload=seasonsToDownload, episodesToDownload=episodesToDownload, parallell=True)
		if background is False:
			self.waitForFreeProcess(1)

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Downloads videos from animelon.com')
	parser.add_argument('videoURLs', metavar='videoURLs', type=str, nargs='+',
						help='A series or video page URL, eg: https://animelon.com/series/Death%%20Note or https://animelon.com/video/579b1be6c13aa2a6b28f1364')
	parser.add_argument("--sleepTime", '-d', metavar='delay', help="Sleep time between each download (defaults to 5)", type=int, default=5)
	parser.add_argument("--savePath", '-f', metavar='savePath', help='Path to save', type=str, default="")
	parser.add_argument('--forks', metavar='forks', help='Number of worker process for simultaneous downloads (defaults to 1)', type=int, default=1)
	parser.add_argument('--maxTries', metavar='maxTries', help='Maximum number of retries in case of failed requests (defaults to 5)', type=int, default=5)
	args = parser.parse_args()
	urls = args.videoURLs
	downloader = AnimelonDownloader(savePath=args.savePath, processMax=args.forks, maxTries=args.maxTries, sleepTime=args.sleepTime)
	downloader.downloadFromURLList(urls)
	exit(0)
