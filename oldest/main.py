import json
import os
import re
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import psycopg
import pytz
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

EVERY_THIRTY_MINUTES = 60 / 30
SIX_HOURS = 6


@dataclass
class KnownBirthdate:
    birth_date_epoch: int
    times_seen: int
    tweeted: int


def main(event, context):
    with psycopg.connect(os.environ["NEON_DATABASE_URL"]) as conn:
        conn.autocommit = True
        oldest_people_table = scrape_wikipedia_oldest_living_people_table()
        oldest_person_dict = table_to_oldest_person_dict(oldest_people_table)
        oldest_person_birthdate_epoch = birthdate_str_to_epoch(
            oldest_person_dict["Birth date"]
        )

        known_birthdates = find_birthdates_from_database(conn)
        times_seen_threshold = EVERY_THIRTY_MINUTES * SIX_HOURS

        known_birthday_match = None

        for b in known_birthdates:
            if b.birth_date_epoch == oldest_person_birthdate_epoch:
                known_birthday_match = b
                break

        print(f"Known birthday match: {known_birthday_match}")

        youngest_tweeted_birthdate = -2114294400
        for b in known_birthdates:
            if b.tweeted:
                youngest_tweeted_birthdate = max(
                    youngest_tweeted_birthdate, b.birth_date_epoch
                )

        # If we have not seen it before, add it
        if not known_birthday_match:
            add_new_birthdate_to_database(conn, oldest_person_birthdate_epoch)

        # If it's older than the youngest tweeted birthdate, it's probably vandalism
        elif oldest_person_birthdate_epoch < youngest_tweeted_birthdate:
            print(
                f"Skipping {oldest_person_birthdate_epoch} because it's older than the youngest tweeted birthdate"
            )

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
            send_tweet(tweet_message)
            mark_birthdate_as_tweeted(conn, oldest_person_birthdate_epoch)
            # To alert me via email
            raise Exception("New oldest person")

        return {"status": "OK"}


def scrape_wikipedia_oldest_living_people_table():
    wikiurl = "https://en.wikipedia.org/wiki/List_of_the_oldest_living_people"
    response = requests.get(wikiurl)

    soup = BeautifulSoup(response.text, "html.parser")
    return soup.find("table", {"class": "wikitable"})


def link_to_oldest_person_page(oldest_people_table):
    try:
        url_snippet = (
            oldest_people_table.findAll("tr")[1].findAll("td")[1].find("a")["href"]
        )
        if url_snippet.startswith("/wiki/") and not url_snippet.endswith("Prefecture"):
            return f"https://en.wikipedia.org{url_snippet}"
        raise
    except:  # noqa E722
        return "https://en.wikipedia.org/wiki/List_of_the_oldest_living_people"


def table_to_oldest_person_dict(oldest_people_table):
    oldest_people_df = pd.read_html(str(oldest_people_table))
    return pd.DataFrame(oldest_people_df[0]).iloc[0].to_dict()


def find_birthdates_from_database(conn):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT birth_date_epoch, times_seen, tweeted FROM known_birthdates;"
        )
        results = []
        for row in cursor.fetchall():
            results.append(KnownBirthdate(*row))
        print("Known birthdates", results)
        return results


def generate_tweet_message(oldest_person_dict, oldest_person_page_link):
    return (
        f"{clean_person_name(oldest_person_dict['Name'])} of {oldest_person_dict['Country of residence']}, born {oldest_person_dict['Birth date']}, "
        f"is now the world's oldest living person, according to Wikipedia: {oldest_person_page_link}"
    )


def add_new_birthdate_to_database(conn, oldest_person_birthdate_epoch):
    with conn.cursor() as cursor:
        print(f"Adding new birthdate to database: {oldest_person_birthdate_epoch}")
        cursor.execute(
            "INSERT INTO known_birthdates (birth_date_epoch, times_seen, tweeted) VALUES (%s, 1, 0);",
            (oldest_person_birthdate_epoch,),
        )


def increment_birthdate_times_seen(conn, known_birthday_match):
    with conn.cursor() as cursor:
        print(f"Incrementing times seen for {known_birthday_match.birth_date_epoch}")
        cursor.execute(
            "UPDATE known_birthdates SET times_seen = coalesce(times_seen, 0) + 1 WHERE birth_date_epoch = %s;",
            (known_birthday_match.birth_date_epoch,),
        )
    print(f"Incrementing times seen for {known_birthday_match.birth_date_epoch}")


def mark_birthdate_as_tweeted(conn, oldest_person_birthdate_epoch):
    with conn.cursor() as cursor:
        print(f"Marking {oldest_person_birthdate_epoch} as tweeted")
        cursor.execute(
            "UPDATE known_birthdates SET tweeted = 1 WHERE birth_date_epoch = %s;",
            (oldest_person_birthdate_epoch,),
        )


def send_tweet(message):
    """Twitter shut down apps like mine :("""
    pass


def clean_person_name(name):
    # Remove the annotations: Kane Tanaka[3] -> Kane Tanaka
    return re.sub("[\(\[].*?[\)\]]", "", name)


def birthdate_str_to_epoch(wikipedia_birthdate_string):
    epoch = int(
        pytz.utc.localize(
            datetime.strptime(wikipedia_birthdate_string, "%d %B %Y")
        ).timestamp()
    )
    print("Oldest person birthdate epoch", epoch)
    return epoch
