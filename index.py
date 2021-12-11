import pandas as pd
import requests
from bs4 import BeautifulSoup

wikiurl = "https://en.wikipedia.org/wiki/List_of_the_oldest_living_people"
response = requests.get(wikiurl)
print(response.status_code)

soup = BeautifulSoup(response.text, "html.parser")
table = soup.find("table", {"class": "wikitable"})

print(table)

df = pd.read_html(str(table))
df = pd.DataFrame(df[0])
print(df.head())
