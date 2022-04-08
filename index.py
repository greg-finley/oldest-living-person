import os
import re
from dataclasses import dataclass
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


@dataclass
class KnownBirthdate:
    birth_date_epoch: int
    times_seen: int
    tweeted: bool


def main():
    oldest_people_table = scrape_wikipedia_oldest_living_people_table()
    oldest_person_dict = table_to_oldest_person_dict(oldest_people_table)
    oldest_person_birthdate_epoch = birthdate_str_to_epoch(
        oldest_person_dict["Birth date"]
    )

    conn = get_database_connection()

    known_birthdates = find_birthdates_from_database(conn)
    times_seen_threshold = int(os.environ.get("TIMES_SEEN_THRESHOLD", 18))

    known_birthday_match = None

    for b in known_birthdates:
        if b.birth_date_epoch == oldest_person_birthdate_epoch:
            known_birthday_match = b
            break
            
    print(f"Known birthday match: {known_birthday_match}")

    # If we have not seen it before, add it
    if not known_birthday_match:
        add_new_birthdate_to_database(conn, oldest_person_birthdate_epoch)

    # If we already tweeted it, skip
    elif known_birthday_match.tweeted:
        print(
            f"{clean_person_name(oldest_person_dict['Name'])} is still the oldest person"
        )

    # If we have only seen a few times, increment the counter
    elif known_birthday_match.times_seen < times_seen_threshold:
        increment_birthdate_times_seen(conn, known_birthday_match)

    # If we have seen it a lot, tweet it
    else:
        oldest_person_page_link = link_to_oldest_person_page(oldest_people_table)
        tweet_message = generate_tweet_message(
            oldest_person_dict, oldest_person_page_link
        )
        send_tweet_and_email(tweet_message)
        mark_birthdate_as_tweeted(conn, oldest_person_birthdate_epoch)

    conn.close()


def scrape_wikipedia_oldest_living_people_table():
    wikiurl = "https://en.wikipedia.org/wiki/List_of_the_oldest_living_people"
    response = requests.get(wikiurl)

    soup = BeautifulSoup(response.text, "html.parser")
    return soup.find("table", {"class": "wikitable"})


def link_to_oldest_person_page(oldest_people_table):
    for tr in oldest_people_table.findAll("tr"):
        trs = tr.findAll("td")
        for each in trs:
            try:
                snippet = each.find("a")["href"]
                if snippet.startswith("/wiki/"):
                    return f"https://en.wikipedia.org{snippet}"
            except:
                pass

    raise Exception("Could not find link to oldest person page")


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
            "CREATE TABLE IF NOT EXISTS known_birthdates (id serial PRIMARY KEY, birth_date_epoch bigint, times_seen int, tweeted bool);"
        )
        curs.execute(
            "SELECT birth_date_epoch, times_seen, tweeted FROM known_birthdates;"
        )
        rows = curs.fetchall()
    results = []
    for row in rows:
        results.append(KnownBirthdate(*row))
    print("Known birthdates", results)
    return results


def generate_tweet_message(oldest_person_dict, oldest_person_page_link):
    return (
        f"{clean_person_name(oldest_person_dict['Name'])} of {oldest_person_dict['Country of residence']}, born {oldest_person_dict['Birth date']}, "
        f"is now the world's oldest living person, according to Wikipedia: {oldest_person_page_link}"
    )


def add_new_birthdate_to_database(conn, oldest_person_birthdate_epoch):
    print(f"Adding new birthdate to database: {oldest_person_birthdate_epoch}")
    with conn.cursor() as curs:
        curs.execute(
            "INSERT INTO known_birthdates (birth_date_epoch, times_seen, tweeted) VALUES (%s, 1, false);",
            (oldest_person_birthdate_epoch,),
        )


def increment_birthdate_times_seen(conn, known_birthday_match):
    print(f"Incrementing times seen for {known_birthday_match.birth_date_epoch}")
    with conn.cursor() as curs:
        curs.execute(
            "UPDATE known_birthdates SET times_seen = coalesce(times_seen, 0) + 1 WHERE birth_date_epoch = %s;",
            (known_birthday_match.birth_date_epoch,),
        )


def mark_birthdate_as_tweeted(conn, oldest_person_birthdate_epoch):
    with conn.cursor() as curs:
        curs.execute(
            "UPDATE known_birthdates SET tweeted = true WHERE birth_date_epoch = %s;",
            (oldest_person_birthdate_epoch,),
        )


def send_tweet_and_email(message):
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
        print("Tweet forbidden")
    send_email("New oldest living person", "New oldest living person")


def clean_person_name(name):
    # Remove the annotations: Kane Tanaka[3] -> Kane Tanaka
    return re.sub("[\(\[].*?[\)\]]", "", name)


def send_email(subject, message):
    if os.environ.get("EMAIL_TO"):
        mailgun_domain = os.environ["MAILGUN_DOMAIN"]
        requests.post(
            f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
            auth=("api", os.environ["MAILGUN_API_KEY"]),
            data={
                "from": f"Heroku Error <heroku.error@{mailgun_domain}>",
                "to": [os.environ["EMAIL_TO"]],
                "subject": subject,
                "text": message,
            },
        )
        print(f"Emailed {message}")
    else:
        print(f"Did not email because no email env set: {message}")


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
        send_email("Oldest Living Person execution error", e)
        raise e
