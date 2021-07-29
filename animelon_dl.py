from requests import get , post, Session
import time
import os
import json
import numpy as np
from multiprocessing import Process
import progressbar
import argparse
import sys

class AnimelonDownloader():
	def __init__(self, baseURL="https://animelon.com/", session=Session(), processMax=1, sleepTime=5, maxTries=5, savePath="", userAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"):
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

	def __repr__(self):
		rep = 'AnimelonDownloader(baseURL="%s", processMax=%d, sleepTime=%d, maxTries=%d, savePath="%s", session=%s, userAgent="%s", headers="%s", processList=%s)' \
		% (self.baseURL, self.processMax, self.sleepTime, self.maxTries, self.savePath, self.session, self.userAgent, self.headers, self.processList)
		return rep

	def waitForFreeProcess(self, processMax=None):
		if processMax is None:
			processMax = self.processMax
		while len(self.processList) >= processMax:
			newList = [process for process in self.processList if process.is_alive()]
			self.processList = newList
			time.sleep(5)

	def launchBackgroundTask(self, function, args:tuple):
		self.waitForFreeProcess()
		p = Process(target=function, args=args)
		self.processList.append(p)
		p.start()

	def __del__(self):
		self.waitForFreeProcess(1)

	def downloadVideo(self, url, fileName=None, stream=None):
		if fileName is None:
			fileName = url.split("/")[-1] + ".mp4"
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
		fileName = os.path.join(self.savePath, fileName)
		with open(fileName, 'wb') as f:
			for i, chunk in enumerate(video.iter_content(chunk_size=n_chunk * block_size)):
				f.write(chunk)
				if bar is not None:
					bar.update(i+1)
		# (did not)Add a little sleep so you can see the bar progress

	def downloadFromResObj(self, resObj, fileName=None):
		if fileName is None:
			fileName = resObj["title"] + ".mp4"
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

	def downloadFromVideoPage(self, url=None, id=None, fileName=None, background=False):
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
		return (self.downloadFromResObj(jsonsed["resObj"], fileName=fileName))

	def getEpisodeList(self, seriesUrl):
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
				seriesUrl = seriesUrl.remove('\\')
				return (self.getEpisodeList(seriesUrl))
			assert (resObj is not None)
		except Exception as e:
			print ("Error: Could not parse anime info :\n", e, url , "\n", response, response.content, file=sys.stderr)
			return None
		return resObj

	def initSavePath(self, name):
		if self.savePath == "":
			self.savePath = name
		os.makedirs(self.savePath, exist_ok=True)

	def downloadEpisodes(self, episodes:dict, title:str, episodesToDownload:dict=None, seasonNumber:int=0):
		index = 0
		for episode in episodes:
			index += 1
			if episodesToDownload is None or index in episodesToDownload[seasonNumber]:
				self.waitForFreeProcess()
				url = self.baseURL + "video/" + episode
				fileName = title + " S" + str(seasonNumber) + "E" + str(index) + ".mp4"
				print(fileName, " : ", url)
				try:
					self.downloadFromVideoPage(url, fileName=fileName, background=True)
				except Exception as e:
					print("Error: Failed to download " + url, file=sys.stderr)
					print(e)

#episodesToDownload = {season_i : [episode_j, episode_j+1]}
	def downloadSeries(self, url, seasonsToDownload:list=None, episodesToDownload:dict=None, background=False):
		#https://animelon.com/api/series/Shoujo%20Shuumatsu%20Ryokou%20(Girls'%20Last%20Tour)
		#url = everything after last /
		resObj = self.getEpisodeList(url)
		if resObj is None:
			return
		title = resObj["_id"]
		print("Title: ", title)
		self.initSavePath(title)
		seasons = resObj["seasons"]
		for season in seasons:
			seasonNumber = int(season["number"])
			if seasonsToDownload is None or seasonNumber in seasonsToDownload:
				print("Season %d:" % (seasonNumber))
				episodes = season["episodes"]
				self.downloadEpisodes(episodes, title, episodesToDownload=episodesToDownload, seasonNumber=seasonNumber)
		if background is False:
			self.waitForFreeProcess(1)

	def downloadFromURL(self, url:str, seasonsToDownload:list=None, episodesToDownload:dict=None, background=False):
		try:
			type = url.split('/')[3]
		except IndexError:
			print('Error: Bad URL : "%s"' % url)
			return
		if type == 'series':
			downloader.downloadSeries(url, seasonsToDownload=seasonsToDownload, episodesToDownload=episodesToDownload)
		elif type == 'video':
			downloader.downloadFromVideoPage(url, background=background)
		else:
			print('Error: Unknown URL type "%"' % type, file=sys.stderr)


	def downloadFromURLList(self, URLs:list, seasonsToDownload:list=None, episodesToDownload:dict=None, background=False):
		for url in URLs:
			self.downloadFromURL(url, seasonsToDownload=seasonsToDownload, episodesToDownload=episodesToDownload, background=True)
		if background:
			self.waitForFreeProcess(1)

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Downloads videos from animelon.com')
	parser.add_argument('videoURLs', metavar='videoURLs', type=str, nargs='+',
						help='A video page URL, eg: https://animelon.com/video/579b1be6c13aa2a6b28f1364')
	parser.add_argument('-d', "--sleepTime", metavar='delay', help="Sleep time between each download (defaults to 5)", type=int, default=5)
	parser.add_argument('--savePath', metavar='savePath', help='Path to save', type=str, default="")
	parser.add_argument('--forks', metavar='forks', help='Number of worker process for simultaneous downloads (defaults to 1)', type=int, default=1)
	parser.add_argument('--maxTries', metavar='maxTries', help='Maximum number of retries in case of failed requests (defaults to 5)', type=int, default=5)
	args = parser.parse_args()
	urls = args.videoURLs
	print(urls)
	downloader = AnimelonDownloader(savePath=args.savePath, processMax=args.forks, maxTries=args.maxTries, sleepTime=args.sleepTime)
	downloader.downloadFromURLList(urls)
	exit(0)
