import os
import re
import logging
import shutil
import errno
import time
import getopt
import sys
import requests
import platform
from bs4 import BeautifulSoup
from collections import OrderedDict
from multiprocessing.dummy import Pool as ThreadPool
import itertools
from socket import error as SocketError
from logins import cookie_member_id, cookie_pass_hash

requests.adapters.DEFAULT_RETRIES = 3

failures = 'failures.txt'
headers = {
            'Host': 'exhentai.org',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.104 Safari/537.36',
            'Referer': 'http://exhentai.org/',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Cookie': 'ipb_member_id=%s; ipb_pass_hash=%s' % (cookie_member_id, cookie_pass_hash)
        }

proxies = {
    "http": "http://192.168.1.100:8887",
    "https": "http://192.168.1.100:8887",
}
proxies = {}
def regex(pattern, string, group=0):
    result = None
    # print "String: " + string + " |Pattern: " + pattern

    p = re.compile(pattern)
    m = p.match(string)
    if m is not None:
        result = m.group(group)
    return result

def add2dict(dict, key):
    if not dict.has_key(key):
        dict[key] = ''

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

def get_html(url, headers, proxies=None):
    r = requests.get(url, headers=headers, proxies = proxies)
    return BeautifulSoup(r.text)

def extract_urls(dict, a_attrubute, pattern, group=0):
    url = regex(pattern, str(a_attrubute), group)
    if url is not None:
        add2dict(dict, url)

def save_jpg(dest_folder, title, filename, response):
    with open(dest_folder + title + '/' + filename, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
                print "%s saved.." % filename

def save_failures(jpg_url, dest_folder, title):
    with open(failures, 'a+') as file:
        file.writelines("{dest_folder},{title},{jpg_url}\n".format(dest_folder=dest_folder,title=title,jpg_url=jpg_url))

def download_jpg(jpg_url, dest_folder, title, headers, proxies):

    time.sleep(0.2)
    jpg_pattern = '.+(http://.+jpg)" style'
    jpg_original_pattern = '.+(http://exhentai.org/fullimg.php.+)">Download'
    soup = get_html(jpg_url,headers,proxies)
    has_original = False
    if soup.text.find("Download original"):
        has_original = True
    for a in soup.find_all('a'):
        if has_original:
            jpg = regex(jpg_original_pattern, str(a), 1)            
        else:
            jpg = regex(jpg_pattern, str(a), 1)

        if jpg is not None:
            if jpg.find('image.php') > 0:
                print "403 Error occurs..wait 10s and retry.."
                save_failures(jpg_url,dest_folder,title)
                return
            if has_original:
                jpg = jpg.replace('&amp;','&')

            try:
                response = requests.get(jpg, stream=True, headers=headers, proxies = proxies, timeout = 60)

            except SocketError as e:
                if e.errno != errno.ECONNRESET:
                    print "Error at %s" % jpg
                    raise
                if e.errno == errno.ECONNRESET:
                    time.sleep(10)
                    print "Connection reset by peer wait 10s and retry.."
                    response = requests.get(jpg, stream=True, headers=headers, proxies = proxies)
            except KeyboardInterrupt:
                    sys.exit(1)
            except Exception as e:
                save_failures(jpg_url,dest_folder,title)
                return
            #two issues need to be handled here.
            #1.  timeout pics -> a good retry decorator or record failures and
            #retry
            #2.  503 access denied
            try:
                if has_original:
                    Content_Disposition = response.headers['Content-Disposition']
                    filename = Content_Disposition[Content_Disposition.rfind('=') + 1:]
                else:
                    filename = jpg[jpg.rfind('/') + 1:]
                save_jpg(dest_folder, title, filename, response)
            except KeyboardInterrupt:
                    sys.exit(1)
            except Exception as e:
                    print e
                    print response.status_code
                    
def multiple_run_wrapper(args):
    download_jpg(*args)

def main(argv):
    
    dest_folder = 'HDownload/'
    num_thread = 10

    try:
        opts, args = getopt.getopt(argv,"u:",[])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    url = ''
    url_string = ''

    for opt, arg in opts:
        if opt in ['-u']:
            url_string = arg
    
    if len(url_string) == 0:
        print "input a hentai gallery url.."
        sys.exit(1)

    urls = url_string.split(',')
    for url in urls:
        if url[-1] != '/':
            url = url + '/'

        print "start to analysis url..."
        soup = get_html(url, headers, proxies)

        if platform.system() == 'Windows':
            title = str(soup.title)[7:-23].decode('utf8').encode('CP936')
        else:
            title = str(soup.title)[7:-23]
            
        print "Create dir %s at %s" % (title, dest_folder)

        gallery_id_pattern = 'http://.+hentai.org/g/(\d+)/[\w\d]+/'
        gallery_id = regex(gallery_id_pattern, url, 1)
        print "gallery ID found: " + gallery_id

        page_index_pattern = '.+(http://.+hentai\.org.+\?p=\d+)'
        pic_index_pattern = '.+(http://.+hentai\.org/s/[\w\d]+/%s-\d+)' % gallery_id

        pages = OrderedDict({})
        pics = OrderedDict({})
        for a in soup.find_all('a'):
            extract_urls(pages, a, page_index_pattern, 1)
            extract_urls(pics, a, pic_index_pattern, 1)

        for key in pages:
            print key
            soup = get_html(str(key), headers, proxies)
            for a in soup.find_all('a'):
                extract_urls(pics, a, pic_index_pattern, 1)      
    
        mkdir_p(dest_folder + title)
        pool = ThreadPool(num_thread)

        num_page = len(pics)  
        pool.map(multiple_run_wrapper, itertools.izip(pics.keys()[:num_page], [dest_folder] * num_page,
                                                                [title] * num_page, [headers] * num_page, [proxies] * num_page))
        pool.close()
        pool.join()

        print 'Downloading completed..'
        if os.path.exists(failures):
            print 'Starting recover failures..'
        else:
            sys.exit(0)

        retry = 3
        while(retry > 0):
            retry = retry - 1
            with open(failures,'w+') as file:
                failed_urls = file.read().split('\n')
                file.truncate(0)

            for line in failed_urls:
            #add recover logic here
                pass



if __name__ == '__main__':
    main(sys.argv[1:])

