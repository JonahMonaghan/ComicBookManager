import requests
from bs4 import BeautifulSoup

class MAWFetcher:

    url = "http://www.mikesamazingworld.com/mikes/features/comic/seriesissues.php"

    def __init__(self, sid="0000"):
        self._seriesid = sid
        self._issues = []
        self._cover_dates = []

    @property
    def seriesid(self):
        return self._seriesid
    
    @seriesid.setter
    def seriesid(self, value):
        if isinstance(value, str):
            self._seriesid = value
        else:
            raise ValueError("seriesid must be a string")
        
    @property
    def issues(self):
        return self._issues
    
    @property
    def cover_dates(self):
        return self._cover_dates

    def fetch(self):

        POST_data = {
            "seriesid": {self.seriesid},
            "sortField": "date",
            "sortDir": "ASC"
        }

        response = requests.post(MAWFetcher.url, data=POST_data)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            rows = soup.find_all("tr")
            for row in rows:
                columns = row.find_all("td")
                if len(columns) >= 2:
                    issue_number = columns[0].text.strip()
                    cover_date = columns[1].text.strip()
                    self._issues.append(issue_number)
                    self._cover_dates.append(cover_date)
        else:
            print(f"Failed to make the POST request. Status code: {response.status_code}")