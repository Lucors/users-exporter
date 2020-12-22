# -*- coding: utf-8 -*-
import sys
import os
import json
import time
import datetime
import requests
import traceback 
from lxml import etree
from requests.exceptions import HTTPError
from bs4 import BeautifulSoup, SoupStrainer

class UsersExporter:
	"""Универсальный экспортер пользователей"""
	def __init__(self, customConfig=""):
		self.log = ""
		self.readConfig(customConfig)

	def readConfig(self, customFilename):
		filename = "config.json"
		if (customFilename != ""):
			filename = customFilename
		configFile = open(filename, "r", encoding="utf-8")
		self.config = configFile.read()
		configFile.close()
		self.config = json.loads(self.config)
		self.__setupByConfig()
		self.__log("Прочитаны данные конфигурации: " + filename)

	def __setupByConfig(self):
		pass

	def __waitForAnswer(self, msg, trueVal = ["y", "д"], falseVal = ["n"], returnNone = False):
		self.__log(msg, prefix = "<?>", end = "")
		answer = input().lower()
		for i in range(len(trueVal)):
			if (answer == trueVal[i].lower()):
				return True
		for i in range(len(falseVal)):
			if (answer == falseVal[i].lower()):
				return False
		if (returnNull):
			return None
		else:
			self.__error("Невозможно истолковать ваш ответ.", start="")
			self.__waitForAnswer(msg, trueVal=trueVal, falseVal=falseVal, returnNone=returnNone)

	def shutdown(self):
		if (self.config["oOutputConfig"]["fCreateLogFile"]):
			self.writeLog();
		sys.exit(1)

	def __error(self, msg, start = "%time", end = "\n"):
		self.__log(msg, prefix = "<!>", start=start, end=end)
		
	def __clog(self, msg, end = "\n"):
		self.__log(msg, prefix="", start="", end=end)

	def __log(self, msg, prefix = "<->", start = "%time", end = "\n"):
		if (start == "%time"):
			start = datetime.datetime.today().strftime("%H:%M:%S")
		output = f"{start} {prefix} {msg}"
		self.log += f"{output} {end}" 
		if (self.config["oOutputConfig"]["fConsoleOutput"]):
			print(output, end = end)

	def writeLog(self, filename = "log.txt"):
		logfile = open(filename, 'w', encoding = "utf-8")
		logfile.write(self.log)
		logfile.close()

	def __redirector(self, localpath):
		if (not os.path.exists(localpath)):
			os.mkdir(localpath)
		os.chdir(localpath)

	def mreplace(self, target, replacement):
	    for i, j in replacement.items():
	    	if (j == "%CUTAFTER"):
	    		pos = target.find(i)
	    		if (pos > 0):
	    			target = target[:pos]
	    	elif (j == "%CUTBEFORE"):
	    		pos = target.find(i)
	    		if (pos > 0):
	    			target = target[pos+1:]
	    	else:
	        	target = target.replace(i, j)
	    return target

	def isIgnoringByID(self, userid):
		for i in range(len(self.config["aIgnoringByID"])):
			if (userid == self.config["aIgnoringByID"][i]):
				return True
		return False

	def isIgnoringByContent(self, username, imageLink):
		username = username.lower()
		for i in range(len(self.config["aIgnoringByContent"])):
			if (self.config["aIgnoringByContent"][i]["vUsernameSubstring"] != "" and
				self.config["aIgnoringByContent"][i]["vUsernameSubstring"].lower() in username):
				return True
			if (self.config["aIgnoringByContent"][i]["vImageSrcSubstring"] != "" and
				self.config["aIgnoringByContent"][i]["vImageSrcSubstring"].lower() in imageLink):
				return True
		return False

	def isIgnoringByBlocks(self, soup):
		for i in range(len(self.config["aIgnoringByBlocks"])):
			if (not (soup.select_one(self.config["aIgnoringByBlocks"][i]) is None)):
				return True
		return False

	def start(self):
		try:
			self.session = requests.Session()
			if (self.config["fRequiresAuth"]):
				authQuery = {
					self.config["oAuthConfig"]["vLIFName"]: self.config["oAuthConfig"]["vLogin"],
					self.config["oAuthConfig"]["vPIFName"]: self.config["oAuthConfig"]["vPassword"]
				}
				self.session.post(self.config["vPage"] + self.config["oAuthConfig"]["vPage"], authQuery)

			self.__redirector(self.config["oOutputConfig"]["vPath"])

			endID = self.config["oUserConfig"]["vStartID"] + self.config["oUserConfig"]["vRequiresCount"]
			step = -1 if self.config["oUserConfig"]["vRequiresCount"] < 0 else 1
			if (self.config["oOutputConfig"]["fCreateIDsFolder"]):
				if (step > 0):
					dirPath = f"{str(self.config['oUserConfig']['vStartID'])}-{str(endID-1)}"
				else:
					dirPath = f"{str(endID+1)}-{str(self.config['oUserConfig']['vStartID'])}"
				self.__redirector(dirPath)
			
			for userID in range(self.config["oUserConfig"]["vStartID"], endID, step):
				currentPage = self.session.get(self.config["vPage"] + self.config["oUserConfig"]["vPageTemplate"] + str(userID))
				soup = BeautifulSoup(currentPage.text, 'lxml')

				self.__log(f"{str(userID)}", end = " ")

				if (self.isIgnoringByBlocks(soup)):
					self.__clog("Ignored")
					continue

				username = soup.select_one(self.config["oUserConfig"]["vUsernameSelector"])
				if (username is None):
					self.__clog("Ignored")
					continue
				username = username.text.replace("\"", "'")
				self.__clog(f"{username}", end = " ")
				avatarImg = soup.select_one(self.config["oUserConfig"]["vImageSelector"])

				if (avatarImg is None):
					imageLink = ""
				else:
					imageLink = avatarImg.get(self.config["oUserConfig"]["vRequiresImageBlockAttribute"])
				if (self.isIgnoringByID(userID) or self.isIgnoringByContent(username, imageLink)):
					self.__clog("Ignored")
					continue

				if (self.config["fDownloadUsersImages"]):
					probablyMissing = None
					if (self.config["oUserConfig"]["vMissingImageSelector"]):
						probablyMissing = soup.select_one(self.config["oUserConfig"]["vMissingImageSelector"])
					if ((probablyMissing is None) and (not (avatarImg is None))):
						imageLink = self.mreplace(imageLink, self.config["oUserConfig"]["oImageSrcReplace"])
						if (imageLink[0] == '.' or imageLink[0] == '/'):
							imageLink = self.config["vPage"] + "/" + imageLink[1:]
						ext = imageLink.split(".")
						outputFile = open(f"{username} {str(userID)}.{ext[len(ext)-1]}", "wb")
						outputFile.write(requests.get(imageLink).content)
						outputFile.close();
						self.__clog("OK", end = " ")
					else:
						self.__clog("WithoutImage", end = " ")

				if (self.config["fSearchUsers"]):
					if ((self.config["oSearchConfig"]["vUsernameSubstring"].lower() != "" and
						self.config["oSearchConfig"]["vUsernameSubstring"].lower() in username.lower()) or
						(self.config["oSearchConfig"]["vImageSrcSubstring"].lower() != "" and
						self.config["oSearchConfig"]["vImageSrcSubstring"].lower() in imageLink.lower())):
						self.__clog("Found", end = "")
						if (self.config["oSearchConfig"]["fPauseSearching"]):
							if (self.config["oOutputConfig"]["fConsoleOutput"]):
								if (not self.__waitForAnswer("Встречен искомый объект, продолжить? [y/n]: ")):
									self.shutdown()
					else:
						self.__clog("")
				else:
					self.__clog("")
				time.sleep(self.config["vSleepTime"])
		except:
			self.__error(traceback.format_exc())
		finally:
			self.shutdown()

if (len(sys.argv) > 1):
	ue = UsersExporter(sys.argv[1])
else:
	ue = UsersExporter()
ue.start()