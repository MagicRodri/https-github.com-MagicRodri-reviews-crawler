from scraping import get_branches
import pprint

if __name__ == '__main__':
    branches = get_branches()
    pprint.pprint(branches)
