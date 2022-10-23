import re
import itertools
import urllib.robotparser
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from http.client import responses
from utils import get_logger


stop_words_set = (['a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', "aren't", 'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', "can't", 'cannot', 'could', "couldn't", 'did', "didn't", 'do', 'does', "doesn't", 'doing', "don't", 'down', 'during', 'each', 'few', 'for', 'from', 'further', 'had', "hadn't", 'has', "hasn't", 'have', "haven't", 'having', 'he', "he'd", "he'll", "he's", 'her', 'here', "here's", 'hers', 'herself', 'him', 'himself', 'his', 'how', "how's", 'i', "i'd", "i'll", "i'm", "i've", 'if', 'in', 'into', 'is', "isn't", 'it', "it's", 'its', 'itself', "let's", 'me', 'more', 'most', "mustn't", 'my', 'myself', 'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought', 'our', 'ours\tourselves', 'out', 'over', 'own', 'same', "shan't", 'she', "she'd", "she'll", "she's", 'should', "shouldn't", 'so', 'some', 'such', 'than', 'that', "that's", 'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', "there's", 'these', 'they', "they'd", "they'll", "they're", "they've", 'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', "wasn't", 'we', "we'd", "we'll", "we're", "we've", 'were', "weren't", 'what', "what's", 'when', "when's", 'where', "where's", 'which', 'while', 'who', "who's", 'whom', 'why', "why's", 'with', "won't", 'would', "wouldn't", 'you', "you'd", "you'll", "you're", "you've", 'your', 'yours', 'yourself'])

# Store the visited url to prevent revisiting
visited_url = set()
unique_url = set()
word_dict = {}
longest_url = None
long_url_words_count = 0
sub_domain = {}

def sub_domain_check(url):
    parsed = urlparse(url)
    url_domain = parsed.scheme + '://' + parsed.netloc
    
    if re.search('ics.uci.edu', url):
        if sub_domain.get(url_domain) == None:
            sub_domain[url_domain] = 1
        else:
            sub_domain[url_domain] += 1
        

def log_update():
    global unique_url, word_dict, longest_url, long_url_words_count, sub_domain
    word_dict = dict(sorted(word_dict.items(), key=lambda item: item[1], reverse=True))
    top_50 = dict(itertools.islice(word_dict.items(), 50))
    
    
    logger = get_logger('CRAWLER')
    logger.info(f"Unique urls: {len(unique_url)}.\nTop 50 words are {top_50}.\nLongest page is {longest_url} with {long_url_words_count} words.\nNumber of ics.uci.edu subdomain: {len(sub_domain)}")
    

def word_counter(text):
    for word in text:
        if word not in stop_words_set:
            if word_dict.get(word) == None:
                word_dict[word] = 1
            else:
                word_dict[word] += 1
                    

def extract_content(resp):
    global longest_url, long_url_words_count

    soup = BeautifulSoup(resp.raw_response.content, "html.parser")
    text = soup.get_text(" ", strip=True).lower().split()
    new_text = []
    
    for word in text:
        if re.search(f"^[(]", word):
            if re.search(f"[)]$", word):
                word = word[1: -1]
            else:
                word = word[1:]
                
        if re.search(f"^[“]", word):
            if re.search(f"[“]$", word):
                word = word[1: -1]
            else:
                word = word[1:]
        
        if re.search(f"[.):,“]$", word):
            word = word[:-1]
            
        if re.search(r"[^a-z-’.]", word):
            continue
        else:
            if (len(word) == 1 and re.search(f"^[-@!#$%^&*()_+=`~<>,./?]", word)):
                continue
            elif word == '':
                continue
            else:
                new_text.append(word)
    
    if len(new_text) > long_url_words_count:
        long_url_words_count = len(new_text)
        longest_url = resp.raw_response.url
        
    return new_text


def unique_url_check(url):
    global unique_url
    
    parsed = urlparse(url)
    link = parsed.scheme + '://' + parsed.netloc
    
    if link not in unique_url:
        unique_url.add(link)
        

# check for the trap in url
def safty_check(url):

    parsed = urlparse(url)
    
    if len(parsed.path) > 150:
        return False

    return True
    
def status_check(resp):
    if resp.status != 200:
        if(resp.status > 599):
            print(f'Caching error {resp.status}: {resp.error}')
        else:
            print(responses[resp.status])
            
        return False
    else:
        return True


def scraper(url, resp):
    
    global visited_url
    
    if url in visited_url:
        return list()
    
    visited_url.add(url)
    unique_url_check(url)
    sub_domain_check(url)
    
    if not status_check(resp):
        return list()
    
    text = extract_content(resp)
    word_counter(text)
        
    valid_link = extract_next_links(url, resp)
    
    log_update()
    
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
    
        
    soup = BeautifulSoup(resp.raw_response.content, "html.parser")
    links_per_page = set()

    for link in soup.find_all(lambda tag: tag.name=='a' and tag.get("href")):
        if is_valid(link.get("href")) and link.get("href") not in links_per_page:
            links_per_page.add(link.get("href"))
            
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
        if parsed.hostname is None:
            return False
        
        # defragment the url
        if parsed.fragment != '':
            return False
        
        # chech the domain
        if not re.match(r".*\.(ics.uci.edu|cs.uci.edu|informatics.uci.edu|stat.uci.edu|today.uci.edu/department/information_computer_sciences)", parsed.hostname.lower()):
            return False
            
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz|ppsx|txt)$", parsed.path.lower()):
            return False
            
        # Avoid revisiting the visited url
        if url in visited_url:
            return False
        
            
    except TypeError:
        print ("TypeError for ", parsed)
        raise
    
    return True
