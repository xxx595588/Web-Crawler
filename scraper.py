from importlib.resources import path
import re
import itertools
import urllib.robotparser
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup
from http.client import responses
from utils import get_logger


stop_words_set = (["a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself"])

# Store the visited url to prevent revisiting
visited_url = set()
unique_url = set()
word_dict = {}
longest_url = None
long_url_words_count = 0
sub_domain = {}
exc_dup_dec = set()

# ------------------------ HELPER FUNCTIONS ------------------------

# This funcation will check the given url is a subdomain of ics.uci.edu
def sub_domain_check(url):
    global sub_domain
    parsed = urlparse(url)
    
    if parsed.netloc.find('.ics.uci.edu') > 0:
        if sub_domain.get(parsed.netloc) is None:
            sub_domain[parsed.netloc] = 1
        else:
            sub_domain[parsed.netloc] += 1
        
# This function will keep updating for the cralwer
def log_update(url):
    global unique_url, word_dict, longest_url, long_url_words_count, sub_domain
    word_dict = dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True))
    top_50 = dict(itertools.islice(word_dict.items(), 50))
    
    logger = get_logger('CRAWLER')
    logger.info(f"Current url: {url}\n")
    logger.info(f"Unique pages: {len(unique_url)}.\nTop 50 words are {top_50}.\nLongest page is {longest_url} with {long_url_words_count} words.\nNumber of ics.uci.edu subdomain: {len(sub_domain)}. List below: {sub_domain}\n\n")
    
# This function the frequency of each word by given list
def word_counter(text):
    global word_dict

    for word in text:
        if word not in stop_words_set:
            if word_dict.get(word) is None:
                word_dict[word] = 1
            else:
                word_dict[word] += 1
                    

# This function will extract the content from the page to a list of string
def extract_content(resp):
    global longest_url, long_url_words_count

    #print(f"\n\nnow in {resp.raw_response.url}\n")

    # Empty page, no content
    if resp.raw_response is None:
        return []

    soup = BeautifulSoup(resp.raw_response.content, "html.parser")
    text = soup.get_text(" ", strip=True).lower().split()
    new_text = []
    
    for word in text:

        # Extract words in (). E.g, (Hello) -> Hello
        if re.search(f"^[(]", word):
            if re.search(f"[)]$", word):
                word = word[1: -1]
            else:
                word = word[1:]
        
        # Extract words in "". E.g, "Hello" -> Hello
        if re.search(f"^[“]", word):
            if re.search(f"[“]$", word):
                word = word[1: -1]
            else:
                word = word[1:]
        
        # Extract words end wtih .):,“. E.g, Hello, -> Hello
        if re.search(f"[.):,“]$", word):
            word = word[:-1]
        
        # Ignore words which is not alphbet. E.g, $2000 or 2000-02-12
        if re.search(r"[^a-z-’.]", word):
            continue
        else:
            # Ignore single character
            if (len(word) == 1 and re.search(f"^[-@!#$%^&*()_+=`~<>,./?]", word)):
                continue
            # Empty String
            elif word == '':
                continue
            else:
                new_text.append(word)
    
    # Counter for the valid words and update for the longest page in terms of number of word
    if len(new_text) > long_url_words_count:
        long_url_words_count = len(new_text)
        longest_url = resp.raw_response.url
 
    return new_text

# This function will check the uniquity of given url
def unique_url_check(url):
    global unique_url
    
    # defrage the url
    parsed, frag = urldefrag(url)
    
    # add to the set if domain name hasn't been seen
    if parsed not in unique_url:
        unique_url.add(parsed)
        

# This function will check the follwoing traps for the given url
#   1. Long path url
#   2. Repeating direction
#   3. Events page
def safty_check(url):
    parsed = urlparse(url)

    # 1. Long path url
    if len(parsed.path) > 150:
        return False

    # 2. Repeating direction
    path_element = parsed.path.split("/")
    path_element.remove("")
    if len(path_element) != len(set(path_element)):
        return False

    # 3. Event page
    if re.search(r"/events/|/events|/event/|/event", parsed.path):
        return False

    return True
    
