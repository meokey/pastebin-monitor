#!/usr/bin/env python3
from math import ceil,fmod,fabs
from optparse import OptionParser
import os
import re
import time
import sys
import urllib
import urllib.request
import tarfile
import random

from pyquery import PyQuery


def get_timestamp():
    return time.strftime('%Y/%m/%d %H:%M:%S')

def all_python_encodings():
     return ["ascii",
             "big5",
             "big5hkscs",
             "cp037",
             "cp424",
             "cp437",
             "cp500",
             "cp720",
             "cp737",
             "cp775",
             "cp850",
             "cp852",
             "cp855",
             "cp856",
             "cp857",
             "cp858",
             "cp860",
             "cp861",
             "cp862",
             "cp863",
             "cp864",
             "cp865",
             "cp866",
             "cp869",
             "cp874",
             "cp875",
             "cp932",
             "cp949",
             "cp950",
             "cp1006",
             "cp1026",
             "cp1140",
             "cp1250",
             "cp1251",
             "cp1252",
             "cp1253",
             "cp1254",
             "cp1255",
             "cp1256",
             "cp1257",
             "cp1258",
             "euc_jp",
             "euc_jis_2004",
             "euc_jisx0213",
             "euc_kr",
             "gb2312",
             "gbk",
             "gb18030",
             "hz",
             "iso2022_jp",
             "iso2022_jp_1",
             "iso2022_jp_2",
             "iso2022_jp_2004",
             "iso2022_jp_3",
             "iso2022_jp_ext",
             "iso2022_kr",
             "latin_1",
             "iso8859_2",
             "iso8859_3",
             "iso8859_4",
             "iso8859_5",
             "iso8859_6",
             "iso8859_7",
             "iso8859_8",
             "iso8859_9",
             "iso8859_10",
             "iso8859_13",
             "iso8859_14",
             "iso8859_15",
             "iso8859_16",
             "johab",
             "koi8_r",
             "koi8_u",
             "mac_cyrillic",
             "mac_greek",
             "mac_iceland",
             "mac_latin2",
             "mac_roman",
             "mac_turkish",
             "ptcp154",
             "shift_jis",
             "shift_jis_2004",
             "shift_jisx0213",
             "utf_32",
             "utf_32_be",
             "utf_32_le",
             "utf_16",
             "utf_16_be",
             "utf_16_le",
             "utf_7",
             "utf_8",
             "utf_8_sig"]


class Logger:

    shell_mod = {
        '':'',
       'PURPLE' : '\033[95m',
       'CYAN' : '\033[96m',
       'DARKCYAN' : '\033[36m',
       'BLUE' : '\033[94m',
       'GREEN' : '\033[92m',
       'YELLOW' : '\033[93m',
       'RED' : '\033[91m',
       'BOLD' : '\033[1m',
       'UNDERLINE' : '\033[4m',
       'RESET' : '\033[0m'
    }

    def log ( self, message, is_bold=False, color='', log_time=True):
        prefix = ''
        suffix = ''
        logfile = 'pastebin_crawler.log'

        if log_time:
            prefix += '[{:s}] '.format(get_timestamp())

        if os.name == 'posix':
            if is_bold:
                prefix += self.shell_mod['BOLD']
            prefix += self.shell_mod[color.upper()]

            suffix = self.shell_mod['RESET']

        message = prefix + message + suffix
#        print ( message )
#        sys.stdout.flush()
        size = os.path.getsize(logfile)
        if size > 1024*1024*256:
                tarf = logfile+'.gz'
                mode='w:gz'
                with tarfile.open(tarf,mode) as out:
                    out.add(logfile)
                os.remove(logfile)
        with open(logfile, "a+") as logf:
          logf.write(message+"\n")

    def error(self, err):
        self.log(err, True, 'RED')

    def fatal_error(self, err):
        self.error(err)
        exit()

class Crawler:

    PASTEBIN_URL = 'http://pastebin.com'
    PASTES_URL = PASTEBIN_URL + '/archive'
    REGEXES_FILE = 'regexes.txt'
    OK = 1
    ACCESS_DENIED = -1
    CONNECTION_FAIL = -2
    OTHER_ERROR = -3

    prev_checked_ids = []
    new_checked_ids = []

    def read_regexes(self):
        try:
            with open ( self.REGEXES_FILE, 'r') as f:
                try:
                    self.regexes = [ [ field.strip() for field in line.split(',')] for line in f.readlines() if line.strip() != '' and not line.startswith('#')]

                    # In case commas exist in the regexes...merge everything.
                    for i in range(len(self.regexes)):
                        self.regexes[i] = [','.join(self.regexes[i][:-2])] + self.regexes[i][-2:]
                except KeyboardInterrupt:
                    raise
                except:
                    Logger().fatal_error('Malformed regexes file. Format: regex_pattern,URL logging file, directory logging file.')

