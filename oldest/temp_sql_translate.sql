import sqlglot

sql = """
CREATE TABLE "known_birthdates" (
  "id" int NOT NULL AUTO_INCREMENT,
  "birth_date_epoch" int NOT NULL,
  "times_seen" int NOT NULL,
  "tweeted" tinyint(1) NOT NULL,
  PRIMARY KEY ("id")
)
"""

print(sqlglot.transpile(sql, read="mysql", write="postgres")[0])
