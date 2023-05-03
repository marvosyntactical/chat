import requests
import os
from typing import List

SEARCH_URL = "https://contextualwebsearch-websearch-v1.p.rapidapi.com/api/Search/WebSearchAPI"
NEWS_URL = "https://contextualwebsearch-websearch-v1.p.rapidapi.com/api/search/NewsSearchAPI"

OPTIONS = ("SEARCH", "NEWS")

curr_dir = f"{__file__[:len(__file__)-__file__[::-1].find('/')]}"

x_rapidapi_key = os.getenv("x_rapidapi_key")

if x_rapidapi_key is None:
    x_rapid_filename = curr_dir+ ".x_rapidapi_key"
    try:
        with open(x_rapid_filename, "r") as api_file:
            x_rapidapi_key = api_file.read()[:-1]
    except FileNotFoundError as FNFE:
        print(f"X-RapidAPI Key must be provided at "+x_rapid_filename)
        raise FNFE




def main(args: List[str]):
    """
    Arg 1: SEARCH or NEWS
    """

    option = args[0]

    if option == "SEARCH":
        url = SEARCH_URL
    elif option == "NEWS":
        url = NEWS_URL
    else:
        raise NotImplemented(f"{option}")

    query = args[1]


    n_results = args[2]

    querystring = {"q": query,"pageNumber":"1","pageSize": str(n_results),"autoCorrect":"false"}

    headers = {
        "X-RapidAPI-Key": x_rapidapi_key,
        "X-RapidAPI-Host": "contextualwebsearch-websearch-v1.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)

    # print([k for k in response.json().keys()])
    bodies = [v["body"] for v in response.json()["value"]]

    for i, b in enumerate(bodies):
        content = b.replace("\n\n", "\n").strip()
        print(f"================ Result #{i} ==================")
        print(content)
        print("\n")



if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
