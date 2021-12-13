# Oldest Living Person

## On Twitter

https://twitter.com/OldestLivingBot

## Description

Watch [Wikipedia's list of oldest living people](https://en.wikipedia.org/wiki/List_of_the_oldest_living_people) in a periodic job. Tweet when there's a new oldest person.

This topic has always fascinated me and been a reminder of our own mortality. For instance, as of a few years ago, we no longer had anyone alive who was born in the 19th century.

The logic is keep a database of the seen top spots and tweet if the top spot has a *birth date* we have not yet seen (hedge against Wikipedia changing the *name* of the person in the top spot and triggering an errant tweet).

[Here](https://medium.com/analytics-vidhya/web-scraping-a-wikipedia-table-into-a-dataframe-c52617e1f451) is a reference used on basic web scraper.

## Development

Install [poetry](https://python-poetry.org/docs/#installation)

`cp .env.example .env` and fill in the parameters

`poetry install` from repo root. I used Python 3.9.

`poetry run python index.py`

## Deployment

I deployed the app on Heroku Free tier. It leverages these free add-ons: [Heroku Scheduler](https://elements.heroku.com/addons/scheduler) (run the check periodically), [Heroku Postgres](https://elements.heroku.com/addons/heroku-postgresql) (remember the birthdates of the oldest living person that we have already seen), and [Mailgun](https://elements.heroku.com/addons/mailgun) (optional -- alert me if something goes wrong, maybe Wikipedia changes its page layoff eventually, etc.). I needed the [python-poetry-buildpack](https://github.com/moneymeets/python-poetry-buildpack.git) set before the standard `heroku/python` buildpack, since I used Poetry for package installs.
