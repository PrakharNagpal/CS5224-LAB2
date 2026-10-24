

import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

VERIFY_USERS = ["214328887", "107830991"]


def main(input_path: str, output_path: str) -> None:
    spark = (SparkSession.builder
             .appName("cs5224-twitter-degree-counts")
             .getOrCreate())

    # ---- read ------------------------------------------------------------
    raw = spark.read.text(input_path)
    raw_count = raw.count()

    # ---- parse and clean -------------------------------------------------
    parsed = (raw
              .select(F.split(F.trim(F.col("value")), r"\s+").alias("parts"))
              .filter(F.size("parts") == 2)
              .select(F.col("parts")[0].alias("follower"),
                      F.col("parts")[1].alias("followee")))

    edges = (parsed
             .filter(F.col("follower") != F.col("followee"))   # self-loops
             .dropDuplicates(["follower", "followee"]))        # duplicates
    edges.cache()
    edge_count = edges.count()

    # ---- count -----------------------------------------------------------
    followee_counts = (edges
                       .groupBy("follower")
                       .agg(F.count("*").alias("followees"))
                       .withColumnRenamed("follower", "user_id"))

    follower_counts = (edges
                       .groupBy("followee")
                       .agg(F.count("*").alias("followers"))
                       .withColumnRenamed("followee", "user_id"))

    # full outer join: a user may only appear on one side of the edge list
    result = (followee_counts
              .join(follower_counts, on="user_id", how="full_outer")
              .fillna(0, subset=["followers", "followees"])
              .select("user_id", "followers", "followees"))
    result.cache()

    # ---- log a summary for the report screenshot -------------------------
    print("=" * 60)
    print(f"raw lines           : {raw_count:,}")
    print(f"clean unique edges  : {edge_count:,}")
    print(f"distinct users      : {result.count():,}")
    for uid in VERIFY_USERS:
        row = result.filter(F.col("user_id") == uid).collect()
        if row:
            r = row[0]
            print(f"{uid} has {r['followers']} followers")
            print(f"{uid} has {r['followees']} followees")
        else:
            print(f"{uid} not found")
    print("=" * 60)

    # ---- write -----------------------------------------------------------
    # coalesce(1) keeps the output as a single file so the loader is simple.
    # Safe here: 81k rows. Remove it for a genuinely large dataset.
    (result
     .coalesce(1)
     .write
     .mode("overwrite")
     .json(output_path))

    spark.stop()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: spark_job.py <input_path> <output_path>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])