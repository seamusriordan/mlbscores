#!/usr/bin/python

from bs4 import BeautifulSoup

soup = BeautifulSoup(open("standings.html", "r").read(), 'html.parser')

for d in soup.find_all('div'):
	try:
		if "standingsTable" in d['id']:
			for child in d.children:
				print child

