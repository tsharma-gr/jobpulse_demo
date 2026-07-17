import requests
from bs4 import BeautifulSoup

def search(query):
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    res = requests.post(url, data={"q": query}, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    snippets = soup.find_all("a", class_="result__snippet")
    for s in snippets[:2]:
        print(s.text.strip())

if __name__ == "__main__":
    search("Fawkes and Reece UK recruitment agency")
