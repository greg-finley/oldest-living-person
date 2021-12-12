import os
import re

import pandas as pd
import psycopg2
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()


def main():
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


def send_email(subject, message):
    print("Sending email about exception")
    print(message)
    mailgun_domain = os.environ["MAILGUN_DOMAIN"]
    return requests.post(
        f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
        auth=("api", os.environ["MAILGUN_API_KEY"]),
        data={
            "from": f"Heroku Error <heroku.error@{mailgun_domain}>",
            "to": [os.environ["EMAIL_TO"]],
            "subject": subject,
            "text": message,
        },
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("EMAIL_TO"):
            send_email("Oldest Living Person execution error", e)