#            for regex,file,directory in self.regexes:
#                Logger ().log ( directory+':\t'+file+':\t'+regex[:68])
            Logger ().log ( '{:d} regex rules are refreshed.'.format(len(self.regexes)), True)

        except KeyboardInterrupt:
            raise
        except:
            Logger().fatal_error('{:s} not found or not acessible.'.format(self.REGEXES_FILE))


    def __init__(self):
#        self.read_regexes()
        self.delayfactor = 1	# dynamically adjust the delay time of retrieving each paste
        self.min_delayfactor = 0.5


    def get_pastes ( self ):
        Logger ().log ( 'Getting pastes', True )
        try:
            page = PyQuery ( url = self.PASTES_URL )
        except KeyboardInterrupt:
            raise
        except:
            return self.CONNECTION_FAIL,None


        """
        There are a set of encoding issues which, coupled with some bugs in etree (such as in the Raspbian packages) can
        trigger encoding exceptions here. As a workaround, we try every possible encoding first, and even if that fails,
        we resort to a very hacky workaround whereby we manually get the page and attempt to encode it as utf-8. It's
        ugly, but it works for now.
        """
        try:
            page_html = page.html ()
        except KeyboardInterrupt:
            raise
        except:
            worked = False
            for enc in all_python_encodings():
                try:
                    page_html = page.html(encoding=enc)
                    worked = True
                    break
                except KeyboardInterrupt:
                    raise
                except:
                    pass
            if not worked:
                # One last try...
                try:
                    f = urllib.request.urlopen(Crawler.PASTES_URL)
                    page_html = PyQuery(str(f.read()).encode('utf8')).html()
                    f.close()
                except KeyboardInterrupt:
                    raise
                except:
                    return self.OTHER_ERROR, None
        if re.match ( r'Pastebin\.com - Access Denied Warning', page_html, re.IGNORECASE ) or 'blocked your IP' in page_html or 'unatural browsing behavior' in page_html:
            return self.ACCESS_DENIED,None
        else:
            return self.OK,page('.maintable img').next('a')

    def check_paste ( self, paste_id ):
        paste_url = self.PASTEBIN_URL + paste_id
        try:
            paste_txt = PyQuery ( url = paste_url )('#paste_code').text()

            for regex,file,directory in self.regexes:
                if re.match ( regex, paste_txt, re.IGNORECASE ):
                    Logger ().log ( 'Found a matching paste: ' + paste_url.rsplit('/')[-1] + ' (' + file + '): '+ regex[:40], True, 'CYAN' )
                    self.save_result ( paste_url,paste_id,'data/'+file,'data/'+directory )
                    return True