# This function will check the resp.status
# Only retuen Ture when status code is 200
# Otherwise, return False and print the error code
def status_check(resp):
    if resp.status != 200:
        if(resp.status > 599):
            print(f'Caching error {resp.status}: {resp.error}')
        else:
            print(responses[resp.status])
            
        return False
    else:
        return True

# --------------------- END OF HELPER FUNCTIONS ---------------------

def scraper(url, resp):

    if resp.raw_response is None:
        return list()

    if resp.raw_response.headers.get("Content-Type") is None:
        return list()

    #print(f"url:{resp.url}\n status: {resp.status}\n response: {resp.raw_response.content}")

    file_type = resp.raw_response.headers["Content-Type"].split(";")[0]
    if file_type != "text/html":
        return list()

    if not safty_check(url):
        return list()

    global visited_url
    if url in visited_url:
        return list()

    sub_domain_check(url)

    visited_url.add(url)

    # get the status of url
    if not status_check(resp):
        return list()

    unique_url_check(url)

    text = extract_content(resp)

    # found the duplication, skip the url
    hash_num = hash(frozenset(text))
    if hash_num in exc_dup_dec:
        return list()
    else:
        exc_dup_dec.add(hash_num)
   
    # Only do the statistic when there're more than 50 words to adviod page without information
    # However, we still extract links from this page and add it to the unique link set
    if len(text) > 50:
        word_counter(text)
    
    valid_link = extract_next_links(resp.raw_response.url, resp)

    log_update(url)

    return valid_link

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    
    # if status code is other than 200, print the erro and return an empty list
    
    #print(f"extracing from {url}")
    
    soup = BeautifulSoup(resp.raw_response.content, "html.parser")
    links_per_page = set()
    ori = urlparse(url)

    # get all a tag with link
    for link in soup.find_all(lambda tag: tag.name=='a' and tag.get("href")):
        mod_link = link.get("href")

        # ignore the fragement url
        if mod_link[0] == "#":
            continue

        mod_parsed = urlparse(mod_link)

        # convert relative url to absoulate url
        if mod_parsed.scheme == "":
        #print(f"before: {mod_link}")
            if ori.path == "":
                mod_link = url + mod_link
            else:
                if ori.path [-1] == "/":
                    #if mod_link[0] == "/":
                    mod_link = urljoin(url, mod_link)
                    #else:
                        #mod_link = url + mod_link
                elif ori.path [-1] != "/":
                    mod_link = urljoin(url, mod_link)

        #print(f"after: {mod_link}")

        # reconstruct the absoluate url
        mod_parsed = urlparse(mod_link)
        mod_link = mod_parsed.scheme + "://" + mod_parsed.netloc + mod_parsed.path

        if is_valid(mod_link) and mod_link not in links_per_page:
            links_per_page.add(mod_link)
               
    return list(links_per_page)
 

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    
    try:
        parsed = urlparse(url)
        
        # check the scheme
        if parsed.scheme not in set(["http", "https"]):
            return False
        
        # if no domain name is presented
        if parsed.netloc is None:
            return False
        
        # defragment the url
        if parsed.fragment != "":
            return False
        
        # chech the domain
        if not re.match(r".*\.(ics.uci.edu|cs.uci.edu|informatics.uci.edu|stat.uci.edu|today.uci.edu/department/information_computer_sciences)", parsed.netloc):
            return False
        
        # Here is a rough check to filiter out by the end of path 
        # Since we can list all the type, so we will check header in scraper function again
        # Remove the path with ova & apk which are typically large and no infomation
        # Advoid file like java, cpp, c, h, and json which are no valuable infomation in it
        # Don't get the bat, nna,, maf, etc... (no valuable infomation)
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz"
            + r"|ppsx|txt|pdf|php|odp|h|cc|py|ova|apk|m|tst|bat|nna|maf|xml|json|cpp|java)$", parsed.path.lower()):
            return False
            
        # Avoid revisiting the visited url
        if url in visited_url:
            return False
        
    except TypeError:
        print ("TypeError for ", parsed)
        raise
    
    return True
