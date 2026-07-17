from duckduckgo_search import DDGS
import json

def test():
    results = DDGS().text('Fawkes and Reece UK recruitment')
    # Convert generator to list if necessary
    results_list = list(results) if not isinstance(results, list) else results
    for r in results_list:
        print(json.dumps(r, indent=2))

if __name__ == "__main__":
    test()