#            Logger ().log ( 'Not matching paste: ' + paste_url )
        except KeyboardInterrupt:
            raise
        except:
            Logger ().log ( 'Error reading paste (probably a 404 or encoding issue or regex issue).', True, 'YELLOW')
        return False

    def save_result ( self, paste_url, paste_id, file, directory ):
        fn,ext = os.path.splitext(os.path.split(file)[1])
        timestamp = get_timestamp()
        with open ( file, 'a' ) as matching:
            matching.write ( fn + '-' + timestamp + '-' + paste_url + '\n' )

        try:
            os.mkdir(directory)
        except KeyboardInterrupt:
            raise
        except:
            pass

        with open( directory + '/' + fn + '_' + timestamp.replace('/','_').replace(':','_').replace(' ','__') + '_' + paste_id.replace('/','') + '.txt', mode='w' ) as paste:
            paste_txt = PyQuery(url=paste_url)('#paste_code').text()
            paste.write(paste_txt + '\n')


    def start ( self, refresh_time = 200, delay = 5, ban_wait = 30, flush_after_x_refreshes=100, connection_timeout=60 ):
        count = 0
        while True:
            status,pastes = self.get_pastes ()
            numofpastes = len(pastes) or 0
            Logger().log('Retreived {:d} pastes, will process using delay factor of {:.2f} ...'.format(numofpastes,self.delayfactor), True)
            self.read_regexes()

            start_time = time.time()
            if status == self.OK:
                delayed = 0
                currpaste = 0
                totaldelayed = 0
                chkedpaste = 0
                for paste in pastes:
                    currpaste += 1
                    paste_id = PyQuery ( paste ).attr('href')
                    self.new_checked_ids.append ( paste_id )
                    if paste_id not in self.prev_checked_ids:
                        chkedpaste += 1
                        self.check_paste ( paste_id )
                        delaytime = delay*random.uniform(0.6,1.1)*self.delayfactor
                        totaldelayed += delaytime
                        Logger().log('Paste {:02d}/{:02d} done; Waiting {:.2f} seconds for next paste ...'.format(currpaste,numofpastes,delaytime), False)
                        if currpaste < numofpastes:
                            time.sleep(delaytime)

                    if currpaste == numofpastes:
                        Logger().log('Average/Total waiting time is {:.2f}s/{:.2f}m for the pastes'.format(totaldelayed/numofpastes,totaldelayed/60), False)
                        if chkedpaste < numofpastes:
                            Logger().log('Good job! You caught up all new pastes since last update! {:d} pastes are already checked'.format(numofpastes-chkedpaste), True)
                            self.delayfactor = self.delayfactor + 0.02*fabs(numofpastes-chkedpaste)
                        else:
                            self.delayfactor = self.min_delayfactor if self.delayfactor <= self.min_delayfactor else (self.delayfactor - 0.08)
                    count += 1

                if count == flush_after_x_refreshes:
                    self.prev_checked_ids = self.new_checked_ids
                    count = 0
                else:
                    self.prev_checked_ids += self.new_checked_ids
                self.new_checked_ids = []

                elapsed_time = time.time() - start_time
                sleep_time = ceil(max(0,(refresh_time*random.gauss(1,0.2) - elapsed_time)))
                if sleep_time > 0:
                    Logger().log('Waiting {:d} seconds to refresh...'.format(sleep_time), True)
                    time.sleep ( sleep_time )
                else:
                    Logger().log('refresh_time={:d}, elapsed_time={:.2f}, sleep_time={:.2f}'.format(refresh_time,elapsed_time,sleep_time), False)
            elif status == self.ACCESS_DENIED:
                delayed += 1
                self.delayfactor = 1
                Logger ().log ( 'Damn! It looks like you have been banned (probably temporarily)', True, 'YELLOW' )
                for n in range ( 0, ceil(ban_wait*random.gauss(1+delayed*0.2,0.2)) ):
                    Logger ().log ( 'Please wait ' + str ( ban_wait - n ) + ' minute' + ( 's' if ( ban_wait - n ) > 1 else '' ) )
                    time.sleep ( 60 )
            elif status == self.CONNECTION_FAIL:
                Logger().log ( 'Connection down. Waiting {:d} seconds and trying again'.format(connection_timeout), True, 'RED')
                time.sleep(connection_timeout)
            elif status == self.OTHER_ERROR:
                Logger().log('Unknown error. Maybe an encoding problem? Trying again.'.format(connection_timeout), True,'RED')
                time.sleep(1)

def parse_input():
    parser = OptionParser()
    parser.add_option('-r', '--refresh-time', help='Set the refresh time (default: 200)', dest='refresh_time', type='int', default=200)
    parser.add_option('-d', '--delay-time', help='Set the delay time (default: 5)', dest='delay', type='float', default=5)
    parser.add_option('-b', '--ban-wait-time', help='Set the ban wait time (default: 30)', dest='ban_wait', type='int', default=30)
    parser.add_option('-f', '--flush-after-x-refreshes', help='Set the number of refreshes after which memory is flushed (default: 100)', dest='flush_after_x_refreshes', type='int', default=100)
    parser.add_option('-c', '--connection-timeout', help='Set the connection timeout waiting time (default: 60)', dest='connection_timeout', type='float', default=60)
    (options, args) = parser.parse_args()
    return options.refresh_time, options.delay, options.ban_wait, options.flush_after_x_refreshes, options.connection_timeout


try:
    Crawler ().start (*parse_input())
except KeyboardInterrupt:
    Logger ().log ( 'Bye! Hope you found what you were looking for :)', True )
