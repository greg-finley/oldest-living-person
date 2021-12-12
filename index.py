import os
import re

import pandas as pd
import psycopg2
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

conn = psycopg2.connect(DATABASE_URL, sslmode="require")
conn.autocommit = True

cur = conn.cursor()

cur.execute(
    "CREATE TABLE IF NOT EXISTS test (id serial PRIMARY KEY, num integer, data varchar);"
)

cur.close()
conn.close()

# Scrape the table
wikiurl = "https://en.wikipedia.org/wiki/List_of_the_oldest_living_people"
response = requests.get(wikiurl)
print(response.status_code)

soup = BeautifulSoup(response.text, "html.parser")
table = soup.find("table", {"class": "wikitable"})

# Put it in a pandas dataframe
df = pd.read_html(str(table))
df = pd.DataFrame(df[0])
# Remove the annotations: Kane Tanaka[3] -> Kane Tanaka
df["Name"] = df["Name"].apply(lambda x: re.sub("[\(\[].*?[\)\]]", "", x))
print(df.head())

# Check if the top spot has a birthday we haven't seen in our database

# If so, tweet about it!
