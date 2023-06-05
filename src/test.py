import pprint

import requests

from scraping import get_branch_reviews

if __name__ == "__main__":
    # params = {'limit': 5, 'key': "37c04fe6-a560-4549-b459-02309cf643ad"}
    # res = requests.get(
    #     "https://public-api.reviews.2gis.com/2.0/branches/70000001054154198/reviews",
    #     params=params)
    # data = res.json()
    # pprint.pprint(data['meta'])
    reviews = get_branch_reviews('70000001054154198',
                                 '37c04fe6-a560-4549-b459-02309cf643ad')

    pprint.pprint(reviews)