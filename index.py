import os
import re
from datetime import datetime

import pandas as pd
import psycopg2
import pytz
import requests
import tweepy
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tweepy.errors import Forbidden as TweetForbidden

load_dotenv()


def main():
    oldest_people_table = scrape_wikipedia_oldest_living_people_table()
    oldest_person_dict = table_to_oldest_person_dict(oldest_people_table)
    oldest_person_birthdate_epoch = birthdate_str_to_epoch(
        oldest_person_dict["Birth date"]
    )

    conn = get_database_connection()

    known_birthdates = find_birthdates_from_database(conn)

    # Maybe other info in the table might change, but the birthdates hopefully are stable, especially for the oldest person.
    # If the oldest person's birthdate is not in our list of known birthdates, we'll tweet.
    if oldest_person_birthdate_epoch not in known_birthdates:
        tweet_message = generate_tweet_message(oldest_person_dict)
        send_tweet(tweet_message)
        add_new_birthdate_to_database(conn, oldest_person_birthdate_epoch)
    else:
        print(
            f"{clean_person_name(oldest_person_dict['Name'])} is still the oldest person"
        )

    conn.close()


def scrape_wikipedia_oldest_living_people_table():
    wikiurl = "https://en.wikipedia.org/wiki/List_of_the_oldest_living_people"
    response = requests.get(wikiurl)

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
            "CREATE TABLE IF NOT EXISTS known_birthdates (id serial PRIMARY KEY, birth_date_epoch int);"
        )
        curs.execute("SELECT birth_date_epoch FROM known_birthdates;")
        rows = curs.fetchall()
    known_birthdates = [row[0] for row in rows]
    print("Known birthdate epochs", known_birthdates)
    return known_birthdates


def generate_tweet_message(oldest_person_dict):
    return (
        f"{clean_person_name(oldest_person_dict['Name'])} of {oldest_person_dict['Country of residence']}, born {oldest_person_dict['Birth date']}, "
        "is now the world's oldest living person, according to Wikipedia: https://en.wikipedia.org/wiki/List_of_the_oldest_living_people"
    )


def add_new_birthdate_to_database(conn, oldest_person_birthdate_epoch):
    with conn.cursor() as curs:
        curs.execute(
            "INSERT INTO known_birthdates (birth_date_epoch) VALUES (%s)",
            (oldest_person_birthdate_epoch,),
        )


def send_tweet(message):
    client = tweepy.Client(
        bearer_token=os.environ["TWITTER_BEARER_TOKEN"],
        consumer_key=os.environ["TWITTER_CONSUMER_KEY"],
        consumer_secret=os.environ["TWITTER_CONSUMER_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_SECRET"],
    )

    try:
        client.create_tweet(text=message)
        print(f"Tweeted {message}")
    except TweetForbidden:
        send_email("New oldest living person", "New oldest living person")
        print(f"Emailed {message}")


def clean_person_name(name):
    # Remove the annotations: Kane Tanaka[3] -> Kane Tanaka
    return re.sub("[\(\[].*?[\)\]]", "", name)


def send_email(subject, message):
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


def birthdate_str_to_epoch(wikipedia_birthdate_string):
    epoch = int(
        pytz.utc.localize(
            datetime.strptime(wikipedia_birthdate_string, "%d %B %Y")
        ).timestamp()
    )
    print("Oldest person birthdate epoch", epoch)
    return epoch


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("EMAIL_TO"):
            send_email("Oldest Living Person execution error", e)
        raise e
