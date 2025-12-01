import requests

from bs4 import BeautifulSoup

# Send a GET request to the URL

response = requests.get('https://www.hostinger.com/tutorials/how-to-run-a-python-script-in-linux')

# Parse the HTML content using BeautifulSoup

soup = BeautifulSoup(response.text, 'html.parser')

# Find all elements with a specific tag (e.g. all h2 headings)

titles = soup.find_all('h3')

# Extract text content from each H2 element

for title in titles:
    print(title.text)

# Find all <a> tags (links)

# all_links = soup.find_all('a')

# print('All <a> tag hrefs:')

# for link in all_links:
#     print(link.get('href'))