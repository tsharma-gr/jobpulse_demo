import requests

def test():
    query = 'Kenton Black UK recruitment agency'
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.post(url, data={"q": query}, headers=headers, timeout=5)
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(res.text, "html.parser")
    snippets = soup.find_all("a", class_="result__snippet")
    for s in snippets[:2]:
        print(s.text.strip())

if __name__ == "__main__":
    test()
