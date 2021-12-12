import os
import re

import pandas as pd
import psycopg2
import requests
import tweepy
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
    oldest_people_table = soup.find("table", {"class": "wikitable"})

    # Put it in a pandas dataframe and then the oldest person's info into a dict
    oldest_people_df = pd.read_html(str(oldest_people_table))
    oldest_person_dict = pd.DataFrame(oldest_people_df[0]).iloc[0].to_dict()

    # Remove the annotations: Kane Tanaka[3] -> Kane Tanaka
    oldest_person_dict["Name"] = re.sub(
        "[\(\[].*?[\)\]]", "", oldest_person_dict["Name"]
    )

    print(oldest_person_dict)

    # Check if the top spot has a birthday we haven't seen in our database

    # If so, tweet about it!


def send_tweet(message):
    client = tweepy.Client(
        bearer_token=os.environ["TWITTER_BEARER_TOKEN"],
        consumer_key=os.environ["TWITTER_CONSUMER_KEY"],
        consumer_secret=os.environ["TWITTER_CONSUMER_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_SECRET"],
    )

    client.create_tweet(text=message)

    print(f"Tweeted {message}")


def send_email_on_exception(message):
    print("Sending email about exception")
    mailgun_domain = os.environ["MAILGUN_DOMAIN"]
    return requests.post(
        f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
        auth=("api", os.environ["MAILGUN_API_KEY"]),
        data={
            "from": f"Heroku Error <heroku.error@{mailgun_domain}>",
            "to": [os.environ["EMAIL_TO"]],
            "subject": "Oldest Living Person execution error",
            "text": message,
        },
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
        if os.environ.get("EMAIL_TO"):
            send_email_on_exception(e)
