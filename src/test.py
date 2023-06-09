import pprint

from requests_html import HTMLSession

from scraping import get_branch_reviews, get_branches
from utils import get_user_agent

if __name__ == "__main__":
    branches = get_branches("tashsir pizza")
    pprint.pprint(branches)
    print(len(branches))