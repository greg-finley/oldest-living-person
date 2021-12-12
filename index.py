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
    oldest_people_table = scrape_wikipedia_oldest_living_people_table()
    oldest_person_dict = table_to_oldest_person_dict(oldest_people_table)

    conn = get_database_connection()
    known_birthdates = find_birthdates_from_database(conn)

    if oldest_person_dict["Birth date"] not in known_birthdates:
        tweet_message = generate_tweet_message(oldest_person_dict)
        send_tweet(tweet_message)
        add_new_birthdate_to_database(conn, oldest_person_dict)
    else:
        print(f"{oldest_person_dict['Name']} is still the oldest person")

    conn.close()


def scrape_wikipedia_oldest_living_people_table():
    wikiurl = "https://en.wikipedia.org/wiki/List_of_the_oldest_living_people"
    response = requests.get(wikiurl)
    print(response.status_code)

    soup = BeautifulSoup(response.text, "html.parser")
    return soup.find("table", {"class": "wikitable"})


def table_to_oldest_person_dict(oldest_people_table):
    oldest_people_df = pd.read_html(str(oldest_people_table))
    return pd.DataFrame(oldest_people_df[0]).iloc[0].to_dict()


def get_database_connection():
    DATABASE_URL = os.environ["DATABASE_URL"]

    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    conn.autocommit = True

    return conn


def find_birthdates_from_database(conn):
    with conn.cursor() as curs:
        curs.execute(
            "CREATE TABLE IF NOT EXISTS test (id serial PRIMARY KEY, num integer, data varchar);"
        )


def generate_tweet_message(oldest_person_dict):
    clean_name = re.sub("[\(\[].*?[\)\]]", "", oldest_person_dict["Name"])
    return f"{clean_name} was born on {oldest_person_dict['Birth date']}"


def add_new_birthdate_to_database(conn, oldest_person_dict):
    with conn.cursor() as curs:
        curs.execute(
            "CREATE TABLE IF NOT EXISTS test (id serial PRIMARY KEY, num integer, data varchar);"
        )

    print(oldest_person_dict)


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
