import pprint

import requests

from scraping import get_branch_reviews, get_branches
from utils import get_user_agent

if __name__ == "__main__":
    branches = get_branches("Вкусно-и точка")
    pprint.pprint(branches)