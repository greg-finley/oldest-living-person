import json
import os
import re
from dataclasses import dataclass
from datetime import datetime

import MySQLdb
import pandas as pd
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


mysql_config = json.loads(os.environ["MYSQL_CONFIG"])
mysql_client = MySQLdb.connect(
    host=mysql_config["MYSQL_HOST"],
    user=mysql_config["MYSQL_USERNAME"],
    passwd=mysql_config["MYSQL_PASSWORD"],
    db=mysql_config["MYSQL_DATABASE"],
    ssl_mode="VERIFY_IDENTITY",
    ssl={"ca": os.environ.get("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt")},
)
mysql_client.autocommit(True)


def main(event, context):
    oldest_people_table = scrape_wikipedia_oldest_living_people_table()
    oldest_person_dict = table_to_oldest_person_dict(oldest_people_table)
    oldest_person_birthdate_epoch = birthdate_str_to_epoch(
        oldest_person_dict["Birth date"]
    )

    known_birthdates = find_birthdates_from_database()
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
        add_new_birthdate_to_database(oldest_person_birthdate_epoch)

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
        increment_birthdate_times_seen(known_birthday_match)

    # If we have seen it a lot, tweet it
    else:
        oldest_person_page_link = link_to_oldest_person_page(oldest_people_table)
        tweet_message = generate_tweet_message(
            oldest_person_dict, oldest_person_page_link
        )
        send_tweet(tweet_message)
        mark_birthdate_as_tweeted(oldest_person_birthdate_epoch)
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


def find_birthdates_from_database():
    mysql_client.query(
        "SELECT birth_date_epoch, times_seen, tweeted FROM known_birthdates;"
    )
    r = mysql_client.store_result()
    results = []
    for row in r.fetch_row(maxrows=0, how=1):
        results.append(KnownBirthdate(**row))
    print("Known birthdates", results)
    return results


def generate_tweet_message(oldest_person_dict, oldest_person_page_link):
    return (
        f"{clean_person_name(oldest_person_dict['Name'])} of {oldest_person_dict['Country of residence']}, born {oldest_person_dict['Birth date']}, "
        f"is now the world's oldest living person, according to Wikipedia: {oldest_person_page_link}"
    )


def add_new_birthdate_to_database(oldest_person_birthdate_epoch):
    print(f"Adding new birthdate to database: {oldest_person_birthdate_epoch}")
    mysql_client.query(
        f"INSERT INTO oldest_living_person.known_birthdates (birth_date_epoch, times_seen, tweeted) VALUES ({oldest_person_birthdate_epoch}, 1, 0);"
    )


def increment_birthdate_times_seen(known_birthday_match):
    print(f"Incrementing times seen for {known_birthday_match.birth_date_epoch}")
    mysql_client.query(
        f"UPDATE oldest_living_person.known_birthdates SET times_seen = coalesce(times_seen, 0) + 1 WHERE birth_date_epoch = {known_birthday_match.birth_date_epoch};"
    )


def mark_birthdate_as_tweeted(oldest_person_birthdate_epoch):
    mysql_client.query(
        f"UPDATE oldest_living_person.known_birthdates SET tweeted = 1 WHERE birth_date_epoch = {oldest_person_birthdate_epoch};"
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


main({}, {})
