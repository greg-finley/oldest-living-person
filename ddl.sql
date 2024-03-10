CREATE TABLE "known_birthdates" (
  "id" int NOT NULL AUTO_INCREMENT,
  "birth_date_epoch" int DEFAULT NULL,
  "times_seen" int DEFAULT NULL,
  "tweeted" tinyint(1) DEFAULT NULL,
  PRIMARY KEY ("id")
);
