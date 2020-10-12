import os
import csv
import glob
import requests
import datetime
import fire
import operator
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import difflib

stats = {"new count": 0, "updated count": 0}

def save_file(file_path, contents):
  with open(file_path, 'w') as file:
    file.write(contents)
    file.close()

def read_file(file_path):
  with open(file_path) as file:
    contents = file.read()
    file.close()
    return contents

def get_changes(html1, html2):
  html1 = clean_html(html1)
  html2 = clean_html(html2)
  soup1 = BeautifulSoup(html1, features="html.parser")
  soup2 = BeautifulSoup(html2, features="html.parser")
  
  diff = difflib.unified_diff(list(soup1.stripped_strings), list(soup2.stripped_strings))
  return list(diff)

def get_changes_as_html(html1, html2):
  html1 = clean_html(html1)
  html2 = clean_html(html2)
  soup1 = BeautifulSoup(html1, features="html.parser")
  soup2 = BeautifulSoup(html2, features="html.parser")
  
  diff = difflib.HtmlDiff()
  html_table =  diff.make_table(list(soup1.stripped_strings), list(soup2.stripped_strings), context=True)
  html_table = html_table.replace(' nowrap="nowrap"','')
  return html_table

def html_get_title(html):
  soup = BeautifulSoup(html, features="html.parser")
  return soup.find("title").string

def file_get_datetime(file_path):
  created = os.stat(file_path).st_ctime
  return datetime.datetime.fromtimestamp(created)


def check_significant_change(html1, html2):
  if len(get_changes(html1, html2)) > 0:
    return True
  else:
    return False

def clean_html(html):
  
  soup = BeautifulSoup(html, 'html.parser')
  title = soup.find('title').string
  main = soup.find('main')
  cleaned_html = "<html><head><title>%s</title></head><body>%s</body></html>" % (title, main)

  soup = BeautifulSoup(cleaned_html, 'html.parser')

  for script in soup.find_all("script"):
    script.decompose()

  for meta in soup.find_all("meta"):
    meta.decompose()

  for link in soup.find_all("link"):
    link.decompose()

  for header in soup.find_all("header"):
    header.decompose()

  for footer in soup.find_all("footer"):
    footer.decompose()

  for div in soup.find_all("div", class_="gem-c-feedback"):
      div.decompose()
  
  return soup.prettify()

class CovidDocs(object):
    """A scraper for covidsecure pages from governments in the UK."""
    def scrape(self):

        with open('urls.csv') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                save = False
                url = row[0]
                parsed_url = urlparse(url)

                if parsed_url.netloc == "www.gov.uk":
                  data_dir = 'data/gov_uk'
                elif parsed_url.netloc == "gov.wales":
                  data_dir = 'data/gov_wales'
                else:
                  raise Exception("Invalid domain: %s" % parsed_url.netloc)

                dir_name = parsed_url.path.replace("/", "_").replace(":", "")
                dir_path = "%s/%s" % (data_dir, dir_name)

                if not os.path.exists(dir_path):
                    os.makedirs(dir_path)

                scraped_page = requests.get(url)
                scraped_time = datetime.datetime.now()

                previous_files = glob.glob('%s/*.html' % dir_path)
                if previous_files == []:
                    save = True
                    stats["new count"] += 1
                else:

                    # check to see if this version is different from the saved one
                    most_recent_file_path = max(previous_files, key=os.path.getctime)
                    current_hash = ""
                    with open(most_recent_file_path) as current:
                        significant_change = check_significant_change(current.read(), scraped_page.text)

                    if significant_change:
                        save = True
                        stats["updated count"] += 1

                if save:
                    file_name = scraped_time.strftime("%Y-%m-%dT%H:%M:%S.html")
                    file_path = "%s/%s" % (dir_path, file_name)
                    with open(file_path, 'w') as html:
                        html.write(scraped_page.text)
                        html.close()

        print(stats)

    def docs(object):

        chchchanges = []

        scraped_dirs = glob.glob('data/*/*')
        for dir_path in scraped_dirs:
          scraped_files = glob.glob('%s/*.html' % dir_path)
          scraped_files.sort(key=os.path.getmtime)

          for index, file in enumerate(scraped_files):
            if index > 0:
              html = read_file(file)
              previous_html = read_file(scraped_files[index - 1])
              diffs = get_changes(previous_html, html)
              diff_html = get_changes_as_html(previous_html, html)

              if diffs != []:
                change = {"date-time-scraped": file_get_datetime(file), "diffs": diffs, "diff-html": diff_html, "title": html_get_title(html)}
                chchchanges.append(change)

        # sort by date
        chchchanges.sort(key=operator.itemgetter('date-time-scraped'), reverse=True)

        #Save as html
        feed_html = """<html>
                          <head>
                            <title>Changes to COVID Secure guidence for workplaces</title>
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
                          </head>
                          <body>
                          <style>
                            table.diff {font-family:Courier; border:medium; table-layout:fixed; width:100%;word-wrap:break-word}
                            .diff_header {background-color:#e0e0e0}
                            td {width:45%;}
                            td.diff_header {text-align:right; width:5%}
                            .diff_next {display:none;width:0%;}
                            .diff_add {background-color:#aaffaa}
                            .diff_chg {background-color:#ffff77}
                            .diff_sub {background-color:#ffaaaa}
                          </style>
                          <h1>Changes to COVID Secure guidence for workplaces</h1>
        """
        for change in chchchanges:
          feed_html += "<div><h3>%s</h3><h4>Change spotted at: %s</h4>%s</div>" % (change['title'], change['date-time-scraped'], change['diff-html'])
        feed_html += "</body></html>"
        save_file("docs/feed.html", feed_html)

if __name__ == '__main__':
  fire.Fire(CovidDocs)