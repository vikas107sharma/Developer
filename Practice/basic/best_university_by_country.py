# Question 2: Best University By Country (REST API)
#
# Retrieve university information from a global database and find the
# highest-ranked university in a specified country. Use HTTP GET requests to
# access the database at https://jsonmock.hackerrank.com/api/universities,
# with pagination available by appending ?page=num to the URL (replace num).
#
# The API response includes:
#   - page: current page number
#   - per_page: maximum results per page
#   - total: total number of records
#   - total_pages: total number of pages
#   - data: array of university information objects
#
# Each university object contains:
#   - university: name of the university
#   - rank_display: university rank according to 2022 QS Rankings
#   - score: university score according to 2022 QS Rankings
#   - type: university type (e.g., Public)
#   - student_faculty_ratio: ratio of students to faculty
#   - international_students: number of international students
#   - faculty_count: number of faculty members
#   - location: object with city, country, and region information
#
# Given a country name, return the name of the highest-ranked university in
# that country. If no university exists for the specified country, return an
# empty string ("").
#
# Function: bestUniversityByCountry(country)
#   country (string): name of the country whose universities are to be filtered
#   Returns (string): the name of the highest rated university or ""
#
# Sample cases:
#   "India"          -> "Indian Institute of Technology Bombay (IITB)"
#   "United Kingdom" -> "University of Oxford"
#   "North Korea"    -> ""  (no data for North Korea)

import requests


def bestUniversityByCountry(country):
    """Return the name of the highest-ranked (lowest rank_display) university
    in the given country, or "" if the country has no universities."""
    best_name = ""
    best_rank = float("inf")

    page = 1
    total_pages = 1
    while page <= total_pages:
        resp = requests.get(
            "https://jsonmock.hackerrank.com/api/universities",
            params={"page": page},
        ).json()
        total_pages = resp["total_pages"]

        for uni in resp["data"]:
            if uni["location"]["country"] != country:
                continue
            # rank_display is a string; strip a leading "=" used for tied ranks
            rank = int(uni["rank_display"].lstrip("="))
            if rank < best_rank:
                best_rank = rank
                best_name = uni["university"]

        page += 1

    return best_name


if __name__ == "__main__":
    country = input().strip()
    print(bestUniversityByCountry(country))
